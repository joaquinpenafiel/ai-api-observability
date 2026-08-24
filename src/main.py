from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(
    title="API Integration Lab",
    description="Reproducible laboratory for REST API integration and data processing.",
    version="0.1.0",
)


class ProcessRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    source: str = Field(default="manual")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/process")
def process_data(payload: ProcessRequest):
    normalized_text = " ".join(payload.text.split())

    return {
        "source": payload.source,
        "original_text": payload.text,
        "normalized_text": normalized_text,
        "character_count": len(normalized_text),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
