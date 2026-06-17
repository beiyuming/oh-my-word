param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\OhMyWord\tts\voxcpm",
    [string]$ModelCacheRoot = "$env:LOCALAPPDATA\OhMyWord\tts\voxcpm\models",
    [string]$PythonExe = "py",
    [string]$PythonVersion = "-3.11",
    [string]$Device = "auto",
    [string]$TorchCudaIndexUrl = "https://download.pytorch.org/whl/cu130",
    [switch]$CpuOnly,
    [switch]$SkipCudaTorchInstall,
    [switch]$UseHfMirror
)

$ErrorActionPreference = "Stop"

function Normalize-PathArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $trimmed = $Value.Trim()
    if ($trimmed.Length -ge 2) {
        $first = $trimmed[0]
        $last = $trimmed[$trimmed.Length - 1]
        if (
            (($first -eq "'") -and ($last -eq "'")) -or
            (($first -eq '"') -and ($last -eq '"'))
        ) {
            return $trimmed.Substring(1, $trimmed.Length - 2)
        }
    }

    return $trimmed
}

$installPath = [System.IO.Path]::GetFullPath((Normalize-PathArgument $InstallRoot))
$modelCachePath = [System.IO.Path]::GetFullPath((Normalize-PathArgument $ModelCacheRoot))
$modelHubCachePath = Join-Path $modelCachePath "hub"
$localModelPath = Join-Path $modelCachePath "VoxCPM2-local"
$venvPath = Join-Path $installPath ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$logPath = Join-Path $installPath "install.log"
$serverDir = Join-Path $installPath "service"
$startScriptPath = Join-Path $installPath "start_service.ps1"
$modelCheckScriptPath = Join-Path $installPath "model_check.py"

function Escape-PowerShellSingleQuoted {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Replace("'", "''")
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Get-PythonRuntimeCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    try {
        $probeArgs = @()
        if ($Arguments.Count -gt 0) {
            $probeArgs += $Arguments
        }
        $probeArgs += @("-c", "import sys; print('{}.{}'.format(sys.version_info[0], sys.version_info[1]))")
        $probeOutput = & $FilePath @probeArgs 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }

        $versionText = ($probeOutput | Select-Object -Last 1).Trim()
        if ([string]::IsNullOrWhiteSpace($versionText)) {
            return $null
        }

        $versionParts = $versionText.Split('.')
        if ($versionParts.Length -lt 2) {
            return $null
        }

        $major = [int]$versionParts[0]
        $minor = [int]$versionParts[1]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Write-Host "Skipping Python runtime $Label because it resolves to Python $versionText"
            return $null
        }

        return [PSCustomObject]@{
            FilePath = $FilePath
            Arguments = $Arguments
            Label = $Label
            Version = $versionText
        }
    }
    catch {
        return $null
    }
}

function Resolve-PythonRuntime {
    $candidates = @(
        @{ FilePath = $PythonExe; Arguments = @($PythonVersion); Label = "$PythonExe $PythonVersion" },
        @{ FilePath = "py"; Arguments = @("-3.11"); Label = "py -3.11" },
        @{ FilePath = "py"; Arguments = @("-3.12"); Label = "py -3.12" },
        @{ FilePath = "py"; Arguments = @("-3"); Label = "py -3" },
        @{ FilePath = "python"; Arguments = @(); Label = "python" },
        @{ FilePath = "python3"; Arguments = @(); Label = "python3" }
    )

    $resolvedCandidates = @()
    $seenRuntimeKeys = @{}
    foreach ($candidate in $candidates) {
        $resolved = Get-PythonRuntimeCandidate -FilePath $candidate.FilePath -Arguments $candidate.Arguments -Label $candidate.Label
        if ($null -ne $resolved) {
            $runtimeKey = "$($resolved.FilePath)|$($resolved.Arguments -join ' ')"
            if (-not $seenRuntimeKeys.ContainsKey($runtimeKey)) {
                $seenRuntimeKeys[$runtimeKey] = $true
                $resolvedCandidates += $resolved
            }
        }
    }

    if ($resolvedCandidates.Count -eq 0) {
        throw "No suitable Python runtime found. Install Python 3.11 or newer, or make py/python available."
    }

    $selected = $resolvedCandidates[0]
    Write-Host "Selected Python runtime: $($selected.Label) ($($selected.Version))"
    return ,$resolvedCandidates
}

