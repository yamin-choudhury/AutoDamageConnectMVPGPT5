from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel
from pathlib import Path
from uuid import uuid4
import os, json, tempfile, shutil, subprocess
import httpx
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_BUCKET = os.getenv("REPORT_BUCKET", "reports")

_sb: Client | None = None

def supabase() -> Client:
    global _sb
    if _sb is None:
        _sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _sb

app = FastAPI(title="Damage Report Service")

class GeneratePayload(BaseModel):
    document: dict

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
async def download_images(images: list[dict] | list[str], dest: Path):
    """Download each image url into dest/<idx>.jpg asynchronously."""
    print(f"Attempting to download {len(images)} images...")
    for idx, img in enumerate(images):
        url = img["url"] if isinstance(img, dict) else img
        print(f"Image {idx}: {url}")
    
    async with httpx.AsyncClient(timeout=60) as client:
        for idx, img in enumerate(images):
            try:
                url = img["url"] if isinstance(img, dict) else img
                print(f"Downloading image {idx} from: {url}")
                
                if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
                    raise ValueError(f"Invalid URL: {url}")
                
                r = await client.get(url)
                r.raise_for_status()
                (dest / f"{idx}.jpg").write_bytes(r.content)
                print(f"Successfully downloaded image {idx}")
            except Exception as e:
                print(f"Failed to download image {idx} from {url}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Failed to download image {idx}: {str(e)}")

def run_subprocess(cmd: list[str]):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)

