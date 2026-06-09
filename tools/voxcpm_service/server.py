from __future__ import annotations

import io
from typing import Literal

import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .engine import synthesize_wav_samples


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    accent: str = "us"
    format: Literal["wav"] = "wav"


app = FastAPI(title="oh-my-word VoxCPM local service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/synthesize")
def synthesize(request: SynthesizeRequest) -> Response:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    samples, sample_rate = synthesize_wav_samples(text, accent=request.accent)
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV")
    return Response(content=buffer.getvalue(), media_type="audio/wav")
