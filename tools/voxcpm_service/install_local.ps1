param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\OhMyWord\voxcpm",
    [string]$PythonExe = "py",
    [string]$PythonVersion = "-3.11",
    [string]$Device = "auto",
    [switch]$CpuOnly,
    [switch]$UseHfMirror
)

$ErrorActionPreference = "Stop"
$installPath = [System.IO.Path]::GetFullPath($InstallRoot)
$venvPath = Join-Path $installPath ".venv"
$logPath = Join-Path $installPath "install.log"
$serverDir = Join-Path $installPath "service"

New-Item -ItemType Directory -Force -Path $installPath | Out-Null
Start-Transcript -Path $logPath -Append | Out-Null

try {
    if (-not (Test-Path -LiteralPath $venvPath)) {
        & $PythonExe $PythonVersion -m venv $venvPath
    }

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install -r "$PSScriptRoot\requirements.txt"

    New-Item -ItemType Directory -Force -Path $serverDir | Out-Null
    Copy-Item -Force "$PSScriptRoot\server.py" $serverDir
    Copy-Item -Force "$PSScriptRoot\engine.py" $serverDir
    Copy-Item -Force "$PSScriptRoot\requirements.txt" $serverDir
    Copy-Item -Force "$PSScriptRoot\README.md" $serverDir

    if ($UseHfMirror) {
        $env:HF_ENDPOINT = "https://hf-mirror.com"
    }
    if ($CpuOnly) {
        $env:VOXCPM_DEVICE = "cpu"
        $env:VOXCPM_OPTIMIZE = "0"
    } else {
        $env:VOXCPM_DEVICE = $Device
        if (-not $env:VOXCPM_OPTIMIZE) {
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
    & $venvPython -c $modelCheck
    Write-Host "VoxCPM local setup completed: $installPath"
    Write-Host "Install log: $logPath"
}
finally {
    Stop-Transcript | Out-Null
}
