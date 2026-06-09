param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\OhMyWord\voxcpm",
    [string]$PythonExe = "py",
    [string]$PythonVersion = "-3.11",
    [string]$Device = "auto",
    [string]$TorchCudaIndexUrl = "https://download.pytorch.org/whl/cu130",
    [switch]$CpuOnly,
    [switch]$SkipCudaTorchInstall,
    [switch]$UseHfMirror
)

$ErrorActionPreference = "Stop"
$installPath = [System.IO.Path]::GetFullPath($InstallRoot)
$venvPath = Join-Path $installPath ".venv"
$logPath = Join-Path $installPath "install.log"
$serverDir = Join-Path $installPath "service"

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

function Test-NvidiaGpuAvailable {
    $nvidiaSmi = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
    if ($null -eq $nvidiaSmi) {
        return $false
    }

    & $nvidiaSmi.Source -L | Out-Null
    return $LASTEXITCODE -eq 0
}

New-Item -ItemType Directory -Force -Path $installPath | Out-Null
Start-Transcript -Path $logPath -Append | Out-Null

try {
    if (-not (Test-Path -LiteralPath $venvPath)) {
        Invoke-Native $PythonExe $PythonVersion -m venv $venvPath
    }

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
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

    New-Item -ItemType Directory -Force -Path $serverDir | Out-Null
    Copy-Item -Force "$PSScriptRoot\server.py" $serverDir
    Copy-Item -Force "$PSScriptRoot\engine.py" $serverDir
    Copy-Item -Force "$PSScriptRoot\requirements.txt" $serverDir
    Copy-Item -Force "$PSScriptRoot\README.md" $serverDir

    if ($UseHfMirror) {
        $env:HF_ENDPOINT = "https://hf-mirror.com"
    }
    $cudaAvailable = (& $venvPython -c "import torch; print('1' if torch.cuda.is_available() else '0')").Trim() -eq "1"
    Write-Host "CUDA available: $cudaAvailable"

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
        if (-not $env:VOXCPM_OPTIMIZE -and $env:VOXCPM_DEVICE -like "cuda*") {
            $env:VOXCPM_OPTIMIZE = "1"
        }
    }

    $modelCheck = @"
from voxcpm import VoxCPM
import os
device = os.environ.get("VOXCPM_DEVICE", "auto")
optimize = os.environ.get("VOXCPM_OPTIMIZE", "1") != "0"
VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, device=device, optimize=optimize)
print("VoxCPM model check completed")
"@
    Invoke-Native $venvPython -c $modelCheck
    Write-Host "VoxCPM local setup completed: $installPath"
    Write-Host "Install log: $logPath"
}
finally {
    Stop-Transcript | Out-Null
}
