# VoxCPM2 ModelScope Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users download and import a split VoxCPM2 runtime package and model package directly from ModelScope, while keeping manual local import as a fallback.

**Architecture:** Extend the runtime package contract to support split runtime/model artifacts, add download/import helpers to the existing runtime/service manager layer, then expose direct-download and manual-model-import actions in the settings UI/controller.

**Tech Stack:** Python 3.11, PySide6, `urllib.request`, `zipfile`, `hashlib`, `pathlib`, unittest/pytest

---

## File Map

- Modify: `app/voxcpm_runtime.py`
- Modify: `app/voxcpm_service.py`
- Modify: `app/settings_window.py`
- Modify: `app/controller.py`
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `docs/specs/packaging-runtime.md`
- Modify: `README.md`
- Test: `tests/test_voxcpm_runtime.py`
- Test: `tests/test_voxcpm_service_manager.py`
- Test: `tests/test_settings_window.py`
- Test: `tests/test_controller.py`

### Task 1: Add split-package runtime/model contracts

**Files:**
- Modify: `app/voxcpm_runtime.py`
- Test: `tests/test_voxcpm_runtime.py`

- [ ] Add failing tests for runtime manifests that reference a model package, model-manifest parsing, runtime zip validation without embedded model files, and model zip validation under `models/VoxCPM2-local/`.
- [ ] Run the focused runtime tests and confirm the new assertions fail for the expected contract mismatch.
- [ ] Extend the runtime helpers with model-manifest dataclasses/loaders and split-package validation helpers.
- [ ] Re-run the focused runtime tests and confirm they pass.

### Task 2: Add runtime/model import and ModelScope download helpers

**Files:**
- Modify: `app/voxcpm_service.py`
- Test: `tests/test_voxcpm_service_manager.py`

- [ ] Add failing tests for model package import, sequential runtime+model download/import, SHA256 verification, and driver-version rejection before download starts.
- [ ] Run the focused service manager tests and confirm they fail for the expected missing methods/fields.
- [ ] Add manager methods for `import_model_package(...)`, `download_and_import_runtime_bundle(...)`, and internal file-download/checksum helpers using ModelScope URLs.
- [ ] Re-run the focused service manager tests and confirm they pass.

### Task 3: Expose direct-download and manual model import in the UI/controller

**Files:**
- Modify: `app/settings_window.py`
- Modify: `app/controller.py`
- Test: `tests/test_settings_window.py`
- Test: `tests/test_controller.py`

- [ ] Add failing tests for the new buttons/signals and the controller actions that call into the manager.
- [ ] Run the focused UI/controller tests and confirm they fail because the new actions do not exist yet.
- [ ] Add `下载并导入运行时包`、`下载并导入模型包`、`导入模型包` actions, editable ModelScope path fields, and controller wiring/tray feedback.
- [ ] Re-run the focused UI/controller tests and confirm they pass.

### Task 4: Update docs and run verification

**Files:**
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `docs/specs/packaging-runtime.md`
- Modify: `README.md`

- [ ] Update stable docs to reflect ModelScope primary download, split runtime/model packages, and manual fallback flow.
- [ ] Run the focused runtime/service/UI/controller tests.
- [ ] Run the full suite.
