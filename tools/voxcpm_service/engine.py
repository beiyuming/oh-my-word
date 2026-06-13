from __future__ import annotations

import os
from functools import lru_cache
from collections.abc import Iterator

import numpy as np
from voxcpm import VoxCPM


VOXCPM_CFG_VALUE = float(os.environ.get("VOXCPM_CFG_VALUE", "1.5"))
VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD = float(
    os.environ.get("VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD", "4.0")
)
LEADING_SILENCE_SECONDS = 0.12
TRAILING_SILENCE_SECONDS = 0.30


@lru_cache(maxsize=1)
def get_model() -> VoxCPM:
    model_id = os.environ.get("VOXCPM_MODEL_ID", "openbmb/VoxCPM2")
    device = os.environ.get("VOXCPM_DEVICE", "auto")
    optimize = os.environ.get("VOXCPM_OPTIMIZE", "0") != "0"
    return VoxCPM.from_pretrained(
        model_id,
        load_denoiser=False,
        device=device,
        optimize=optimize,
    )


def synthesize_wav_samples(text: str, *, accent: str) -> tuple[np.ndarray, int]:
    model = get_model()
    # VoxCPM 2.0.3 does not expose an accent/control argument.
    _ = accent
    wav = model.generate(
        text=text,
        cfg_value=VOXCPM_CFG_VALUE,
        inference_timesteps=10,
        retry_badcase=True,
        retry_badcase_max_times=3,
        retry_badcase_ratio_threshold=VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD,
    )
    sample_rate = model.tts_model.sample_rate
    return _pad_audio_edges(np.asarray(wav, dtype=np.float32), sample_rate), sample_rate


def synthesize_pcm_chunks(text: str, *, accent: str) -> tuple[Iterator[bytes], int]:
    model = get_model()
    # VoxCPM 2.0.3 does not expose an accent/control argument.
    _ = accent
    sample_rate = model.tts_model.sample_rate

    def chunks() -> Iterator[bytes]:
        leading_silence = _silence_pcm_bytes(sample_rate, LEADING_SILENCE_SECONDS)
        if leading_silence:
            yield leading_silence

        for chunk in model.generate_streaming(
            text=text,
            cfg_value=VOXCPM_CFG_VALUE,
            inference_timesteps=10,
            retry_badcase=True,
            retry_badcase_max_times=3,
            retry_badcase_ratio_threshold=VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD,
        ):
            samples = np.asarray(chunk, dtype=np.float32)
            if samples.size == 0:
                continue
            yield _samples_to_s16le_bytes(samples)

        trailing_silence = _silence_pcm_bytes(sample_rate, TRAILING_SILENCE_SECONDS)
        if trailing_silence:
            yield trailing_silence

    return chunks(), sample_rate


def _pad_audio_edges(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if samples.size == 0 or sample_rate <= 0:
        return samples
    leading_frames = int(round(sample_rate * LEADING_SILENCE_SECONDS))
    trailing_frames = int(round(sample_rate * TRAILING_SILENCE_SECONDS))
    if leading_frames <= 0 and trailing_frames <= 0:
        return samples
    return np.pad(samples, (leading_frames, trailing_frames), mode="constant").astype(np.float32, copy=False)


def _silence_pcm_bytes(sample_rate: int, seconds: float) -> bytes:
    if sample_rate <= 0 or seconds <= 0:
        return b""
    frame_count = int(round(sample_rate * seconds))
    return b"\x00\x00" * frame_count


def _samples_to_s16le_bytes(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2", copy=False).tobytes()
