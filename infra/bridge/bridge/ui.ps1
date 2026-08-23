$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'bridge-lib.ps1')

New-Item -ItemType Directory -Path $script:StateDir -Force | Out-Null
$PID | Set-Content -LiteralPath $script:UiPidFile -Encoding ascii

function Get-DaemonPid {
    if (Test-Path -LiteralPath $script:ExecutorPidFile) {
        try { return [int]((Get-Content -LiteralPath $script:ExecutorPidFile -Raw).Trim()) } catch { return $null }
    }
    return $null
}

function Read-State {
    if (Test-Path -LiteralPath $script:StateFile) {
        try { return Get-Content -LiteralPath $script:StateFile -Raw | ConvertFrom-Json -AsHashtable } catch { return $null }
    }
    return $null
}

function Update-Display {
    param([hashtable]$State)
    if ($null -eq $State) {
        $statusLabel.Text = 'SIN DATOS'
        $detailBox.Text = 'No se pudo leer el estado.'
        return
    }
    $statusLabel.Text = $State.status
    $color = switch ($State.status) {
        'TRABAJANDO' { [System.Drawing.Color]::DarkOrange }
        'TERMINADO — ESPERANDO SEGUI' { [System.Drawing.Color]::ForestGreen }
        'DECISIÓN DE USUARIO REQUERIDA' { [System.Drawing.Color]::DarkRed }
        'ERROR' { [System.Drawing.Color]::Firebrick }
        'TAREA DISPONIBLE' { [System.Drawing.Color]::DodgerBlue }
        default { [System.Drawing.Color]::DimGray }
    }
    $statusLabel.ForeColor = $color
    $alarm = ''
    if ($State.status -eq 'TERMINADO — ESPERANDO SEGUI' -or $State.status -eq 'DECISIÓN DE USUARIO REQUERIDA') {
        $alarm = if ($State.alarmSilenced) { "Alarma: silenciada`n" } else { "Alarma: ACTIVA`n" }
    }
    $taskId = if ($State.taskId) { $State.taskId } else { '-' }
    $detailBox.Text = 'Proyecto: ' + $State.projectId + "`n" +
                      'TASK_ID: ' + $taskId + "`n" +
                      $alarm +
                      $State.statusDetail
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'ChatGPT/OpenCode — Ejecutor local'
$form.Size = New-Object System.Drawing.Size(560, 380)
$form.StartPosition = 'CenterScreen'
$form.MinimumSize = New-Object System.Drawing.Size(480, 320)
$form.BackColor = [System.Drawing.Color]::White

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Location = New-Object System.Drawing.Point(20, 20)
$statusLabel.Size = New-Object System.Drawing.Size(500, 40)
$statusLabel.Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
$statusLabel.Text = '...'
$form.Controls.Add($statusLabel)

$detailBox = New-Object System.Windows.Forms.TextBox
$detailBox.Location = New-Object System.Drawing.Point(20, 70)
$detailBox.Size = New-Object System.Drawing.Size(500, 120)
$detailBox.Multiline = $true
$detailBox.ReadOnly = $true
$detailBox.BackColor = [System.Drawing.Color]::WhiteSmoke
$detailBox.Font = New-Object System.Drawing.Font('Consolas', 10)
$form.Controls.Add($detailBox)

function New-Button {
    param([string]$Text, [int]$X, [int]$Y, [int]$W, [int]$H, [scriptblock]$Action)
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $Text
    $btn.Location = New-Object System.Drawing.Point($X, $Y)
    $btn.Size = New-Object System.Drawing.Size($W, $H)
    $btn.Add_Click($Action)
    $form.Controls.Add($btn)
    return $btn
}

New-Button -Text 'Procesar tarea pendiente' -X 20 -Y 210 -W 260 -H 40 -Action {
    Enqueue-Command 'process'
    $statusLabel.Text = 'Orden enviada: Procesar'
}
New-Button -Text 'Silenciar alarma' -X 290 -Y 210 -W 230 -H 40 -Action {
    Enqueue-Command 'mute'
    $statusLabel.Text = 'Orden enviada: Silenciar'
}
New-Button -Text 'Ver estado' -X 20 -Y 260 -W 260 -H 40 -Action {
    $st = Read-State
    Update-Display -State $st
    if ($null -ne $st) {
        [void][System.Windows.Forms.MessageBox]::Show((Get-StatusText -State $st -Cfg (Get-Config)), 'Estado del ejecutor', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)
    }
}
New-Button -Text 'Detener ejecutor' -X 290 -Y 260 -W 230 -H 40 -Action {
    Enqueue-Command 'stop'
    $statusLabel.Text = 'Orden enviada: Detener'
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 500
$timer.Add_Tick({
    $daemonPid = Get-DaemonPid
    $alive = $false
    if ($daemonPid) { $alive = [bool](Get-Process -Id $daemonPid -ErrorAction SilentlyContinue) }
    if (-not $alive) {
        $timer.Stop()
        $statusLabel.Text = 'EJECUTOR DETENIDO'
        $statusLabel.ForeColor = [System.Drawing.Color]::DimGray
        $detailBox.Text = 'El daemon del ejecutor ya no está corriendo. Esta ventana se cerrará.'
        Start-Sleep -Seconds 2
        $form.Close()
        return
    }
    Update-Display -State (Read-State)
})
$timer.Start()

$st0 = Read-State
if ($null -ne $st0) { Update-Display -State $st0 }

[void][System.Windows.Forms.Application]::Run($form)
Remove-Item -LiteralPath $script:UiPidFile -Force -ErrorAction SilentlyContinue
