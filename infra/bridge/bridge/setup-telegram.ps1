param(
    [Parameter(Mandatory = $true)][string]$Token,
    [switch]$ListChats
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-lib.ps1')

Save-TokenProtected -Token $Token
Write-Output 'Token guardado protegido con DPAPI (CurrentUser).'

Add-Type -AssemblyName System.Security
$stored = Get-TelegramToken
$me = Invoke-RestMethod -Uri ("https://api.telegram.org/bot" + $stored + "/getMe") -Method Get -TimeoutSec 30
if ($me.ok) {
    Write-Output ('Bot verificado: @' + $me.result.username + ' (id ' + $me.result.id + ')')
}
else {
    Write-Output 'ERROR: getMe fallo. Verifica el token.'
    exit 1
}

if ($ListChats) {
    $upd = Invoke-RestMethod -Uri ("https://api.telegram.org/bot" + $stored + "/getUpdates?timeout=2") -Method Get -TimeoutSec 30
    $found = $false
    foreach ($u in @($upd.result)) {
        if ($u.message) {
            $m = $u.message
            if ($m.chat.type -eq 'private') {
                $found = $true
                Write-Output ('CANDIDATO: nombre=' + $m.chat.first_name + ' username=' + $m.from.username + ' user_id=' + $m.from.id + ' chat_id=' + $m.chat.id + ' ultimo_texto=' + $m.text)
            }
        }
    }
    if (-not $found) {
        Write-Output 'No se encontraron chats privados. Envia /start al bot desde Telegram y reintenta.'
    }
}
