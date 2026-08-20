param()

# CANCEL - Pruebas unitarias de la cancelación segura de tareas pendientes en el executor.
# Verifica Invoke-CancelPoll (available -> cancelled, ventana inbox, rechazos, idempotencia,
# estado global y trazabilidad). Usa directorios temporales y stubs; SIN Telegram real,
# SIN OpenCode, SIN tocar C:\prueba.

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-lib.ps1')

$script:Failures = 0
$script:TelegramSent = @()
$script:AlarmCalls = @()

function Send-TelegramActionable {
    param([string]$Text)
    $script:TelegramSent += $Text
}

function Send-TelegramMessage {
    param([string]$Text)
    $script:TelegramSent += $Text
}

function Invoke-Alarm {
    param([string]$Type)
    $script:AlarmCalls += $Type
}

function Assert-Equal {
    param($Actual, $Expected, [string]$Label)
    if ($Actual -eq $Expected) {
        Write-Host ('PASS ' + $Label)
    }
    else {
        Write-Host ('FAIL ' + $Label + ' esperado=[' + $Expected + '] obtenido=[' + $Actual + ']')
        $script:Failures++
    }
}

function Assert-True {
    param($Actual, [string]$Label)
    Assert-Equal $Actual $true $Label
}

function Assert-False {
    param($Actual, [string]$Label)
    Assert-Equal $Actual $false $Label
}

# ---- Stubs B3/AUTO_TECNICA: réplica determinista del autoarranque del executor ----
# Invoke-AutoStartLite reproduce la lógica real de executor.ps1::Invoke-AutoStart
# (misma secuencia de precondiciones Test-AutoExecutionPreconditions) pero NO ejecuta
# OpenCode real. Si llegara a intentar lanzar opencode, Start-OpenCodeRun falla el test.
$script:OpenCodeRunCalls = 0
$script:B3Facts = @{ branch = 'beta6'; head = 'c28ccf6942fd0b52fc1c84090f0a6df083b26488'; clean = $true; remoteUrl = 'https://github.com/x/y.git' }

function Get-GitRepoFacts {
    param([hashtable]$Proj)
    return $script:B3Facts
}

function Start-OpenCodeRun {
    param([hashtable]$Proj, [string]$Prompt, [string]$OutFile, [string]$ErrFile)
    $script:OpenCodeRunCalls++
    throw 'CANCEL: Start-OpenCodeRun no debe ejecutarse durante la simulacion'
}

