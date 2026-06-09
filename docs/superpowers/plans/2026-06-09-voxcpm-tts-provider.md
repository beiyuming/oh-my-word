# VoxCPM Local TTS Provider Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-selectable VoxCPM text-to-speech provider that runs on the user's own computer without putting heavy model dependencies inside the PySide desktop process or PyInstaller installer.

**Architecture:** Keep `PronunciationService` as the app-facing TTS facade, split the actual engines behind provider classes, and make the desktop app call a VoxCPM companion process on `127.0.0.1` for generated WAV audio. The companion process runs on the same user machine and should wrap the VoxCPM Python API first; this is not a cloud/server deployment.

**Tech Stack:** Python 3.11, PySide6, QtTextToSpeech, QtMultimedia, stdlib `urllib.request`, optional separate VoxCPM service environment with `voxcpm`, `fastapi`, `uvicorn`, `soundfile`, and `numpy`.

---

## Decision

Use a local machine companion process by default, not the VoxCPM Python API inside the PySide desktop process.

This does not mean deploying to a remote server. Both recommended paths are local to the user's own computer:

- The desktop app remains the lightweight tray app.
- A separate local VoxCPM Python environment loads the model and exposes a localhost API.
- The localhost API can later be started manually, auto-started by the app, or replaced by a named-pipe/subprocess transport if HTTP is undesirable.

The desktop app is a lightweight Windows-first PySide6 tray application packaged by PyInstaller. VoxCPM brings model weights, PyTorch, device selection, first-run downloads, optional denoiser dependencies, and GPU/CPU runtime pressure. Putting those directly inside `main.py` or `app/tts.py` would make startup slower, packaging larger, crash isolation weaker, and installer support harder.

The better design is:

```text
oh-my-word desktop app
  -> PronunciationService
     -> QtTextToSpeech provider
     -> VoxCPM HTTP provider
        -> http://127.0.0.1:8808/synthesize
           -> local VoxCPM companion process on the user's computer
              -> VoxCPM Python API first
              -> NanoVLLM-VoxCPM or vLLM-Omni later
```

This still uses the VoxCPM Python API. The important boundary is where it runs: in a dedicated local Python process instead of the GUI process. The app keeps a stable provider contract and does not care whether the local process internals are standard VoxCPM, NanoVLLM-VoxCPM, or vLLM-Omni.

## Direct Python API Boundary

Directly importing VoxCPM in the desktop app is acceptable only for a developer/source-run mode where the user controls the Python environment and accepts slower startup and heavier dependencies.

Do not make direct in-process VoxCPM the first packaged EXE path because:

- root `requirements.txt` would need ML/runtime dependencies that conflict with the current lightweight desktop dependency set;
- PyInstaller would have to collect PyTorch/CUDA-related packages and still would not own model checkpoint downloads cleanly;
- model loading, GPU memory pressure, and synthesis exceptions would share the same process as tray, hotkeys, and popups;
- a failed model import could break the whole app before the user can open settings and switch back to system TTS.

If a future implementation wants in-process Python API support, add it as an explicit experimental provider after the local companion process works:

```text
TtsProvider.SYSTEM_QT
TtsProvider.VOXCPM_LOCAL_PROCESS
TtsProvider.VOXCPM_IN_PROCESS_EXPERIMENTAL
```

The first implementation should only expose the stable local-process option in the user settings.

## Verified Source Notes

Checked on 2026-06-09:

- VoxCPM official quick start exposes Python API, CLI, and web demo paths: `https://voxcpm.readthedocs.io/en/latest/quickstart.html`.
- VoxCPM installation docs list Python 3.10-3.12, PyTorch >= 2.5.0, optional CUDA >= 12.0 for NVIDIA GPU acceleration, and several GB of disk for model weights: `https://voxcpm.readthedocs.io/en/latest/installation.html`.
- VoxCPM FAQ lists reference VRAM and speed on RTX 4090: VoxCPM 1.0 about 5 GB VRAM, VoxCPM 1.5 about 6 GB VRAM, VoxCPM 2 about 8 GB VRAM; CPU works but is slow: `https://voxcpm.readthedocs.io/en/latest/faq.html`.
- NanoVLLM-VoxCPM documentation says it provides Python sync/async streaming and an optional FastAPI demo server, but is GPU-centric and does not support CPU-only execution: `https://voxcpm.readthedocs.io/en/latest/deployment/nanovllm_voxcpm.html`.
- vLLM-Omni documentation offers an OpenAI-compatible serving direction for production multi-tenant deployments: `https://voxcpm.readthedocs.io/en/latest/deployment/vllm_omni.html`.

