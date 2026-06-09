from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVICE_DIR = ROOT / "tools" / "voxcpm_service"


def test_voxcpm_service_files_are_service_only() -> None:
    requirements = (SERVICE_DIR / "requirements.txt").read_text(encoding="utf-8")
    root_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "voxcpm" in requirements
    assert "fastapi" in requirements
    assert "voxcpm" not in root_requirements.lower()
    assert "torch" not in root_requirements.lower()


def test_voxcpm_server_exposes_local_health_and_synthesize_routes() -> None:
    server_source = (SERVICE_DIR / "server.py").read_text(encoding="utf-8")
    readme = (SERVICE_DIR / "README.md").read_text(encoding="utf-8")

    assert '@app.get("/health")' in server_source
    assert '@app.post("/synthesize")' in server_source
    assert "127.0.0.1" in readme
    assert "not a cloud server" in readme


def test_voxcpm_local_installer_script_is_user_scoped_and_resumable() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "$env:LOCALAPPDATA\\OhMyWord\\voxcpm" in script
    assert "Start-Transcript" in script
    assert "requirements.txt" in script
    assert "VoxCPM.from_pretrained" in script
    assert "openbmb/VoxCPM2" in script


def test_voxcpm_local_installer_script_checks_native_exit_codes() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "function Invoke-Native" in script
    assert "$LASTEXITCODE" in script
    assert script.count("Invoke-Native") >= 5
    assert "Command failed" in script


def test_windows_installer_voxcpm_option_is_optional_and_non_fatal() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "Install local VoxCPM pronunciation engine" in installer_script
    assert "install_local.ps1" in installer_script
    assert "Checked = false" in installer_script
    assert "VoxCPM setup failed" in installer_script
    assert "app installation completed" in installer_script


def test_windows_installer_uses_temp_staging_instead_of_tracked_build_dir() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "GetTempPath" in installer_script
    assert '"build\\installer"' not in installer_script


def test_stable_docs_describe_voxcpm_provider_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    settings_spec = (ROOT / "docs" / "specs" / "settings-and-storage.md").read_text(encoding="utf-8")
    tts_spec = (ROOT / "docs" / "specs" / "tray-hotkeys-tts.md").read_text(encoding="utf-8")
    packaging_spec = (ROOT / "docs" / "specs" / "packaging-runtime.md").read_text(encoding="utf-8")

    assert "tts_provider" in settings_spec
    assert "voxcpm_endpoint" in settings_spec
    assert "voxcpm_timeout_seconds" in settings_spec
    assert "system_qt" in tts_spec
    assert "voxcpm_local" in tts_spec
    assert "127.0.0.1" in tts_spec
    assert "VoxCPM 本地" in readme
    assert "默认关闭" in packaging_spec
