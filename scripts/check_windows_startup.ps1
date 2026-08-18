[CmdletBinding()]
param(
    [string]$TaskName = "Vector Office AI",
    [ValidateRange(1, 30)]
    [int]$TimeoutSeconds = 3,
    [switch]$AllowReady
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$checks = [System.Collections.Generic.List[object]]::new()

function Add-StartupCheck {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    $checks.Add([PSCustomObject]@{
        Status = if ($Passed) { "PASS" } else { "FAIL" }
        Check = $Name
        Detail = $Detail
    })
}

function Test-LocalEndpoint {
    param([string]$Uri)

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -Method Get `
            -UseBasicParsing `
            -TimeoutSec $TimeoutSeconds
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Get-MatchingProcessCount {
    param([string]$CommandPattern)

    $matches = @(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $_.CommandLine -like $CommandPattern })
    $matchingIds = @($matches | ForEach-Object { $_.ProcessId })
    $roots = @($matches | Where-Object {
        $_.ParentProcessId -notin $matchingIds
    })
    return $roots.Count
}

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    Add-StartupCheck "Scheduled task registered" $true $task.State

    $expectedScript = Join-Path $projectRoot (
        "scripts\start_vector_office_hidden.vbs"
    )
    $actionMatches = @($task.Actions | Where-Object {
        $_.Arguments -like "*$expectedScript*"
    }).Count -eq 1
    Add-StartupCheck "Scheduled action matches project" $actionMatches "configured"

    $stateAccepted = $task.State -eq "Running" -or (
        $AllowReady -and $task.State -eq "Ready"
    )
    Add-StartupCheck "Scheduled task state" $stateAccepted $task.State

    $acceptedResults = @(0, 267009)
    $resultAccepted = $taskInfo.LastTaskResult -in $acceptedResults
    Add-StartupCheck "Last task result" $resultAccepted ([string]$taskInfo.LastTaskResult)
}
catch {
    Add-StartupCheck "Scheduled task registered" $false "unavailable"
}

$wirePodAvailable = Test-LocalEndpoint "http://127.0.0.1:8080/api/get_logs"
$ollamaAvailable = Test-LocalEndpoint "http://127.0.0.1:11434/api/tags"
Add-StartupCheck "WirePod endpoint" $wirePodAvailable "local"
Add-StartupCheck "Ollama endpoint" $ollamaAvailable "local"

try {
    $watchdogCount = Get-MatchingProcessCount "*-m application.host_watchdog*"
    $mainPattern = "*$projectRoot*main.py*"
    $mainCount = Get-MatchingProcessCount $mainPattern
    $chipperCount = @(Get-Process chipper -ErrorAction SilentlyContinue).Count
    $requiredCount = if ($AllowReady) { 0 } else { 1 }
    $watchdogValid = if ($AllowReady) {
        $watchdogCount -le 1
    } else {
        $watchdogCount -eq $requiredCount
    }
    $mainValid = if ($AllowReady) { $mainCount -le 1 } else { $mainCount -eq 1 }
    Add-StartupCheck "Single host watchdog" $watchdogValid ([string]$watchdogCount)
    Add-StartupCheck "Single application process" $mainValid ([string]$mainCount)
    Add-StartupCheck "No duplicate WirePod process" ($chipperCount -le 1) (
        [string]$chipperCount
    )
}
catch {
    Add-StartupCheck "Process inspection" $false "unavailable"
}

$checks | Format-Table -AutoSize
$failed = @($checks | Where-Object { $_.Status -eq "FAIL" }).Count
if ($failed -gt 0) {
    Write-Output "Startup acceptance failed: $failed check(s)."
    exit 1
}

Write-Output "Startup acceptance passed. No secrets or conversation data were read."
exit 0
