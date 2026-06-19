from __future__ import annotations

import json
import unittest
import zipfile
import hashlib
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from app.voxcpm_service import EndpointProcess, VoxCpmServiceManager


class _FakeProcess:
    def __init__(self, return_code: int | None = None) -> None:
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True
        self.return_code = 0

    def wait(self, timeout: float | None = None) -> int:
        return self.return_code if self.return_code is not None else 0

    def kill(self) -> None:
        self.killed = True
        self.return_code = -9


class _FakeResponse:
    def __init__(self, payload: bytes | dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _runtime_package_python_path(*, legacy_layout: bool = False) -> str:
    if legacy_layout:
        return "runtime/.venv/Scripts/python.exe"
    return "runtime/python/python.exe"


def _runtime_install_python_path(runtime_root: Path, *, legacy_layout: bool = False) -> Path:
    if legacy_layout:
        return runtime_root / ".venv" / "Scripts" / "python.exe"
    return runtime_root / "python" / "python.exe"


def _write_installed_runtime(install_root: Path, *, legacy_layout: bool = False) -> Path:
    python_path = _runtime_install_python_path(install_root, legacy_layout=legacy_layout)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (install_root / "start_service.ps1").write_text("", encoding="utf-8")
    return python_path


def _write_runtime_package(zip_path: Path, *, legacy_layout: bool = False) -> None:
    python_payload = b"python-runtime"
    start_payload = b"start-service"
    health_payload = b"health-check"
    service_payload = b"service-code"
    runtime_python_path = _runtime_package_python_path(legacy_layout=legacy_layout)
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "runtime_id": "voxcpm2-runtime-win-x64-cu124-r1",
                    "runtime_version": "r1",
                    "target_os": "windows",
                    "target_arch": "x64",
                    "cuda_tag": "cu124",
                    "min_driver_version": "551.00",
                    "python_version": "3.11.9",
                    "torch_version": "2.6.0",
                    "model_id": "openbmb/VoxCPM2",
                    "model_version": "2026-06-18",
                    "model_package_id": "voxcpm2-model-cu130-r1",
                    "model_package_filename": "voxcpm2-model-cu130-r1.zip",
                    "expected_layout_version": 1,
                    "package_size": 1024,
                    "file_hashes": {
                        runtime_python_path: _sha256_bytes(python_payload),
                        "runtime/start_service.ps1": _sha256_bytes(start_payload),
                        "runtime/healthcheck.ps1": _sha256_bytes(health_payload),
                        "runtime/service/server.py": _sha256_bytes(service_payload),
                    },
                    "built_at": "2026-06-18T12:00:00Z",
                }
            ),
        )
        archive.writestr(runtime_python_path, python_payload)
        if not legacy_layout:
            archive.writestr("runtime/.venv/Scripts/python.exe", python_payload)
        archive.writestr("runtime/start_service.ps1", start_payload)
        archive.writestr("runtime/healthcheck.ps1", health_payload)
        archive.writestr("runtime/service/server.py", service_payload)


def _write_model_package(zip_path: Path) -> None:
    model_payload = b"model-payload"
    config_payload = b"{}"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "model_manifest.json",
            json.dumps(
                {
                    "model_id": "openbmb/VoxCPM2",
                    "model_version": "2026-06-18",
                    "model_package_filename": "voxcpm2-model-cu130-r1.zip",
                    "expected_model_dir": "VoxCPM2-local",
                    "package_size": 2048,
                    "file_hashes": {
                        "models/VoxCPM2-local/model.safetensors": _sha256_bytes(model_payload),
                        "models/VoxCPM2-local/config.json": _sha256_bytes(config_payload),
                    },
                    "built_at": "2026-06-18T12:00:00Z",
                }
            ),
        )
        archive.writestr("models/VoxCPM2-local/model.safetensors", model_payload)
        archive.writestr("models/VoxCPM2-local/config.json", config_payload)


