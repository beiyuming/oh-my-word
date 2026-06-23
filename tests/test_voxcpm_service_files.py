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
    assert '@app.post("/synthesize_stream")' in server_source
    assert "StreamingResponse" in server_source
    assert "audio/L16" in server_source
    assert "127.0.0.1" in readme
    assert "not a cloud server" in readme
    assert "generate_streaming()" in readme
    assert "s16le" in readme


def test_voxcpm_local_installer_script_is_user_scoped_and_resumable() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "$env:LOCALAPPDATA\\OhMyWord\\tts\\voxcpm" in script
    assert "Start-Transcript" in script
    assert "requirements.txt" in script
    assert "VoxCPM.from_pretrained" in script
    assert "openbmb/VoxCPM2" in script


def test_voxcpm_local_installer_uses_user_selected_model_cache() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "ModelCacheRoot" in script
    assert "$env:LOCALAPPDATA\\OhMyWord\\tts\\voxcpm\\models" in script
    assert "$modelCachePath" in script
    assert "$env:HF_HOME = $modelCachePath" in script
    assert "$env:HF_HUB_CACHE = Join-Path $modelCachePath \"hub\"" in script
    assert "VoxCPM model cache:" in script


def test_voxcpm_local_installer_probes_available_python_runtimes() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "function Resolve-PythonRuntime" in script
    assert "function Get-PythonRuntimeCandidate" in script
    assert "py -3.11" in script
    assert "py -3.12" in script
    assert "python3" in script
    assert "No suitable Python runtime found" in script
    assert 'Label = "$PythonExe $PythonVersion"' in script
    assert "Selected Python runtime" in script


def test_voxcpm_local_installer_returns_flat_python_runtime_candidates() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "return ,$resolvedCandidates" not in script
    assert "$pythonRuntimes = @(Resolve-PythonRuntime)" not in script
    assert "$pythonRuntimes = Resolve-PythonRuntime" in script


def test_voxcpm_local_installer_accepts_empty_python_runtime_arguments() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "[string[]]$Arguments = @()" in script
    assert "[Parameter(Mandatory = $true)]`n        [string[]]$Arguments" not in script


def test_voxcpm_local_installer_retries_next_python_runtime_when_venv_creation_fails() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "function New-VenvWithFallback" in script
    assert "Failed to create virtual environment with" in script
    assert "Trying next Python runtime candidate" in script
    assert "Unable to create virtual environment with any supported Python runtime." in script


def test_voxcpm_local_installer_direct_downloads_mirror_large_files_to_local_model_dir() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "$localModelPath" in script
    assert "function Invoke-ResumableDownload" in script
    assert "curl.exe" in script
    assert "$curlArgs = @(" in script
    assert "function ConvertTo-ProcessArgument" in script
    assert '$processArguments = ($curlArgs | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " "' in script
    assert "$maxAttempts = 20" in script
    assert "$noProgressTimeoutSeconds = 120" in script
    assert "$progressPollSeconds = 10" in script
    assert "Start-Sleep -Seconds 5" in script
    assert "New-Object System.Diagnostics.Process" in script
    assert "$curlProcess.StartInfo.FileName = $curl.Source" in script
    assert "$curlProcess.StartInfo.Arguments = $processArguments" in script
    assert "[void]$curlProcess.Start()" in script
    assert "WaitForExit($progressPollSeconds * 1000)" in script
    assert "Get-Item -LiteralPath $Destination" in script
    assert "Using existing file: $Destination" in script
    assert "$curlProcess.Refresh()" in script
    assert "Download attempt made no progress for $noProgressTimeoutSeconds seconds" in script
    assert "Stop-Process -Id $curlProcess.Id -Force" in script
    assert "--retry-all-errors" in script
    assert "--connect-timeout" in script
    assert "--speed-time" in script
    assert "--speed-limit" in script
    assert "-C" in script
    assert "$mirrorFileSizes = @{" in script
    assert '"audiovae.pth" = 376951122' in script
    assert '"model.safetensors" = 4580080592' in script
    assert "https://www.modelscope.cn/models/OpenBMB/VoxCPM2/resolve/master" in script
    assert "https://hf-mirror.com/openbmb/VoxCPM2/resolve/main" in script
    assert "audiovae.pth" in script
    assert "model.safetensors" in script
    assert "$runtimeModelId = $localModelPath" in script
    assert '$env:VOXCPM_MODEL_ID = $runtimeModelId' in script
    assert 'VoxCPM.from_pretrained(model_id' in script


