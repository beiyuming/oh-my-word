param(
    [string]$EntryPoint = "main.py",
    [string]$Name = "oh-my-word-py"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$preferredPython = Join-Path $env:LOCALAPPDATA "Python\\pythoncore-3.11-64\\python.exe"
$launcher = $null
$pythonArgs = @()

if (Test-Path $preferredPython) {
    $launcher = @{
        Source = $preferredPython
        Name = "python311"
    }
}
else {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $launcher) {
        $launcher = Get-Command python -ErrorAction SilentlyContinue
    }

    if ($null -eq $launcher) {
        throw "Could not find a usable Python launcher."
    }

    if ($launcher.Name -eq "py") {
        $pythonArgs += "-3.11"
    }
}

$pythonArgs += @(
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--windowed",
    "--name",
    $Name,
    "--add-data",
    "data;data",
    "--add-data",
    "storage;storage",
    $EntryPoint
)

Push-Location $projectRoot
try {
    & $launcher.Source @pythonArgs
}
finally {
    Pop-Location
}