class VoxCpmServiceManagerTests(unittest.TestCase):
    def test_detects_runtime_installation_from_imported_runtime_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            install_root = Path(tmp_dir) / "voxcpm"
            _write_installed_runtime(install_root)
            (install_root / "runtime_manifest.json").write_text(
                json.dumps(
                    {
                        "runtime_id": "voxcpm2-runtime-win-x64-cu124-r1",
                        "runtime_version": "r1",
                        "target_os": "windows",
                        "target_arch": "x64",
                        "cuda_tag": "cu124",
                        "min_driver_version": "551.00",
                        "python_version": "3.11.9",
                        "torch_version": "2.6.0",
                        "model_id": "openbmb/VoxCPM2",
                        "model_version": "2026-06-18",
                        "model_package_id": "voxcpm2-model-cu130-r2",
                        "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                        "expected_layout_version": 1,
                        "package_size": 1024,
                        "file_hashes": {},
                        "built_at": "2026-06-18T12:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=Path(tmp_dir) / "scripts",
            )

            status = manager.status()

        self.assertTrue(status.installed)
        self.assertEqual(status.runtime_state, "imported")
        self.assertEqual(status.runtime_id, "voxcpm2-runtime-win-x64-cu124-r1")
        self.assertEqual(status.cuda_tag, "cu124")

    def test_detects_installation_from_python_and_start_script(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            install_root = Path(tmp_dir) / "voxcpm"
            _write_installed_runtime(install_root)

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=Path(tmp_dir) / "scripts",
            )

            self.assertTrue(manager.is_installed())
            self.assertTrue(manager.status().installed)

    def test_reports_legacy_install_when_manifest_is_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            install_root = Path(tmp_dir) / "voxcpm"
            _write_installed_runtime(install_root, legacy_layout=True)

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=Path(tmp_dir) / "scripts",
            )

            status = manager.status()

        self.assertTrue(status.installed)
        self.assertEqual(status.runtime_state, "legacy")


    def test_start_refuses_when_service_is_not_installed(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manager = VoxCpmServiceManager(
                install_root=Path(tmp_dir) / "missing",
                model_cache_root=Path(tmp_dir) / "models",
                script_root=Path(tmp_dir) / "scripts",
                urlopen_func=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("down")),
            )

            self.assertFalse(manager.start_service())
            self.assertIn("尚未安装", manager.status().message)

    def test_start_tracks_process_and_stop_only_stops_tracked_process(self) -> None:
        process = _FakeProcess()

        def fake_process_factory(*_: Any, **__: Any) -> _FakeProcess:
            return process

        with TemporaryDirectory() as tmp_dir:
            install_root = Path(tmp_dir) / "voxcpm"
            _write_installed_runtime(install_root)
            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=Path(tmp_dir) / "scripts",
                process_factory=fake_process_factory,
                urlopen_func=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("down")),
            )

            self.assertTrue(manager.start_service())
            self.assertTrue(manager.status().running)
            self.assertTrue(manager.stop_service())

            self.assertTrue(process.terminated)
            self.assertFalse(manager.status().running)

    def test_start_service_does_not_probe_health_before_spawning(self) -> None:
        process = _FakeProcess()
        calls = {"urlopen": 0}

        def fake_process_factory(*_: Any, **__: Any) -> _FakeProcess:
            return process

        def fake_urlopen(*_args: Any, **_kwargs: Any) -> _FakeResponse:
            calls["urlopen"] += 1
            return _FakeResponse({"status": "ok"})

        with TemporaryDirectory() as tmp_dir:
            install_root = Path(tmp_dir) / "voxcpm"
            _write_installed_runtime(install_root)
            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=Path(tmp_dir) / "scripts",
                process_factory=fake_process_factory,
                urlopen_func=fake_urlopen,
            )

            self.assertTrue(manager.start_service())

        self.assertEqual(calls["urlopen"], 0)

    def test_stop_service_stops_matching_endpoint_process_started_by_previous_app_session(self) -> None:
        killed: list[int] = []

        with TemporaryDirectory() as tmp_dir:
            manager = VoxCpmServiceManager(
                install_root=Path(tmp_dir) / "voxcpm",
                model_cache_root=Path(tmp_dir) / "models",
                script_root=Path(tmp_dir) / "scripts",
                endpoint="http://127.0.0.1:8808",
                endpoint_process_finder=lambda _port: [
                    EndpointProcess(
                        pid=1234,
                        command_line="python.exe -m uvicorn service.server:app --host 127.0.0.1 --port 8808",
                    )
                ],
                process_terminator=lambda pid: killed.append(pid),
            )

            self.assertTrue(manager.stop_service())

            self.assertEqual(killed, [1234])
            self.assertFalse(manager.status().running)
            self.assertIn("已停止", manager.status().message)

    def test_stop_service_does_not_kill_unrelated_process_on_same_port(self) -> None:
        killed: list[int] = []

        with TemporaryDirectory() as tmp_dir:
            manager = VoxCpmServiceManager(
                install_root=Path(tmp_dir) / "voxcpm",
                model_cache_root=Path(tmp_dir) / "models",
                script_root=Path(tmp_dir) / "scripts",
                endpoint="http://127.0.0.1:8808",
                endpoint_process_finder=lambda _port: [
                    EndpointProcess(pid=5678, command_line="python.exe -m http.server 8808")
                ],
                process_terminator=lambda pid: killed.append(pid),
            )

            self.assertFalse(manager.stop_service())

            self.assertEqual(killed, [])

    def test_parses_netstat_fallback_when_get_net_tcp_connection_returns_no_processes(self) -> None:
        commands: list[list[str]] = []

        def fake_run(args: list[str], **_: Any) -> Any:
            commands.append(args)
            if "Get-NetTCPConnection" in args[-1]:
                return type("Result", (), {"stdout": ""})()
            if "netstat" in args[-1]:
                return type(
                    "Result",
                    (),
                    {"stdout": "  TCP    127.0.0.1:8808         0.0.0.0:0              LISTENING       75372\n"},
                )()
            return type(
                "Result",
                (),
                {"stdout": "75372\tpython.exe -m uvicorn service.server:app --host 127.0.0.1 --port 8808\n"},
            )()

        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.voxcpm_service.subprocess.run", side_effect=fake_run),
        ):
            manager = VoxCpmServiceManager(
                install_root=Path(tmp_dir) / "voxcpm",
                model_cache_root=Path(tmp_dir) / "models",
                script_root=Path(tmp_dir) / "scripts",
            )

            processes = manager._find_endpoint_processes(8808)

        self.assertEqual(processes, [EndpointProcess(75372, "python.exe -m uvicorn service.server:app --host 127.0.0.1 --port 8808")])
        self.assertEqual(len(commands), 3)

    def test_health_check_reads_local_endpoint_status(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manager = VoxCpmServiceManager(
                install_root=Path(tmp_dir) / "voxcpm",
                model_cache_root=Path(tmp_dir) / "models",
                script_root=Path(tmp_dir) / "scripts",
                endpoint="http://127.0.0.1:8808",
                urlopen_func=lambda *_args, **_kwargs: _FakeResponse({"status": "ok"}),
            )

            self.assertTrue(manager.health_check())
            self.assertTrue(manager.status().running)

    def test_import_runtime_package_extracts_to_staging_and_promotes_runtime(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = root / "runtime.zip"
            _write_runtime_package(zip_path)
            install_root = root / "voxcpm"

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=root / "scripts",
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "552.12",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (True, "ok"),
            )

            self.assertTrue(manager.import_runtime_package(zip_path))

            status = manager.status()
            self.assertTrue(status.installed)
            self.assertEqual(status.runtime_state, "imported")
            self.assertEqual(status.runtime_id, "voxcpm2-runtime-win-x64-cu124-r1")
            self.assertTrue(_runtime_install_python_path(install_root).exists())
            self.assertTrue((install_root / "runtime_manifest.json").exists())

    def test_import_runtime_package_accepts_legacy_runtime_bundle(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = root / "runtime.zip"
            _write_runtime_package(zip_path, legacy_layout=True)
            install_root = root / "voxcpm"

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=root / "scripts",
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "552.12",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (True, "ok"),
            )

            self.assertTrue(manager.import_runtime_package(zip_path))
            self.assertTrue(_runtime_install_python_path(install_root, legacy_layout=True).exists())
            self.assertEqual(manager.status().runtime_state, "imported")

    def test_import_runtime_package_rewrites_runtime_scripts_for_current_paths(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = root / "runtime.zip"
            _write_runtime_package(zip_path)
            install_root = root / "voxcpm"
            model_cache_root = root / "custom-model-cache"

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=model_cache_root,
                script_root=root / "scripts",
                endpoint="http://localhost:8899",
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "552.12",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (True, "ok"),
            )

            self.assertTrue(manager.import_runtime_package(zip_path))

            start_script = (install_root / "start_service.ps1").read_text(encoding="utf-8")
            healthcheck_script = (install_root / "healthcheck.ps1").read_text(encoding="utf-8")
            self.assertIn("Split-Path -Parent $PSCommandPath", start_script)
            self.assertIn(str(model_cache_root), start_script)
            self.assertIn(str(model_cache_root / "VoxCPM2-local"), start_script)
            self.assertIn('--host "localhost" --port 8899', start_script)
            self.assertIn("http://localhost:8899/health", healthcheck_script)
            self.assertNotEqual(start_script.strip(), "start-service")
            self.assertNotEqual(healthcheck_script.strip(), "health-check")

    def test_import_runtime_package_falls_back_to_shutil_move_when_runtime_rename_is_denied(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = root / "runtime.zip"
            _write_runtime_package(zip_path)
            install_root = root / "voxcpm"
            staging_runtime_root = root / "voxcpm.import-staging" / "runtime"
            original_rename = Path.rename

            def flaky_rename(path_self: Path, target: Path) -> Path:
                if Path(path_self) == staging_runtime_root and Path(target) == install_root:
                    raise PermissionError(13, "拒绝访问。")
                return original_rename(path_self, target)

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=root / "scripts",
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "552.12",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (True, "ok"),
            )

            with patch("pathlib.Path.rename", new=flaky_rename):
                self.assertTrue(manager.import_runtime_package(zip_path))

            self.assertTrue(_runtime_install_python_path(install_root).exists())
            self.assertFalse(staging_runtime_root.exists())
            self.assertEqual(manager.status().runtime_state, "imported")

    def test_import_runtime_package_async_marks_manager_busy_and_spawns_thread(self) -> None:
        calls: dict[str, Any] = {}

        class FakeThread:
            def __init__(self, *, target: Any, args: tuple[Any, ...], daemon: bool) -> None:
                calls["target"] = target
                calls["args"] = args
                calls["daemon"] = daemon

            def start(self) -> None:
                calls["started"] = True

        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.voxcpm_service.threading.Thread", FakeThread),
        ):
            root = Path(tmp_dir)
            zip_path = root / "runtime.zip"
            _write_runtime_package(zip_path)
            manager = VoxCpmServiceManager(
                install_root=root / "voxcpm",
                model_cache_root=root / "voxcpm" / "models",
                script_root=root / "scripts",
            )

            self.assertTrue(manager.import_runtime_package_async(zip_path))

            status = manager.status()
            self.assertTrue(status.busy)
            self.assertIn("正在导入 VoxCPM 运行时包", status.message)
            self.assertTrue(calls["started"])
            self.assertEqual(calls["args"], (zip_path,))
            self.assertTrue(calls["daemon"])

    def test_runtime_healthcheck_imports_service_module_with_runtime_python(self) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def fake_run(args: list[str], **kwargs: Any) -> Any:
            calls.append((args, kwargs))
            return type("Result", (), {"returncode": 0, "stdout": "runtime import ok"})()

        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.voxcpm_service.subprocess.run", side_effect=fake_run),
        ):
            root = Path(tmp_dir)
            runtime_root = root / "runtime"
            python_path = _runtime_install_python_path(runtime_root)
            service_server_path = runtime_root / "service" / "server.py"
            python_path.parent.mkdir(parents=True, exist_ok=True)
            service_server_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            service_server_path.write_text("", encoding="utf-8")

            manager = VoxCpmServiceManager(
                install_root=root / "voxcpm",
                model_cache_root=root / "voxcpm" / "models",
                script_root=root / "scripts",
            )

            ok, message = manager._run_runtime_healthcheck(runtime_root)

        self.assertTrue(ok)
        self.assertEqual(message, "runtime import ok")
        self.assertEqual(calls[0][0][0], str(python_path))
        self.assertEqual(calls[0][0][1], "-c")
        self.assertIn("import service.server", calls[0][0][2])

    def test_import_model_package_extracts_model_payload(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            install_root = root / "voxcpm"
            model_root = install_root / "models"
            package_path = root / "model.zip"
            _write_model_package(package_path)
            _write_installed_runtime(install_root)

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=model_root,
                script_root=root / "scripts",
            )

            self.assertTrue(manager.import_model_package(package_path))

            self.assertTrue((model_root / "VoxCPM2-local" / "model.safetensors").exists())
            self.assertTrue((model_root / "model_manifest.json").exists())

    def test_import_model_package_falls_back_to_shutil_move_when_model_rename_is_denied(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            install_root = root / "voxcpm"
            model_root = install_root / "models"
            package_path = root / "model.zip"
            _write_model_package(package_path)
            _write_installed_runtime(install_root)
            staging_model_root = root / "models.model-staging" / "models"
            original_rename = Path.rename

            def flaky_rename(path_self: Path, target: Path) -> Path:
                if Path(path_self) == staging_model_root and Path(target) == model_root:
                    raise PermissionError(13, "拒绝访问。")
                return original_rename(path_self, target)

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=model_root,
                script_root=root / "scripts",
            )

            with patch("pathlib.Path.rename", new=flaky_rename):
                self.assertTrue(manager.import_model_package(package_path))

            self.assertTrue((model_root / "VoxCPM2-local" / "model.safetensors").exists())
            self.assertFalse(staging_model_root.exists())

    def test_download_and_import_runtime_bundle_rejects_old_driver_before_download(self) -> None:
        calls = {"urlopen": 0}

        def fake_urlopen(*_args: Any, **_kwargs: Any) -> _FakeResponse:
            calls["urlopen"] += 1
            return _FakeResponse(b"")

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manager = VoxCpmServiceManager(
                install_root=root / "voxcpm",
                model_cache_root=root / "voxcpm" / "models",
                script_root=root / "scripts",
                urlopen_func=fake_urlopen,
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "551.00",
                    "free_bytes": 10_000_000,
                },
            )

            self.assertFalse(
                manager._download_and_import_runtime_bundle_blocking(
                    namespace="demo",
                    repo_name="repo",
                    runtime_filename="voxcpm2-runtime-win-x64-cu130-r1.zip",
                    min_driver_version="580",
                )
            )

            self.assertEqual(calls["urlopen"], 0)
            self.assertIn("580", manager.status().message)

    def test_download_and_import_runtime_bundle_downloads_runtime_and_model_packages(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime_zip = root / "runtime.zip"
            model_zip = root / "model.zip"
            _write_runtime_package(runtime_zip)
            _write_model_package(model_zip)
            runtime_bytes = runtime_zip.read_bytes()
            model_bytes = model_zip.read_bytes()
            runtime_sha = f"{_sha256_bytes(runtime_bytes)}  voxcpm2-runtime-win-x64-cu130-r1.zip".encode("utf-8")
            model_sha = f"{_sha256_bytes(model_bytes)}  voxcpm2-model-cu130-r1.zip".encode("utf-8")

            def fake_urlopen(request: Any, **_kwargs: Any) -> _FakeResponse:
                url = request.full_url if hasattr(request, "full_url") else str(request)
                if "voxcpm2-runtime-win-x64-cu130-r1.zip.sha256" in url:
                    return _FakeResponse(runtime_sha)
                if "voxcpm2-runtime-win-x64-cu130-r1.zip" in url:
                    return _FakeResponse(runtime_bytes)
                if "voxcpm2-model-cu130-r1.zip.sha256" in url:
                    return _FakeResponse(model_sha)
                if "voxcpm2-model-cu130-r1.zip" in url:
                    return _FakeResponse(model_bytes)
                raise AssertionError(url)

            manager = VoxCpmServiceManager(
                install_root=root / "voxcpm",
                model_cache_root=root / "voxcpm" / "models",
                script_root=root / "scripts",
                urlopen_func=fake_urlopen,
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "580.88",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (True, "ok"),
            )

            self.assertTrue(
                manager._download_and_import_runtime_bundle_blocking(
                    namespace="demo",
                    repo_name="repo",
                    runtime_filename="voxcpm2-runtime-win-x64-cu130-r1.zip",
                    min_driver_version="580",
                )
            )

            self.assertTrue((root / "voxcpm" / ".venv" / "Scripts" / "python.exe").exists())
            self.assertTrue((root / "voxcpm" / "models" / "VoxCPM2-local" / "model.safetensors").exists())
            self.assertIn("已下载并导入", manager.status().message)

    def test_download_and_import_model_package_uses_imported_runtime_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime_zip = root / "runtime.zip"
            model_zip = root / "model.zip"
            _write_runtime_package(runtime_zip)
            _write_model_package(model_zip)
            runtime_bytes = runtime_zip.read_bytes()
            model_bytes = model_zip.read_bytes()
            runtime_sha = f"{_sha256_bytes(runtime_bytes)}  voxcpm2-runtime-win-x64-cu130-r1.zip".encode("utf-8")
            model_sha = f"{_sha256_bytes(model_bytes)}  voxcpm2-model-cu130-r1.zip".encode("utf-8")

            def fake_urlopen(request: Any, **_kwargs: Any) -> _FakeResponse:
                url = request.full_url if hasattr(request, "full_url") else str(request)
                if "voxcpm2-runtime-win-x64-cu130-r1.zip.sha256" in url:
                    return _FakeResponse(runtime_sha)
                if "voxcpm2-runtime-win-x64-cu130-r1.zip" in url:
                    return _FakeResponse(runtime_bytes)
                if "voxcpm2-model-cu130-r1.zip.sha256" in url:
                    return _FakeResponse(model_sha)
                if "voxcpm2-model-cu130-r1.zip" in url:
                    return _FakeResponse(model_bytes)
                raise AssertionError(url)

            manager = VoxCpmServiceManager(
                install_root=root / "voxcpm",
                model_cache_root=root / "voxcpm" / "models",
                script_root=root / "scripts",
                urlopen_func=fake_urlopen,
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "580.88",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (True, "ok"),
            )

            self.assertTrue(
                manager._download_and_import_runtime_bundle_blocking(
                    namespace="demo",
                    repo_name="repo",
                    runtime_filename="voxcpm2-runtime-win-x64-cu130-r1.zip",
                    min_driver_version="580",
                )
            )
            shutil.rmtree(root / "voxcpm" / "models")

            self.assertTrue(
                manager._download_and_import_model_package_blocking(
                    namespace="demo",
                    repo_name="repo",
                )
            )

            self.assertTrue((root / "voxcpm" / "models" / "VoxCPM2-local" / "model.safetensors").exists())
            self.assertIn("模型包", manager.status().message)

    def test_import_runtime_package_restores_backup_when_activation_fails(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            zip_path = root / "runtime.zip"
            _write_runtime_package(zip_path)
            install_root = root / "voxcpm"
            (install_root / ".venv" / "Scripts").mkdir(parents=True)
            legacy_python = install_root / ".venv" / "Scripts" / "python.exe"
            legacy_python.write_text("legacy", encoding="utf-8")
            (install_root / "start_service.ps1").write_text("legacy-start", encoding="utf-8")

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=root / "scripts",
                environment_probe=lambda: {
                    "target_os": "windows",
                    "target_arch": "x64",
                    "has_nvidia_gpu": True,
                    "driver_version": "552.12",
                    "free_bytes": 10_000_000,
                },
                runtime_healthcheck_runner=lambda _runtime_root: (False, "healthcheck failed"),
            )

            self.assertFalse(manager.import_runtime_package(zip_path))

            status = manager.status()
            self.assertTrue(legacy_python.exists())
            self.assertTrue(status.installed)
            self.assertEqual(status.runtime_state, "legacy")
            self.assertIn("healthcheck failed", status.message)
