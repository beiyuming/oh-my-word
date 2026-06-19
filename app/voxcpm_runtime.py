from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zipfile import ZipFile

RUNTIME_MANIFEST_FILENAME = "runtime_manifest.json"
MODEL_MANIFEST_FILENAME = "model_manifest.json"


@dataclass(slots=True, frozen=True)
class VoxCpmRuntimeManifest:
    runtime_id: str
    runtime_version: str
    target_os: str
    target_arch: str
    cuda_tag: str
    min_driver_version: str
    python_version: str
    torch_version: str
    model_id: str
    model_version: str
    model_package_id: str
    model_package_filename: str
    expected_layout_version: int
    package_size: int
    file_hashes: dict[str, str]
    built_at: str


@dataclass(slots=True, frozen=True)
class VoxCpmModelManifest:
    model_id: str
    model_version: str
    model_package_filename: str
    expected_model_dir: str
    package_size: int
    file_hashes: dict[str, str]
    built_at: str


@dataclass(slots=True, frozen=True)
class VoxCpmRuntimeValidationResult:
    ok: bool
    message: str = ""


_REQUIRED_MANIFEST_FIELDS = {
    "runtime_id",
    "runtime_version",
    "target_os",
    "target_arch",
    "cuda_tag",
    "min_driver_version",
    "python_version",
    "torch_version",
    "model_id",
    "model_version",
    "model_package_id",
    "model_package_filename",
    "expected_layout_version",
    "package_size",
    "file_hashes",
    "built_at",
}

_REQUIRED_MODEL_MANIFEST_FIELDS = {
    "model_id",
    "model_version",
    "model_package_filename",
    "expected_model_dir",
    "package_size",
    "file_hashes",
    "built_at",
}

_REQUIRED_RUNTIME_FILES = (
    "runtime/start_service.ps1",
    "runtime/healthcheck.ps1",
)

_REQUIRED_RUNTIME_EXECUTABLE_PATHS = (
    "runtime/python/python.exe",
    "runtime/.venv/Scripts/python.exe",
)

_REQUIRED_RUNTIME_PREFIXES = (
    "runtime/service/",
)


def compare_version_parts(left: str, right: str) -> int:
    left_parts = [int(part) for part in left.split(".")]
    right_parts = [int(part) for part in right.split(".")]
    width = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (width - len(left_parts)))
    right_parts.extend([0] * (width - len(right_parts)))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def load_runtime_manifest_from_zip(zip_path: Path) -> VoxCpmRuntimeManifest:
    with ZipFile(zip_path) as archive:
        payload = json.loads(archive.read("manifest.json").decode("utf-8"))
    return _manifest_from_payload(payload)


def load_runtime_manifest_from_path(path: Path) -> VoxCpmRuntimeManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _manifest_from_payload(payload)


def load_model_manifest_from_zip(zip_path: Path) -> VoxCpmModelManifest:
    with ZipFile(zip_path) as archive:
        payload = json.loads(archive.read("model_manifest.json").decode("utf-8"))
    return _model_manifest_from_payload(payload)


def load_model_manifest_from_path(path: Path) -> VoxCpmModelManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _model_manifest_from_payload(payload)


