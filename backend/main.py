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
        # Turn JSON into a simple pretty-printed HTML so Playwright can convert it
        html_path = tmp_dir / "report.html"
        html_content = (
            "<html><head><meta charset='utf-8'><title>Damage Report</title>"
            "<style>body{font-family:Arial,Helvetica,sans-serif;}pre{white-space:pre-wrap;font-family:monospace;}</style>"
            "</head><body><h1>Vehicle Damage Report</h1><pre>" +
            json.dumps(json.loads(out_json.read_text("utf-8")), indent=2) +
            "</pre></body></html>"
        )
        html_path.write_text(html_content, encoding="utf-8")

        # Now render that HTML to PDF using Playwright
        pdf_path = tmp_dir / "report.pdf"
        html_to_pdf = Path(__file__).resolve().parent / "html_to_pdf.py"
        if not html_to_pdf.exists():
            html_to_pdf = Path(__file__).resolve().parent.parent / "html_to_pdf.py"
        print("Converting to PDF…")
        run_subprocess(["python", str(html_to_pdf), str(html_path), str(pdf_path)])

        # Upload to storage ---------------------------------------------------
        sb = supabase()
        bucket = sb.storage.from_(SUPABASE_BUCKET)
        json_key = f"{doc_id}.json"
        pdf_key = f"{doc_id}.pdf"
        print("Uploading JSON and PDF to Supabase storage…")
        bucket.upload(json_key, out_json.read_bytes(), upsert=True, content_type="application/json")
        bucket.upload(pdf_key, pdf_path.read_bytes(), upsert=True, content_type="application/pdf")
        json_url = bucket.get_public_url(json_key)
        pdf_url = bucket.get_public_url(pdf_key)

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
