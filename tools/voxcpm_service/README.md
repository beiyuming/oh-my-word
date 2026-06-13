# VoxCPM Local Companion Process

This local process is optional and runs on the user's own computer. It is not a cloud server and is not part of the desktop app installer. It keeps VoxCPM, PyTorch, model checkpoints, and GPU runtime dependencies outside the PySide/PyInstaller process.

The process uses the VoxCPM Python API internally. The desktop app talks to it through `http://127.0.0.1:8808` so the GUI remains stable even if model loading or synthesis fails.

## Install

```powershell
py -3.11 -m venv .venv-voxcpm
.\.venv-voxcpm\Scripts\python.exe -m pip install -r tools\voxcpm_service\requirements.txt
```

The installer-facing setup script accepts a model cache directory:

```powershell
.\tools\voxcpm_service\install_local.ps1 -ModelCacheRoot "$env:LOCALAPPDATA\OhMyWord\voxcpm\models"
```

That path is used for `HF_HOME` and `HF_HUB_CACHE`, so model weights do not have to use the global Hugging Face cache.
Use `-UseHfMirror` when direct Hugging Face access is unreliable.

## Run

```powershell
$env:HF_HOME = "$env:LOCALAPPDATA\OhMyWord\voxcpm\models"
$env:HF_HUB_CACHE = "$env:LOCALAPPDATA\OhMyWord\voxcpm\models\hub"
$env:VOXCPM_MODEL_ID = "openbmb/VoxCPM2"
$env:VOXCPM_DEVICE = "auto"
.\.venv-voxcpm\Scripts\python.exe -m uvicorn tools.voxcpm_service.server:app --host 127.0.0.1 --port 8808
```

The desktop app should use `http://127.0.0.1:8808` as the VoxCPM endpoint.

## API

- `GET /health` returns `{"status": "ok"}`.
- `POST /synthesize_stream` uses VoxCPM `generate_streaming()` and streams `s16le` mono PCM chunks. Response headers include `X-OhMyWord-Sample-Rate`, `X-OhMyWord-Channels`, and `X-OhMyWord-Sample-Format`.
- `POST /synthesize` returns a complete WAV response and remains available as a compatibility fallback.

Both synthesis routes explicitly enable VoxCPM badcase retries and use the same defaults:

- `cfg_value=1.5`
- `inference_timesteps=10`
- `retry_badcase=True`
- `retry_badcase_max_times=3`
- `retry_badcase_ratio_threshold=4.0`

`VOXCPM_CFG_VALUE` and `VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD` can be set before starting the service for local tuning. The service also adds short leading and trailing silence to both streamed PCM and complete WAV output to reduce clipped starts or endings on short word playback.

## Check

```powershell
curl.exe http://127.0.0.1:8808/health
```

The first synthesis request may be slow because model weights can be downloaded and loaded by VoxCPM.
