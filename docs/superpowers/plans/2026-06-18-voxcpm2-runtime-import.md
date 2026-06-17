# VoxCPM2 Runtime Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a validated VoxCPM2 runtime zip import flow for supported Windows + NVIDIA environments while preserving the existing local `voxcpm_local` HTTP service architecture.

**Architecture:** Add a focused runtime-package module for manifest parsing, environment checks, staging extraction, hash validation, and activation/rollback. Extend the existing `VoxCpmServiceManager`, settings UI, and controller to expose runtime import, runtime metadata/status, and compatibility messaging without changing the existing pronunciation HTTP protocol.

**Tech Stack:** Python 3.11, PySide6, zipfile/hashlib/shutil/pathlib, unittest/pytest

---

## File Map

- Create: `app/voxcpm_runtime.py`
- Modify: `app/voxcpm_service.py`
- Modify: `app/settings_window.py`
- Modify: `app/controller.py`
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Test: `tests/test_voxcpm_runtime.py`
- Test: `tests/test_voxcpm_service_manager.py`
- Test: `tests/test_settings_window.py`
- Test: `tests/test_controller.py`

### Task 1: Add pure runtime-package parsing and validation helpers

**Files:**
- Create: `app/voxcpm_runtime.py`
- Test: `tests/test_voxcpm_runtime.py`

- [ ] **Step 1: Write the failing tests for manifest parsing, layout checks, and version comparison**

Add tests that cover:

```python
def test_reads_runtime_manifest_and_required_fields(): ...
def test_rejects_zip_without_runtime_directory(): ...
def test_rejects_hash_mismatch(): ...
def test_driver_version_comparison_handles_multi_part_versions(): ...
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `py -3.11 -m pytest tests/test_voxcpm_runtime.py -q`
Expected: failures because `app.voxcpm_runtime` does not exist yet.

- [ ] **Step 3: Implement the minimal runtime helpers**

Add:

```python
@dataclass(frozen=True, slots=True)
class VoxCpmRuntimeManifest: ...

@dataclass(frozen=True, slots=True)
class VoxCpmRuntimeValidationResult: ...

def load_runtime_manifest_from_zip(zip_path: Path) -> VoxCpmRuntimeManifest: ...
def compare_version_parts(left: str, right: str) -> int: ...
def validate_runtime_zip_layout(zip_path: Path, manifest: VoxCpmRuntimeManifest) -> VoxCpmRuntimeValidationResult: ...
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `py -3.11 -m pytest tests/test_voxcpm_runtime.py -q`
Expected: pass.

### Task 2: Add staging import, activation, and rollback behavior to the service manager

**Files:**
- Modify: `app/voxcpm_service.py`
- Test: `tests/test_voxcpm_service_manager.py`

- [ ] **Step 1: Write the failing tests for runtime import and legacy detection**

Add tests that cover:

```python
def test_detects_runtime_installation_from_imported_runtime_manifest(): ...
def test_reports_legacy_install_when_manifest_is_missing(): ...
def test_import_runtime_package_extracts_to_staging_and_promotes_runtime(): ...
def test_import_runtime_package_restores_backup_when_activation_fails(): ...
```

- [ ] **Step 2: Run the focused manager tests to verify they fail**

Run: `py -3.11 -m pytest tests/test_voxcpm_service_manager.py -q`
Expected: failures because import/status helpers do not exist yet.

- [ ] **Step 3: Implement runtime-aware manager behavior**

Extend:

```python
@dataclass(slots=True, frozen=True)
class VoxCpmServiceStatus:
    installed: bool
    running: bool
    installing: bool
    message: str
    log_path: Path
    runtime_state: str = "missing"
    runtime_id: str = ""
    cuda_tag: str = ""
    min_driver_version: str = ""
    model_version: str = ""
```

Add manager methods:

```python
def import_runtime_package(self, package_path: Path) -> bool: ...
def runtime_manifest_path(self) -> Path: ...
def _detect_runtime_metadata(self) -> ...: ...
def _activate_imported_runtime(self, staging_root: Path, manifest: ...) -> None: ...
```

- [ ] **Step 4: Run the focused manager tests to verify they pass**

Run: `py -3.11 -m pytest tests/test_voxcpm_service_manager.py -q`
Expected: pass.

### Task 3: Expose runtime import and richer runtime status in the settings UI/controller

**Files:**
- Modify: `app/settings_window.py`
- Modify: `app/controller.py`
- Test: `tests/test_settings_window.py`
- Test: `tests/test_controller.py`

- [ ] **Step 1: Write the failing UI/controller tests**

Add tests that cover:

```python
def test_voxcpm_action_buttons_emit_runtime_import_signal(): ...
def test_set_voxcpm_status_shows_runtime_metadata(): ...
def test_import_runtime_package_uses_file_dialog_and_manager(): ...
```

- [ ] **Step 2: Run the focused UI/controller tests to verify they fail**

Run: `py -3.11 -m pytest tests/test_settings_window.py tests/test_controller.py -q`
Expected: failures because the new signal/button/controller action do not exist yet.

- [ ] **Step 3: Implement the UI/controller changes**

Add:

```python
class SettingsDialog(QDialog):
    voxcpm_runtime_import_requested = Signal()
```

Update the pronunciation tab with:

```python
self._voxcpm_runtime_button = QPushButton("导入运行时包", self)
self._voxcpm_runtime_meta = QLabel("", self)
```

Add controller flow:

```python
def import_voxcpm_runtime_package(self) -> None:
    package_path, _ = QFileDialog.getOpenFileName(...)
    ...
    imported = self.voxcpm_service.import_runtime_package(Path(package_path))
```

- [ ] **Step 4: Run the focused UI/controller tests to verify they pass**

Run: `py -3.11 -m pytest tests/test_settings_window.py tests/test_controller.py -q`
Expected: pass.

### Task 4: Align stable specs and run full verification

**Files:**
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`

- [ ] **Step 1: Update the settings/runtime stable docs**

Document:

```text
- 运行时导入按钮与状态字段
- 旧脚本安装路径降级为次要/兼容路径
- runtime zip 仍落位到 <应用目录>\tts\voxcpm
```

- [ ] **Step 2: Run the new focused tests**

Run: `py -3.11 -m pytest tests/test_voxcpm_runtime.py tests/test_voxcpm_service_manager.py tests/test_settings_window.py tests/test_controller.py -q`
Expected: pass.

- [ ] **Step 3: Run the full suite**

Run: `py -3.11 -m pytest tests -q`
Expected: pass.

- [ ] **Step 4: Rebuild the installer and do Windows runtime checks**

Run:

```powershell
.\build\build_installer.ps1
```

Runtime checks:

```text
- short-start dist\oh-my-word-py\oh-my-word-py.exe
- verify settings page shows runtime import button
- verify built payload still excludes storage and only contains intended tools payload
```

## Self-Review

- Spec coverage: package layout, manifest contract, import flow, runtime metadata UI, rollback, and compatibility messaging are all covered by Tasks 1-4.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: plan uses `runtime_id`, `cuda_tag`, `min_driver_version`, `model_version`, and `voxcpm_runtime_import_requested` consistently across tasks.
