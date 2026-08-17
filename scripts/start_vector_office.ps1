[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "The project virtual environment is missing."
}

Push-Location -LiteralPath $projectRoot
try {
    & $pythonExecutable -m application.host_watchdog --parent-pid $PID
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
