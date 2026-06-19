import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "voxcpm_service"
INSTALL_SCRIPT = TOOLS / "install_local.ps1"
BUILD_ROOT = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "oh-my-word-voxcpm2-build"
INSTALL_DIR = BUILD_ROOT / "voxcpm"
MODEL_DIR = INSTALL_DIR / "models"
OUTPUT_DIR = ROOT / "dist" / "voxcpm2-packages"
LOCAL_MODEL_DIRNAME = "VoxCPM2-local"

CUDA_TAG = "cu130"
RUNTIME_REVISION = "r2"
MODEL_REVISION = "r2"
RUNTIME_ID = f"voxcpm2-runtime-win-x64-{CUDA_TAG}-{RUNTIME_REVISION}"
MODEL_PACKAGE_FILENAME = f"voxcpm2-model-{CUDA_TAG}-{MODEL_REVISION}.zip"
MIN_DRIVER = "580"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-install-root", type=Path, default=None)
    return parser.parse_args()


def sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256(path: Path, target: str) -> Path:
    sha_path = Path(str(path) + ".sha256")
    sha_path.write_text(f"{sha256_hex(path)}  {target}\n", encoding="utf-8")
    return sha_path


def build_file_hashes(root: Path, prefix: str = "") -> dict[str, str]:
    hashes: dict[str, str] = {}
    for file_path in sorted(root.rglob("*")):
        if file_path.is_file():
            relative_path = (prefix + str(file_path.relative_to(root))).replace("\\", "/")
            hashes[relative_path] = sha256_hex(file_path)
    return hashes