def test_voxcpm_local_installer_normalizes_quoted_path_arguments() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "function Normalize-PathArgument" in script
    assert "$first -eq \"'\"" in script
    assert "$first -eq '\"'" in script
    assert "Substring(1, $trimmed.Length - 2)" in script
    assert "Normalize-PathArgument $InstallRoot" in script
    assert "Normalize-PathArgument $ModelCacheRoot" in script


def test_voxcpm_local_installer_writes_start_script_with_model_cache() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "$startScriptPath" in script
    assert "start_service.ps1" in script
    assert "__init__.py" in script
    assert "HF_HOME" in script
    assert "HF_HUB_CACHE" in script
    assert "uvicorn" in script
    assert "service.server:app" in script
    assert "Set-Location -LiteralPath '$escapedInstallPath'" in script
    assert "Copy-Item -Recurse -Force" in script
    assert "Remove-Item -LiteralPath $serverDir -Recurse -Force" in script
    assert "$servicePayloadFiles = @(" in script
    assert '"server.py"' in script
    assert '"engine.py"' in script
    assert '"requirements.txt"' in script
    assert '"README.md"' in script
    assert '"install_local.ps1"' not in script[script.index("$servicePayloadFiles = @(") : script.index("$copiedServerPath")]
    assert "synthesize_stream" in script


def test_voxcpm_local_installer_script_checks_native_exit_codes() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "function Invoke-Native" in script
    assert "$LASTEXITCODE" in script
    assert script.count("Invoke-Native") >= 5
    assert "Command failed" in script


def test_voxcpm_local_installer_disables_optimize_without_cuda() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "torch.cuda.is_available()" in script
    assert "$cudaAvailable" in script
    assert '$env:VOXCPM_OPTIMIZE = "0"' in script
    assert "CUDA available" in script


def test_voxcpm_local_installer_prefers_cuda_torch_when_nvidia_is_present() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "TorchCudaIndexUrl" in script
    assert "https://download.pytorch.org/whl/cu130" in script
    assert "nvidia-smi" in script
    assert "torch torchaudio" in script
    assert "CUDA PyTorch install failed" in script
    assert "Falling back to CPU torch" in script


def test_voxcpm_local_installer_keeps_setuptools_compatible_with_torch() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "setuptools<82" in script
    assert "pip setuptools wheel" not in script


def test_voxcpm_local_installer_disables_cuda_optimize_without_triton() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "importlib.util.find_spec('triton')" in script
    assert "$tritonAvailable" in script
    assert "Triton available" in script
    assert "Triton is not available; disabling VoxCPM optimize" in script


def test_voxcpm_local_installer_logs_model_check_tracebacks() -> None:
    script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    assert "import traceback" in script
    assert "traceback.print_exc()" in script
    assert "except Exception:" in script
    assert "$modelCheckScriptPath" in script
    assert "model_check.py" in script
    assert "Invoke-Native $venvPython $modelCheckScriptPath" in script
    assert "-c $modelCheck" not in script


def test_voxcpm_service_defaults_to_non_optimized_runtime() -> None:
    engine_source = (SERVICE_DIR / "engine.py").read_text(encoding="utf-8")

    assert 'os.environ.get("VOXCPM_OPTIMIZE", "0")' in engine_source


def test_voxcpm_service_uses_supported_generate_arguments_for_badcase_retries() -> None:
    engine_source = (SERVICE_DIR / "engine.py").read_text(encoding="utf-8")

    assert "model.generate(" in engine_source
    assert "model.generate_streaming(" in engine_source
    assert "control=" not in engine_source
    assert 'VOXCPM_CFG_VALUE = _env_float("VOXCPM_CFG_VALUE", "1.5")' in engine_source
    assert (
        'VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD = _env_float("VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD", "4.0")'
        in engine_source
    )
    assert "cfg_value=VOXCPM_CFG_VALUE" in engine_source
    assert "inference_timesteps=VOXCPM_INFERENCE_TIMESTEPS" in engine_source
    assert "retry_badcase=VOXCPM_RETRY_BADCASE" in engine_source
    assert "retry_badcase_max_times=VOXCPM_RETRY_BADCASE_MAX_TIMES" in engine_source
    assert "retry_badcase_ratio_threshold=VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD" in engine_source