function New-VenvWithFallback {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$PythonRuntimes
    )

    $failureMessages = New-Object System.Collections.Generic.List[string]
    foreach ($pythonRuntime in $PythonRuntimes) {
        try {
            if (Test-Path -LiteralPath $venvPath) {
                Remove-Item -LiteralPath $venvPath -Recurse -Force -ErrorAction Stop
            }
            Write-Host "Using Python runtime: $($pythonRuntime.Label)"
            Invoke-Native $pythonRuntime.FilePath @($pythonRuntime.Arguments + @("-m", "venv", $venvPath))
            return $pythonRuntime
        }
        catch {
            $failureMessage = $_.Exception.Message
            $failureMessages.Add("$($pythonRuntime.Label): $failureMessage")
            Write-Host "Failed to create virtual environment with $($pythonRuntime.Label): $failureMessage"
            if (Test-Path -LiteralPath $venvPath) {
                try {
                    Remove-Item -LiteralPath $venvPath -Recurse -Force -ErrorAction Stop
                }
                catch {
                    throw "Failed to remove incomplete virtual environment at $venvPath after $($pythonRuntime.Label) failed: $($_.Exception.Message)"
                }
            }
            Write-Host "Trying next Python runtime candidate"
        }
    }

    throw "Unable to create virtual environment with any supported Python runtime. $($failureMessages -join ' | ')"
}

function Test-NvidiaGpuAvailable {
    $nvidiaSmi = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
    if ($null -eq $nvidiaSmi) {
        return $false
    }

    & $nvidiaSmi.Source -L | Out-Null
    return $LASTEXITCODE -eq 0
}

function ConvertTo-ProcessArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value.Length -eq 0) {
        return '""'
    }
    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $escaped = $Value.Replace('"', '\"')
    if ($escaped.EndsWith("\")) {
        $escaped = "$escaped\"
    }
    return '"' + $escaped + '"'
}

function Invoke-ResumableDownload {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [Parameter(Mandatory = $true)]
        [string]$Destination,

        [long]$ExpectedBytes = 0
    )

    $destinationDir = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    $curl = Get-Command "curl.exe" -ErrorAction SilentlyContinue
    if ($null -eq $curl) {
        throw "curl.exe is required for resumable model downloads."
    }

    $existingDownload = Get-Item -LiteralPath $Destination -ErrorAction SilentlyContinue
    if ($null -ne $existingDownload) {
        if (($ExpectedBytes -gt 0) -and ($existingDownload.Length -eq $ExpectedBytes)) {
            Write-Host "Using existing completed file: $Destination"
            return
        }
        if (($ExpectedBytes -eq 0) -and ($existingDownload.Length -gt 0)) {
            Write-Host "Using existing file: $Destination"
            return
        }
    }

    Write-Host "Downloading $Url"
    $maxAttempts = 20
    $noProgressTimeoutSeconds = 120
    $progressPollSeconds = 10
    $curlArgs = @(
        "-L",
        "--fail",
        "--retry",
        "5",
        "--retry-delay",
        "5",
        "--retry-all-errors",
        "--connect-timeout",
        "30",
        "--speed-time",
        "60",
        "--speed-limit",
        "1024",
        "-C",
        "-",
        "-o",
        $Destination,
        $Url
    )
    $processArguments = ($curlArgs | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " "

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        Write-Host "Download attempt $attempt/$maxAttempts"
        $curlProcess = New-Object System.Diagnostics.Process
        $curlProcess.StartInfo.FileName = $curl.Source
        $curlProcess.StartInfo.Arguments = $processArguments
        $curlProcess.StartInfo.UseShellExecute = $false
        $curlProcess.StartInfo.CreateNoWindow = $true
        [void]$curlProcess.Start()

        $timedOut = $false
        $lastObservedItem = Get-Item -LiteralPath $Destination -ErrorAction SilentlyContinue
        if ($null -eq $lastObservedItem) {
            $lastObservedLength = 0
        } else {
            $lastObservedLength = $lastObservedItem.Length
        }
        $lastProgressAt = Get-Date
        while (-not $curlProcess.WaitForExit($progressPollSeconds * 1000)) {
            $currentItem = Get-Item -LiteralPath $Destination -ErrorAction SilentlyContinue
            if ($null -eq $currentItem) {
                $currentLength = 0
            } else {
                $currentLength = $currentItem.Length
            }

            if ($currentLength -gt $lastObservedLength) {
                $lastObservedLength = $currentLength
                $lastProgressAt = Get-Date
                Write-Host "Downloaded bytes: $lastObservedLength"
            }

            if (((Get-Date) - $lastProgressAt).TotalSeconds -ge $noProgressTimeoutSeconds) {
                Write-Host "Download attempt made no progress for $noProgressTimeoutSeconds seconds"
                Stop-Process -Id $curlProcess.Id -Force -ErrorAction SilentlyContinue
                [void]$curlProcess.WaitForExit(10000)
                $exitCode = 124
                $timedOut = $true
                break
            }
        }

        if (-not $timedOut) {
            $curlProcess.Refresh()
            $exitCode = $curlProcess.ExitCode
        }

        if ($exitCode -eq 0) {
            break
        }

        if ($attempt -ge $maxAttempts) {
            throw "Command failed ($exitCode): $($curl.Source) $($curlArgs -join ' ')"
        }

        Write-Host "Download attempt failed with exit code $exitCode; retrying in 5 seconds"
        Start-Sleep -Seconds 5
    }

    $downloaded = Get-Item -LiteralPath $Destination -ErrorAction Stop
    if ($downloaded.Length -le 0) {
        throw "Downloaded file is empty: $Destination"
    }
    if (($ExpectedBytes -gt 0) -and ($downloaded.Length -ne $ExpectedBytes)) {
        throw "Downloaded file has unexpected size: $Destination ($($downloaded.Length) bytes, expected $ExpectedBytes)"
    }
}

