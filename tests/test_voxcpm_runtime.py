from __future__ import annotations

import hashlib
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from app.voxcpm_runtime import (
    compare_version_parts,
    load_model_manifest_from_zip,
    load_runtime_manifest_from_zip,
    validate_model_zip_layout,
    validate_runtime_environment,
    validate_runtime_zip_layout,
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class VoxCpmRuntimeTests(unittest.TestCase):
    def test_reads_runtime_manifest_and_required_fields(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "runtime.zip"
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
                            "model_package_id": "voxcpm2-model-cu130-r2",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_layout_version": 1,
                            "package_size": 123,
                            "file_hashes": {},
                            "built_at": "2026-06-18T12:00:00Z",
                        }
                    ),
                )

            manifest = load_runtime_manifest_from_zip(zip_path)

        self.assertEqual(manifest.runtime_id, "voxcpm2-runtime-win-x64-cu124-r1")
        self.assertEqual(manifest.cuda_tag, "cu124")
        self.assertEqual(manifest.min_driver_version, "551.00")
        self.assertEqual(manifest.model_package_filename, "voxcpm2-model-cu130-r2.zip")

    def test_rejects_zip_without_runtime_directory(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "runtime.zip"
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
                            "model_package_id": "voxcpm2-model-cu130-r2",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_layout_version": 1,
                            "package_size": 123,
                            "file_hashes": {},
                            "built_at": "2026-06-18T12:00:00Z",
                        }
                    ),
                )
                archive.writestr("readme.txt", "missing runtime subtree")

            manifest = load_runtime_manifest_from_zip(zip_path)
            result = validate_runtime_zip_layout(zip_path, manifest)

        self.assertFalse(result.ok)
        self.assertIn("runtime/", result.message)

    def test_rejects_hash_mismatch(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "runtime.zip"
            python_payload = b"python-bytes"
            start_payload = b"start-script"
            health_payload = b"health-script"
            service_payload = b"service-code"
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
                            "model_package_id": "voxcpm2-model-cu130-r2",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_layout_version": 1,
                            "package_size": 123,
                            "file_hashes": {
                                "runtime/python/python.exe": _sha256_bytes(python_payload),
                                "runtime/start_service.ps1": "deadbeef",
                                "runtime/healthcheck.ps1": _sha256_bytes(health_payload),
                                "runtime/service/server.py": _sha256_bytes(service_payload),
                            },
                            "built_at": "2026-06-18T12:00:00Z",
                        }
                    ),
                )
                archive.writestr("runtime/python/python.exe", python_payload)
                archive.writestr("runtime/start_service.ps1", start_payload)
                archive.writestr("runtime/healthcheck.ps1", health_payload)
                archive.writestr("runtime/service/server.py", service_payload)

            manifest = load_runtime_manifest_from_zip(zip_path)
            result = validate_runtime_zip_layout(zip_path, manifest)

        self.assertFalse(result.ok)
        self.assertIn("hash", result.message.lower())

    def test_accepts_legacy_runtime_venv_layout(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "runtime.zip"
            python_payload = b"python-bytes"
            start_payload = b"start-script"
            health_payload = b"health-script"
            service_payload = b"service-code"
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
                            "model_package_id": "voxcpm2-model-cu130-r2",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_layout_version": 1,
                            "package_size": 123,
                            "file_hashes": {
                                "runtime/.venv/Scripts/python.exe": _sha256_bytes(python_payload),
                                "runtime/start_service.ps1": _sha256_bytes(start_payload),
                                "runtime/healthcheck.ps1": _sha256_bytes(health_payload),
                                "runtime/service/server.py": _sha256_bytes(service_payload),
                            },
                            "built_at": "2026-06-18T12:00:00Z",
                        }
                    ),
                )
                archive.writestr("runtime/.venv/Scripts/python.exe", python_payload)
                archive.writestr("runtime/start_service.ps1", start_payload)
                archive.writestr("runtime/healthcheck.ps1", health_payload)
                archive.writestr("runtime/service/server.py", service_payload)

            manifest = load_runtime_manifest_from_zip(zip_path)
            result = validate_runtime_zip_layout(zip_path, manifest)

        self.assertTrue(result.ok)

    def test_driver_version_comparison_handles_multi_part_versions(self) -> None:
        self.assertLess(compare_version_parts("551.00", "552.12"), 0)
        self.assertEqual(compare_version_parts("551.00", "551.0"), 0)
        self.assertGreater(compare_version_parts("576.80", "552.12"), 0)

    def test_rejects_runtime_when_nvidia_driver_is_too_old(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "runtime.zip"
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
                            "model_package_id": "voxcpm2-model-cu130-r2",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_layout_version": 1,
                            "package_size": 123,
                            "file_hashes": {},
                            "built_at": "2026-06-18T12:00:00Z",
                        }
                    ),
                )

            manifest = load_runtime_manifest_from_zip(zip_path)

        result = validate_runtime_environment(
            manifest,
            {
                "target_os": "windows",
                "target_arch": "x64",
                "has_nvidia_gpu": True,
                "driver_version": "550.40",
                "free_bytes": 10_000,
            },
        )

        self.assertFalse(result.ok)
        self.assertIn("551.00", result.message)

    def test_rejects_runtime_when_nvidia_gpu_is_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "runtime.zip"
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
                            "model_package_id": "voxcpm2-model-cu130-r2",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_layout_version": 1,
                            "package_size": 123,
                            "file_hashes": {},
                            "built_at": "2026-06-18T12:00:00Z",
                        }
                    ),
                )

            manifest = load_runtime_manifest_from_zip(zip_path)

        result = validate_runtime_environment(
            manifest,
            {
                "target_os": "windows",
                "target_arch": "x64",
                "has_nvidia_gpu": False,
                "driver_version": "",
                "free_bytes": 10_000,
            },
        )

        self.assertFalse(result.ok)
        self.assertIn("NVIDIA GPU", result.message)

    def test_validates_split_model_package_layout(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "model.zip"
            model_payload = b"model-bytes"
            config_payload = b"{}"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "model_manifest.json",
                    json.dumps(
                        {
                            "model_id": "openbmb/VoxCPM2",
                            "model_version": "2026-06-18",
                            "model_package_filename": "voxcpm2-model-cu130-r2.zip",
                            "expected_model_dir": "VoxCPM2-local",
                            "package_size": 456,
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

            manifest = load_model_manifest_from_zip(zip_path)
            result = validate_model_zip_layout(zip_path, manifest)

        self.assertEqual(manifest.expected_model_dir, "VoxCPM2-local")
        self.assertTrue(result.ok)