## Local Hardware Profiles

The installer and settings UI must communicate the requirement plainly before downloading anything:

| Profile | Expected behavior | Recommended handling |
| --- | --- | --- |
| App only | No VoxCPM model, current Qt system TTS remains available. | Default install path. |
| CPU-only VoxCPM | Technically possible with `device="cpu"` and `optimize=False`, but likely slow. | Allow only after warning; suitable for short word/example synthesis tests, not a polished default. |
| NVIDIA GPU, 5-6 GB VRAM | May fit smaller VoxCPM 0.5B/1.5 checkpoints if the implementation chooses those models. | Offer as "lighter model" only after model selection is designed. |
| NVIDIA GPU, 8 GB+ VRAM | Official reference for VoxCPM2 is about 8 GB VRAM. | Recommended local VoxCPM2 target. |
| No reliable Hugging Face access | Model download can fail or stall. | Offer mirror/source configuration and keep retry logs. |

Do not block the main desktop installation on these requirements. VoxCPM is an optional pronunciation engine; users without the right runtime should still get the lightweight app.

## Installer One-Click Deployment Decision

Yes, the installer can provide a one-click local deployment option, but it should be a post-install optional step rather than part of the required install path.

Recommended first UX:

```text
Install oh my word
  [x] Create desktop shortcut
  [x] Launch after install
  [ ] Install local VoxCPM pronunciation engine

If checked:
  open "Local VoxCPM setup" step after app files are installed
  choose model directory
  choose CPU / auto GPU mode
  install service-only Python environment
  download/check model
  run health check
  save app setting: provider = voxcpm_local
```

Implementation rule:

