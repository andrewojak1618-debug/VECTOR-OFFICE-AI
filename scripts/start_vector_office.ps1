[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
$currentProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $PID"
$ownerProcessId = [int]$currentProcess.ParentProcessId

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "The project virtual environment is missing."
}

if ($ownerProcessId -le 0) {
    throw "The windowless task owner could not be identified."
}

Push-Location -LiteralPath $projectRoot
try {
    & $pythonExecutable -m application.host_watchdog --parent-pid $ownerProcessId
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
