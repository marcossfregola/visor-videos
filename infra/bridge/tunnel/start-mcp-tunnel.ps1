$ErrorActionPreference = 'Stop'

$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$keyFile = Join-Path $base 'secrets\control-plane-api-key.dpapi'
$tc = Join-Path $base 'tunnel-client\tunnel-client.exe'
$profileFile = Join-Path $base 'tunnel-client\profiles\bridge-mcp.yaml'
$pidFile = Join-Path $base 'tunnel-client\tunnel.pid'
$logDir = Join-Path $base 'logs'
$outLog = Join-Path $logDir 'tunnel-client.out.log'
$errLog = Join-Path $logDir 'tunnel-client.err.log'
$healthFile = Join-Path $base 'tunnel-client\health.url'

if (-not (Test-Path -LiteralPath $keyFile)) { throw 'No existe secrets\control-plane-api-key.dpapi' }
if (-not (Test-Path -LiteralPath $tc)) { throw 'No existe tunnel-client.exe' }
if (-not (Test-Path -LiteralPath $profileFile)) { throw 'No existe el perfil bridge-mcp.yaml' }

Add-Type -AssemblyName System.Security
$hex = (Get-Content -LiteralPath $keyFile -Raw).Trim()
$keyBytes = New-Object byte[] ($hex.Length / 2)
for ($i = 0; $i -lt $hex.Length; $i += 2) {
    $keyBytes[$i / 2] = [Convert]::ToByte($hex.Substring($i, 2), 16)
}
$rawKey = [Security.Cryptography.ProtectedData]::Unprotect($keyBytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
$apiKey = ([Text.Encoding]::Unicode.GetString($rawKey)).Trim()
if ([string]::IsNullOrWhiteSpace($apiKey)) { throw 'Runtime API key vacia' }

$env:CONTROL_PLANE_API_KEY = $apiKey
$apiKey = $null
$rawKey = $null
$keyBytes = $null

if (Test-Path -LiteralPath $pidFile) {
    try {
        $oldPid = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim())
        $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($old -and $old.ProcessName -eq 'tunnel-client') {
            Stop-Process -Id $oldPid -Force
            Write-Output ('tunnel-client anterior detenido (PID ' + $oldPid + ')')
        }
    }
    catch {}
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$p = Start-Process -FilePath $tc -ArgumentList @('run', '--profile-file', ('"' + $profileFile + '"'), '--pid.file', ('"' + $pidFile + '"')) -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru

Start-Sleep -Seconds 8
if ($p.HasExited) {
    Write-Output ('ERROR: tunnel-client salio (exit ' + $p.ExitCode + '). Revisa logs.')
    exit 1
}
Write-Output ('tunnel-client iniciado. PID=' + $p.Id)
$health = if (Test-Path -LiteralPath $healthFile) { (Get-Content -LiteralPath $healthFile -Raw).Trim() } else { '(sin health.url aun)' }
Write-Output ('health base URL: ' + $health)
Write-Output ('readyz: ' + $health + '/readyz')
Write-Output ('detener: ' + (Join-Path $base 'stop-mcp-tunnel.ps1'))
