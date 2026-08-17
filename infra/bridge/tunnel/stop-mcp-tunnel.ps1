$ErrorActionPreference = 'Continue'

$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $base 'tunnel-client\tunnel.pid'
$stopped = $false

if (Test-Path -LiteralPath $pidFile) {
    try {
        $pidVal = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim())
        $p = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
        if ($p -and $p.ProcessName -eq 'tunnel-client') {
            Stop-Process -Id $pidVal -Force
            Write-Output ('tunnel-client detenido (PID ' + $pidVal + ')')
            $stopped = $true
        }
        else {
            Write-Output ('no habia proceso tunnel-client vivo para PID ' + $pidVal)
        }
    }
    catch {}
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

$serverProcs = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'mcp[\\/]mcp-server\.py' })
foreach ($sp in $serverProcs) {
    try {
        Stop-Process -Id $sp.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Output ('MCP server detenido (PID ' + $sp.ProcessId + ')')
        $stopped = $true
    }
    catch {}
}

if (-not $stopped) {
    Write-Output 'No habia procesos del tunnel MCP registrados.'
}
