from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from uuid import uuid4
import os, json, tempfile, shutil, subprocess
import asyncio
import httpx
import hashlib, time
from typing import Optional, List
from supabase import create_client, Client
try:
    # Use OpenAI v1 SDK
    from openai import OpenAI  # type: ignore
    openai_client = OpenAI()
except Exception:
    openai_client = None

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

# ---------------------------------------------------------------------------
# CORS (allow frontend to call this API)
# ---------------------------------------------------------------------------
allowed_origins_env = os.getenv(
    "ALLOWED_ORIGINS",
    # Default to common local dev origins
    ",".join([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]),
)
allowed_origin_regex_env = os.getenv(
    "ALLOWED_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
print(f"CORS allowed origins: {allowed_origins}")
print(f"CORS allowed origin regex: {allowed_origin_regex_env}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex_env,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GeneratePayload(BaseModel):
    document: dict

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
async def download_images(images: list[dict] | list[str], dest: Path):
    """Download images into dest with angle-aware filenames.

    - Exterior images with known angle are saved as idx_{angle}.jpg
    - Exterior images without angle saved as idx.jpg
    - Interior/document images are skipped (not part of angle-bucket detection)
    """
    print(f"Attempting to download {len(images)} images...")
    for idx, img in enumerate(images):
        url = img["url"] if isinstance(img, dict) else img
        print(f"Image {idx}: {url}")

    async with httpx.AsyncClient(timeout=60) as client:
        for idx, img in enumerate(images):
            try:
                if isinstance(img, dict):
                    url = img.get("url")
                    category = (img.get("category") or "exterior").lower()
                    angle = (img.get("angle") or "").lower()
                    is_closeup = bool(img.get("is_closeup"))
                else:
                    url = img
                    category = "exterior"
                    angle = ""
                    is_closeup = False

                if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
                    raise ValueError(f"Invalid URL: {url}")

                # Skip interior/document from detection set
                if category in ("interior", "document"):
                    print(f"Skipping non-exterior image {idx} ({category})")
                    continue

                print(f"Downloading image {idx} from: {url}")
                r = await client.get(url)
                r.raise_for_status()
                # Encode close-up flag into filename to allow staged generator to prioritize
                cu_suffix = "_cu" if is_closeup else ""
                fname = f"{idx}_{angle}{cu_suffix}.jpg" if angle else f"{idx}{cu_suffix}.jpg"
                (dest / fname).write_bytes(r.content)
                print(f"Successfully downloaded image {idx} -> {fname}")
            except Exception as e:
                print(f"Failed to download image {idx} from {url}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Failed to download image {idx}: {str(e)}")

def run_subprocess(cmd: list[str], env: dict | None = None):
    print(f"🔧 Running command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
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
            # Build command with optional vehicle args from payload
            cmd = [
                "python", str(gen_script),
                "--images_dir", str(tmp_dir),
                "--out", str(out_json),
            ]
            # Smart defaults for comprehensive, high-recall + verified reporting.
            # We do not require the user to set envs; we set sane defaults unless already provided by deployment.
            env = os.environ.copy()
            smart_env = {
                "COMPREHENSIVE_MODE": "1",
                "STRICT_MODE": "0",
                "ENABLE_COMPLETENESS_PASS": "1",
                "CLUSTER_IOU_THRESH": "0.45",
                "PHASE2_ALLOW_NEW_PARTS": "1",
                "PERSIST_MAX_UNION": "1",
                "PERSIST_MIN_SUPPORT": "1",
                "MAX_DAMAGED_PARTS": "0",
                # Union vote thresholds
                "MIN_VOTES_PER_PART": "1",
                "MIN_VOTES_SEVERE": "2",
                "MIN_VOTES_MODERATE": "1",
                "MIN_VOTES_MINOR": "1",
                # Verification
                "ENABLE_VERIFICATION_PASS": "1",
                "VERIFY_TEMPS": "0.0,0.3",
                "VERIFY_CONF_SEVERE": "0.60",
                "VERIFY_CONF_MODERATE": "0.55",
                "VERIFY_CONF_MINOR": "0.45",
                "VERIFY_REQUIRE_PASSES_SEVERE": "2",
                "VERIFY_REQUIRE_PASSES_MODERATE": "2",
                "VERIFY_REQUIRE_PASSES_MINOR": "1",
                # Detection temps for higher recall on subtle defects
                "DETECTION_TEMPS": env.get("DETECTION_TEMPS", "0.0,0.25,0.4"),
                # OpenAI robustness
                "OPENAI_MAX_RETRIES": env.get("OPENAI_MAX_RETRIES", "5"),
                "OPENAI_CONCURRENCY": env.get("OPENAI_CONCURRENCY", "4"),
                # Angle bucketing defaults (enable by default for reviewed images)
                "ANGLE_BUCKETING": env.get("ANGLE_BUCKETING", "1"),
                "ANGLES": env.get("ANGLES", "front,front_left,front_right,side_left,side_right,back,back_left,back_right"),
                # Use at least a small non-zero default; 5 keeps payloads bounded and robust
                "MAX_ANGLE_IMAGES": env.get("MAX_ANGLE_IMAGES", "5"),
                # Close-up prioritization feature flags
                "USE_CLOSEUPS_FOR_DETECTION": env.get("USE_CLOSEUPS_FOR_DETECTION", "1"),
                "CLOSEUP_PRIORITY_BOOST": env.get("CLOSEUP_PRIORITY_BOOST", "1.35"),
            }
            for k, v in smart_env.items():
                # Do not override if deployment explicitly set it
                if k not in env or env[k] in (None, ""):
                    env[k] = v
            # Ensure Python can import backend packages when script is relocated at /app
            py_paths = [
                str(Path(__file__).resolve().parent),          # /.../backend
                str(Path(__file__).resolve().parent.parent),    # repo root
            ]
            current_py = env.get("PYTHONPATH", "")
            for p in py_paths:
                if p and p not in current_py:
                    current_py = f"{p}:{current_py}" if current_py else p
            env["PYTHONPATH"] = current_py
            # Provider selection and model defaults
            provider = (env.get("MODEL_PROVIDER") or os.getenv("MODEL_PROVIDER") or "gemini").strip().lower()
            if "MODEL_PROVIDER" not in env or not env.get("MODEL_PROVIDER"):
                env["MODEL_PROVIDER"] = provider
            # Configure provider-specific settings (no secrets printed)
            if provider in ("gemini", "google", "googleai", "google-ai"):
                if not env.get("GEMINI_VISION_MODEL"):
                    env["GEMINI_VISION_MODEL"] = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
                if not env.get("GEMINI_TEXT_MODEL"):
                    env["GEMINI_TEXT_MODEL"] = os.getenv("GEMINI_TEXT_MODEL", env["GEMINI_VISION_MODEL"]) 
                if not env.get("GEMINI_CONCURRENCY"):
                    env["GEMINI_CONCURRENCY"] = os.getenv("GEMINI_CONCURRENCY", env.get("OPENAI_CONCURRENCY", "4"))
                if not env.get("GEMINI_MAX_RETRIES"):
                    env["GEMINI_MAX_RETRIES"] = os.getenv("GEMINI_MAX_RETRIES", env.get("OPENAI_MAX_RETRIES", "5"))
                # API key pass-through (do NOT print)
                if not env.get("GOOGLE_API_KEY") and (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
                    env["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            else:
                # OpenAI defaults (models)
                if not env.get("OPENAI_VISION_MODEL") and os.getenv("OPENAI_VISION_MODEL"):
                    env["OPENAI_VISION_MODEL"] = os.getenv("OPENAI_VISION_MODEL")
                if not env.get("OPENAI_TEXT_MODEL") and os.getenv("OPENAI_TEXT_MODEL"):
                    env["OPENAI_TEXT_MODEL"] = os.getenv("OPENAI_TEXT_MODEL")

            print("Smart ENV applied for generator (non-secret subset):")
            for k in sorted(smart_env.keys()):
                print(f"  - {k}={env.get(k)}")
            print(f"  - MODEL_PROVIDER={env.get('MODEL_PROVIDER')}")
            if provider in ("gemini", "google", "googleai", "google-ai"):
                print(f"  - GEMINI_VISION_MODEL={env.get('GEMINI_VISION_MODEL')}")
                print(f"  - GEMINI_TEXT_MODEL={env.get('GEMINI_TEXT_MODEL')}")
            else:
                print(f"  - OPENAI_VISION_MODEL={env.get('OPENAI_VISION_MODEL')}")
                print(f"  - OPENAI_TEXT_MODEL={env.get('OPENAI_TEXT_MODEL')}")
            # Support both top-level fields and nested document.vehicle
            veh_doc = (doc.get("vehicle") or {}) if isinstance(doc, dict) else {}
            vehicle_make = doc.get("make") if isinstance(doc, dict) else None
            vehicle_model = doc.get("model") if isinstance(doc, dict) else None
            vehicle_year = doc.get("year") if isinstance(doc, dict) else None
            vehicle_make = vehicle_make or veh_doc.get("make")
            vehicle_model = vehicle_model or veh_doc.get("model")
            vehicle_year = vehicle_year or veh_doc.get("year")
            if vehicle_make not in (None, ""):
                cmd += ["--vehicle_make", str(vehicle_make)]
            if vehicle_model not in (None, ""):
                cmd += ["--vehicle_model", str(vehicle_model)]
            if vehicle_year not in (None, "", 0):
                cmd += ["--vehicle_year", str(vehicle_year)]
            print(f"Generator command: {' '.join(cmd)}")
            run_subprocess(cmd, env=env)
            print("Damage report generation completed")
        except Exception as e:
            print(f"Damage report generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Damage report generation failed: {str(e)}")

        # Convert to PDF ------------------------------------------------------
        print("Starting PDF conversion process...")
        html_path = tmp_dir / "report.html"
        print(f"Reading JSON from: {out_json}")
        try:
            json_content = json.loads(out_json.read_text("utf-8"))
            print("JSON loaded successfully")
        except Exception as e:
            print(f"Failed to read JSON: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read generated JSON: {str(e)}")

        # Build professional HTML with images and annotations
        # Fallback to payload image URLs if Supabase has no images yet
        fallback_urls: list[str] = []
        try:
            fallback_urls = [
                (img.get("url") if isinstance(img, dict) else str(img))
                for img in (doc.get("images") or [])
                if ((isinstance(img, dict) and img.get("url")) or (isinstance(img, str) and img))
            ]
        except Exception:
            fallback_urls = []
        html_content = await generate_visual_html_report(json_content, doc_id, fallback_image_urls=fallback_urls)
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

async def generate_visual_html_report(report_json: dict, doc_id: str, fallback_image_urls: list[str] | None = None) -> str:
    """
    Generate a professional HTML damage report with images and annotations.
    """
    from datetime import datetime
    
    # Get vehicle info
    vehicle = report_json.get('vehicle', {})
    damaged_parts = report_json.get('damaged_parts', [])
    potential_parts = report_json.get('potential_parts', [])
    repair_parts = report_json.get('repair_parts', [])
    summary = report_json.get('summary', {})
    config = report_json.get('_config', {})
    metrics = report_json.get('_metrics', {})
    
    # Get images from Supabase (with angle metadata)
    sb = supabase()
    images_result = sb.table("images").select("url, angle, category, is_closeup").eq("document_id", doc_id).execute()
    images_data = images_result.data or []
    image_urls = [img.get('url') for img in images_data if img.get('url')]
    if not image_urls and fallback_image_urls:
        image_urls = fallback_image_urls

    # Prepare groupings for angle/close-up/interior evidence
    angle_order = [
        "front", "front_left", "side_left", "back_left",
        "back", "back_right", "side_right", "front_right", "unknown",
    ]
    def norm_angle(a: str | None) -> str:
        a = (a or "").strip().lower().replace("-", "_")
        return a if a in angle_order else ("unknown" if a else "unknown")
    def norm_cat(c: str | None) -> str:
        c = (c or "").strip().lower()
        return c if c in ("exterior", "interior", "document") else "exterior"

    grouped_exterior: dict[str, list[str]] = {k: [] for k in angle_order}
    grouped_closeups: dict[str, list[str]] = {k: [] for k in angle_order}
    interior_urls: list[str] = []
    for r in images_data:
        url = r.get('url');
        if not url:
            continue
        cat = norm_cat(r.get('category'))
        ang = norm_angle(r.get('angle'))
        is_cu = bool(r.get('is_closeup'))
        if cat == "interior":
            interior_urls.append(url)
        elif cat == "exterior":
            if is_cu:
                grouped_closeups[ang].append(url)
            else:
                grouped_exterior[ang].append(url)

    # Compute severity counts
    def sev_key(s: str) -> str:
        s = (s or "").strip().lower()
        return 'high' if s == 'severe' else ('moderate' if s == 'moderate' else 'low')
    def count_sev(parts: list[dict]):
        d = {"severe": 0, "moderate": 0, "minor": 0}
        for p in parts:
            s = (p.get('severity') or 'minor').strip().lower()
            if s in d:
                d[s] += 1
        return d
    sev_def = count_sev(damaged_parts)
    sev_pot = count_sev(potential_parts)

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
        .potential-part {{
            border-left: 4px solid #f59e0b;
            padding: 20px;
            margin: 20px 0;
            background-color: #fff7ed;
            border-radius: 0 8px 8px 0;
        }}
        .damage-part h3 {{
            color: #1e40af;
            margin-top: 0;
        }}
        .potential-part h3 {{
            color: #92400e;
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
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 9999px;
            font-size: 0.75em;
            background-color: #e5e7eb;
            color: #111827;
            margin-left: 8px;
        }}
        .badge-reason {{ background-color: #fde68a; color: #78350f; }}
        .muted {{ color: #6b7280; }}
        .small {{ font-size: 0.9em; }}
        .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #6b7280;
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
            <div class="info-label">Definitive parts:</div>
            <div class="info-value">{len(damaged_parts)} (severe {sev_def['severe']}, moderate {sev_def['moderate']}, minor {sev_def['minor']})</div>
            <div class="info-label">Potential parts:</div>
            <div class="info-value">{len(potential_parts)} (severe {sev_pot['severe']}, moderate {sev_pot['moderate']}, minor {sev_pot['minor']})</div>
            <div class="info-label">Comprehensive mode:</div>
            <div class="info-value">{ 'ON' if config.get('comprehensive_mode') else 'OFF' }</div>
        </div>
        {f'<p><strong>Comments:</strong> {summary.get("comments", "")}' if summary.get('comments') else ''}</p>
    </div>

    <div class="section">
        <h2>📸 Damage Images</h2>
        <div class="images-grid">
"""
    # Add images to the report (all images fallback view)
    for i, img_url in enumerate(image_urls, 1):
        html += f"""
            <div class=\"image-container\">
                <img src=\"{img_url}\" alt=\"Damage Image {i}\" onerror=\"this.style.display='none';this.nextElementSibling.innerHTML='Image not available'\">
                <div class=\"image-caption\">Image {i} - Vehicle Damage</div>
            </div>
        """
    
    html += """
        </div>
    </div>

    <div class=\"section\">
        <h2>🧭 Exterior Overview by Angle</h2>
"""
    any_exterior = any(len(v) for v in grouped_exterior.values())
    if any_exterior:
        for ang in angle_order:
            urls = grouped_exterior.get(ang) or []
            if not urls:
                continue
            ang_h = ang.replace("_"," ").title()
            html += f"""
            <h3 style=\"margin-top:10px\">{ang_h}</h3>
            <div class=\"images-grid\">
            """
            for i, u in enumerate(urls, 1):
                html += f"""
                <div class=\"image-container\">
                    <img src=\"{u}\" alt=\"{ang_h} {i}\" onerror=\"this.style.display='none';this.nextElementSibling.innerHTML='Image not available'\">
                    <div class=\"image-caption\">{ang_h} {i}</div>
                </div>
                """
            html += """
            </div>
            """
    else:
        html += """
        <p class=\"muted\">No exterior images with angle metadata available.</p>
        """

    html += """
    </div>

    <div class=\"section\">
        <h2>🔎 Close-up Evidence by Angle</h2>
"""
    any_closeups = any(len(v) for v in grouped_closeups.values())
    if any_closeups:
        for ang in angle_order:
            urls = grouped_closeups.get(ang) or []
            if not urls:
                continue
            ang_h = ang.replace("_"," ").title()
            html += f"""
            <h3 style=\"margin-top:10px\">{ang_h}</h3>
            <div class=\"images-grid\">
            """
            for i, u in enumerate(urls, 1):
                html += f"""
                <div class=\"image-container\">
                    <img src=\"{u}\" alt=\"Close-up {ang_h} {i}\" onerror=\"this.style.display='none';this.nextElementSibling.innerHTML='Image not available'\">
                    <div class=\"image-caption\">Close-up {ang_h} {i}</div>
                </div>
                """
            html += """
            </div>
            """
    else:
        html += """
        <p class=\"muted\">No close-up images available.</p>
        """

    html += """
    </div>

    <div class=\"section\">
        <h2>🛋️ Interior Evidence</h2>
"""
    if interior_urls:
        html += """
        <div class=\"images-grid\">
        """
        for i, u in enumerate(interior_urls, 1):
            html += f"""
            <div class=\"image-container\">
                <img src=\"{u}\" alt=\"Interior {i}\" onerror=\"this.style.display='none';this.nextElementSibling.innerHTML='Image not available'\">
                <div class=\"image-caption\">Interior {i}</div>
            </div>
            """
        html += """
        </div>
        """
    else:
        html += """
        <p class=\"muted\">No interior images available.</p>
        """

    html += """
    </div>

    <div class="section">
        <h2>🔧 Damaged Parts Analysis</h2>
    """
    
    # Add damaged parts
    for i, part in enumerate(damaged_parts, 1):
        severity_class = f"severity-{sev_key(part.get('severity', 'low'))}"
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
                <div class="info-value {severity_class}">{(part.get('severity') or 'N/A').upper()}</div>
                <div class="info-label">Repair Method:</div>
                <div class="info-value">{part.get('repair_method', 'N/A').upper()}</div>
            </div>
            {f'<p><strong>Description:</strong> {part.get("description", "")}' if part.get('description') else ''}</p>
            {f'<p><strong>Notes:</strong> {part.get("notes", "")}' if part.get('notes') else ''}</p>
        </div>
        """

    # Potential parts section
    if potential_parts:
        html += """
    </div>

    <div class="section">
        <h2>🟧 Potential Damage Candidates</h2>
        <p class="muted small">Items surfaced for assessor review. Reasons shown per item. Verification evidence included when available.</p>
        """
        for i, part in enumerate(potential_parts, 1):
            severity_class = f"severity-{sev_key(part.get('severity', 'low'))}"
            reason = part.get('_potential_reason', 'candidate')
            reason_map = {
                'insufficient_votes': 'Low consensus across detection runs',
                'verification_failed': 'Did not meet verification threshold',
            }
            reason_h = reason_map.get(reason, reason.replace('_',' ').title())
            verify = part.get('_verify') or {}
            passes = verify.get('passes') or []
            thr = verify.get('threshold')
            votes = verify.get('votes_yes')
            req = verify.get('consensus_required')
            ev_html = ""
            if passes:
                rows = "".join([
                    f"<tr><td>Pass {idx+1}</td><td>{'YES' if r.get('present') else 'NO'}</td><td>{r.get('confidence',0):.2f}</td><td>{r.get('temp')}</td></tr>"
                    for idx, r in enumerate(passes[:3])
                ])
                ev_html = f"""
                <div class="small">
                    <div class="muted">Verification evidence</div>
                    <table class="parts-table" style="margin-top:8px;">
                        <thead><tr><th>Pass</th><th>Present</th><th>Conf.</th><th>Temp</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                    <div class="muted">Threshold: {thr if thr is not None else '—'} | Votes yes: {votes if votes is not None else '—'} | Required: {req if req is not None else '—'}</div>
                </div>
                """
            html += f"""
            <div class=\"potential-part\">
                <h3>{i}. {part.get('name','Unknown Part')} <span class=\"badge badge-reason\">{reason_h}</span></h3>
                <div class=\"vehicle-info\">
                    <div class=\"info-label\">Location:</div>
                    <div class=\"info-value\">{part.get('location','N/A')}</div>
                    <div class=\"info-label\">Category:</div>
                    <div class=\"info-value\">{part.get('category','N/A')}</div>
                    <div class=\"info-label\">Severity:</div>
                    <div class=\"info-value {severity_class}\">{(part.get('severity') or 'N/A').upper()}</div>
                </div>
                {f'<p><strong>Description:</strong> {part.get("description", "")}' if part.get('description') else ''}</p>
                {ev_html}
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

    <div class="section">
        <h2>🧪 Audit & Settings</h2>
        <div class="small">
            <div><span class="info-label">Model:</span> {config.get('model','gpt-4o')}</div>
            <div><span class="info-label">Detection temps:</span> {', '.join([str(t) for t in (config.get('detection_temps') or [])])}</div>
            <div><span class="info-label">Verification temps:</span> {', '.join([str(t) for t in ((config.get('verification') or {}).get('temps') or [])])}</div>
            <div><span class="info-label">Verification thresholds (S/M/m):</span> {((config.get('verification') or {}).get('conf_thresholds') or {})}</div>
            <div><span class="info-label">Consensus required:</span> {((config.get('verification') or {}).get('consensus_required') or {})}</div>
            <div><span class="info-label">Vote thresholds (S/M/m):</span> {config.get('min_votes')}</div>
            <div><span class="info-label">Cluster IoU:</span> {config.get('cluster_iou_thresh')}</div>
        </div>
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

# ---------------------------------------------------------------------------
# /classify-angles – LLM primary with cache, heuristic fallback
# ---------------------------------------------------------------------------
class AngleImageIn(BaseModel):
    url: str
    id: Optional[str] = None

class ClassifyAnglesRequest(BaseModel):
    images: List[AngleImageIn]
    reclassify_unknown_only: bool = True
    max_concurrency: int = 4
    llm_enabled: bool = True

@app.post("/classify-angles")
async def classify_angles(req: ClassifyAnglesRequest):
    t0 = time.time()
    tmp_dir = Path(tempfile.mkdtemp(prefix="angles_"))
    cache_path = Path(tempfile.gettempdir()) / "angle_cache.json"

    def load_cache() -> dict:
        try:
            if cache_path.exists():
                return json.loads(cache_path.read_text())
        except Exception:
            pass
        return {}

    def save_cache(db: dict) -> None:
        try:
            cache_path.write_text(json.dumps(db, indent=2))
        except Exception:
            pass

    def content_hash_bytes(b: bytes) -> str:
        h = hashlib.sha1(); h.update(b); return h.hexdigest()

    def classify_heuristic_from_name(name: str) -> str:
        s = name.lower().replace("rear", "back")
        if ("front left" in s) or ("left front" in s) or (" fl" in s):
            return "front_left"
        if ("front right" in s) or ("right front" in s) or (" fr" in s):
            return "front_right"
        if ("back left" in s) or ("left back" in s) or ("rear left" in s) or (" rl" in s):
            return "back_left"
        if ("back right" in s) or ("right back" in s) or ("rear right" in s) or (" rr" in s):
            return "back_right"
        if "front" in s:
            return "front"
        if "back" in s:
            return "back"
        if "side" in s and "left" in s:
            return "side_left"
        if "side" in s and "right" in s:
            return "side_right"
        if " left" in s:
            return "side_left"
        if " right" in s:
            return "side_right"
        return "unknown"

    async with httpx.AsyncClient(timeout=30) as client:
        cache = load_cache()
        results = []
        for item in req.images:
            status = "ok"; err = None; angle = "unknown"; source = "llm"; conf: Optional[float] = None
            url = item.url
            try:
                if not url.startswith(("http://", "https://")):
                    raise ValueError("Invalid URL")
                # Download
                r = await client.get(url)
                r.raise_for_status()
                b = r.content
                ch = content_hash_bytes(b)
                # Cache hit
                c = cache.get(ch)
                if c and isinstance(c, dict) and c.get("angle"):
                    angle = c["angle"]; source = c.get("source", "cache"); conf = c.get("confidence")
                else:
                    # LLM primary (if enabled and SDK available)
                    used_llm = False
                    if req.llm_enabled and openai_client is not None:
                        try:
                            prompt = (
                                "Classify the vehicle viewing angle into one of: front, front_left, front_right, "
                                "side_left, side_right, back, back_left, back_right. Respond ONLY with the angle token."
                            )
                            completion = openai_client.chat.completions.create(
                                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                                messages=[
                                    {"role": "system", "content": "You are a strict classifier."},
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": prompt},
                                            {"type": "image_url", "image_url": {"url": url}},
                                        ],
                                    },
                                ],
                                temperature=0.0,
                            )
                            txt = (completion.choices[0].message.content or "").strip().lower()
                            aliases = {"rear": "back", "rear_left": "back_left", "rear_right": "back_right"}
                            txt = aliases.get(txt, txt)
                            if txt in [
                                "front","front_left","front_right","side_left","side_right","back","back_left","back_right"
                            ]:
                                angle = txt; source = "llm"; conf = None; used_llm = True
                        except Exception as le:
                            # LLM failure -> remain unknown for now; fall back to heuristic below
                            print(f"LLM classify failed for {url}: {le}")
                    # Heuristic fallback (use URL as filename proxy) only if LLM did not yield a valid angle
                    if angle == "unknown" and not used_llm:
                        angle = classify_heuristic_from_name(url)
                        source = "heuristic"
                    # Save to cache
                    cache[ch] = {"angle": angle, "source": source, "confidence": conf, "updated": time.time()}
            except Exception as e:
                status = "error"; err = str(e)
            results.append({
                "url": url,
                "id": item.id,
                "angle": angle,
                "source": source,
                "confidence": conf,
                "status": status,
                "error": err,
                "duration_ms": int((time.time() - t0) * 1000),
            })
        save_cache(cache)
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
    return {"results": results}

# ---------------------------------------------------------------------------
# /save-angle-metadata – persist user corrections
# ---------------------------------------------------------------------------
class SaveAngleItem(BaseModel):
    url: str
    angle: Optional[str] = None
    category: Optional[str] = None
    is_closeup: Optional[bool] = None
    source: Optional[str] = None
    confidence: Optional[float] = None

class SaveAnglePayload(BaseModel):
    document_id: str
    images: List[SaveAngleItem]

@app.post("/save-angle-metadata")
async def save_angle_metadata(payload: SaveAnglePayload):
    sb = supabase()
    rows = []
    for it in payload.images:
        row = {
            "document_id": payload.document_id,
            "url": it.url,
        }
        if it.angle is not None:
            row["angle"] = it.angle
        if it.category is not None:
            row["category"] = it.category
        if it.is_closeup is not None:
            row["is_closeup"] = it.is_closeup
        if it.source is not None:
            row["source"] = it.source
        if it.confidence is not None:
            row["confidence"] = it.confidence
        rows.append(row)
    try:
        # Use upsert to persist by (document_id, url) if DB is configured with a unique constraint
        # supabase-py expects on_conflict as a comma-separated string, not a list
        res = sb.table("images").upsert(rows, on_conflict="document_id,url").execute()
        updated = len(rows)
        return {"updated": updated, "errors": 0}
    except Exception as e:
        # Fallback to iterative update
        errors = 0
        for row in rows:
            try:
                sb.table("images").update({k: v for k, v in row.items() if k not in ("document_id", "url")}).eq("document_id", row["document_id"]).eq("url", row["url"]).execute()
            except Exception:
                errors += 1
        return {"updated": len(rows) - errors, "errors": errors}

# ---------------------------------------------------------------------------
# Background angle classification orchestration
#   - POST /angles/classify/start: queue background classification for a document
#   - GET  /angles/classify/status: report unknown exterior count
# ---------------------------------------------------------------------------
class AngleClassifyStartPayload(BaseModel):
    document_id: str
    reclassify_unknown_only: bool = True
    llm_enabled: bool = True
    debug_sync: bool = False

@app.post("/angles/classify/start")
async def angles_classify_start(payload: AngleClassifyStartPayload):
    doc_id = payload.document_id
    sb = supabase()
    # Fetch current images for this document (prefer enriched images; fallback to legacy)
    try:
        res = sb.table("images").select("url, category, angle, is_closeup, source, confidence").eq("document_id", doc_id).execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            # Fallback to legacy document_images
            try:
                leg = sb.table("document_images").select("image_url").eq("document_id", doc_id).execute()
                leg_rows = getattr(leg, "data", None) or []
                # Map to enriched-like shape; treat as exterior unknown
                rows = [{"url": r.get("image_url"), "category": "exterior", "angle": None} for r in leg_rows if r.get("image_url")]
            except Exception:
                pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase read failed: {e}")

    def _is_unknown_exterior(r: dict) -> bool:
        cat = (r.get("category") or "exterior").lower()
        ang = (r.get("angle") or "unknown").lower()
        return cat == "exterior" and (not ang or ang == "unknown")

    to_classify = [
        {"url": r.get("url"), "id": r.get("id")}
        for r in rows
        if r.get("url") and _is_unknown_exterior(r)
    ]

    queued = len(to_classify)
    print(f"[angles] start: document_id={doc_id} queued={queued} total_rows={len(rows)}")
    if queued > 0:
        sample = [it.get("url") for it in to_classify[:3]]
        print(f"[angles] sample urls: {sample}")
    if queued == 0:
        return {"status": "started", "queued": 0, "document_id": doc_id}

    async def _classify_and_persist(doc_id: str, items: list[dict]):
        # Reuse similar logic as /classify-angles but persist directly
        cache_path = Path(tempfile.gettempdir()) / "angle_cache.json"

        def load_cache() -> dict:
            try:
                if cache_path.exists():
                    return json.loads(cache_path.read_text())
            except Exception:
                pass
            return {}

        def save_cache(db: dict) -> None:
            try:
                cache_path.write_text(json.dumps(db, indent=2))
            except Exception:
                pass

        def content_hash_bytes(b: bytes) -> str:
            h = hashlib.sha1(); h.update(b); return h.hexdigest()

        try:
            print(f"[angles] worker: start doc={doc_id} items={len(items)}")
            async with httpx.AsyncClient(timeout=30) as client:
                cache = load_cache()
                rows_to_upsert = []
                for idx, it in enumerate(items, start=1):
                    url = it.get("url")
                    angle = "unknown"; source = "llm"; conf = None
                    try:
                        if not url or not url.startswith(("http://", "https://")):
                            raise ValueError("Invalid URL")
                        try:
                            resp = await client.get(url)
                            resp.raise_for_status()
                            b = resp.content
                            ch = content_hash_bytes(b)
                        except Exception as fetch_err:
                            print(f"[angles] fetch error idx={idx} url={url}: {fetch_err}")
                            ch = None
                        c = cache.get(ch) if ch else None
                        if c and isinstance(c, dict) and c.get("angle"):
                            angle = c["angle"]; source = c.get("source", "cache"); conf = c.get("confidence")
                        else:
                            used_llm = False
                            if payload.llm_enabled and openai_client is not None:
                                try:
                                    prompt = (
                                        "Classify the vehicle viewing angle into one of: front, front_left, front_right, "
                                        "side_left, side_right, back, back_left, back_right. Respond ONLY with the angle token."
                                    )
                                    completion = openai_client.chat.completions.create(
                                        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                                        messages=[
                                            {"role": "system", "content": "You are a strict classifier."},
                                            {
                                                "role": "user",
                                                "content": [
                                                    {"type": "text", "text": prompt},
                                                    {"type": "image_url", "image_url": {"url": url}},
                                                ],
                                            },
                                        ],
                                        temperature=0.0,
                                    )
                                    txt = (completion.choices[0].message.content or "").strip().lower()
                                    aliases = {"rear": "back", "rear_left": "back_left", "rear_right": "back_right"}
                                    txt = aliases.get(txt, txt)
                                    if txt in [
                                        "front","front_left","front_right","side_left","side_right","back","back_left","back_right"
                                    ]:
                                        angle = txt; source = "llm"; conf = None; used_llm = True
                                except Exception as llm_err:
                                    print(f"[angles] llm error idx={idx} url={url}: {llm_err}")
                            if angle == "unknown" and not used_llm:
                                s = url.lower().replace("rear", "back")
                                if ("front left" in s) or ("left front" in s) or (" fl" in s): angle = "front_left"
                                elif ("front right" in s) or ("right front" in s) or (" fr" in s): angle = "front_right"
                                elif ("back left" in s) or ("left back" in s) or ("rear left" in s) or (" rl" in s): angle = "back_left"
                                elif ("back right" in s) or ("right back" in s) or ("rear right" in s) or (" rr" in s): angle = "back_right"
                                elif "front" in s: angle = "front"
                                elif "back" in s: angle = "back"
                                elif "side" in s and "left" in s: angle = "side_left"
                                elif "side" in s and "right" in s: angle = "side_right"
                                elif " left" in s: angle = "side_left"
                                elif " right" in s: angle = "side_right"
                                else: angle = "unknown"
                                source = "heuristic"
                        cache[ch] = {"angle": angle, "source": source, "confidence": conf, "updated": time.time()} if ch else {"angle": angle, "source": source, "confidence": conf}
                    except Exception as item_err:
                        print(f"[angles] classify error idx={idx} url={url}: {item_err}")
                        angle = "unknown"; source = "error"; conf = None
                    rows_to_upsert.append({
                        "document_id": doc_id,
                        "url": url,
                        "angle": angle,
                        "source": source,
                        "confidence": conf,
                    })
                save_cache(cache)
            try:
                # supabase-py expects on_conflict as a comma-separated string
                sb.table("images").upsert(rows_to_upsert, on_conflict="document_id,url").execute()
                print(f"[angles] upserted {len(rows_to_upsert)} rows for doc={doc_id}")
            except Exception as up_err:
                print(f"[angles] upsert error doc={doc_id}: {up_err}")
                # Best-effort fallback
                ok = 0
                for row in rows_to_upsert:
                    try:
                        sb.table("images").update({k: v for k, v in row.items() if k not in ("document_id","url")} ).eq("document_id", row["document_id"]).eq("url", row["url"]).execute()
                        ok += 1
                    except Exception as upd_err:
                        print(f"[angles] update error doc={doc_id} url={row.get('url')}: {upd_err}")
                print(f"[angles] fallback updated {ok}/{len(rows_to_upsert)} rows for doc={doc_id}")
        except Exception as worker_err:
            print(f"[angles] worker fatal doc={doc_id}: {worker_err}")

    # Fire-and-forget background task (or run synchronously for debugging)
    if payload.debug_sync:
        print(f"[angles] debug_sync enabled for doc={doc_id}")
        await _classify_and_persist(doc_id, to_classify)
        return {"status": "completed", "queued": queued, "document_id": doc_id}
    else:
        asyncio.create_task(_classify_and_persist(doc_id, to_classify))
        return {"status": "started", "queued": queued, "document_id": doc_id}

@app.get("/angles/classify/status")
async def angles_classify_status(document_id: str):
    sb = supabase()
    try:
        res = sb.table("images").select("url, category, angle").eq("document_id", document_id).execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            # Fallback to legacy document_images to compute totals
            try:
                leg = sb.table("document_images").select("image_url").eq("document_id", document_id).execute()
                leg_rows = getattr(leg, "data", None) or []
                rows = [{"url": r.get("image_url"), "category": "exterior", "angle": None} for r in leg_rows if r.get("image_url")]
            except Exception:
                pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase read failed: {e}")
    total_exterior = 0; unknown_exterior = 0
    for r in rows:
        cat = (r.get("category") or "exterior").lower()
        ang = (r.get("angle") or "unknown").lower()
        if cat == "exterior":
            total_exterior += 1
            if not ang or ang == "unknown":
                unknown_exterior += 1
    out = {"document_id": document_id, "total_exterior": total_exterior, "unknown_exterior": unknown_exterior}
    print(f"[angles] status: doc={document_id} totals={total_exterior} unknown={unknown_exterior}")
    return out
