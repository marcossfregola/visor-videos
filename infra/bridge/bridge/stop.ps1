$ErrorActionPreference = 'Continue'
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDir = Join-Path $baseDir 'state'

foreach ($name in @('executor', 'ui')) {
    $pidFile = Join-Path $stateDir ($name + '.pid')
    if (Test-Path -LiteralPath $pidFile) {
        $pidVal = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim())
        $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $pidVal -Force
            Write-Output ($name + ' detenido (PID ' + $pidVal + ')')
        }
        else {
            Write-Output ($name + ' no estaba corriendo (PID ' + $pidVal + ')')
        }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
    else {
        Write-Output ('Sin PID registrado para ' + $name)
    }
}
