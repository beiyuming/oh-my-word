from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

from .voxcpm_runtime import (
    MODEL_MANIFEST_FILENAME,
    RUNTIME_MANIFEST_FILENAME,
    VoxCpmModelManifest,
    VoxCpmRuntimeManifest,
    extract_model_zip_to_staging,
    extract_runtime_zip_to_staging,
    load_model_manifest_from_path,
    load_model_manifest_from_zip,
    load_runtime_manifest_from_path,
    load_runtime_manifest_from_zip,
    validate_model_zip_layout,
    validate_runtime_environment,
    validate_runtime_zip_layout,
    write_model_manifest,
    write_runtime_manifest,
)


ProcessFactory = Callable[..., Any]
UrlopenFunc = Callable[..., Any]
EndpointProcessFinder = Callable[[int], Sequence["EndpointProcess"]]
ProcessTerminator = Callable[[int], None]
_LOCAL_MODEL_DIRNAME = "VoxCPM2-local"


@dataclass(slots=True, frozen=True)
class EndpointProcess:
    pid: int
    command_line: str


@dataclass(slots=True, frozen=True)
class VoxCpmServiceStatus:
    installed: bool
    running: bool
    installing: bool
    message: str
    log_path: Path
    busy: bool = False
    runtime_state: str = "missing"
    runtime_id: str = ""
    cuda_tag: str = ""
    min_driver_version: str = ""
    model_version: str = ""