function Invoke-AutoStartLite {
    param([hashtable]$State)
    # Misma lógica que executor.ps1::Invoke-AutoStart, sin Start-PendingTask real.
    if ($State.status -eq 'TRABAJANDO') { return }
    if ($State.status -eq 'DECISIÓN DE USUARIO REQUERIDA') { return }
    $task = Get-OldestAvailableTask -State $State
    if ($null -eq $task) { return }
    $mode = if ($task.executionMode) { [string]$task.executionMode } else { 'MANUAL' }
    if ($mode -ne 'AUTO_TECNICA') { return }
    $pre = Test-AutoExecutionPreconditions -State $State -Cfg $script:Cfg -Proj $script:Proj -Task $task
    if (-not $pre.ok) {
        Block-AutoExecution -State $State -Task $task -Reason $pre.reason
        return
    }
    $State.status = 'TRABAJANDO'
    $State.statusDetail = 'Ejecutando tarea ' + $task.taskId
    $State.taskId = $task.taskId
    $State.tasks[$task.taskId].status = 'running'
    $State.tasks[$task.taskId].startedAt = (Get-Date).ToUniversalTime().ToString('o')
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bridge-cancel-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$script:StateDir = Join-Path $tempRoot 'state'
$script:StateFile = Join-Path $script:StateDir 'state.json'
$script:LogDir = Join-Path $tempRoot 'logs'
$script:LogFile = Join-Path $script:LogDir 'bridge.log'
$script:InboxDir = Join-Path $script:StateDir 'inbox'
$script:ResolutionsDir = Join-Path $script:StateDir 'resolutions'
$script:AuditsDir = Join-Path $script:StateDir 'audits'
$script:AuditsHistoryDir = Join-Path $script:AuditsDir 'history'
$script:CancellationsDir = Join-Path $script:StateDir 'cancellations'
$script:CancellationsHistoryDir = Join-Path $script:CancellationsDir 'history'
$script:ReportsDir = Join-Path $tempRoot 'reports'
$script:ConfigFile = Join-Path $tempRoot 'config.json'
New-Item -ItemType Directory -Path $script:StateDir, $script:LogDir, $script:AuditsDir, $script:CancellationsDir -Force | Out-Null

$tempCfg = @{
    activeProjectId = 'visor-videos'
    projects = @(@{ projectId = 'visor-videos'; repo = 'x/y'; localRepo = 'C:\prueba'; issueControl = 1 })
    executor = @{ pollIntervalMs = 500; githubPollEverySec = 15; telegramPollTimeoutSec = 5; alarmAIntervalSec = 2; alarmBIntervalSec = 2; opencodeTimeoutMs = 900000; githubAuthor = 'marcossfregola' }
    telegram = @{ authorizedUserId = $null; authorizedChatId = $null }
}
Save-Config -Cfg $tempCfg
$script:Cfg = $tempCfg
$script:Proj = @{ projectId = 'visor-videos'; repo = 'x/y'; localRepo = 'C:\prueba'; issueControl = 1 }

function New-CancelState {
    param([string]$TaskId, [string]$Status, [hashtable]$TaskFields = @{})
    $task = @{ taskId = $TaskId; status = 'available'; body = 'x'; createdAt = '2026-08-17T00:00:00Z' }
    foreach ($k in $TaskFields.Keys) { $task[$k] = $TaskFields[$k] }
    return @{
        projectId = 'visor-videos'; status = $Status; statusDetail = ''; taskId = $TaskId
        commentId = $null; lastAlarmPlay = $null; alarmSilenced = $false; seenComments = @{}
        tasks = @{ $TaskId = $task }
        telegramOffset = 0
    }
}

function Write-CancelRequest {
    param([string]$TaskId, [string]$Reason)
    $payload = @{ task_id = $TaskId; reason = $Reason; created_at = '2026-08-17T00:05:00Z'; source = 'mcp' }
    New-Item -ItemType Directory -Path $script:CancellationsDir -Force | Out-Null
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:CancellationsDir ($TaskId + '.cancel.json')) -Encoding utf8
}

function Write-InboxTask {
    param([string]$TaskId, [string]$Prompt, [hashtable]$Extra = @{})
    $payload = @{ task_id = $TaskId; prompt = $Prompt; created_at = '2026-08-17T00:02:00Z'; source = 'mcp'; execution_mode = 'MANUAL' }
    foreach ($k in $Extra.Keys) { $payload[$k] = $Extra[$k] }
    New-Item -ItemType Directory -Path $script:InboxDir -Force | Out-Null
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:InboxDir ($TaskId + '.task.json')) -Encoding utf8
}

