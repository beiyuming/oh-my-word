from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal


ProcessFactory = Callable[..., Any]
UrlopenFunc = Callable[..., Any]


@dataclass(slots=True, frozen=True)
class VoxCpmServiceStatus:
    installed: bool
    running: bool
    installing: bool
    message: str
    log_path: Path


class VoxCpmServiceManager(QObject):
    status_changed = Signal(object)

    def __init__(
        self,
        *,
        install_root: Path,
        model_cache_root: Path,
        script_root: Path,
        endpoint: str = "http://127.0.0.1:8808",
        use_model_mirror: bool = True,
        process_factory: ProcessFactory | None = None,
        urlopen_func: UrlopenFunc | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._install_root = Path(install_root)
        self._model_cache_root = Path(model_cache_root)
        self._script_root = Path(script_root)
        self._endpoint = endpoint.rstrip("/")
        self._use_model_mirror = use_model_mirror
        self._process_factory = process_factory or subprocess.Popen
        self._urlopen = urlopen_func or urlopen
        self._install_process: Any | None = None
        self._service_process: Any | None = None
        self._install_log_handle: IO[str] | None = None
        self._message = ""
        self._health_running = False

    @property
    def log_path(self) -> Path:
        return self._install_root / "install.log"

    def configure(
        self,
        *,
        install_root: Path,
        model_cache_root: Path,
        endpoint: str,
        use_model_mirror: bool,
    ) -> None:
        self._install_root = Path(install_root)
        self._model_cache_root = Path(model_cache_root)
        self._endpoint = endpoint.rstrip("/")
        self._use_model_mirror = use_model_mirror
        self._emit_status()

    def is_installed(self) -> bool:
        return self._python_executable().exists() and self._start_script().exists()

    def is_installing(self) -> bool:
        if self._install_process is None:
            return False
        return self._install_process.poll() is None

    def is_running(self) -> bool:
        if self._service_process is not None and self._service_process.poll() is None:
            return True
        return self._health_running

    def status(self) -> VoxCpmServiceStatus:
        if self._install_process is not None and self._install_process.poll() is not None:
            self._close_install_log()
        return VoxCpmServiceStatus(
            installed=self.is_installed(),
            running=self.is_running(),
            installing=self.is_installing(),
            message=self._message,
            log_path=self.log_path,
        )

    def install_async(self) -> bool:
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False

        install_script = self._script_root / "install_local.ps1"
        if not install_script.exists():
            self._message = f"找不到 VoxCPM 安装脚本：{install_script}"
            self._emit_status()
            return False

        self._install_root.mkdir(parents=True, exist_ok=True)
        self._model_cache_root.mkdir(parents=True, exist_ok=True)
        self._close_install_log()

        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(install_script),
            "-InstallRoot",
            str(self._install_root),
            "-ModelCacheRoot",
            str(self._model_cache_root),
        ]
        if self._use_model_mirror:
            args.append("-UseHfMirror")

        with self.log_path.open("a", encoding="utf-8") as log_handle:
            self._install_process = self._spawn(args, cwd=self._script_root, stdout=log_handle)
        self._message = "VoxCPM 已开始后台安装。"
        self._emit_status()
        return True

    def start_service(self) -> bool:
        if self.health_check():
            self._message = "VoxCPM 本地服务已在运行。"
            self._emit_status()
            return True
        if not self.is_installed():
            self._message = "VoxCPM 尚未安装。"
            self._emit_status()
            return False
        if self._service_process is not None and self._service_process.poll() is None:
            self._message = "VoxCPM 本地服务正在运行。"
            self._emit_status()
            return True

        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self._start_script()),
        ]
        self._service_process = self._spawn(args, cwd=self._install_root)
        self._message = "VoxCPM 本地服务正在启动。"
        self._emit_status()
        return True

    def stop_service(self) -> bool:
        if self._service_process is None or self._service_process.poll() is not None:
            self._health_running = False
            self._message = "没有由应用启动的 VoxCPM 服务进程。"
            self._emit_status()
            return False

        if os.name == "nt" and getattr(self._service_process, "pid", None):
            subprocess.run(
                ["taskkill", "/PID", str(self._service_process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            self._service_process.terminate()
            try:
                self._service_process.wait(timeout=5)
            except Exception:
                self._service_process.kill()
        self._health_running = False
        self._message = "VoxCPM 本地服务已停止。"
        self._emit_status()
        return True

    def health_check(self) -> bool:
        request = Request(f"{self._endpoint}/health")
        try:
            with self._urlopen(request, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self._health_running = False
            self._message = f"VoxCPM 服务未响应：{exc}"
            self._emit_status()
            return False

        self._health_running = payload.get("status") == "ok"
        self._message = "VoxCPM 本地服务正常。" if self._health_running else "VoxCPM 服务状态异常。"
        self._emit_status()
        return self._health_running

    def _spawn(self, args: Sequence[str], *, cwd: Path, stdout: IO[str] | None = None) -> Any:
        kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stdout": stdout or subprocess.DEVNULL,
            "stderr": stdout or subprocess.DEVNULL,
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return self._process_factory(list(args), **kwargs)

    def _python_executable(self) -> Path:
        return self._install_root / ".venv" / "Scripts" / "python.exe"

    def _start_script(self) -> Path:
        return self._install_root / "start_service.ps1"

    def _close_install_log(self) -> None:
        if self._install_log_handle is None:
            return
        try:
            self._install_log_handle.close()
        finally:
            self._install_log_handle = None

    def _emit_status(self) -> None:
        self.status_changed.emit(self.status())