def test_voxcpm_service_advanced_parameters_are_environment_driven() -> None:
    engine_source = (SERVICE_DIR / "engine.py").read_text(encoding="utf-8")

    assert 'os.environ.get("VOXCPM_DEVICE", "auto")' in engine_source
    assert 'VOXCPM_INFERENCE_TIMESTEPS = _env_int("VOXCPM_INFERENCE_TIMESTEPS", "10")' in engine_source
    assert 'os.environ.get("VOXCPM_RETRY_BADCASE", "1")' in engine_source
    assert 'VOXCPM_RETRY_BADCASE_MAX_TIMES = _env_int("VOXCPM_RETRY_BADCASE_MAX_TIMES", "3")' in engine_source
    assert 'LEADING_SILENCE_SECONDS = _env_float("VOXCPM_LEADING_SILENCE_SECONDS", "0.12")' in engine_source
    assert 'TRAILING_SILENCE_SECONDS = _env_float("VOXCPM_TRAILING_SILENCE_SECONDS", "0.3")' in engine_source
    assert "inference_timesteps=VOXCPM_INFERENCE_TIMESTEPS" in engine_source
    assert "retry_badcase=VOXCPM_RETRY_BADCASE" in engine_source
    assert "retry_badcase_max_times=VOXCPM_RETRY_BADCASE_MAX_TIMES" in engine_source
    assert "retry_badcase_ratio_threshold=VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD" in engine_source


def test_voxcpm_service_optimize_falls_back_without_crashing_model_load() -> None:
    engine_source = (SERVICE_DIR / "engine.py").read_text(encoding="utf-8")

    assert "except Exception" in engine_source
    assert "optimize=False" in engine_source
    assert "VOXCPM_OPTIMIZE" in engine_source


def test_voxcpm_service_pads_audio_edges_to_protect_short_word_playback() -> None:
    engine_source = (SERVICE_DIR / "engine.py").read_text(encoding="utf-8")

    assert "LEADING_SILENCE_SECONDS" in engine_source
    assert "TRAILING_SILENCE_SECONDS" in engine_source
    assert "_pad_audio_edges" in engine_source
    assert "np.pad(" in engine_source
    assert "_silence_pcm_bytes(sample_rate, LEADING_SILENCE_SECONDS)" in engine_source
    assert "_silence_pcm_bytes(sample_rate, TRAILING_SILENCE_SECONDS)" in engine_source


def test_voxcpm_service_streams_s16le_pcm_chunks() -> None:
    engine_source = (SERVICE_DIR / "engine.py").read_text(encoding="utf-8")
    server_source = (SERVICE_DIR / "server.py").read_text(encoding="utf-8")

    assert "synthesize_pcm_chunks" in engine_source
    assert "np.clip" in engine_source
    assert "astype(\"<i2\"" in engine_source
    assert "X-OhMyWord-Sample-Rate" in server_source
    assert "X-OhMyWord-Sample-Format" in server_source
    assert "s16le" in server_source


def test_voxcpm_client_logs_streaming_diagnostics_and_fallback_reason() -> None:
    tts_source = (ROOT / "app" / "tts.py").read_text(encoding="utf-8")

    assert "VoxCPM stream first byte" in tts_source
    assert "VoxCPM stream prebuffer reached" in tts_source
    assert "VoxCPM stream generation finished" in tts_source
    assert "below real-time playback" in tts_source
    assert "does not support /synthesize_stream" in tts_source


def test_windows_installer_removes_legacy_voxcpm_setup_ui() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "Install local VoxCPM pronunciation engine" not in installer_script
    assert "VoxCPM engine folder" not in installer_script
    assert "VoxCPM model cache folder" not in installer_script
    assert "Use model download mirror" not in installer_script
    assert "RunVoxCpmSetup" not in installer_script
    assert "voxcpm_service.zip" not in installer_script


def test_pyinstaller_payload_includes_voxcpm_service_scripts_for_in_app_install() -> None:
    build_script = (ROOT / "build" / "build_exe.ps1").read_text(encoding="utf-8")
    spec_file = (ROOT / "oh-my-word-py.spec").read_text(encoding="utf-8")

    assert "$voxcpmServicePayloadFiles = @(" in build_script
    for file_name in ("install_local.ps1", "server.py", "engine.py", "requirements.txt", "README.md"):
        assert file_name in build_script
        assert f"tools\\\\voxcpm_service\\\\{file_name}" in spec_file
    assert "tools\\voxcpm_service;tools\\voxcpm_service" not in build_script
    assert "('tools\\\\voxcpm_service', 'tools\\\\voxcpm_service')" not in spec_file
    assert "tools/voxcpm_service" in spec_file or r"tools\\voxcpm_service" in spec_file


