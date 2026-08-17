[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [switch]$ConfirmRemoval
)

$ErrorActionPreference = "Stop"
$taskName = "Vector Office AI"

if (-not $ConfirmRemoval) {
    throw "Pass -ConfirmRemoval to remove the scheduled startup task."
}

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Output "Scheduled task '$taskName' is not installed."
    exit 0
}

if ($PSCmdlet.ShouldProcess($taskName, "Remove scheduled startup task")) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Output "Scheduled task '$taskName' removed."
}