- The checkbox must be off by default.
- The local model install must be resumable and repairable from settings later.
- The installer must not require administrator privileges for VoxCPM setup.
- Put the VoxCPM venv and model cache in a user-writable directory such as `%LOCALAPPDATA%\OhMyWord\voxcpm\` or a user-selected model directory, not inside `Program Files`.
- If setup fails, the main app install still succeeds and keeps `system_qt` as the provider.
- Log setup output to a user-writable file and surface the path in the failure message.
- Do not silently download several GB of model data. Show estimated disk/network cost before starting.

## Project Constraints To Preserve

- Do not put VoxCPM, PyTorch, CUDA, model checkpoints, or NanoVLLM dependencies in root `requirements.txt`.
- Do not package model files into `dist/`, the portable folder, or `oh-my-word-setup.exe`.
- Do not write provider credentials or machine-specific model paths into tracked app settings defaults.
- Keep `storage/settings.json` as user configuration and `storage/oh_my_word.sqlite3` as learning state. This feature does not need database schema changes.
- Preserve existing pronunciation behavior: the app speaks `word. example_sentence` and records `last_pronounced_at` only when `speak()` returns `True`.
- If the local VoxCPM service is unavailable, return `False`, log/report the failure, and do not silently claim pronunciation succeeded.

## File Structure

- Modify `app/models.py`: add `TtsProvider` enum and VoxCPM settings fields to `AppSettings`.
- Modify `app/settings.py`: normalize and persist provider, endpoint, and timeout fields.
- Modify `app/settings_window.py`: add provider selector, endpoint input, and timeout input in the pronunciation settings area.
- Modify `app/tts.py`: keep `PronunciationService` public API, add provider selection and backend classes.
- Modify `app/controller.py`: construct and refresh `PronunciationService` from settings.
- Create `tests/test_tts.py`: cover provider selection, HTTP success, HTTP failure, local-only endpoint validation, and WAV playback delegation without real audio output.
- Modify `tests/test_settings.py`: cover new settings defaults, invalid normalization, and persistence.
- Create `tests/test_settings_window.py`: offscreen round-trip for new settings controls.
- Modify `tests/test_controller.py`: cover provider rebuild on settings change and failure not recording pronunciation.
- Create `tools/voxcpm_service/README.md`: local companion process setup and run instructions.
- Create `tools/voxcpm_service/engine.py`: thin wrapper around the VoxCPM Python API.
- Create `tools/voxcpm_service/server.py`: minimal FastAPI wrapper around `engine.py`.
- Create `tools/voxcpm_service/requirements.txt`: service-only dependencies.
- Create `tools/voxcpm_service/install_local.ps1`: resumable local deployment script for the optional installer path.
- Modify `build/build_installer.ps1`: add an optional post-install checkbox that launches the local deployment script without bundling model dependencies.
- Modify `README.md`, `docs/specs/settings-and-storage.md`, `docs/specs/tray-hotkeys-tts.md`, and `docs/specs/packaging-runtime.md`: document the provider contract and packaging boundary.

---

### Task 1: Add Settings Schema For TTS Providers

**Files:**
- Modify: `app/models.py`
- Modify: `app/settings.py`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings tests**

Add these imports in `tests/test_settings.py`:

```python
from app.models import TtsProvider
from app.settings import settings_to_dict
```

Add these tests to `SettingsStoreTests`:

```python
    def test_tts_provider_defaults_to_system_qt(self) -> None:
        settings = AppSettings()

        self.assertIs(settings.tts_provider, TtsProvider.SYSTEM_QT)
        self.assertEqual(settings.voxcpm_endpoint, "http://127.0.0.1:8808")
        self.assertEqual(settings.voxcpm_timeout_seconds, 15)

    def test_normalizes_tts_provider_settings(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps(
                    {
                        "tts_provider": "voxcpm_local",
                        "voxcpm_endpoint": "http://localhost:8808/",
                        "voxcpm_timeout_seconds": 31,
                    }
                ),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
            self.assertEqual(settings.voxcpm_endpoint, "http://localhost:8808")
            self.assertEqual(settings.voxcpm_timeout_seconds, 31)

    def test_rejects_non_local_voxcpm_endpoint(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps(
                    {
                        "tts_provider": "voxcpm_local",
                        "voxcpm_endpoint": "https://example.com/tts",
                        "voxcpm_timeout_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
            self.assertEqual(settings.voxcpm_endpoint, "http://127.0.0.1:8808")
            self.assertEqual(settings.voxcpm_timeout_seconds, 15)

    def test_persists_tts_provider_settings(self) -> None:
        payload = settings_to_dict(
            AppSettings(
                tts_provider=TtsProvider.VOXCPM_LOCAL,
                voxcpm_endpoint="http://localhost:8810",
                voxcpm_timeout_seconds=22,
            )
        )

        self.assertEqual(payload["tts_provider"], "voxcpm_local")
        self.assertEqual(payload["voxcpm_endpoint"], "http://localhost:8810")
        self.assertEqual(payload["voxcpm_timeout_seconds"], 22)
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_settings.py -q
```

Expected: fails because `TtsProvider`, `tts_provider`, `voxcpm_endpoint`, and `voxcpm_timeout_seconds` do not exist yet.

- [ ] **Step 3: Add model fields**

In `app/models.py`, add:

```python
class TtsProvider(Enum):
    SYSTEM_QT = "system_qt"
    VOXCPM_LOCAL = "voxcpm_local"


DEFAULT_VOXCPM_ENDPOINT = "http://127.0.0.1:8808"
DEFAULT_VOXCPM_TIMEOUT_SECONDS = 15
```

Add fields to `AppSettings` near `mute_pronunciation` and `accent`:

```python
    tts_provider: TtsProvider = TtsProvider.SYSTEM_QT
    voxcpm_endpoint: str = DEFAULT_VOXCPM_ENDPOINT
    voxcpm_timeout_seconds: int = DEFAULT_VOXCPM_TIMEOUT_SECONDS
```

- [ ] **Step 4: Normalize and persist settings**

In `app/settings.py`, import:

```python
from urllib.parse import urlparse
```

Add helper functions:

```python
def _normalize_local_http_endpoint(value: Any, default: str) -> str:
    text = _normalize_optional_text(value, default) or default
    parsed = urlparse(text)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "http":
        return default
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        return default
    if parsed.port is None:
        return default
    return text.rstrip("/")


def _normalize_timeout_seconds(value: Any, default: int) -> int:
    timeout = _normalize_positive_int(value, default)
    return min(max(timeout, 1), 120)
```

Update `normalize_settings()`:

```python
        tts_provider=_normalize_enum(data.get("tts_provider"), TtsProvider, defaults.tts_provider),
        voxcpm_endpoint=_normalize_local_http_endpoint(
            data.get("voxcpm_endpoint"),
            defaults.voxcpm_endpoint,
        ),
        voxcpm_timeout_seconds=_normalize_timeout_seconds(
            data.get("voxcpm_timeout_seconds"),
            defaults.voxcpm_timeout_seconds,
        ),
```

Update `settings_to_dict()` so these fields are written as:

```python
        "tts_provider": settings.tts_provider.value,
        "voxcpm_endpoint": settings.voxcpm_endpoint,
        "voxcpm_timeout_seconds": settings.voxcpm_timeout_seconds,
```

- [ ] **Step 5: Run settings tests**

Run:

```powershell
py -3.11 -m pytest tests/test_settings.py -q
```

Expected: all settings tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app/models.py app/settings.py tests/test_settings.py
git commit -m "feat: add tts provider settings"
```

---

### Task 2: Add TTS Provider Backends

**Files:**
- Modify: `app/tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write provider tests**

Create `tests/test_tts.py`:

```python
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app.models import Accent, TtsProvider
from app.tts import PronunciationService, VoxCpmHttpProvider


class _FakeResponse:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class VoxCpmHttpProviderTests(unittest.TestCase):
    def test_posts_text_and_plays_wav_bytes(self) -> None:
        player = Mock()
        with TemporaryDirectory() as tmp_dir:
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=player,
            )

            with patch("app.tts.urlopen", return_value=_FakeResponse(b"RIFFfake-wave")) as urlopen:
                result = provider.speak("focus. Focus on review.", accent=Accent.US)

        self.assertTrue(result)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8808/synthesize")
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["text"], "focus. Focus on review.")
        self.assertEqual(payload["accent"], "us")
        player.play.assert_called_once()

    def test_returns_false_when_http_fails(self) -> None:
        player = Mock()
        provider = VoxCpmHttpProvider(
            endpoint="http://127.0.0.1:8808",
            timeout_seconds=1,
            cache_dir=Path("."),
            audio_player=player,
        )

        with patch("app.tts.urlopen", side_effect=OSError("service down")):
            result = provider.speak("focus", accent=Accent.US)

        self.assertFalse(result)
        self.assertIn("service down", provider.last_error or "")
        player.play.assert_not_called()


class PronunciationServiceProviderTests(unittest.TestCase):
    def test_uses_voxcpm_provider_when_selected(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            service = PronunciationService(
                provider=TtsProvider.VOXCPM_LOCAL,
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
            )

        self.assertEqual(service.provider, TtsProvider.VOXCPM_LOCAL)
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_tts.py -q
```

Expected: fails because `VoxCpmHttpProvider` and new `PronunciationService` parameters do not exist yet.

- [ ] **Step 3: Refactor `app/tts.py` behind the existing service API**

Keep these public methods and signals on `PronunciationService`:

```python
availability_changed = Signal(bool)
error_occurred = Signal(str)

def speak(self, text: str, *, accent: Any | None = None) -> bool: ...
def stop(self) -> None: ...
def set_accent(self, accent: Any | None) -> None: ...
@property
def is_available(self) -> bool: ...
@property
def last_error(self) -> str | None: ...
```

Add these implementation classes in `app/tts.py`:

```python
class QtTextToSpeechProvider:
    def __init__(self, owner: QObject, accent: Any | None = None) -> None: ...
    @property
    def is_available(self) -> bool: ...
    @property
    def last_error(self) -> str | None: ...
    def set_accent(self, accent: Any | None) -> None: ...
    def speak(self, text: str, *, accent: Any | None = None) -> bool: ...
    def stop(self) -> None: ...


class LocalWavPlayer(QObject):
    def play(self, path: Path) -> bool: ...
    def stop(self) -> None: ...


class VoxCpmHttpProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: int,
        cache_dir: Path,
        audio_player: LocalWavPlayer | Any | None = None,
    ) -> None: ...
    @property
    def is_available(self) -> bool: ...
    @property
    def last_error(self) -> str | None: ...
    def set_accent(self, accent: Any | None) -> None: ...
    def speak(self, text: str, *, accent: Any | None = None) -> bool: ...
    def stop(self) -> None: ...
```

Use stdlib HTTP imports:

```python
from urllib.request import Request, urlopen
```

For VoxCPM, write WAV bytes to one rotating runtime file:

```python
audio_path = self._cache_dir / "voxcpm-current.wav"
audio_path.write_bytes(audio_bytes)
return self._audio_player.play(audio_path)
```

The provider should send:

```python
{
    "text": message,
    "accent": str(getattr(accent, "value", accent) or "").lower(),
    "format": "wav"
}
```

The provider should call `POST {endpoint}/synthesize` and require a non-empty response body. HTTP or playback exceptions set `last_error` and return `False`.

- [ ] **Step 4: Implement `PronunciationService` provider selection**

Change `PronunciationService.__init__` to accept:

```python
provider: TtsProvider = TtsProvider.SYSTEM_QT
endpoint: str = DEFAULT_VOXCPM_ENDPOINT
timeout_seconds: int = DEFAULT_VOXCPM_TIMEOUT_SECONDS
cache_dir: Path | None = None
```

Add a property:

```python
@property
def provider(self) -> TtsProvider:
    return self._provider_name
```

For `SYSTEM_QT`, instantiate `QtTextToSpeechProvider`. For `VOXCPM_LOCAL`, instantiate `VoxCpmHttpProvider`. Emit `availability_changed` after backend creation. Forward `speak()`, `stop()`, `set_accent()`, `is_available`, and `last_error` to the selected provider. On a failed `speak()`, emit `error_occurred` with the backend error string.

- [ ] **Step 5: Run TTS tests**

Run:

```powershell
py -3.11 -m pytest tests/test_tts.py -q
```

Expected: all TTS provider tests pass without requiring VoxCPM or real audio output.

- [ ] **Step 6: Commit**

```powershell
git add app/tts.py tests/test_tts.py
git commit -m "feat: add selectable tts provider backends"
```

---

### Task 3: Add Settings Window Controls

**Files:**
- Modify: `app/settings_window.py`
- Create: `tests/test_settings_window.py`

- [ ] **Step 1: Write offscreen round-trip tests**

Create `tests/test_settings_window.py`:

```python
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.models import AppSettings, TtsProvider
from app.settings_window import SettingsDialog


class SettingsDialogTtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_round_trips_voxcpm_provider_settings(self) -> None:
        dialog = SettingsDialog(
            AppSettings(
                tts_provider=TtsProvider.VOXCPM_LOCAL,
                voxcpm_endpoint="http://localhost:8810",
                voxcpm_timeout_seconds=25,
            )
        )
        self.addCleanup(dialog.close)

        settings = dialog.get_settings()

        self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
        self.assertEqual(settings.voxcpm_endpoint, "http://localhost:8810")
        self.assertEqual(settings.voxcpm_timeout_seconds, 25)
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_settings_window.py -q
```

Expected: fails because settings controls do not exist or do not round-trip.

- [ ] **Step 3: Add UI controls**

In `SettingsDialog.__init__`, add:

```python
self._tts_provider = QComboBox(self)
self._voxcpm_endpoint = QLineEdit(self)
self._voxcpm_timeout = QSpinBox(self)
```

Import `QLineEdit` if it is not already imported.

In `_build_ui()`, add these controls near the existing pronunciation controls:

```python
self._tts_provider.addItem("系统离线发音", TtsProvider.SYSTEM_QT)
self._tts_provider.addItem("VoxCPM 本地服务", TtsProvider.VOXCPM_LOCAL)
self._voxcpm_endpoint.setPlaceholderText("http://127.0.0.1:8808")
self._voxcpm_timeout.setRange(1, 120)
self._voxcpm_timeout.setSuffix(" 秒")

form.addRow("发音引擎", self._tts_provider)
form.addRow("VoxCPM 地址", self._voxcpm_endpoint)
form.addRow("VoxCPM 超时", self._voxcpm_timeout)
```

Wire `set_settings()`:

```python
self._set_enum_value(self._tts_provider, settings.tts_provider)
self._voxcpm_endpoint.setText(settings.voxcpm_endpoint)
self._voxcpm_timeout.setValue(settings.voxcpm_timeout_seconds)
```

Wire `get_settings()`:

```python
tts_provider=self._tts_provider.currentData(),
voxcpm_endpoint=self._voxcpm_endpoint.text().strip() or AppSettings().voxcpm_endpoint,
voxcpm_timeout_seconds=self._voxcpm_timeout.value(),
```

- [ ] **Step 4: Run settings window tests**

Run:

```powershell
py -3.11 -m pytest tests/test_settings_window.py -q
```

Expected: settings window tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app/settings_window.py tests/test_settings_window.py
git commit -m "feat: expose tts provider settings"
```

---

### Task 4: Integrate Provider Selection In Controller

**Files:**
- Modify: `app/controller.py`
- Modify: `tests/test_controller.py`

- [ ] **Step 1: Write controller tests**

Add these tests to `ControllerPopupActionTests` in `tests/test_controller.py`:

```python
    def test_pronounce_failure_does_not_record_pronounced_at(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.speak.return_value = False
        controller.study_store = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_called_once_with("focus. Focus on review.", accent=controller.settings.accent)
        controller.study_store.record_word_pronounced.assert_not_called()

    def test_apply_settings_rebuilds_tts_when_provider_changes(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.hotkeys = Mock()
        controller.tray = Mock()
        controller.scheduler = Mock()
        controller.tts = Mock()

        new_settings = AppSettings(tts_provider=TtsProvider.VOXCPM_LOCAL)

        with patch("app.controller.PronunciationService") as service_class:
            service_class.return_value = Mock()
            controller._apply_settings(new_settings)

        controller.tts.stop.assert_called_once_with()
        service_class.assert_called_once()
        self.assertIs(controller.settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
```

Add import:

```python
from app.models import TtsProvider
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_controller.py -q
```

Expected: provider rebuild test fails until controller logic is added.

- [ ] **Step 3: Add a controller helper**

In `AppController`, add:

```python
def _create_tts_service(self) -> PronunciationService:
    return PronunciationService(
        accent=self.settings.accent,
        provider=self.settings.tts_provider,
        endpoint=self.settings.voxcpm_endpoint,
        timeout_seconds=self.settings.voxcpm_timeout_seconds,
        cache_dir=self._paths.storage_dir / "tts_cache",
        on_error=lambda message: self._log_warning("%s", message),
    )
```

In `initialize()`, replace direct `PronunciationService(...)` construction with:

```python
self.tts = self._create_tts_service()
```

In `_apply_settings()`, rebuild TTS when any provider field changes:

```python
provider_changed = (
    self.settings.tts_provider != new_settings.tts_provider
    or self.settings.voxcpm_endpoint != new_settings.voxcpm_endpoint
    or self.settings.voxcpm_timeout_seconds != new_settings.voxcpm_timeout_seconds
)
```

If `provider_changed` is true and `self.tts` exists:

```python
self.tts.stop()
self.settings = new_settings
self.tts = self._create_tts_service()
```

If only accent changed:

```python
self.settings = new_settings
if self.tts is not None:
    self.tts.set_accent(self.settings.accent)
```

Keep the existing hotkey, tray, scheduler, and settings persistence behavior intact.

- [ ] **Step 4: Run controller tests**

Run:

```powershell
py -3.11 -m pytest tests/test_controller.py -q
```

Expected: controller tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app/controller.py tests/test_controller.py
git commit -m "feat: switch tts provider from settings"
```

---

### Task 5: Add Separate Local VoxCPM Companion Process Skeleton

**Files:**
- Create: `tools/voxcpm_service/README.md`
- Create: `tools/voxcpm_service/requirements.txt`
- Create: `tools/voxcpm_service/engine.py`
- Create: `tools/voxcpm_service/server.py`

- [ ] **Step 1: Create service-only requirements**

Create `tools/voxcpm_service/requirements.txt`:

```text
voxcpm
fastapi
uvicorn[standard]
soundfile
numpy
```

Do not add these dependencies to root `requirements.txt`.

- [ ] **Step 2: Create the Python API engine wrapper**

Create `tools/voxcpm_service/engine.py`:

```python
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
```

- [ ] **Step 3: Create minimal localhost API wrapper**

Create `tools/voxcpm_service/server.py`:

```python
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
```

- [ ] **Step 4: Document local companion process setup**

Create `tools/voxcpm_service/README.md`:

```markdown
# VoxCPM Local Companion Process

This local process is optional and runs on the user's own computer. It is not a cloud server and is not part of the desktop app installer. It keeps VoxCPM, PyTorch, model checkpoints, and GPU runtime dependencies outside the PySide/PyInstaller process.

The process uses the VoxCPM Python API internally. The desktop app talks to it through `http://127.0.0.1:8808` so the GUI remains stable even if model loading or synthesis fails.

## Install

```powershell
py -3.11 -m venv .venv-voxcpm
.\.venv-voxcpm\Scripts\python.exe -m pip install -r tools\voxcpm_service\requirements.txt
```

## Run

```powershell
$env:VOXCPM_MODEL_ID = "openbmb/VoxCPM2"
$env:VOXCPM_DEVICE = "auto"
.\.venv-voxcpm\Scripts\python.exe -m uvicorn tools.voxcpm_service.server:app --host 127.0.0.1 --port 8808
```

The desktop app should use `http://127.0.0.1:8808` as the VoxCPM endpoint.

## Check

```powershell
curl.exe http://127.0.0.1:8808/health
```

The first synthesis request may be slow because model weights can be downloaded and loaded by VoxCPM.
```

- [ ] **Step 5: Manual companion process smoke test**

Run in an environment where VoxCPM dependencies are installed:

```powershell
.\.venv-voxcpm\Scripts\python.exe -m uvicorn tools.voxcpm_service.server:app --host 127.0.0.1 --port 8808
```

Then in another PowerShell:

```powershell
curl.exe -X POST http://127.0.0.1:8808/synthesize -H "Content-Type: application/json" -d "{\"text\":\"focus. Focus on review.\",\"accent\":\"us\",\"format\":\"wav\"}" --output voxcpm-test.wav
```

Expected: `voxcpm-test.wav` is created and can be played. Record device, Python version, and whether CPU or GPU was used in the implementation final report.

- [ ] **Step 6: Commit**

```powershell
git add tools/voxcpm_service/README.md tools/voxcpm_service/requirements.txt tools/voxcpm_service/engine.py tools/voxcpm_service/server.py
git commit -m "docs: add voxcpm local service skeleton"
```

---

### Task 6: Add Optional Installer Entry For Local VoxCPM Setup

**Files:**
- Create: `tools/voxcpm_service/install_local.ps1`
- Modify: `build/build_installer.ps1`
- Modify: `docs/specs/packaging-runtime.md`

- [ ] **Step 1: Create the local setup script**

Create `tools/voxcpm_service/install_local.ps1`:

```powershell
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\OhMyWord\voxcpm",
    [string]$PythonExe = "py",
    [string]$PythonVersion = "-3.11",
    [string]$Device = "auto",
    [switch]$CpuOnly,
    [switch]$UseHfMirror
)

$ErrorActionPreference = "Stop"
$installPath = [System.IO.Path]::GetFullPath($InstallRoot)
$venvPath = Join-Path $installPath ".venv"
$logPath = Join-Path $installPath "install.log"
$serverDir = Join-Path $installPath "service"

New-Item -ItemType Directory -Force -Path $installPath | Out-Null
Start-Transcript -Path $logPath -Append | Out-Null

try {
    if (-not (Test-Path $venvPath)) {
        & $PythonExe $PythonVersion -m venv $venvPath
    }

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install -r "$PSScriptRoot\requirements.txt"

    New-Item -ItemType Directory -Force -Path $serverDir | Out-Null
    Copy-Item -Force "$PSScriptRoot\server.py" $serverDir
    Copy-Item -Force "$PSScriptRoot\engine.py" $serverDir

    if ($UseHfMirror) {
        $env:HF_ENDPOINT = "https://hf-mirror.com"
    }
    if ($CpuOnly) {
        $env:VOXCPM_DEVICE = "cpu"
        $env:VOXCPM_OPTIMIZE = "0"
    } else {
        $env:VOXCPM_DEVICE = $Device
    }

    & $venvPython -c "from voxcpm import VoxCPM; VoxCPM.from_pretrained('openbmb/VoxCPM2', device='$env:VOXCPM_DEVICE', optimize=($env:VOXCPM_OPTIMIZE -ne '0')); print('VoxCPM model check completed')"
    Write-Host "VoxCPM local setup completed: $installPath"
    Write-Host "Install log: $logPath"
}
finally {
    Stop-Transcript | Out-Null
}
```

This script is intentionally separate from root `requirements.txt`. It may take a long time and download several GB of data.

- [ ] **Step 2: Add installer checkbox**

Modify `build/build_installer.ps1` so the generated WinForms installer includes:

```text
Install local VoxCPM pronunciation engine
```

Rules:

- Checkbox is off by default.
- The checkbox description says it downloads several GB and works best with NVIDIA GPU 8 GB+ VRAM.
- After app files are installed, the installer launches PowerShell for `tools\voxcpm_service\install_local.ps1` or a copied equivalent from the payload.
- The local setup failure must show the setup log path and must not roll back the app installation.

- [ ] **Step 3: Add settings repair path**

If the next implementation also touches settings UI, add a button near the VoxCPM endpoint controls:

```text
Install / repair local VoxCPM engine
```

It should launch the same `install_local.ps1` script. If this is too much for the first implementation slice, document it as the next slice and keep the installer checkbox as "launch setup after install".

- [ ] **Step 4: Validate installer behavior**

Run:

```powershell
.\build\build_installer.ps1
```

Manual checks:

- Installer shows the optional VoxCPM checkbox unchecked by default.
- Installing without VoxCPM still works as before.
- Selecting VoxCPM starts the local setup flow after app file installation.
- Cancelling or failing the VoxCPM setup does not remove the installed app.
- The generated installer payload does not include model checkpoints or `.venv`.

- [ ] **Step 5: Commit**

```powershell
git add tools/voxcpm_service/install_local.ps1 build/build_installer.ps1 docs/specs/packaging-runtime.md
git commit -m "feat: add optional local voxcpm installer setup"
```

---

### Task 7: Update Docs And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `docs/specs/packaging-runtime.md`
- Modify: `memory/03-handoff.md`

- [ ] **Step 1: Update stable docs**

Document these facts:

- `settings.json` now includes `tts_provider`, `voxcpm_endpoint`, and `voxcpm_timeout_seconds`.
- Default provider is `system_qt`.
- `voxcpm_endpoint` is restricted to local HTTP endpoints in the first implementation.
- VoxCPM service dependencies are not root app dependencies and are not packaged into the installer.
- Installer VoxCPM setup is optional, off by default, local-only, and non-fatal when it fails.
- VoxCPM works best with NVIDIA GPU acceleration; CPU is supported but slow.
- Real TTS validation requires Windows runtime checks and a running local service.

- [ ] **Step 2: Run full unit tests**

Run:

```powershell
py -3.11 -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Run source app smoke test**

Run:

```powershell
py -3.11 main.py
```

Check on Windows:

- Settings window opens.
- TTS provider selector is visible.
- System Qt provider still speaks when available.
- VoxCPM provider reports failure cleanly when service is not running.
- With service running, pronunciation plays generated audio and records `last_pronounced_at`.

- [ ] **Step 4: Run packaging check**

Run:

```powershell
.\build\build_exe.ps1
```

Expected:

- Build succeeds.
- Portable payload includes app code and `data/wordbooks/`.
- Portable payload does not include `tools/voxcpm_service/`, VoxCPM model files, `.venv-voxcpm`, or `storage/`.

- [ ] **Step 5: Commit docs and final verification record**

```powershell
git add README.md docs/specs/settings-and-storage.md docs/specs/tray-hotkeys-tts.md docs/specs/packaging-runtime.md memory/03-handoff.md
git commit -m "docs: document voxcpm tts provider contract"
```

## Open Implementation Choices For The Next Session

- Keep automatic fallback disabled in the first implementation. If VoxCPM is selected and unavailable, return failure and show/log the error.
- Keep the VoxCPM endpoint local-only. Remote endpoints require an explicit privacy and credential design.
- Do not cache every generated audio file. Use a single overwritten runtime WAV file first to avoid unbounded `storage/` growth.
- Use NanoVLLM-VoxCPM only when the target machine has Linux plus NVIDIA CUDA. For a Windows desktop user without that runtime, the standard VoxCPM Python API service is the more realistic first local service.
- Do not expose direct in-process VoxCPM in settings until the local companion process path is implemented and verified. Direct Python API can be kept as developer-only experimentation.

## Final Verification Checklist

- [ ] `py -3.11 -m pytest tests -q` passes.
- [ ] `py -3.11 main.py` opens the app and settings UI.
- [ ] Qt provider still speaks on a machine with a working system voice.
- [ ] VoxCPM provider handles service-down failure without recording pronunciation.
- [ ] VoxCPM provider plays WAV audio when `tools/voxcpm_service` is running.
- [ ] `.\build\build_exe.ps1` succeeds.
- [ ] Build payload excludes VoxCPM dependencies, model files, `.venv-voxcpm`, and `storage/`.