New-Item -ItemType Directory -Force -Path $installPath | Out-Null
New-Item -ItemType Directory -Force -Path $modelHubCachePath | Out-Null
Start-Transcript -Path $logPath -Append | Out-Null

try {
    $env:HF_HOME = $modelCachePath
    $env:HF_HUB_CACHE = Join-Path $modelCachePath "hub"
    $modelHubCachePath = $env:HF_HUB_CACHE
    Write-Host "VoxCPM install root: $installPath"
    Write-Host "VoxCPM model cache: $modelCachePath"

    if (-not (Test-Path -LiteralPath $venvPython)) {
        $pythonRuntimes = @(Resolve-PythonRuntime)
        [void](New-VenvWithFallback -PythonRuntimes $pythonRuntimes)
    }
    else {
        Write-Host "Using existing virtual environment: $venvPython"
    }

    Invoke-Native $venvPython -m pip install --upgrade pip wheel "setuptools<82"
    $nvidiaGpuAvailable = Test-NvidiaGpuAvailable
    Write-Host "NVIDIA GPU available: $nvidiaGpuAvailable"

    if ($nvidiaGpuAvailable -and -not $CpuOnly -and -not $SkipCudaTorchInstall) {
        try {
            Write-Host "Installing CUDA PyTorch from $TorchCudaIndexUrl"
            Invoke-Native $venvPython -m pip install --upgrade --force-reinstall torch torchaudio --index-url $TorchCudaIndexUrl
        }
        catch {
            Write-Host "CUDA PyTorch install failed: $($_.Exception.Message)"
            Write-Host "Falling back to CPU torch"
        }
    }

    Invoke-Native $venvPython -m pip install -r "$PSScriptRoot\requirements.txt"

    if (Test-Path -LiteralPath $serverDir) {
        Remove-Item -LiteralPath $serverDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $serverDir | Out-Null
    $servicePayloadFiles = @(
        "server.py",
        "engine.py",
        "requirements.txt",
        "README.md"
    )
    foreach ($servicePayloadFile in $servicePayloadFiles) {
        Copy-Item -Recurse -Force (Join-Path $PSScriptRoot $servicePayloadFile) (Join-Path $serverDir $servicePayloadFile)
    }
    Set-Content -LiteralPath (Join-Path $serverDir "__init__.py") -Value "" -Encoding UTF8
    $copiedServerPath = Join-Path $serverDir "server.py"
    if (-not (Select-String -LiteralPath $copiedServerPath -Pattern "synthesize_stream" -Quiet)) {
        throw "Copied VoxCPM service does not expose synthesize_stream: $copiedServerPath"
    }

    if ($UseHfMirror) {
        $env:HF_ENDPOINT = "https://hf-mirror.com"
        $env:HF_HUB_DISABLE_XET = "1"
    }
    $runtimeModelId = "openbmb/VoxCPM2"
    $cudaAvailable = (& $venvPython -c "import torch; print('1' if torch.cuda.is_available() else '0')").Trim() -eq "1"
    Write-Host "CUDA available: $cudaAvailable"
    $tritonAvailable = (& $venvPython -c "import importlib.util; print('1' if importlib.util.find_spec('triton') else '0')").Trim() -eq "1"
    Write-Host "Triton available: $tritonAvailable"

    if ($CpuOnly) {
        $env:VOXCPM_DEVICE = "cpu"
        $env:VOXCPM_OPTIMIZE = "0"
    } else {
        if ($Device -eq "auto" -and -not $cudaAvailable) {
            if ($nvidiaGpuAvailable) {
                Write-Host "NVIDIA GPU detected, but CUDA PyTorch is unavailable. Falling back to CPU torch"
            }
            $env:VOXCPM_DEVICE = "cpu"
            $env:VOXCPM_OPTIMIZE = "0"
        } else {
            $env:VOXCPM_DEVICE = $Device
        }

        if ($cudaAvailable -and -not $tritonAvailable) {
            Write-Host "Triton is not available; disabling VoxCPM optimize"
            $env:VOXCPM_OPTIMIZE = "0"
        }
        if (-not $env:VOXCPM_OPTIMIZE -and $cudaAvailable -and $tritonAvailable) {
            $env:VOXCPM_OPTIMIZE = "1"
        }
    }

    if ($UseHfMirror) {
        Write-Host "Preparing VoxCPM model from model download mirrors: $localModelPath"
        New-Item -ItemType Directory -Force -Path $localModelPath | Out-Null
        $mirrorBaseUrls = @(
            "https://www.modelscope.cn/models/OpenBMB/VoxCPM2/resolve/master",
            "https://hf-mirror.com/openbmb/VoxCPM2/resolve/main"
        )
        $mirrorFiles = @(
            ".gitattributes",
            "README.md",
            "audiovae.pth",
            "config.json",
            "model.safetensors",
            "special_tokens_map.json",
            "tokenization_voxcpm2.py",
            "tokenizer.json",
            "tokenizer_config.json"
        )
        $mirrorFileSizes = @{
            "audiovae.pth" = 376951122
            "model.safetensors" = 4580080592
        }
        foreach ($fileName in $mirrorFiles) {
            $destinationPath = Join-Path $localModelPath $fileName
            $expectedBytes = 0
            if ($mirrorFileSizes.ContainsKey($fileName)) {
                $expectedBytes = [long]$mirrorFileSizes[$fileName]
            }

            $downloaded = $false
            foreach ($baseUrl in $mirrorBaseUrls) {
                $sourceUrl = "$baseUrl/$fileName"
                Write-Host "Trying model download source: $sourceUrl"
                try {
                    Invoke-ResumableDownload $sourceUrl $destinationPath $expectedBytes
                    $downloaded = $true
                    break
                }
                catch {
                    Write-Host "Model download source failed: $($_.Exception.Message)"
                    if ($baseUrl -eq $mirrorBaseUrls[-1]) {
                        throw
                    }
                }
            }

            if (-not $downloaded) {
                throw "Failed to download model file: $fileName"
            }
        }
        $runtimeModelId = $localModelPath
    }

    $env:VOXCPM_MODEL_ID = $runtimeModelId
    $escapedVenvPython = Escape-PowerShellSingleQuoted $venvPython
    $escapedInstallPath = Escape-PowerShellSingleQuoted $installPath
    $escapedModelCachePath = Escape-PowerShellSingleQuoted $modelCachePath
    $escapedModelHubCachePath = Escape-PowerShellSingleQuoted $modelHubCachePath
    $escapedRuntimeModelId = Escape-PowerShellSingleQuoted $runtimeModelId
    $startScript = @"
`$ErrorActionPreference = "Stop"
`$env:HF_HOME = '$escapedModelCachePath'
`$env:HF_HUB_CACHE = '$escapedModelHubCachePath'
`$env:VOXCPM_MODEL_ID = '$escapedRuntimeModelId'
`$env:VOXCPM_DEVICE = "$($env:VOXCPM_DEVICE)"
`$env:VOXCPM_OPTIMIZE = "$($env:VOXCPM_OPTIMIZE)"
Set-Location -LiteralPath '$escapedInstallPath'
& '$escapedVenvPython' -m uvicorn service.server:app --host 127.0.0.1 --port 8808
"@
    Set-Content -LiteralPath $startScriptPath -Value $startScript -Encoding UTF8

    $modelCheck = @"
import traceback
from voxcpm import VoxCPM
import os
device = os.environ.get("VOXCPM_DEVICE", "auto")
optimize = os.environ.get("VOXCPM_OPTIMIZE", "0") != "0"
model_id = os.environ.get("VOXCPM_MODEL_ID", "openbmb/VoxCPM2")
try:
    VoxCPM.from_pretrained(model_id, load_denoiser=False, device=device, optimize=optimize)
    print("VoxCPM model check completed")
except Exception:
    traceback.print_exc()
    raise
"@
    Set-Content -LiteralPath $modelCheckScriptPath -Value $modelCheck -Encoding UTF8
    Invoke-Native $venvPython $modelCheckScriptPath
    Write-Host "VoxCPM local setup completed: $installPath"
    Write-Host "VoxCPM start script: $startScriptPath"
    Write-Host "Install log: $logPath"
}
finally {
    Stop-Transcript | Out-Null
}