# ---------------------------------------------------------------------------
# /generate – main pipeline entry
# ---------------------------------------------------------------------------
@app.post("/generate")
async def generate_report(payload: GeneratePayload):
    print("=== /generate called ===")
    print(f"Received payload: {payload}")
    doc = payload.document
    print(f"Document data: {doc}")
    doc_id = doc.get("id", str(uuid4()))
    print(f"Document ID: {doc_id}")
    
    # Check images data structure
    images = doc.get("images", [])
    print(f"Images data type: {type(images)}")
    print(f"Images data: {images}")
    print(f"Number of images: {len(images)}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="gen_"))
    try:
        print("Downloading images…")
        await download_images(doc.get("images", []), tmp_dir)

        # Run staged generator ------------------------------------------------
        out_json = tmp_dir / "report.json"
        # Locate generate_damage_report_staged.py whether it lives beside backend/ or at repo root
        root_dir = Path(__file__).resolve().parent
        gen_script = root_dir / "generate_damage_report_staged.py"
        if not gen_script.exists():
            gen_script = root_dir.parent / "generate_damage_report_staged.py"
        if not gen_script.exists():
            raise RuntimeError("generate_damage_report_staged.py not found in expected locations")
        run_subprocess([
            "python", str(gen_script),
            "--images_dir", str(tmp_dir),
            "--out", str(out_json),
        ])

        # Convert to PDF ------------------------------------------------------
        print("Starting PDF conversion process...")
        # Turn JSON into a simple pretty-printed HTML so Playwright can convert it
        html_path = tmp_dir / "report.html"
        print(f"Reading JSON from: {out_json}")
        
        try:
            json_content = json.loads(out_json.read_text("utf-8"))
            print("JSON loaded successfully")
        except Exception as e:
            print(f"Failed to read JSON: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read generated JSON: {str(e)}")
        
        html_content = (
            "<html><head><meta charset='utf-8'><title>Damage Report</title>"
            "<style>body{font-family:Arial,Helvetica,sans-serif;}pre{white-space:pre-wrap;font-family:monospace;}</style>"
            "</head><body><h1>Vehicle Damage Report</h1><pre>" +
            json.dumps(json_content, indent=2) +
            "</pre></body></html>"
        )
        html_path.write_text(html_content, encoding="utf-8")
        print(f"HTML file created: {html_path}")

        # Now render that HTML to PDF using Playwright
        pdf_path = tmp_dir / "report.pdf"
        html_to_pdf = Path(__file__).resolve().parent / "html_to_pdf.py"
        if not html_to_pdf.exists():
            html_to_pdf = Path(__file__).resolve().parent.parent / "html_to_pdf.py"
        
        print(f"Using html_to_pdf script: {html_to_pdf}")
        print("Converting to PDF…")
        
        try:
            run_subprocess(["python", str(html_to_pdf), str(html_path), str(pdf_path)])
            print(f"PDF conversion completed: {pdf_path}")
            
            # Verify PDF was created
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file was not created: {pdf_path}")
            print(f"PDF file size: {pdf_path.stat().st_size} bytes")
        except Exception as e:
            print(f"PDF conversion failed: {e}")
            raise HTTPException(status_code=500, detail=f"PDF conversion failed: {str(e)}")

        # Upload to storage ---------------------------------------------------
        print("Initializing Supabase client...")
        sb = supabase()
        print(f"Supabase bucket: {SUPABASE_BUCKET}")
        bucket = sb.storage.from_(SUPABASE_BUCKET)
        json_key = f"{doc_id}.json"
        pdf_key = f"{doc_id}.pdf"
        print(f"Upload keys: json={json_key}, pdf={pdf_key}")
        
        print("Uploading JSON to Supabase storage…")
        try:
            json_result = bucket.upload(json_key, out_json.read_bytes(), upsert=True, content_type="application/json")
            print(f"JSON upload result: {json_result}")
        except Exception as e:
            print(f"JSON upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"JSON upload failed: {str(e)}")
        
        print("Uploading PDF to Supabase storage…")
        try:
            pdf_result = bucket.upload(pdf_key, pdf_path.read_bytes(), upsert=True, content_type="application/pdf")
            print(f"PDF upload result: {pdf_result}")
        except Exception as e:
            print(f"PDF upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"PDF upload failed: {str(e)}")
        
        print("Getting public URLs...")
        try:
            json_url = bucket.get_public_url(json_key)
            pdf_url = bucket.get_public_url(pdf_key)
            print(f"Generated URLs: json={json_url}, pdf={pdf_url}")
        except Exception as e:
            print(f"URL generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"URL generation failed: {str(e)}")

        # Return to edge function --------------------------------------------
        print("Upload complete, returning URLs…")
        return {"json_url": json_url, "pdf_url": pdf_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# /pdf-from-json – regenerate PDF after edits
# ---------------------------------------------------------------------------
class PDFPayload(BaseModel):
    document_id: str
    json: dict

@app.post("/pdf-from-json")
async def pdf_from_json(payload: PDFPayload):
    doc_id = payload.document_id
    report_json = payload.json

    tmp_dir = Path(tempfile.mkdtemp(prefix="pdf_"))
    try:
        src = tmp_dir / "report.json"
        # Build HTML from given JSON
        html_path = tmp_dir / "report.html"
        html_content = (
            "<html><head><meta charset='utf-8'><title>Damage Report</title>"
            "<style>body{font-family:Arial,Helvetica,sans-serif;}pre{white-space:pre-wrap;font-family:monospace;}</style>"
            "</head><body><h1>Vehicle Damage Report</h1><pre>" +
            json.dumps(report_json, indent=2) +
            "</pre></body></html>"
        )
        html_path.write_text(html_content, encoding="utf-8")
        src.write_text(json.dumps(report_json), encoding="utf-8")
        pdf_path = tmp_dir / "report.pdf"
        html_to_pdf = Path(__file__).resolve().parent / "html_to_pdf.py"
        if not html_to_pdf.exists():
            html_to_pdf = Path(__file__).resolve().parent.parent / "html_to_pdf.py"
        run_subprocess(["python", str(html_to_pdf), str(html_path), str(pdf_path)])

        sb = supabase()
        bucket = sb.storage.from_(SUPABASE_BUCKET)
        pdf_key = f"{doc_id}.pdf"
        bucket.upload(pdf_key, pdf_path.read_bytes(), upsert=True, content_type="application/pdf")
        pdf_url = bucket.get_public_url(pdf_key)

        # Persist new URL
        sb.table("documents").update({"report_pdf_url": pdf_url}).eq("id", doc_id).execute()

        return {"pdf_url": pdf_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# Health check
@app.get("/")
async def root():
    return {"status": "ok"}
