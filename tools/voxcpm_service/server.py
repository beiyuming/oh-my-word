from __future__ import annotations

import io
from typing import Literal

import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .engine import synthesize_pcm_chunks, synthesize_wav_samples


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


@app.post("/synthesize_stream")
def synthesize_stream(request: SynthesizeRequest) -> StreamingResponse:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    chunks, sample_rate = synthesize_pcm_chunks(text, accent=request.accent)
    return StreamingResponse(
        chunks,
        media_type="audio/L16",
        headers={
            "X-OhMyWord-Sample-Rate": str(sample_rate),
            "X-OhMyWord-Channels": "1",
            "X-OhMyWord-Sample-Format": "s16le",
        },
    )
