from __future__ import annotations

import json
import unittest
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
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class VoxCpmServiceManagerTests(unittest.TestCase):
    def test_detects_installation_from_python_and_start_script(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            install_root = Path(tmp_dir) / "voxcpm"
            (install_root / ".venv" / "Scripts").mkdir(parents=True)
            (install_root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
            (install_root / "start_service.ps1").write_text("", encoding="utf-8")

            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=install_root / "models",
                script_root=Path(tmp_dir) / "scripts",
            )

            self.assertTrue(manager.is_installed())
            self.assertTrue(manager.status().installed)

    def test_background_install_creates_directories_and_builds_command(self) -> None:
        captured: dict[str, Any] = {}

        def fake_process_factory(*args: Any, **kwargs: Any) -> _FakeProcess:
            captured["args"] = args[0]
            captured["cwd"] = kwargs.get("cwd")
            return _FakeProcess()

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            script_root = root / "scripts"
            script_root.mkdir()
            (script_root / "install_local.ps1").write_text("", encoding="utf-8")
            install_root = root / "install"
            model_root = root / "models"
            manager = VoxCpmServiceManager(
                install_root=install_root,
                model_cache_root=model_root,
                script_root=script_root,
                use_model_mirror=True,
                process_factory=fake_process_factory,
            )

            self.assertTrue(manager.install_async())

            self.assertTrue(install_root.exists())
            self.assertTrue(model_root.exists())
            self.assertIn("-InstallRoot", captured["args"])
            self.assertIn(str(install_root), captured["args"])
            self.assertIn("-ModelCacheRoot", captured["args"])
            self.assertIn(str(model_root), captured["args"])
            self.assertIn("-UseHfMirror", captured["args"])
            self.assertEqual(captured["cwd"], script_root)
            self.assertTrue(manager.status().installing)

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
            (install_root / ".venv" / "Scripts").mkdir(parents=True)
            (install_root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
            (install_root / "start_service.ps1").write_text("", encoding="utf-8")
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
            (install_root / ".venv" / "Scripts").mkdir(parents=True)
            (install_root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
            (install_root / "start_service.ps1").write_text("", encoding="utf-8")
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
