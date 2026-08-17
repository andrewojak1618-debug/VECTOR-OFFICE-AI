[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateRange(10, 300)]
    [int]$DelaySeconds = 20,
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$taskName = "Vector Office AI"
$startScript = (Resolve-Path -LiteralPath (
    Join-Path $PSScriptRoot "start_vector_office.ps1"
)).Path
$powerShellExecutable = Join-Path $PSHOME "powershell.exe"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""

$action = New-ScheduledTaskAction `
    -Execute $powerShellExecutable `
    -Argument $arguments `
    -WorkingDirectory (Split-Path -Parent $startScript)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$trigger.Delay = "PT${DelaySeconds}S"
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Starts local WirePod supervision and Vector Office AI."

if ($PSCmdlet.ShouldProcess($taskName, "Register scheduled startup task")) {
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
    Write-Output "Scheduled task '$taskName' installed for $currentUser."

    if ($StartNow) {
        Start-ScheduledTask -TaskName $taskName
        Write-Output "Scheduled task '$taskName' started."
    }
}