def write_runtime_manifest(runtime_root: Path, manifest: VoxCpmRuntimeManifest) -> Path:
    path = runtime_root / RUNTIME_MANIFEST_FILENAME
    path.write_text(
        json.dumps(
            {
                "runtime_id": manifest.runtime_id,
                "runtime_version": manifest.runtime_version,
                "target_os": manifest.target_os,
                "target_arch": manifest.target_arch,
                "cuda_tag": manifest.cuda_tag,
                "min_driver_version": manifest.min_driver_version,
                "python_version": manifest.python_version,
                "torch_version": manifest.torch_version,
                "model_id": manifest.model_id,
                "model_version": manifest.model_version,
                "model_package_id": manifest.model_package_id,
                "model_package_filename": manifest.model_package_filename,
                "expected_layout_version": manifest.expected_layout_version,
                "package_size": manifest.package_size,
                "file_hashes": manifest.file_hashes,
                "built_at": manifest.built_at,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def write_model_manifest(model_root: Path, manifest: VoxCpmModelManifest) -> Path:
    path = model_root / MODEL_MANIFEST_FILENAME
    path.write_text(
        json.dumps(
            {
                "model_id": manifest.model_id,
                "model_version": manifest.model_version,
                "model_package_filename": manifest.model_package_filename,
                "expected_model_dir": manifest.expected_model_dir,
                "package_size": manifest.package_size,
                "file_hashes": manifest.file_hashes,
                "built_at": manifest.built_at,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def extract_runtime_zip_to_staging(zip_path: Path, staging_root: Path) -> Path:
    with ZipFile(zip_path) as archive:
        archive.extractall(staging_root)
    return staging_root / "runtime"


def extract_model_zip_to_staging(zip_path: Path, staging_root: Path) -> Path:
    with ZipFile(zip_path) as archive:
        archive.extractall(staging_root)
    return staging_root / "models"


def validate_runtime_environment(
    manifest: VoxCpmRuntimeManifest,
    environment: Mapping[str, object],
) -> VoxCpmRuntimeValidationResult:
    target_os = str(environment.get("target_os", "")).lower()
    target_arch = str(environment.get("target_arch", "")).lower()
    has_nvidia_gpu = bool(environment.get("has_nvidia_gpu", False))
    driver_version = str(environment.get("driver_version", "") or "")
    free_bytes = int(environment.get("free_bytes", 0) or 0)

    if target_os != manifest.target_os.lower():
        return VoxCpmRuntimeValidationResult(False, f"当前系统不是受支持的 {manifest.target_os} 环境。")
    if target_arch != manifest.target_arch.lower():
        return VoxCpmRuntimeValidationResult(False, f"当前系统架构不是受支持的 {manifest.target_arch}。")
    if not has_nvidia_gpu:
        return VoxCpmRuntimeValidationResult(False, "当前机器未检测到受支持的 NVIDIA GPU。")
    if driver_version and compare_version_parts(driver_version, manifest.min_driver_version) < 0:
        return VoxCpmRuntimeValidationResult(
            False,
            f"当前 NVIDIA 驱动版本 {driver_version} 低于运行时要求的 {manifest.min_driver_version}。",
        )
    if free_bytes and free_bytes < manifest.package_size:
        return VoxCpmRuntimeValidationResult(False, "当前磁盘剩余空间不足。")
    return VoxCpmRuntimeValidationResult(True, "ok")


def _manifest_from_payload(payload: Mapping[str, object]) -> VoxCpmRuntimeManifest:
    missing = sorted(_REQUIRED_MANIFEST_FIELDS - payload.keys())
    if missing:
        raise ValueError(f"Runtime manifest is missing fields: {', '.join(missing)}")
    return VoxCpmRuntimeManifest(
        runtime_id=str(payload["runtime_id"]),
        runtime_version=str(payload["runtime_version"]),
        target_os=str(payload["target_os"]),
        target_arch=str(payload["target_arch"]),
        cuda_tag=str(payload["cuda_tag"]),
        min_driver_version=str(payload["min_driver_version"]),
        python_version=str(payload["python_version"]),
        torch_version=str(payload["torch_version"]),
        model_id=str(payload["model_id"]),
        model_version=str(payload["model_version"]),
        model_package_id=str(payload["model_package_id"]),
        model_package_filename=str(payload["model_package_filename"]),
        expected_layout_version=int(payload["expected_layout_version"]),
        package_size=int(payload["package_size"]),
        file_hashes={str(key): str(value) for key, value in dict(payload["file_hashes"]).items()},
        built_at=str(payload["built_at"]),
    )


def _model_manifest_from_payload(payload: Mapping[str, object]) -> VoxCpmModelManifest:
    missing = sorted(_REQUIRED_MODEL_MANIFEST_FIELDS - payload.keys())
    if missing:
        raise ValueError(f"Model manifest is missing fields: {', '.join(missing)}")
    return VoxCpmModelManifest(
        model_id=str(payload["model_id"]),
        model_version=str(payload["model_version"]),
        model_package_filename=str(payload["model_package_filename"]),
        expected_model_dir=str(payload["expected_model_dir"]),
        package_size=int(payload["package_size"]),
        file_hashes={str(key): str(value) for key, value in dict(payload["file_hashes"]).items()},
        built_at=str(payload["built_at"]),
    )


def validate_runtime_zip_layout(
    zip_path: Path,
    manifest: VoxCpmRuntimeManifest,
) -> VoxCpmRuntimeValidationResult:
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if not any(name == "runtime/" or name.startswith("runtime/") for name in names):
            return VoxCpmRuntimeValidationResult(False, "Runtime package is missing runtime/ directory.")

        for path in _REQUIRED_RUNTIME_FILES:
            if path not in names:
                return VoxCpmRuntimeValidationResult(False, f"Runtime package is missing required file: {path}")

        if not any(path in names for path in _REQUIRED_RUNTIME_EXECUTABLE_PATHS):
            return VoxCpmRuntimeValidationResult(
                False,
                "Runtime package is missing required Python runtime executable.",
            )

        for prefix in _REQUIRED_RUNTIME_PREFIXES:
            if not any(name.startswith(prefix) for name in names):
                return VoxCpmRuntimeValidationResult(False, f"Runtime package is missing required content under {prefix}")

        for relative_path, expected_hash in manifest.file_hashes.items():
            if relative_path not in names:
                return VoxCpmRuntimeValidationResult(False, f"Runtime package is missing hashed file: {relative_path}")
            actual_hash = hashlib.sha256(archive.read(relative_path)).hexdigest()
            if actual_hash != expected_hash.lower():
                return VoxCpmRuntimeValidationResult(False, f"Runtime package hash mismatch for {relative_path}.")

    return VoxCpmRuntimeValidationResult(True, "ok")


def validate_model_zip_layout(
    zip_path: Path,
    manifest: VoxCpmModelManifest,
) -> VoxCpmRuntimeValidationResult:
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        expected_prefix = f"models/{manifest.expected_model_dir}/"
        if not any(name.startswith(expected_prefix) for name in names):
            return VoxCpmRuntimeValidationResult(
                False,
                f"Model package is missing required content under {expected_prefix}",
            )

        for relative_path, expected_hash in manifest.file_hashes.items():
            if relative_path not in names:
                return VoxCpmRuntimeValidationResult(False, f"Model package is missing hashed file: {relative_path}")
            actual_hash = hashlib.sha256(archive.read(relative_path)).hexdigest()
            if actual_hash != expected_hash.lower():
                return VoxCpmRuntimeValidationResult(False, f"Model package hash mismatch for {relative_path}.")

    return VoxCpmRuntimeValidationResult(True, "ok")
