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
