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


def test_windows_installer_voxcpm_option_is_optional_and_non_fatal() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "Install local VoxCPM pronunciation engine" in installer_script
    assert "install_local.ps1" in installer_script
    assert "Checked = false" in installer_script
    assert "VoxCPM setup failed" in installer_script
    assert "app installation completed" in installer_script