class VoxCpmServiceManager(QObject):
    status_changed = Signal(object)
    download_progress = Signal(str)

    def __init__(
        self,
        *,
        install_root: Path,
        model_cache_root: Path,
        script_root: Path,
        endpoint: str = "http://127.0.0.1:8808",
        use_model_mirror: bool = True,
        device: str = "auto",
        optimize: bool = False,
        cfg_value: float = 1.5,
        inference_timesteps: int = 10,
        retry_badcase: bool = True,
        retry_badcase_max_times: int = 3,
        retry_badcase_ratio_threshold: float = 4.0,
        leading_silence_seconds: float = 0.12,
        trailing_silence_seconds: float = 0.30,
        process_factory: ProcessFactory | None = None,
        urlopen_func: UrlopenFunc | None = None,
        endpoint_process_finder: EndpointProcessFinder | None = None,
        process_terminator: ProcessTerminator | None = None,
        environment_probe: Callable[[], dict[str, object]] | None = None,
        runtime_healthcheck_runner: Callable[[Path], tuple[bool, str]] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._install_root = Path(install_root)
        self._model_cache_root = Path(model_cache_root)
        self._script_root = Path(script_root)
        self._endpoint = endpoint.rstrip("/")
        self._use_model_mirror = use_model_mirror
        self._device = device
        self._optimize = optimize
        self._cfg_value = cfg_value
        self._inference_timesteps = inference_timesteps
        self._retry_badcase = retry_badcase
        self._retry_badcase_max_times = retry_badcase_max_times
        self._retry_badcase_ratio_threshold = retry_badcase_ratio_threshold
        self._leading_silence_seconds = leading_silence_seconds
        self._trailing_silence_seconds = trailing_silence_seconds
        self._process_factory = process_factory or subprocess.Popen
        self._urlopen = urlopen_func or urlopen
        self._endpoint_process_finder = endpoint_process_finder or self._find_endpoint_processes
        self._process_terminator = process_terminator or self._terminate_process_tree
        self._environment_probe = environment_probe or self._probe_runtime_environment
        self._runtime_healthcheck_runner = runtime_healthcheck_runner or self._run_runtime_healthcheck
        self._install_process: Any | None = None
        self._service_process: Any | None = None
        self._install_log_handle: IO[str] | None = None
        self._message = ""
        self._health_running = False
        self._download_active = False

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
        device: str | None = None,
        optimize: bool | None = None,
        cfg_value: float | None = None,
        inference_timesteps: int | None = None,
        retry_badcase: bool | None = None,
        retry_badcase_max_times: int | None = None,
        retry_badcase_ratio_threshold: float | None = None,
        leading_silence_seconds: float | None = None,
        trailing_silence_seconds: float | None = None,
    ) -> None:
        self._install_root = Path(install_root)
        self._model_cache_root = Path(model_cache_root)
        self._endpoint = endpoint.rstrip("/")
        self._use_model_mirror = use_model_mirror
        if device is not None:
            self._device = device
        if optimize is not None:
            self._optimize = optimize
        if cfg_value is not None:
            self._cfg_value = cfg_value
        if inference_timesteps is not None:
            self._inference_timesteps = inference_timesteps
        if retry_badcase is not None:
            self._retry_badcase = retry_badcase
        if retry_badcase_max_times is not None:
            self._retry_badcase_max_times = retry_badcase_max_times
        if retry_badcase_ratio_threshold is not None:
            self._retry_badcase_ratio_threshold = retry_badcase_ratio_threshold
        if leading_silence_seconds is not None:
            self._leading_silence_seconds = leading_silence_seconds
        if trailing_silence_seconds is not None:
            self._trailing_silence_seconds = trailing_silence_seconds
        self._rewrite_imported_runtime_scripts_if_needed()
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

    def is_busy(self) -> bool:
        return self.is_installing() or self._download_active

    def status(self) -> VoxCpmServiceStatus:
        if self._install_process is not None and self._install_process.poll() is not None:
            self._close_install_log()
        runtime_state, runtime_manifest = self._detect_runtime_metadata()
        return VoxCpmServiceStatus(
            installed=self.is_installed(),
            running=self.is_running(),
            installing=self.is_installing(),
            message=self._message,
            log_path=self.log_path,
            busy=self.is_busy(),
            runtime_state=runtime_state,
            runtime_id=runtime_manifest.runtime_id if runtime_manifest is not None else "",
            cuda_tag=runtime_manifest.cuda_tag if runtime_manifest is not None else "",
            min_driver_version=runtime_manifest.min_driver_version if runtime_manifest is not None else "",
            model_version=runtime_manifest.model_version if runtime_manifest is not None else "",
        )

    def import_runtime_package_async(self, package_path: Path) -> bool:
        if self._download_active:
            self._message = "VoxCPM 正在处理上一个任务。"
            self._emit_status()
            return False
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再导入运行时包。"
            self._emit_status()
            return False

        self._download_active = True
        self._message = f"正在导入 VoxCPM 运行时包：{Path(package_path).name} ..."
        self._emit_status()
        threading.Thread(
            target=self._import_runtime_package_sync,
            args=(Path(package_path),),
            daemon=True,
        ).start()
        return True

    def _import_runtime_package_sync(self, package_path: Path) -> None:
        try:
            self.import_runtime_package(package_path)
        finally:
            self._download_active = False
            self._emit_status()

    def import_runtime_package(self, package_path: Path) -> bool:
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再导入运行时包。"
            self._emit_status()
            return False

        try:
            self.download_progress.emit(f"正在校验 {package_path.name} ...")
            manifest = load_runtime_manifest_from_zip(package_path)
            layout_result = validate_runtime_zip_layout(package_path, manifest)
            if not layout_result.ok:
                self._message = layout_result.message
                self._emit_status()
                return False

            environment_result = validate_runtime_environment(manifest, self._environment_probe())
            if not environment_result.ok:
                self._message = environment_result.message
                self._emit_status()
                return False

            install_parent = self._install_root.parent
            install_parent.mkdir(parents=True, exist_ok=True)
            staging_root = install_parent / f"{self._install_root.name}.import-staging"
            if staging_root.exists():
                self.download_progress.emit("正在清理上次失败残留...")
                shutil.rmtree(staging_root)
            self.download_progress.emit("正在解压运行时包...")
            runtime_root = extract_runtime_zip_to_staging(package_path, staging_root)
            self.download_progress.emit("正在更新运行时脚本...")
            write_runtime_manifest(runtime_root, manifest)
            self._rewrite_imported_runtime_scripts(runtime_root)

            self.download_progress.emit("正在执行运行时自检...")
            health_ok, health_message = self._runtime_healthcheck_runner(runtime_root)
            if not health_ok:
                shutil.rmtree(staging_root, ignore_errors=True)
                self._message = health_message or "VoxCPM 运行时自检失败。"
                self._emit_status()
                return False

            backup_root = install_parent / f"{self._install_root.name}.backup"
            if backup_root.exists():
                shutil.rmtree(backup_root, ignore_errors=True)
            if self._install_root.exists():
                self._install_root.rename(backup_root)
            try:
                self.download_progress.emit("正在激活新的运行时...")
                self._promote_directory(runtime_root, self._install_root)
                shutil.rmtree(staging_root, ignore_errors=True)
            except Exception:
                if self._install_root.exists():
                    shutil.rmtree(self._install_root, ignore_errors=True)
                if backup_root.exists():
                    backup_root.rename(self._install_root)
                shutil.rmtree(staging_root, ignore_errors=True)
                raise

        except Exception as exc:
            self._message = f"导入 VoxCPM 运行时包失败：{exc}"
            self._emit_status()
            return False

        self._message = f"已导入 VoxCPM 运行时包：{manifest.runtime_id}"
        self._emit_status()
        return True

    def import_model_package_async(self, package_path: Path) -> bool:
        if self._download_active:
            self._message = "VoxCPM 正在处理上一个任务。"
            self._emit_status()
            return False
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再导入模型包。"
            self._emit_status()
            return False

        self._download_active = True
        self._message = f"正在导入 VoxCPM 模型包：{Path(package_path).name} ..."
        self._emit_status()
        threading.Thread(
            target=self._import_model_package_sync,
            args=(Path(package_path),),
            daemon=True,
        ).start()
        return True

    def _import_model_package_sync(self, package_path: Path) -> None:
        try:
            self.import_model_package(package_path)
        finally:
            self._download_active = False
            self._emit_status()

    def import_model_package(self, package_path: Path) -> bool:
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再导入模型包。"
            self._emit_status()
            return False
        if not self.is_installed():
            self._message = "请先导入 VoxCPM 运行时包。"
            self._emit_status()
            return False

        try:
            self.download_progress.emit(f"正在校验 {package_path.name} ...")
            manifest = load_model_manifest_from_zip(package_path)
            layout_result = validate_model_zip_layout(package_path, manifest)
            if not layout_result.ok:
                self._message = layout_result.message
                self._emit_status()
                return False

            model_parent = self._model_cache_root.parent
            model_parent.mkdir(parents=True, exist_ok=True)
            staging_root = model_parent / f"{self._model_cache_root.name}.model-staging"
            if staging_root.exists():
                self.download_progress.emit("正在清理上次失败残留...")
                shutil.rmtree(staging_root)
            self.download_progress.emit("正在解压模型包...")
            model_root = extract_model_zip_to_staging(package_path, staging_root)
            write_model_manifest(model_root, manifest)

            backup_root = model_parent / f"{self._model_cache_root.name}.backup"
            if backup_root.exists():
                shutil.rmtree(backup_root, ignore_errors=True)
            if self._model_cache_root.exists():
                self._model_cache_root.rename(backup_root)
            try:
                self.download_progress.emit("正在激活新的模型目录...")
                self._promote_directory(model_root, self._model_cache_root)
                shutil.rmtree(staging_root, ignore_errors=True)
            except Exception:
                if self._model_cache_root.exists():
                    shutil.rmtree(self._model_cache_root, ignore_errors=True)
                if backup_root.exists():
                    backup_root.rename(self._model_cache_root)
                shutil.rmtree(staging_root, ignore_errors=True)
                raise

        except Exception as exc:
            self._message = f"导入 VoxCPM 模型包失败：{exc}"
            self._emit_status()
            return False

        self._message = f"已导入 VoxCPM 模型包：{manifest.model_version}"
        self._emit_status()
        return True

    def download_and_import_model_package(
        self,
        *,
        namespace: str,
        repo_name: str,
    ) -> bool:
        if self._download_active:
            self._message = "VoxCPM 正在处理上一个任务。"
            self._emit_status()
            return False
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再下载模型包。"
            self._emit_status()
            return False

        runtime_state, runtime_manifest = self._detect_runtime_metadata()
        if runtime_state != "imported" or runtime_manifest is None:
            self._message = "请先导入 VoxCPM 运行时包，再下载模型包。"
            self._emit_status()
            return False
        if not runtime_manifest.model_package_filename:
            self._message = "当前运行时未声明模型包文件名。"
            self._emit_status()
            return False

        self._download_active = True
        self._message = "正在准备下载 VoxCPM 模型包..."
        self._emit_status()
        threading.Thread(
            target=self._download_and_import_model_package_sync,
            args=(namespace, repo_name, runtime_manifest.model_package_filename),
            daemon=True,
        ).start()
        return True

    def download_and_import_runtime_bundle(
        self,
        *,
        namespace: str,
        repo_name: str,
        runtime_filename: str,
        min_driver_version: str,
    ) -> bool:
        """Start async download+import.  Returns immediately; progress via download_progress, result via status_changed."""
        if self._download_active:
            self._message = "VoxCPM 正在处理上一个任务。"
            self._emit_status()
            return False
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再下载运行时包。"
            self._emit_status()
            return False

        environment_result = validate_runtime_environment(
            VoxCpmRuntimeManifest(
                runtime_id=runtime_filename,
                runtime_version="download",
                target_os="windows",
                target_arch="x64",
                cuda_tag="cu130",
                min_driver_version=min_driver_version,
                python_version="3.11",
                torch_version="",
                model_id="",
                model_version="",
                model_package_id="",
                model_package_filename="",
                expected_layout_version=1,
                package_size=1,
                file_hashes={},
                built_at="",
            ),
            self._environment_probe(),
        )
        if not environment_result.ok:
            self._message = environment_result.message
            self._emit_status()
            return False

        self._download_active = True
        self._message = "正在准备下载 VoxCPM 运行时包..."
        self._emit_status()
        threading.Thread(
            target=self._download_and_import_runtime_bundle_sync,
            args=(namespace, repo_name, runtime_filename, min_driver_version),
            daemon=True,
        ).start()
        return True

    def _download_and_import_runtime_bundle_sync(
        self,
        namespace: str,
        repo_name: str,
        runtime_filename: str,
        min_driver_version: str,
    ) -> bool:
        """Synchronous body; safe to call from a background thread."""
        download_root = self._install_root.parent / f"{self._install_root.name}.downloads"
        succeeded = False
        try:
            self.download_progress.emit(f"正在下载 {runtime_filename} ...")
            runtime_zip_path = self._download_modelscope_asset(
                namespace=namespace,
                repo_name=repo_name,
                filename=runtime_filename,
                download_root=download_root,
            )
            runtime_manifest = load_runtime_manifest_from_zip(runtime_zip_path)
            self.download_progress.emit("正在导入运行时包...")
            if not self.import_runtime_package(runtime_zip_path):
                return False
            if runtime_manifest.model_package_filename:
                self.download_progress.emit(f"正在下载 {runtime_manifest.model_package_filename} ...")
                model_zip_path = self._download_modelscope_asset(
                    namespace=namespace,
                    repo_name=repo_name,
                    filename=runtime_manifest.model_package_filename,
                    download_root=download_root,
                )
                self.download_progress.emit("正在导入模型包...")
                if not self.import_model_package(model_zip_path):
                    return False

            self._message = f"已下载并导入 VoxCPM 运行时与模型：{runtime_manifest.runtime_id}"
            succeeded = True
        except Exception as exc:
            self._message = f"下载 VoxCPM 运行时包失败：{exc}"
        finally:
            self._download_active = False
            self._emit_status()
        return succeeded

    def _download_and_import_model_package_sync(
        self,
        namespace: str,
        repo_name: str,
        model_filename: str,
    ) -> bool:
        download_root = self._install_root.parent / f"{self._install_root.name}.downloads"
        succeeded = False
        try:
            self.download_progress.emit(f"正在下载 {model_filename} ...")
            model_zip_path = self._download_modelscope_asset(
                namespace=namespace,
                repo_name=repo_name,
                filename=model_filename,
                download_root=download_root,
            )
            self.download_progress.emit("正在导入模型包...")
            if not self.import_model_package(model_zip_path):
                return False
            self._message = f"已下载并导入 VoxCPM 模型包：{model_filename}"
            succeeded = True
        except Exception as exc:
            self._message = f"下载 VoxCPM 模型包失败：{exc}"
        finally:
            self._download_active = False
            self._emit_status()
        return succeeded

    def _download_and_import_runtime_bundle_blocking(
        self,
        *,
        namespace: str,
        repo_name: str,
        runtime_filename: str,
        min_driver_version: str,
    ) -> bool:
        """Blocking convenience wrapper for tests and synchronous callers."""
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再下载运行时包。"
            self._emit_status()
            return False

        environment_result = validate_runtime_environment(
            VoxCpmRuntimeManifest(
                runtime_id=runtime_filename,
                runtime_version="download",
                target_os="windows",
                target_arch="x64",
                cuda_tag="cu130",
                min_driver_version=min_driver_version,
                python_version="3.11",
                torch_version="",
                model_id="",
                model_version="",
                model_package_id="",
                model_package_filename="",
                expected_layout_version=1,
                package_size=1,
                file_hashes={},
                built_at="",
            ),
            self._environment_probe(),
        )
        if not environment_result.ok:
            self._message = environment_result.message
            self._emit_status()
            return False

        self._download_active = True
        return self._download_and_import_runtime_bundle_sync(
            namespace, repo_name, runtime_filename, min_driver_version
        )

    def _download_and_import_model_package_blocking(
        self,
        *,
        namespace: str,
        repo_name: str,
    ) -> bool:
        if self.is_installing():
            self._message = "VoxCPM 正在安装中。"
            self._emit_status()
            return False
        if self.is_running():
            self._message = "请先停止当前 VoxCPM 服务，再下载模型包。"
            self._emit_status()
            return False

        runtime_state, runtime_manifest = self._detect_runtime_metadata()
        if runtime_state != "imported" or runtime_manifest is None:
            self._message = "请先导入 VoxCPM 运行时包，再下载模型包。"
            self._emit_status()
            return False
        if not runtime_manifest.model_package_filename:
            self._message = "当前运行时未声明模型包文件名。"
            self._emit_status()
            return False

        self._download_active = True
        return self._download_and_import_model_package_sync(
            namespace,
            repo_name,
            runtime_manifest.model_package_filename,
        )


    def start_service(self) -> bool:
        if not self.is_installed():
            self._message = "VoxCPM 尚未安装。"
            self._emit_status()
            return False
        if self._runtime_manifest_path().exists() and not self._model_manifest_path().exists():
            self._message = "VoxCPM 模型尚未导入。"
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
        stopped = False
        if self._service_process is not None and self._service_process.poll() is None:
            self._terminate_tracked_process()
            stopped = True

        stopped_external = self._stop_matching_endpoint_processes()
        stopped = stopped or stopped_external
        if not stopped:
            self._health_running = False
            self._message = "没有由应用启动或可识别的 VoxCPM 服务进程。"
            self._emit_status()
            return False

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

    def _terminate_tracked_process(self) -> None:
        assert self._service_process is not None
        if os.name == "nt" and getattr(self._service_process, "pid", None):
            self._process_terminator(int(self._service_process.pid))
        else:
            self._service_process.terminate()
            try:
                self._service_process.wait(timeout=5)
            except Exception:
                self._service_process.kill()

    def _stop_matching_endpoint_processes(self) -> bool:
        port = self._endpoint_port()
        if port is None:
            return False
        stopped = False
        for process in self._endpoint_process_finder(port):
            if not self._is_voxcpm_service_process(process):
                continue
            self._process_terminator(process.pid)
            stopped = True
        return stopped

    def _endpoint_port(self) -> int | None:
        parsed = urlparse(self._endpoint)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "http" or hostname not in {"127.0.0.1", "localhost", "::1"}:
            return None
        return parsed.port

    def _is_voxcpm_service_process(self, process: EndpointProcess) -> bool:
        command_line = process.command_line.lower()
        return "uvicorn" in command_line and "service.server:app" in command_line

    def _find_endpoint_processes(self, port: int) -> Sequence[EndpointProcess]:
        if os.name != "nt":
            return ()
        command = (
            "$ErrorActionPreference='SilentlyContinue'; "
            f"$pids = Get-NetTCPConnection -LocalPort {port} -State Listen | "
            "Select-Object -ExpandProperty OwningProcess -Unique; "
            "foreach ($pidValue in $pids) { "
            "$process = Get-CimInstance Win32_Process -Filter \"ProcessId=$pidValue\"; "
            "if ($process) { \"$($process.ProcessId)`t$($process.CommandLine)\" } "
            "}"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        processes = self._parse_endpoint_process_rows(result.stdout)
        if processes:
            return processes

        pids = self._find_endpoint_pids_with_netstat(port)
        return self._find_processes_by_pids(pids)

    def _find_endpoint_pids_with_netstat(self, port: int) -> Sequence[int]:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "netstat -ano -p tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        pids: list[int] = []
        port_marker = f":{port}"
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0].upper() != "TCP":
                continue
            if parts[1].endswith(port_marker) and parts[3].upper() == "LISTENING":
                try:
                    pids.append(int(parts[4]))
                except ValueError:
                    continue
        return tuple(dict.fromkeys(pids))

    def _find_processes_by_pids(self, pids: Sequence[int]) -> Sequence[EndpointProcess]:
        if not pids:
            return ()
        pid_list = ", ".join(str(pid) for pid in pids)
        command = (
            "$ErrorActionPreference='SilentlyContinue'; "
            f"foreach ($pidValue in @({pid_list})) {{ "
            "$process = Get-CimInstance Win32_Process -Filter \"ProcessId=$pidValue\"; "
            "if ($process) { \"$($process.ProcessId)`t$($process.CommandLine)\" } "
            "}"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        return self._parse_endpoint_process_rows(result.stdout)

    @staticmethod
    def _parse_endpoint_process_rows(output: str) -> list[EndpointProcess]:
        processes: list[EndpointProcess] = []
        for line in output.splitlines():
            pid_text, separator, command_line = line.partition("\t")
            if not separator:
                continue
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            processes.append(EndpointProcess(pid=pid, command_line=command_line))
        return processes

    @staticmethod
    def _terminate_process_tree(pid: int) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        os.kill(pid, 15)

    def _runtime_manifest_path(self) -> Path:
        return self._install_root / RUNTIME_MANIFEST_FILENAME

    def _model_manifest_path(self) -> Path:
        return self._model_cache_root / MODEL_MANIFEST_FILENAME

    def _detect_runtime_metadata(self) -> tuple[str, VoxCpmRuntimeManifest | None]:
        manifest_path = self._runtime_manifest_path()
        if manifest_path.exists():
            try:
                return "imported", load_runtime_manifest_from_path(manifest_path)
            except Exception:
                return "broken", None
        if self.is_installed():
            return "legacy", None
        return "missing", None

    def _probe_runtime_environment(self) -> dict[str, object]:
        driver_version = ""
        has_nvidia_gpu = False
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=driver_version",
                    "--format=csv,noheader",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            driver_version = (result.stdout.splitlines() or [""])[0].strip()
            has_nvidia_gpu = bool(driver_version)
        except Exception:
            driver_version = ""
            has_nvidia_gpu = False

        disk_target = self._install_root.parent if self._install_root.parent.exists() else Path.cwd()
        free_bytes = shutil.disk_usage(disk_target).free
        return {
            "target_os": platform.system().lower(),
            "target_arch": "x64" if "64" in platform.machine().lower() else platform.machine().lower(),
            "has_nvidia_gpu": has_nvidia_gpu,
            "driver_version": driver_version,
            "free_bytes": free_bytes,
        }

    def _run_runtime_healthcheck(self, runtime_root: Path) -> tuple[bool, str]:
        python_path = self._runtime_python_executable(runtime_root)
        service_server_path = runtime_root / "service" / "server.py"
        if not python_path.exists():
            return False, f"运行时缺少 Python：{python_path}"
        if not service_server_path.exists():
            return False, f"运行时缺少服务入口：{service_server_path}"

        env = os.environ.copy()
        env["HF_HOME"] = str(self._model_cache_root)
        env["HF_HUB_CACHE"] = str(self._model_cache_root / "hub")
        env["VOXCPM_MODEL_ID"] = str(self._model_cache_root / _LOCAL_MODEL_DIRNAME)
        kwargs: dict[str, Any] = {
            "cwd": runtime_root,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "check": False,
            "env": env,
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            [
                str(python_path),
                "-c",
                "import service.server; print('runtime import ok')",
            ],
            **kwargs,
        )
        output = (result.stdout or "").strip()
        if result.returncode == 0:
            return True, output or "ok"
        return False, output or "VoxCPM 运行时自检失败。"

    def _build_modelscope_asset_url(self, *, namespace: str, repo_name: str, filename: str) -> str:
        encoded_filename = quote(filename, safe="/")
        return f"https://www.modelscope.cn/models/{namespace}/{repo_name}/resolve/master/{encoded_filename}"

    def _download_modelscope_asset(
        self,
        *,
        namespace: str,
        repo_name: str,
        filename: str,
        download_root: Path,
        on_chunk: Callable[[int, int], None] | None = None,
    ) -> Path:
        download_root.mkdir(parents=True, exist_ok=True)
        asset_path = download_root / filename
        sha_path = download_root / f"{filename}.sha256"
        self._message = f"正在下载 {filename} ..."
        self._emit_status()
        self._download_url_to_path(
            self._build_modelscope_asset_url(namespace=namespace, repo_name=repo_name, filename=filename),
            asset_path,
            on_chunk=on_chunk,
        )
        self._download_url_to_path(
            self._build_modelscope_asset_url(namespace=namespace, repo_name=repo_name, filename=f"{filename}.sha256"),
            sha_path,
        )
        self._verify_downloaded_sha(asset_path, sha_path)
        return asset_path

    def _download_url_to_path(
        self, url: str, destination: Path,
        on_chunk: Callable[[int, int], None] | None = None,
    ) -> None:
        request = Request(url)
        with self._urlopen(request, timeout=30) as response:
            if on_chunk is None:
                destination.write_bytes(response.read())
                return

            total_str = response.headers.get("Content-Length")
            total = int(total_str) if total_str else 0
            downloaded = 0
            with open(destination, "wb") as f:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    on_chunk(downloaded, total)

    def _verify_downloaded_sha(self, asset_path: Path, sha_path: Path) -> None:
        sha_text = sha_path.read_text(encoding="utf-8").strip()
        if not sha_text:
            raise ValueError(f"校验文件为空：{sha_path.name}")
        expected_hash = sha_text.split()[0].strip().lower()
        actual_hash = hashlib.sha256(asset_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"{asset_path.name} 校验失败。")

    def _python_executable(self) -> Path:
        return self._runtime_python_executable(self._install_root)

    @staticmethod
    def _promote_directory(source_root: Path, target_root: Path) -> None:
        try:
            source_root.rename(target_root)
        except PermissionError:
            if target_root.exists():
                shutil.rmtree(target_root, ignore_errors=True)
            shutil.move(str(source_root), str(target_root))

    @staticmethod
    def _runtime_python_executable(runtime_root: Path) -> Path:
        candidates = (
            runtime_root / "python" / "python.exe",
            runtime_root / ".venv" / "Scripts" / "python.exe",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

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

    def _rewrite_imported_runtime_scripts_if_needed(self) -> None:
        if not self._runtime_manifest_path().exists():
            return
        if not self._install_root.exists():
            return
        self._rewrite_imported_runtime_scripts(self._install_root)

    def _rewrite_imported_runtime_scripts(self, runtime_root: Path) -> None:
        runtime_root.mkdir(parents=True, exist_ok=True)
        (runtime_root / "start_service.ps1").write_text(
            self._build_imported_start_script(),
            encoding="utf-8",
        )
        (runtime_root / "healthcheck.ps1").write_text(
            self._build_imported_healthcheck_script(),
            encoding="utf-8",
        )

    def _build_imported_start_script(self) -> str:
        model_cache_root = self._escape_powershell_single_quoted(str(self._model_cache_root))
        model_hub_cache_root = self._escape_powershell_single_quoted(str(self._model_cache_root / "hub"))
        local_model_root = self._escape_powershell_single_quoted(str(self._model_cache_root / _LOCAL_MODEL_DIRNAME))
        host, port = self._local_endpoint_host_port()
        return "\n".join(
            [
                '$ErrorActionPreference = "Stop"',
                '$scriptRoot = Split-Path -Parent $PSCommandPath',
                '$portablePython = Join-Path $scriptRoot "python\\python.exe"',
                '$legacyVenvPython = Join-Path $scriptRoot ".venv\\Scripts\\python.exe"',
                '$runtimePython = if (Test-Path -LiteralPath $portablePython) { $portablePython } else { $legacyVenvPython }',
                'if (-not (Test-Path -LiteralPath $runtimePython)) { throw "VoxCPM runtime python not found: $runtimePython" }',
                f"$env:HF_HOME = '{model_cache_root}'",
                f"$env:HF_HUB_CACHE = '{model_hub_cache_root}'",
                f"$env:VOXCPM_MODEL_ID = '{local_model_root}'",
                f"$env:VOXCPM_DEVICE = '{self._escape_powershell_single_quoted(self._device)}'",
                f"$env:VOXCPM_OPTIMIZE = '{self._bool_env(self._optimize)}'",
                f"$env:VOXCPM_CFG_VALUE = '{self._cfg_value:g}'",
                f"$env:VOXCPM_INFERENCE_TIMESTEPS = '{self._inference_timesteps}'",
                f"$env:VOXCPM_RETRY_BADCASE = '{self._bool_env(self._retry_badcase)}'",
                f"$env:VOXCPM_RETRY_BADCASE_MAX_TIMES = '{self._retry_badcase_max_times}'",
                f"$env:VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD = '{self._retry_badcase_ratio_threshold:g}'",
                f"$env:VOXCPM_LEADING_SILENCE_SECONDS = '{self._leading_silence_seconds:g}'",
                f"$env:VOXCPM_TRAILING_SILENCE_SECONDS = '{self._trailing_silence_seconds:g}'",
                "Set-Location -LiteralPath $scriptRoot",
                f'& $runtimePython -m uvicorn service.server:app --host "{host}" --port {port}',
                "",
            ]
        )

    def _build_imported_healthcheck_script(self) -> str:
        return "\n".join(
            [
                f'$r = Invoke-WebRequest -Uri "{self._build_healthcheck_url()}" -UseBasicParsing -TimeoutSec 5',
                "exit ($r.StatusCode -ne 200)",
                "",
            ]
        )

    def _build_healthcheck_url(self) -> str:
        host, port = self._local_endpoint_host_port()
        return f"http://{host}:{port}/health"

    def _local_endpoint_host_port(self) -> tuple[str, int]:
        parsed = urlparse(self._endpoint)
        host = parsed.hostname or "127.0.0.1"
        if host not in {"127.0.0.1", "localhost", "::1"}:
            host = "127.0.0.1"
        port = parsed.port or 8808
        return host, port

    @staticmethod
    def _escape_powershell_single_quoted(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _bool_env(value: bool) -> str:
        return "1" if value else "0"
