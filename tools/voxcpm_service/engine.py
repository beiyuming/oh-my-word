from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
from voxcpm import VoxCPM


@lru_cache(maxsize=1)
def get_model() -> VoxCPM:
    model_id = os.environ.get("VOXCPM_MODEL_ID", "openbmb/VoxCPM2")
    device = os.environ.get("VOXCPM_DEVICE", "auto")
    optimize = os.environ.get("VOXCPM_OPTIMIZE", "1") != "0"
    return VoxCPM.from_pretrained(
        model_id,
        load_denoiser=False,
        device=device,
        optimize=optimize,
    )


def synthesize_wav_samples(text: str, *, accent: str) -> tuple[np.ndarray, int]:
    model = get_model()
    control = "clear British English pronunciation" if accent == "uk" else "clear American English pronunciation"
    wav = model.generate(
        text=text,
        control=control,
        cfg_value=2.0,
        inference_timesteps=10,
    )
    return np.asarray(wav, dtype=np.float32), model.tts_model.sample_rate
