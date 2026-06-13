# VoxCPM In-App Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-app VoxCPM installation, service lifecycle controls, opt-in use-time auto-start, and a categorized settings dialog.

**Architecture:** Keep VoxCPM optional and outside the core TTS HTTP provider. Add a focused service manager module, persist user-controlled paths and switches in settings, and let the controller bridge UI actions to the manager.

**Tech Stack:** Python 3.11, PySide6, unittest/pytest, PowerShell setup scripts, local HTTP health checks.

---

### Task 1: Settings Schema

**Files:**
- Modify: `app/models.py`
- Modify: `app/settings.py`
- Test: `tests/test_settings.py`

- [ ] Add defaults for VoxCPM install root/model root and booleans.
- [ ] Add `voxcpm_install_root`, `voxcpm_model_cache_root`, `voxcpm_use_model_mirror`, and `voxcpm_auto_start` to `AppSettings`.
- [ ] Normalize and persist these fields in `settings.py`.
- [ ] Test defaults, invalid path fallback, and persistence.

### Task 2: VoxCPM Service Manager

**Files:**
- Create: `app/voxcpm_service.py`
- Test: `tests/test_voxcpm_service_manager.py`

- [ ] Add a lightweight status dataclass with installed/running/installing/error/log path fields.
- [ ] Add a manager that checks installation markers, starts `start_service.ps1`, stops only the tracked process, polls `/health`, and launches `install_local.ps1` in a background `QProcess`.
- [ ] Keep command building testable without running real downloads.
- [ ] Test install command arguments, installed detection, start/stop behavior, and health result mapping.

### Task 3: Controller Integration

**Files:**
- Modify: `app/controller.py`
- Test: `tests/test_controller.py`

- [ ] Construct a VoxCPM manager after settings load.
- [ ] Reconfigure manager when settings paths or endpoint change.
- [ ] Connect settings-window install/start/stop/check/open-log signals to controller methods.
- [ ] On pronunciation with VoxCPM selected and auto-start enabled, start the installed service when the current TTS service is not ready.
- [ ] Do not auto-install or silently download a model from pronunciation.

### Task 4: Categorized Settings UI

**Files:**
- Modify: `app/settings_window.py`
- Test: `tests/test_settings_window.py`

- [ ] Replace the single long `QFormLayout` with tabs: learning, display, pronunciation, hotkeys, wordbooks.
- [ ] Add VoxCPM path controls, mirror/auto-start switches, status labels, and action buttons to the pronunciation tab.
- [ ] Expose signals for install, start, stop, check, browse install root, browse model root, and open log.
- [ ] Keep existing setting round-trip behavior intact.

### Task 5: Packaging and Docs

**Files:**
- Modify: `build/build_installer.ps1`
- Modify: `docs/specs/packaging-runtime.md`
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `README.md`
- Test: `tests/test_voxcpm_service_files.py`

- [ ] Ensure installed payload contains `tools/voxcpm_service` scripts needed by the settings UI.
- [ ] Keep `.venv`, models, and large runtime caches excluded from the installer.
- [ ] Document the in-app install path, model path selection, use-time auto-start, and manual stop behavior.

### Task 6: Verification

**Files:**
- No direct code changes.

- [ ] Run targeted tests for each slice after implementation.
- [ ] Run `py -3.11 -m pytest tests -q`.
- [ ] Run installer build with the repository's Windows build command.
- [ ] Start the app or built executable on Windows and inspect the settings UI.
- [ ] If feasible, use the already installed local VoxCPM service to verify health and one synthesize request.
