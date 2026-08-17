$ErrorActionPreference = 'Stop'
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDir = Join-Path $baseDir 'state'
$logDir = Join-Path $baseDir 'logs'
$oldWatcherPidFile = Join-Path $stateDir 'watcher.pid'
New-Item -ItemType Directory -Path $stateDir, $logDir -Force | Out-Null

if (Test-Path -LiteralPath $oldWatcherPidFile) {
    try {
        $oldPid = [int]((Get-Content -LiteralPath $oldWatcherPidFile -Raw).Trim())
        $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($proc) { Stop-Process -Id $oldPid -Force; Write-Output ('Watcher 0.2 anterior detenido (PID ' + $oldPid + ')') }
    }
    catch {}
    Remove-Item -LiteralPath $oldWatcherPidFile -Force -ErrorAction SilentlyContinue
}

$executor = Join-Path $baseDir 'executor.ps1'
$ui = Join-Path $baseDir 'ui.ps1'
$execOut = Join-Path $logDir 'executor.stdout.log'
$execErr = Join-Path $logDir 'executor.stderr.log'
$uiOut = Join-Path $logDir 'ui.stdout.log'
$uiErr = Join-Path $logDir 'ui.stderr.log'

$pExec = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $executor + '"')) -WindowStyle Hidden -RedirectStandardOutput $execOut -RedirectStandardError $execErr -PassThru
Start-Sleep -Seconds 3
if ($pExec.HasExited) {
    Write-Output 'ERROR: el ejecutor salio inmediatamente. Revisa logs.'
    exit 1
}
$pExec.Id | Set-Content -LiteralPath (Join-Path $stateDir 'executor.pid') -Encoding ascii
Write-Output ('Ejecutor iniciado. PID=' + $pExec.Id)

$pUi = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $ui + '"')) -WindowStyle Hidden -RedirectStandardOutput $uiOut -RedirectStandardError $uiErr -PassThru
Start-Sleep -Seconds 3
if ($pUi.HasExited) {
    Write-Output 'ERROR: la UI salio inmediatamente. Revisa logs.'
    exit 1
}
$pUi.Id | Set-Content -LiteralPath (Join-Path $stateDir 'ui.pid') -Encoding ascii
Write-Output ('UI iniciada. PID=' + $pUi.Id)

Write-Output ('Logs: ' + $logDir)
Write-Output ('Detener: ' + (Join-Path $baseDir 'stop.ps1'))