def test_voxcpm_payload_boundaries_exclude_heavy_runtime_artifacts() -> None:
    build_script = (ROOT / "build" / "build_exe.ps1").read_text(encoding="utf-8")
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")
    install_script = (SERVICE_DIR / "install_local.ps1").read_text(encoding="utf-8")

    for source in (build_script, installer_script):
        assert ".venv" not in source
        assert "model.safetensors" not in source
        assert "audiovae.pth" not in source
        assert "*.whl" not in source
        assert "hub" not in source[source.find("Compress-Archive") : source.find("Compress-Archive") + 500]
    assert "$voxcpmServicePayloadFiles" not in installer_script
    assert "voxcpm_service.zip" not in installer_script
    assert "pip install" in install_script
    assert "VoxCPM.from_pretrained" in install_script


def test_windows_installer_checks_running_app_before_replacing_payload() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "EnsureInstalledAppNotRunning(exePath)" in installer_script
    assert "Process.GetProcessesByName" in installer_script
    assert "process.MainModule.FileName" in installer_script
    assert "Close Oh My Word before installing or updating." in installer_script
    assert (
        "Directory.CreateDirectory(installRoot);\n"
        "            EnsureInstalledAppNotRunning(exePath);\n"
        "            RemoveInstalledFilesFromManifest(installRoot, manifestPath);"
    ) in installer_script


def test_windows_installer_uses_temp_staging_instead_of_tracked_build_dir() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "GetTempPath" in installer_script
    assert '"build\\installer"' not in installer_script


def test_windows_installer_uses_app_version_for_default_output_name() -> None:
    installer_script = (ROOT / "build" / "build_installer.ps1").read_text(encoding="utf-8")

    assert "Get-AppVersion" in installer_script
    assert "oh-my-word-setup-v$AppVersion.exe" in installer_script
    assert "Oh My Word Setup v$AppVersion" in installer_script
    assert "Install Oh My Word v$AppVersion" in installer_script


def test_stable_docs_describe_voxcpm_provider_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    settings_spec = (ROOT / "docs" / "specs" / "settings-and-storage.md").read_text(encoding="utf-8")
    tts_spec = (ROOT / "docs" / "specs" / "tray-hotkeys-tts.md").read_text(encoding="utf-8")
    packaging_spec = (ROOT / "docs" / "specs" / "packaging-runtime.md").read_text(encoding="utf-8")

    assert "tts_provider" in settings_spec
    assert "voxcpm_endpoint" in settings_spec
    assert "voxcpm_timeout_seconds" in settings_spec
    assert "voxcpm_install_root" in settings_spec
    assert "voxcpm_model_cache_root" in settings_spec
    assert "voxcpm_auto_start" in settings_spec
    assert "system_qt" in tts_spec
    assert "voxcpm_local" in tts_spec
    assert "synthesize_stream" in tts_spec
    assert "QAudioSink" in tts_spec
    assert "127.0.0.1" in tts_spec
    assert "使用时自动启动" in tts_spec
    assert "不静默下载" in tts_spec
    assert "VoxCPM 本地" in readme
    assert "导入 VoxCPM 运行时包" in readme
    assert "GitHub Release" in readme
    assert "Windows 10/11 x64" in readme
    assert "NVIDIA GPU" in readme
    assert "8 GB+ VRAM" in readme
    assert "15 GB+" in readme
    assert "下载并导入模型包" in readme
    assert "安装器不再提供 VoxCPM 的下载或安装入口" in readme
    assert "使用时自动启动" in readme
    assert "tts\\voxcpm\\models" in readme
    assert "service-only" in readme
    assert "voxcpm2-runtime-win-x64-cu130-r2.zip" in packaging_spec
    assert "runtime package" in packaging_spec or "运行时包" in packaging_spec
    assert "GitHub Release" in packaging_spec
    assert "下载并导入模型包" in packaging_spec
    assert "导入运行时包" in tts_spec
    assert "install_local.ps1" in packaging_spec
    assert "server.py" in packaging_spec
    assert "engine.py" in packaging_spec
    assert "runtime/python/python.exe" in packaging_spec
    assert "portable Python" in packaging_spec
    assert "不得整目录打包" in packaging_spec
    assert "应用内应支持四条路径" in packaging_spec