def run_python_json(python_path: Path, code: str) -> dict[str, str]:
    result = subprocess.run(
        [str(python_path), "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"Python command failed: {python_path}")
    return json.loads(result.stdout.strip())


def collect_runtime_info(venv_python: Path) -> dict[str, str]:
    payload = run_python_json(
        venv_python,
        (
            "import json, sys, torch; "
            "cuda = (torch.version.cuda or '').replace('.', ''); "
            "print(json.dumps({"
            "'python_version': sys.version.split()[0], "
            "'torch_version': torch.__version__, "
            "'cuda_tag': f\"cu{cuda}\" if cuda else 'cpu', "
            "'base_prefix': sys.base_prefix, "
            "'base_exec_prefix': sys.base_exec_prefix"
            "}))"
        ),
    )
    return {key: str(value) for key, value in payload.items()}


def _ignore_base_python_copy(source_dir: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    source_path = Path(source_dir)
    if source_path.name == "Lib" and "site-packages" in names:
        ignored.add("site-packages")
    for name in names:
        if name == "__pycache__":
            ignored.add(name)
    return ignored


def _ignore_venv_scripts(_source_dir: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        lower_name = name.lower()
        if lower_name.startswith("activate"):
            ignored.add(name)
        if lower_name in {"python.exe", "pythonw.exe"}:
            ignored.add(name)
    return ignored


def build_portable_python_runtime(venv_root: Path, runtime_python_root: Path, base_python_root: Path) -> None:
    if runtime_python_root.exists():
        shutil.rmtree(runtime_python_root)
    shutil.copytree(
        base_python_root,
        runtime_python_root,
        symlinks=False,
        ignore=_ignore_base_python_copy,
    )

    runtime_site_packages = runtime_python_root / "Lib" / "site-packages"
    runtime_site_packages.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        venv_root / "Lib" / "site-packages",
        runtime_site_packages,
        dirs_exist_ok=True,
        symlinks=False,
        ignore=shutil.ignore_patterns("__pycache__"),
    )

    venv_scripts = venv_root / "Scripts"
    if venv_scripts.exists():
        shutil.copytree(
            venv_scripts,
            runtime_python_root / "Scripts",
            dirs_exist_ok=True,
            symlinks=False,
            ignore=_ignore_venv_scripts,
        )


def verify_portable_runtime(runtime_root: Path, model_root: Path) -> None:
    python_path = runtime_root / "python" / "python.exe"
    if not python_path.exists():
        raise RuntimeError(f"Portable runtime is missing python.exe: {python_path}")
    env = os.environ.copy()
    env["HF_HOME"] = str(model_root.parent)
    env["HF_HUB_CACHE"] = str(model_root.parent / "hub")
    env["VOXCPM_MODEL_ID"] = str(model_root)
    result = subprocess.run(
        [
            str(python_path),
            "-c",
            "import torch, uvicorn, service.server; print('portable runtime import ok')",
        ],
        cwd=str(runtime_root),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "Portable runtime self-check failed.")
    print(f"  Portable runtime self-check: {result.stdout.strip() or 'ok'}")


args = parse_args()
source_install_root = args.source_install_root.resolve() if args.source_install_root is not None else INSTALL_DIR
source_model_dir = source_install_root / "models"

if args.source_install_root is None:
    print("=== Step 1: Running install_local.ps1 ===")
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)

    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(INSTALL_SCRIPT),
        "-InstallRoot",
        str(INSTALL_DIR),
        "-ModelCacheRoot",
        str(MODEL_DIR),
        "-UseHfMirror",
    ]
    print(f"Running: {' '.join(command)}")
    print("This will download models (~5GB) and install torch/CUDA. Please wait...")
    install_result = subprocess.run(command, cwd=str(BUILD_ROOT))
    if install_result.returncode != 0:
        print(f"ERROR: install_local.ps1 failed with code {install_result.returncode}")
        print(f"Check log: {INSTALL_DIR / 'install.log'}")
        sys.exit(1)
    print("Install complete.")
else:
    print("=== Step 1: Reusing existing VoxCPM installation ===")
    print(f"Source install root: {source_install_root}")

print("\n=== Step 2: Verifying installation ===")
venv_root = source_install_root / ".venv"
venv_python = venv_root / "Scripts" / "python.exe"
service_dir = source_install_root / "service"
start_script = source_install_root / "start_service.ps1"
model_root = source_model_dir / LOCAL_MODEL_DIRNAME

for path, label in [
    (venv_python, ".venv python"),
    (service_dir, "service dir"),
    (start_script, "start_service.ps1"),
    (model_root, "models/VoxCPM2-local"),
]:
    print(f"  {'OK' if path.exists() else 'MISSING'}: {label}")

if not venv_python.exists():
    print("ERROR: venv python not found. Cannot continue.")
    sys.exit(1)

runtime_info = collect_runtime_info(venv_python)
python_version = runtime_info["python_version"]
torch_version = runtime_info["torch_version"]
detected_cuda_tag = runtime_info["cuda_tag"]
base_python_root = Path(runtime_info["base_prefix"])
built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

print(f"  Python: {python_version}")
print(f"  Torch: {torch_version}")
print(f"  CUDA tag: {detected_cuda_tag}")
print(f"  Base Python: {base_python_root}")

if detected_cuda_tag != CUDA_TAG:
    print(f"ERROR: expected CUDA tag {CUDA_TAG}, but build environment produced {detected_cuda_tag}.")
    sys.exit(1)
if not base_python_root.exists():
    print(f"ERROR: base Python root not found: {base_python_root}")
    sys.exit(1)

print("\n=== Step 3: Building runtime zip ===")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
runtime_zip_path = OUTPUT_DIR / f"{RUNTIME_ID}.zip"
runtime_staging = BUILD_ROOT / "runtime-staging"
if runtime_staging.exists():
    shutil.rmtree(runtime_staging)
runtime_root = runtime_staging / "runtime"
runtime_root.mkdir(parents=True, exist_ok=True)

print("  Copying portable Python runtime ...")
build_portable_python_runtime(venv_root, runtime_root / "python", base_python_root)
print("  Copying service files ...")
shutil.copytree(service_dir, runtime_root / "service", symlinks=False)
shutil.copy2(start_script, runtime_root / "start_service.ps1")

healthcheck_path = runtime_root / "healthcheck.ps1"
healthcheck_path.write_text(
    '$r = Invoke-WebRequest -Uri "http://127.0.0.1:8808/health" -UseBasicParsing -TimeoutSec 5; exit ($r.StatusCode -ne 200)\n',
    encoding="utf-8",
)

verify_portable_runtime(runtime_root, model_root)

runtime_file_hashes = build_file_hashes(runtime_root, "runtime/")
runtime_package_size = sum(file_path.stat().st_size for file_path in runtime_root.rglob("*") if file_path.is_file())
runtime_manifest = {
    "runtime_id": RUNTIME_ID,
    "runtime_version": RUNTIME_REVISION,
    "target_os": "windows",
    "target_arch": "x64",
    "cuda_tag": CUDA_TAG,
    "min_driver_version": MIN_DRIVER,
    "python_version": python_version,
    "torch_version": torch_version,
    "model_id": "openbmb/VoxCPM2",
    "model_version": built_at[:10],
    "model_package_id": MODEL_PACKAGE_FILENAME.removesuffix(".zip"),
    "model_package_filename": MODEL_PACKAGE_FILENAME,
    "expected_layout_version": 1,
    "package_size": runtime_package_size,
    "file_hashes": runtime_file_hashes,
    "built_at": built_at,
}
(runtime_staging / "manifest.json").write_text(
    json.dumps(runtime_manifest, ensure_ascii=True, indent=2, sort_keys=True),
    encoding="utf-8",
)

print(f"  Creating {runtime_zip_path} ...")
with zipfile.ZipFile(runtime_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for file_path in sorted(runtime_staging.rglob("*")):
        if file_path.is_file():
            archive.write(file_path, str(file_path.relative_to(runtime_staging)).replace("\\", "/"))
print(f"  Runtime zip: {runtime_zip_path.stat().st_size / (1024 * 1024):.0f} MB")
print(f"  SHA256: {write_sha256(runtime_zip_path, runtime_zip_path.name)}")

print("\n=== Step 4: Building model zip ===")
model_zip_path = OUTPUT_DIR / MODEL_PACKAGE_FILENAME
model_staging = BUILD_ROOT / "model-staging"
if model_staging.exists():
    shutil.rmtree(model_staging)
models_target = model_staging / "models" / LOCAL_MODEL_DIRNAME
models_target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(model_root, models_target, symlinks=False)

model_file_hashes = build_file_hashes(model_staging / "models", "models/")
model_package_size = sum(file_path.stat().st_size for file_path in model_staging.rglob("*") if file_path.is_file())
model_manifest = {
    "model_id": "openbmb/VoxCPM2",
    "model_version": built_at[:10],
    "model_package_filename": MODEL_PACKAGE_FILENAME,
    "expected_model_dir": LOCAL_MODEL_DIRNAME,
    "package_size": model_package_size,
    "file_hashes": model_file_hashes,
    "built_at": built_at,
}
(model_staging / "model_manifest.json").write_text(
    json.dumps(model_manifest, ensure_ascii=True, indent=2, sort_keys=True),
    encoding="utf-8",
)

print(f"  Creating {model_zip_path} ...")
with zipfile.ZipFile(model_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for file_path in sorted(model_staging.rglob("*")):
        if file_path.is_file():
            archive.write(file_path, str(file_path.relative_to(model_staging)).replace("\\", "/"))
print(f"  Model zip: {model_zip_path.stat().st_size / (1024 * 1024):.0f} MB")
print(f"  SHA256: {write_sha256(model_zip_path, model_zip_path.name)}")

print("\n=== Build Complete ===")
print(f"Output directory: {OUTPUT_DIR}")
for output_path in sorted(OUTPUT_DIR.iterdir()):
    print(f"  {output_path.name}  ({output_path.stat().st_size / (1024 * 1024):.1f} MB)")
print("\nNext step: upload these files to ModelScope repository")
print("  Repo: borealis/oh-my-word-voxcpm2-runtime")