# ===== 1. cancel disponible independiente: available -> cancelled con trazabilidad =====
$state1 = New-CancelState 'cancel-t1' 'TAREA DISPONIBLE' @{ status = 'available' }
Save-State -State $state1
Write-CancelRequest 'cancel-t1' 'reemplazada por tarea nueva'
[void](Invoke-CancelPoll -State $state1)
Assert-Equal $state1.tasks['cancel-t1'].status 'cancelled' '1: available -> cancelled'
Assert-True ($null -ne $state1.tasks['cancel-t1'].cancelledAt) '1: persiste cancelledAt'
Assert-Equal $state1.tasks['cancel-t1'].cancelReason 'reemplazada por tarea nueva' '1: persiste cancelReason'
Assert-Equal $state1.tasks['cancel-t1'].cancelSource 'mcp' '1: persiste cancelSource=mcp'
Assert-True ($null -eq $state1.tasks['cancel-t1'].startedAt) '1: nunca se ejecuto (sin startedAt)'
Assert-True ($null -eq $state1.tasks['cancel-t1'].pid) '1: nunca se ejecuto (sin pid)'
Assert-True ($null -eq $state1.tasks['cancel-t1'].exitCode) '1: nunca se ejecuto (sin exitCode)'
Assert-Equal (Test-Path (Join-Path $script:CancellationsDir 'cancel-t1.cancel.json')) $false '1: solicitud consumida'
Assert-True (Test-Path (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t1.json')) '1: registro archivado en history'

# ===== 2. estado global SIN TAREA tras cancelar la unica available =====
Assert-Equal $state1.status 'SIN TAREA' '2: estado global -> SIN TAREA'
Assert-Equal $state1.taskId $null '2: taskId liberado'
Assert-Equal $state1.commentId $null '2: commentId liberado'

# ===== 3. si queda otra available, se selecciona la mas antigua =====
$state3 = New-CancelState 'cancel-t3a' 'TAREA DISPONIBLE' @{ status = 'available' }
$state3.tasks['cancel-t3ant'] = @{ taskId = 'cancel-t3ant'; status = 'available'; body = 'y'; createdAt = '2026-08-17T00:01:00Z' }
Save-State -State $state3
Write-CancelRequest 'cancel-t3a' 'descartada'
[void](Invoke-CancelPoll -State $state3)
Assert-Equal $state3.tasks['cancel-t3a'].status 'cancelled' '3: primera cancelada'
Assert-Equal $state3.status 'TAREA DISPONIBLE' '3: queda TAREA DISPONIBLE'
Assert-Equal $state3.taskId 'cancel-t3ant' '3: activa la mas antigua restante'

# ===== 4. cancel durante ventana inbox -> state: archiva y no materializa =====
# (la tarea aún NO está en state.json: está solo en inbox esperando materializarse)
$state4 = New-CancelState 'cancel-t4' 'SIN TAREA' @{ status = 'available' }
$state4.tasks.Remove('cancel-t4')
$state4.taskId = $null
Save-State -State $state4
Write-InboxTask 'cancel-t4' 'prompt obsoleto'
Write-CancelRequest 'cancel-t4' 'encolada por error'
[void](Invoke-CancelPoll -State $state4)
Assert-False (Test-Path (Join-Path $script:InboxDir 'cancel-t4.task.json')) '4: inbox eliminado (no se materializa)'
Assert-False $state4.tasks.ContainsKey('cancel-t4') '4: tarea nunca entro a state.json'
Assert-True (Test-Path (Join-Path $script:CancellationsHistoryDir 'inbox-cancel-t4.task.json')) '4: .task.json original conservado en history'
Assert-True (Test-Path (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t4.json')) '4: registro de solicitud archivado'
$hist4 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t4.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist4.outcome 'applied-inbox' '4: outcome applied-inbox'
Assert-True $hist4.inboxTaskPreserved '4: marca de payload conservado'

# ===== 5. reason vacio en la solicitud: el poll la procesa igual (la cliente ya valida; aqui solo se procesa) =====
# (la validacion del reason obligatorio es del MCP; el executor no valida texto)

# ===== 6. solicitud duplicada despues de aplicada: idempotente =====
$state6 = New-CancelState 'cancel-t6' 'SIN TAREA' @{ status = 'cancelled'; cancelledAt = '2026-08-17T00:06:00Z'; cancelReason = 'primera'; cancelSource = 'mcp' }
Save-State -State $state6
Write-CancelRequest 'cancel-t6' 'segunda'
[void](Invoke-CancelPoll -State $state6)
Assert-Equal $state6.tasks['cancel-t6'].status 'cancelled' '6: sigue cancelled'
Assert-Equal $state6.tasks['cancel-t6'].cancelReason 'primera' '6: no se sobrescribe el motivo original'
$hist6 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t6.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist6.outcome 'already-cancelled' '6: duplicada registrada como already-cancelled'

# ===== 7. task inexistente: rechazo conservador =====
$state7 = New-CancelState 'cancel-t7' 'SIN TAREA' @{}
$state7.tasks.Remove('cancel-t7')
Save-State -State $state7
Write-CancelRequest 'cancel-noexiste' 'motivo'
[void](Invoke-CancelPoll -State $state7)
$hist7 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-noexiste.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist7.outcome 'rejected-notfound' '7: rechazada (tarea inexistente)'

# ===== 8. TRABAJANDO nunca se cancela =====
$state8 = New-CancelState 'cancel-t8' 'TRABAJANDO' @{ status = 'running'; startedAt = '2026-08-17T00:03:00Z'; pid = 12345 }
Save-State -State $state8
Write-CancelRequest 'cancel-t8' 'no debe cancelarse'
[void](Invoke-CancelPoll -State $state8)
Assert-Equal $state8.tasks['cancel-t8'].status 'running' '8: TRABAJANDO sigue running'
Assert-Equal $state8.status 'TRABAJANDO' '8: estado global intacto'
$hist8 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t8.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist8.outcome 'rejected-working' '8: rechazada (TRABAJANDO)'

# ===== 9. done / failed / resolved / decision / auditada: rechazo =====
foreach ($case in @(
    @{ name = 'done'; fields = @{ status = 'done'; exitCode = 0 } },
    @{ name = 'failed'; fields = @{ status = 'failed'; exitCode = 1 } },
    @{ name = 'resolved'; fields = @{ status = 'resolved'; resolution = 'x' } },
    @{ name = 'decision'; fields = @{ status = 'decision'; decisionDetalle = 'elegir' } },
    @{ name = 'audited'; fields = @{ status = 'available'; auditedAt = '2026-08-17T00:07:00Z' } }
)) {
    $tid = 'cancel-t9-' + $case.name
    $st9 = New-CancelState $tid 'SIN TAREA' @{}
    foreach ($k in $case.fields.Keys) { $st9.tasks[$tid][$k] = $case.fields[$k] }
    Save-State -State $st9
    Write-CancelRequest $tid 'motivo'
    [void](Invoke-CancelPoll -State $st9)
    $expected = if ($case.name -eq 'audited') { 'rejected-audited' } else { 'rejected-state' }
    $hist9 = Get-Content (Join-Path $script:CancellationsHistoryDir ('cancel-' + $tid + '.json')) -Raw | ConvertFrom-Json -AsHashtable
    Assert-Equal $hist9.outcome $expected ('9: rechazo ' + $case.name)
}

# ===== 10. superseded / cadena (supersedesTaskId / supersededByTaskId): rechazo =====
foreach ($case in @(
    @{ name = 'superseded'; fields = @{ status = 'available'; supersededByTaskId = 't-nueva' } },
    @{ name = 'supersedesTaskId'; fields = @{ status = 'available'; supersedesTaskId = 't-anterior' } }
)) {
    $tid = 'cancel-t10-' + $case.name
    $st10 = New-CancelState $tid 'SIN TAREA' @{}
    foreach ($k in $case.fields.Keys) { $st10.tasks[$tid][$k] = $case.fields[$k] }
    Save-State -State $st10
    Write-CancelRequest $tid 'motivo'
    [void](Invoke-CancelPoll -State $st10)
    $hist10 = Get-Content (Join-Path $script:CancellationsHistoryDir ('cancel-' + $tid + '.json')) -Raw | ConvertFrom-Json -AsHashtable
    Assert-Equal $hist10.outcome 'rejected-chain' ('10: rechazo ' + $case.name)
}

# ===== 11. ternario: tarea en inbox con supersedes_task_id: rechazo y NO se borra el inbox =====
$state11 = New-CancelState 'cancel-t11' 'SIN TAREA' @{}
$state11.tasks.Remove('cancel-t11')
Save-State -State $state11
Write-InboxTask 'cancel-t11' 'correccion encadenada' @{ supersedes_task_id = 't-anterior' }
$inboxPath11 = Join-Path $script:InboxDir 'cancel-t11.task.json'
Write-CancelRequest 'cancel-t11' 'motivo'
[void](Invoke-CancelPoll -State $state11)
Assert-True (Test-Path -LiteralPath $inboxPath11) '11: tarea encadenada en inbox NO se borra'
$hist11 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t11.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist11.outcome 'rejected-chain' '11: rechazada (inbox con supersede)'

# ===== 12. persistencia: la solicitud pendiente se aplica tras un "reinicio" =====
$state12 = New-CancelState 'cancel-t12' 'TAREA DISPONIBLE' @{ status = 'available' }
Save-State -State $state12
Write-CancelRequest 'cancel-t12' 'se mantiene'
# reinicio con el mismo directorio: la solicitud sigue en disco
Assert-True (Test-Path (Join-Path $script:CancellationsDir 'cancel-t12.cancel.json')) '12: solicitud persistente en disco'
[void](Invoke-CancelPoll -State $state12)
Assert-Equal $state12.tasks['cancel-t12'].status 'cancelled' '12: aplicada tras reinicio'

# ===== 13. rejected-started: declaraciones defensivas ante posible inicio =====
$state13 = New-CancelState 'cancel-t13' 'TAREA DISPONIBLE' @{ status = 'available'; startedAt = '2026-08-17T00:08:00Z' }
Save-State -State $state13
Write-CancelRequest 'cancel-t13' 'motivo'
[void](Invoke-CancelPoll -State $state13)
Assert-Equal $state13.tasks['cancel-t13'].status 'available' '13: no se cancela si pudo comenzar'
$hist13 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t13.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist13.outcome 'rejected-started' '13: rechazada (posible inicio)'

# ===== 17. una tarea ya cancelled NUNCA es iniciada por el mecanismo AUTO_TECNICA =====
$script:OpenCodeRunCalls = 0
$state17 = New-CancelState 'cancel-t17' 'SIN TAREA' @{ status = 'cancelled'; cancelledAt = '2026-08-17T00:10:00Z'; cancelReason = 'ya obsoleta'; cancelSource = 'mcp'; executionMode = 'AUTO_TECNICA'; expectedBranch = 'beta6'; expectedHead = 'c28ccf6942fd0b52fc1c84090f0a6df083b26488'; requireCleanWorktree = $true }
Save-State -State $state17
Invoke-AutoStartLite -State $state17
Assert-Equal $state17.tasks['cancel-t17'].status 'cancelled' '17: tarea cancelled no pasa a running'
Assert-Equal $state17.status 'SIN TAREA' '17: el estado global no paso a TRABAJANDO'
Assert-True ($null -eq $state17.tasks['cancel-t17'].startedAt) '17: sin startedAt'
Assert-True ($null -eq $state17.tasks['cancel-t17'].pid) '17: sin pid'
Assert-Equal $script:OpenCodeRunCalls 0 '17: OpenCode no se lanzo'

# ===== 18. AUTO_TECNICA available con cancel pendiente: CancelPoll la cancela ANTES de AutoStart =====
# Reproduce el orden real del executor (executor.ps1): Invoke-CancelPoll ANTES de Invoke-AutoStart.
$script:OpenCodeRunCalls = 0
$state18 = New-CancelState 'cancel-t18' 'TAREA DISPONIBLE' @{ status = 'available'; executionMode = 'AUTO_TECNICA'; expectedBranch = 'beta6'; expectedHead = 'c28ccf6942fd0b52fc1c84090f0a6df083b26488'; requireCleanWorktree = $true }
Save-State -State $state18
# control: la tarea es genuinamente elegible para autoarranque (sin la cancelacion arrancaria)
$pre18 = Test-AutoExecutionPreconditions -State $state18 -Cfg $script:Cfg -Proj $script:Proj -Task $state18.tasks['cancel-t18']
Assert-True $pre18.ok '18: la tarea AUTO_TECNICA es elegible para autoarranque (precondiciones ok)'
# existe la solicitud durable de cancelación pendiente
Write-CancelRequest 'cancel-t18' 'descartar antes de arrancar'
Assert-True (Test-Path (Join-Path $script:CancellationsDir 'cancel-t18.cancel.json')) '18: solicitud pendiente presente'
# orden real del executor: primero la cancelación, luego el intento de autoarranque
[void](Invoke-CancelPoll -State $state18)
Invoke-AutoStartLite -State $state18
Assert-Equal $state18.tasks['cancel-t18'].status 'cancelled' '18: cancelada antes del autoarranque'
Assert-True ($null -eq $state18.tasks['cancel-t18'].startedAt) '18: sin startedAt'
Assert-True ($null -eq $state18.tasks['cancel-t18'].pid) '18: sin pid'
Assert-Equal $script:OpenCodeRunCalls 0 '18: OpenCode no se lanzo'
Assert-Equal $state18.status 'SIN TAREA' '18: SIN TAREA tras cancelar la unica disponible'
$hist18 = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-cancel-t18.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist18.outcome 'applied' '18: solicitud trazada (outcome=applied)'
Assert-Equal $hist18.reason 'descartar antes de arrancar' '18: traza conserva el motivo'

Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($script:Failures -eq 0) {
    Write-Host 'RESULTADO CANCEL: TODOS LOS TESTS PASAN'
    exit 0
}
else {
    Write-Host ('RESULTADO CANCEL: ' + $script:Failures + ' FALLIDOS')
    exit 1
}