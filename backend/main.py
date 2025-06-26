from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI(title="Damage Report Service")

class GeneratePayload(BaseModel):
    document: dict

@app.post("/generate")
async def generate_report(payload: GeneratePayload):
    """Placeholder implementation.

    Railway just needs a responding endpoint so we can wire the
    Supabase Edge Function end-to-end. Replace the stub with calls
    into generate_damage_report.py / _staged.py when ready.
    """
    # In a real implementation you would:
    # 1. Download / open the image URLs in payload.document["images"].
    # 2. Call the GPT-4o logic from generate_damage_report_staged.py.
    # 3. Upload the JSON + PDF to storage (e.g. S3) and return the URLs.

    doc_id = str(uuid.uuid4())
    json_url = f"https://example.com/reports/{doc_id}.json"
    pdf_url = f"https://example.com/reports/{doc_id}.pdf"

    return {"json_url": json_url, "pdf_url": pdf_url}

@app.get("/")
async def root():
    return {"status": "ok"}
