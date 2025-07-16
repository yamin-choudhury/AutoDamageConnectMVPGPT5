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
print("=== Environment Variables Check ===")
try:
    SUPABASE_URL = os.environ["SUPABASE_URL"]
    print(f"SUPABASE_URL: {SUPABASE_URL[:50]}..." if len(SUPABASE_URL) > 50 else f"SUPABASE_URL: {SUPABASE_URL}")
except KeyError:
    print("ERROR: SUPABASE_URL environment variable not set")
    raise

try:
    SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    print(f"SUPABASE_SERVICE_ROLE_KEY: {'*' * min(20, len(SUPABASE_SERVICE_ROLE_KEY))}... (length: {len(SUPABASE_SERVICE_ROLE_KEY)})")
except KeyError:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY environment variable not set")
    raise

SUPABASE_BUCKET = os.getenv("REPORT_BUCKET", "reports")
print(f"SUPABASE_BUCKET: {SUPABASE_BUCKET}")
print("=== Environment Variables OK ===")
# Force redeploy to pick up updated SUPABASE_URL

_sb: Client | None = None

def supabase() -> Client:
    global _sb
    if _sb is None:
        print(f"Creating Supabase client...")
        
        # Clean the URL by stripping whitespace and common problematic characters
        cleaned_url = SUPABASE_URL.strip()  # Remove leading/trailing whitespace
        cleaned_url = cleaned_url.lstrip(' =')  # Remove leading spaces and equals
        cleaned_url = cleaned_url.rstrip(';')  # Remove trailing semicolons
        # Additional safety: remove any remaining leading non-alphanumeric chars except https://
        if not cleaned_url.startswith('https://'):
            # Find where https:// starts
            https_pos = cleaned_url.find('https://')
            if https_pos > 0:
                cleaned_url = cleaned_url[https_pos:]
        print(f"Original URL repr: {repr(SUPABASE_URL)}")
        print(f"Cleaned URL: {cleaned_url}")
        print(f"Cleaned URL length: {len(cleaned_url)}, starts with https: {cleaned_url.startswith('https://')}")
        
        # Check for invisible characters
        for i, char in enumerate(SUPABASE_URL):
            if ord(char) < 32 or ord(char) > 126:
                print(f"Non-printable character at position {i}: {repr(char)} (ord: {ord(char)})")
        
        print(f"Service role key length: {len(SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else 'None'}")
        print(f"Service role key starts with: {SUPABASE_SERVICE_ROLE_KEY[:20] if SUPABASE_SERVICE_ROLE_KEY else 'None'}...")
        
        try:
            import supabase as sb_module
            print(f"Supabase library version: {getattr(sb_module, '__version__', 'unknown')}")
            
            # Try with cleaned URL first
            print(f"Attempting client creation with cleaned URL...")
            _sb = create_client(cleaned_url, SUPABASE_SERVICE_ROLE_KEY)
            print("Supabase client created successfully with cleaned URL")
        except Exception as e:
            print(f"Supabase client creation failed!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error args: {e.args}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Supabase client error: {str(e)}")
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
    print(f"🔧 Running command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"❌ Command failed with return code {proc.returncode}")
        print(f"STDOUT: {proc.stdout}")
        print(f"STDERR: {proc.stderr}")
        raise RuntimeError(f"Command failed: {proc.stderr or proc.stdout}")
    print(f"✅ Command completed successfully")

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
        try:
            print(f"Starting damage report generation with script: {gen_script}")
            run_subprocess([
                "python", str(gen_script),
                "--images_dir", str(tmp_dir),
                "--out", str(out_json),
            ])
            print("Damage report generation completed")
        except Exception as e:
            print(f"Damage report generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Damage report generation failed: {str(e)}")

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
            print(f"Starting PDF conversion with script: {html_to_pdf}")
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
            json_result = bucket.upload(json_key, out_json.read_bytes())
            print(f"JSON upload result: {json_result}")
        except Exception as e:
            print(f"JSON upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"JSON upload failed: {str(e)}")
        
        print("Uploading PDF to Supabase storage…")
        try:
            pdf_result = bucket.upload(pdf_key, pdf_path.read_bytes())
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

        # Call the report-complete webhook -------------------------------------
        print("Calling report-complete webhook...")
        
        # First, fetch the JSON content to send to webhook
        report_json = None
        try:
            report_json = json.loads(out_json.read_text("utf-8"))
        except Exception as e:
            print(f"Warning: Could not read JSON for webhook: {e}")
        
        # Get webhook URL from environment or construct it
        webhook_url = os.getenv("REPORT_COMPLETE_WEBHOOK_URL")
        if not webhook_url:
            # Construct webhook URL from Supabase URL
            supabase_base = SUPABASE_URL.replace('/rest/v1', '')
            webhook_url = f"{supabase_base}/functions/v1/report-complete"
        
        try:
            webhook_payload = {
                "document_id": doc_id,
                "json_url": json_url,
                "pdf_url": pdf_url,
                "report_json": report_json
            }
            
            async with httpx.AsyncClient() as client:
                webhook_response = await client.post(
                    webhook_url,
                    json=webhook_payload,
                    headers={"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
                    timeout=30
                )
                
            if webhook_response.status_code == 200:
                print(f"✅ Webhook called successfully for document {doc_id}")
            else:
                print(f"⚠️ Webhook returned status {webhook_response.status_code}: {webhook_response.text}")
                
        except Exception as webhook_error:
            print(f"❌ Webhook call failed: {webhook_error}")
            # Don't fail the entire process if webhook fails
            
        # Return to edge function --------------------------------------------
        print("Upload complete, returning URLs…")
        return {"json_url": json_url, "pdf_url": pdf_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

async def generate_visual_html_report(report_json: dict, doc_id: str) -> str:
    """
    Generate a professional HTML damage report with images and annotations.
    """
    from datetime import datetime
    
    # Get vehicle info
    vehicle = report_json.get('vehicle', {})
    damaged_parts = report_json.get('damaged_parts', [])
    repair_parts = report_json.get('repair_parts', [])
    summary = report_json.get('summary', {})
    
    # Get images from Supabase
    sb = supabase()
    images_result = sb.table("images").select("url").eq("document_id", doc_id).execute()
    image_urls = [img['url'] for img in images_result.data] if images_result.data else []
    
    # HTML template with embedded CSS for professional styling
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vehicle Damage Assessment Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .report-date {{
            font-size: 1.1em;
            margin-top: 10px;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            margin: 20px 0;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #1e3a8a;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}
        .vehicle-info, .summary-info {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 15px;
            margin-bottom: 20px;
        }}
        .info-label {{
            font-weight: bold;
            color: #374151;
        }}
        .info-value {{
            color: #1f2937;
        }}
        .severity-high {{ color: #dc2626; font-weight: bold; }}
        .severity-moderate {{ color: #f59e0b; font-weight: bold; }}
        .severity-low {{ color: #10b981; font-weight: bold; }}
        .damage-part {{
            border-left: 4px solid #3b82f6;
            padding: 20px;
            margin: 20px 0;
            background-color: #f8fafc;
            border-radius: 0 8px 8px 0;
        }}
        .damage-part h3 {{
            color: #1e40af;
            margin-top: 0;
        }}
        .images-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .image-container {{
            position: relative;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .image-container img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .image-caption {{
            background-color: #374151;
            color: white;
            padding: 10px;
            font-size: 0.9em;
            text-align: center;
        }}
        .parts-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        .parts-table th, .parts-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}
        .parts-table th {{
            background-color: #f3f4f6;
            font-weight: 600;
            color: #374151;
        }}
        .parts-table tr:hover {{
            background-color: #f8fafc;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #6b7280;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚗 Vehicle Damage Assessment Report</h1>
        <div class="report-date">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
    </div>

    <div class="section">
        <h2>🚙 Vehicle Information</h2>
        <div class="vehicle-info">
            <div class="info-label">Make:</div>
            <div class="info-value">{vehicle.get('make', 'N/A')}</div>
            <div class="info-label">Model:</div>
            <div class="info-value">{vehicle.get('model', 'N/A')}</div>
            <div class="info-label">Year:</div>
            <div class="info-value">{vehicle.get('year', 'N/A')}</div>
        </div>
    </div>

    <div class="section">
        <h2>📋 Damage Summary</h2>
        <div class="summary-info">
            <div class="info-label">Overall Severity:</div>
            <div class="info-value severity-{summary.get('overall_severity', 'low')}">
                {summary.get('overall_severity', 'N/A').upper()}
            </div>
            <div class="info-label">Repair Complexity:</div>
            <div class="info-value">{summary.get('repair_complexity', 'N/A').title()}</div>
            <div class="info-label">Safety Impact:</div>
            <div class="info-value">{'YES' if summary.get('safety_impacted') else 'NO'}</div>
            <div class="info-label">Estimated Hours:</div>
            <div class="info-value">{summary.get('total_estimated_hours', 0)} hours</div>
        </div>
        {f'<p><strong>Comments:</strong> {summary.get("comments", "")}' if summary.get('comments') else ''}</p>
    </div>

    <div class="section">
        <h2>📸 Damage Images</h2>
        <div class="images-grid">
"""
    
    # Add images to the report
    for i, img_url in enumerate(image_urls, 1):
        html += f"""
            <div class="image-container">
                <img src="{img_url}" alt="Damage Image {i}" onerror="this.style.display='none';this.nextElementSibling.innerHTML='Image not available'">
                <div class="image-caption">Image {i} - Vehicle Damage</div>
            </div>
        """
    
    html += """
        </div>
    </div>

    <div class="section">
        <h2>🔧 Damaged Parts Analysis</h2>
    """
    
    # Add damaged parts
    for i, part in enumerate(damaged_parts, 1):
        severity_class = f"severity-{part.get('severity', 'low')}"
        html += f"""
        <div class="damage-part">
            <h3>{i}. {part.get('name', 'Unknown Part')}</h3>
            <div class="vehicle-info">
                <div class="info-label">Location:</div>
                <div class="info-value">{part.get('location', 'N/A')}</div>
                <div class="info-label">Category:</div>
                <div class="info-value">{part.get('category', 'N/A')}</div>
                <div class="info-label">Damage Type:</div>
                <div class="info-value">{part.get('damage_type', 'N/A')}</div>
                <div class="info-label">Severity:</div>
                <div class="info-value {severity_class}">{part.get('severity', 'N/A').upper()}</div>
                <div class="info-label">Repair Method:</div>
                <div class="info-value">{part.get('repair_method', 'N/A').upper()}</div>
            </div>
            {f'<p><strong>Description:</strong> {part.get("description", "")}' if part.get('description') else ''}</p>
            {f'<p><strong>Notes:</strong> {part.get("notes", "")}' if part.get('notes') else ''}</p>
        </div>
        """
    
    # Add repair parts table if available
    if repair_parts:
        html += """
    </div>

    <div class="section">
        <h2>🛠️ Required Parts & Labor</h2>
        <table class="parts-table">
            <thead>
                <tr>
                    <th>Part Name</th>
                    <th>Category</th>
                    <th>Labor Hours</th>
                    <th>Paint Hours</th>
                </tr>
            </thead>
            <tbody>
        """
        
        total_labor = 0
        total_paint = 0
        
        for part in repair_parts:
            labor_hours = part.get('labour_hours', 0)
            paint_hours = part.get('paint_hours', 0)
            total_labor += labor_hours
            total_paint += paint_hours
            
            html += f"""
                <tr>
                    <td>{part.get('name', 'N/A')}</td>
                    <td>{part.get('category', 'N/A')}</td>
                    <td>{labor_hours:.1f}h</td>
                    <td>{paint_hours:.1f}h</td>
                </tr>
            """
        
        html += f"""
                <tr style="font-weight: bold; background-color: #f3f4f6;">
                    <td>TOTAL</td>
                    <td></td>
                    <td>{total_labor:.1f}h</td>
                    <td>{total_paint:.1f}h</td>
                </tr>
            </tbody>
        </table>
        """
    
    html += """
    </div>

    <div class="footer">
        <p>📄 End of Vehicle Damage Assessment Report</p>
        <p>This report was generated automatically using AI damage detection technology.</p>
    </div>

</body>
</html>
    """
    
    return html

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
        # Build professional HTML with images and annotations
        html_path = tmp_dir / "report.html"
        html_content = await generate_visual_html_report(report_json, doc_id)
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
        bucket.upload(pdf_key, pdf_path.read_bytes())
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
