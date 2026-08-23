param()

# ABANDON - Pruebas unitarias del abandono administrativo de tareas pendientes en el executor.
# Verifica Invoke-AbandonPoll (available -> abandoned, ventana inbox, rechazos, idempotencia,
# cadena preservada, estado global y trazabilidad). Usa directorios temporales y stubs; SIN
# Telegram real, SIN OpenCode, SIN tocar C:\prueba.

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
$script:OpenCodeRunCalls = 0
$script:B3Facts = @{ branch = 'beta6'; head = 'c28ccf6942fd0b52fc1c84090f0a6df083b26488'; clean = $true; remoteUrl = 'https://github.com/x/y.git' }

function Get-GitRepoFacts {
    param([hashtable]$Proj)
    return $script:B3Facts
}

function Start-OpenCodeRun {
    param([hashtable]$Proj, [string]$Prompt, [string]$OutFile, [string]$ErrFile)
    $script:OpenCodeRunCalls++
    throw 'ABANDON: Start-OpenCodeRun no debe ejecutarse durante la simulacion'
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

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bridge-abandon-test-' + [guid]::NewGuid().ToString('N'))
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
$script:AbandonmentsDir = Join-Path $script:StateDir 'abandonments'
$script:AbandonmentsHistoryDir = Join-Path $script:AbandonmentsDir 'history'
$script:ReportsDir = Join-Path $tempRoot 'reports'
$script:ConfigFile = Join-Path $tempRoot 'config.json'
New-Item -ItemType Directory -Path $script:StateDir, $script:LogDir, $script:AuditsDir, $script:CancellationsDir, $script:AbandonmentsDir -Force | Out-Null

$tempCfg = @{
    activeProjectId = 'visor-videos'
    projects = @(@{ projectId = 'visor-videos'; repo = 'x/y'; localRepo = 'C:\prueba'; issueControl = 1 })
    executor = @{ pollIntervalMs = 500; githubPollEverySec = 15; telegramPollTimeoutSec = 5; alarmAIntervalSec = 2; alarmBIntervalSec = 2; opencodeTimeoutMs = 900000; githubAuthor = 'marcossfregola' }
    telegram = @{ authorizedUserId = $null; authorizedChatId = $null }
}
Save-Config -Cfg $tempCfg
$script:Cfg = $tempCfg
$script:Proj = @{ projectId = 'visor-videos'; repo = 'x/y'; localRepo = 'C:\prueba'; issueControl = 1 }

function New-AbandonState {
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

function Write-AbandonRequest {
    param([string]$TaskId, [string]$Reason, [bool]$ConfirmChain = $false)
    $payload = @{ task_id = $TaskId; reason = $Reason; confirm_chain_abandon = $ConfirmChain; created_at = '2026-08-17T00:05:00Z'; source = 'mcp' }
    New-Item -ItemType Directory -Path $script:AbandonmentsDir -Force | Out-Null
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:AbandonmentsDir ($TaskId + '.abandon.json')) -Encoding utf8
}

function Write-InboxTask {
    param([string]$TaskId, [string]$Prompt, [hashtable]$Extra = @{})
    $payload = @{ task_id = $TaskId; prompt = $Prompt; created_at = '2026-08-17T00:02:00Z'; source = 'mcp'; execution_mode = 'MANUAL' }
    foreach ($k in $Extra.Keys) { $payload[$k] = $Extra[$k] }
    New-Item -ItemType Directory -Path $script:InboxDir -Force | Out-Null
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:InboxDir ($TaskId + '.task.json')) -Encoding utf8
}

# ===== 1. abandon disponible independiente: available -> abandoned con trazabilidad =====
$state1 = New-AbandonState 'abn-t1' 'TAREA DISPONIBLE' @{ status = 'available' }
Save-State -State $state1
Write-AbandonRequest 'abn-t1' 'se descarta administrativamente'
[void](Invoke-AbandonPoll -State $state1)
Assert-Equal $state1.tasks['abn-t1'].status 'abandoned' '1: available -> abandoned'
Assert-True ($null -ne $state1.tasks['abn-t1'].abandonedAt) '1: persiste abandonedAt'
Assert-Equal $state1.tasks['abn-t1'].abandonReason 'se descarta administrativamente' '1: persiste abandonReason'
Assert-Equal $state1.tasks['abn-t1'].abandonSource 'mcp' '1: persiste abandonSource=mcp'
Assert-True ($null -eq $state1.tasks['abn-t1'].startedAt) '1: nunca se ejecuto (sin startedAt)'
Assert-True ($null -eq $state1.tasks['abn-t1'].pid) '1: nunca se ejecuto (sin pid)'
Assert-True ($null -eq $state1.tasks['abn-t1'].exitCode) '1: nunca se ejecuto (sin exitCode)'
Assert-False (Test-Path (Join-Path $script:AbandonmentsDir 'abn-t1.abandon.json')) '1: solicitud consumida'
Assert-True (Test-Path (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t1.json')) '1: registro archivado en history'

# ===== 2. estado global SIN TAREA tras abandonar la unica available =====
Assert-Equal $state1.status 'SIN TAREA' '2: estado global -> SIN TAREA'
Assert-Equal $state1.taskId $null '2: taskId liberado'
Assert-Equal $state1.commentId $null '2: commentId liberado'

# ===== 3. si queda otra available, se selecciona la mas antigua =====
$state3 = New-AbandonState 'abn-t3a' 'TAREA DISPONIBLE' @{ status = 'available' }
$state3.tasks['abn-t3ant'] = @{ taskId = 'abn-t3ant'; status = 'available'; body = 'y'; createdAt = '2026-08-17T00:01:00Z' }
Save-State -State $state3
Write-AbandonRequest 'abn-t3a' 'descartada'
[void](Invoke-AbandonPoll -State $state3)
Assert-Equal $state3.tasks['abn-t3a'].status 'abandoned' '3: primera abandonada'
Assert-Equal $state3.status 'TAREA DISPONIBLE' '3: queda TAREA DISPONIBLE'
Assert-Equal $state3.taskId 'abn-t3ant' '3: activa la mas antigua restante'

# ===== 4. abandon durante ventana inbox -> descarte preservando el payload =====
$state4 = New-AbandonState 'abn-t4' 'SIN TAREA' @{ status = 'available' }
$state4.tasks.Remove('abn-t4')
$state4.taskId = $null
Save-State -State $state4
Write-InboxTask 'abn-t4' 'prompt obsoleto'
Write-AbandonRequest 'abn-t4' 'encolada por error'
[void](Invoke-AbandonPoll -State $state4)
Assert-False (Test-Path (Join-Path $script:InboxDir 'abn-t4.task.json')) '4: inbox eliminado (no se materializa)'
Assert-False $state4.tasks.ContainsKey('abn-t4') '4: tarea nunca entro a state.json'
Assert-True (Test-Path (Join-Path $script:AbandonmentsHistoryDir 'inbox-abn-t4.task.json')) '4: .task.json original conservado en history'
Assert-True (Test-Path (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t4.json')) '4: registro de solicitud archivado'
$hist4 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t4.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist4.outcome 'applied-inbox' '4: outcome applied-inbox'
Assert-True $hist4.inboxTaskPreserved '4: marca de payload conservado'

# ===== 5. reason vacio en la solicitud: el poll la procesa igual (la cliente ya valida) =====
$state5 = New-AbandonState 'abn-t5' 'TAREA DISPONIBLE' @{ status = 'available' }
Save-State -State $state5
Write-AbandonRequest 'abn-t5' ''
[void](Invoke-AbandonPoll -State $state5)
Assert-Equal $state5.tasks['abn-t5'].status 'abandoned' '5: el poll procesa la solicitud (razon la valida el MCP)'

# ===== 6. solicitud duplicada despues de aplicada: idempotente =====
$state6 = New-AbandonState 'abn-t6' 'SIN TAREA' @{ status = 'abandoned'; abandonedAt = '2026-08-17T00:06:00Z'; abandonReason = 'primera'; abandonSource = 'mcp' }
Save-State -State $state6
Write-AbandonRequest 'abn-t6' 'segunda'
[void](Invoke-AbandonPoll -State $state6)
Assert-Equal $state6.tasks['abn-t6'].status 'abandoned' '6: sigue abandoned'
Assert-Equal $state6.tasks['abn-t6'].abandonReason 'primera' '6: no se sobrescribe el motivo original'
$hist6 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t6.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist6.outcome 'already-abandoned' '6: duplicada registrada como already-abandoned'

# ===== 7. task inexistente: rechazo conservador =====
$state7 = New-AbandonState 'abn-t7' 'SIN TAREA' @{}
$state7.tasks.Remove('abn-t7')
Save-State -State $state7
Write-AbandonRequest 'abn-noexiste' 'motivo'
[void](Invoke-AbandonPoll -State $state7)
$hist7 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-noexiste.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist7.outcome 'rejected-notfound' '7: rechazada (tarea inexistente)'

# ===== 8. TRABAJANDO nunca se abandona =====
$state8 = New-AbandonState 'abn-t8' 'TRABAJANDO' @{ status = 'running'; startedAt = '2026-08-17T00:03:00Z'; pid = 12345 }
Save-State -State $state8
Write-AbandonRequest 'abn-t8' 'no debe abandonarse'
[void](Invoke-AbandonPoll -State $state8)
Assert-Equal $state8.tasks['abn-t8'].status 'running' '8: TRABAJANDO sigue running'
Assert-Equal $state8.status 'TRABAJANDO' '8: estado global intacto'
$hist8 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t8.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist8.outcome 'rejected-working' '8: rechazada (TRABAJANDO)'

# ===== 9. done / failed / resolved / decision / auditada: rechazo =====
foreach ($case in @(
    @{ name = 'done'; fields = @{ status = 'done'; exitCode = 0 } },
    @{ name = 'failed'; fields = @{ status = 'failed'; exitCode = 1 } },
    @{ name = 'resolved'; fields = @{ status = 'resolved'; resolution = 'x' } },
    @{ name = 'decision'; fields = @{ status = 'decision'; decisionDetalle = 'elegir' } },
    @{ name = 'audited'; fields = @{ status = 'available'; auditedAt = '2026-08-17T00:07:00Z' } }
)) {
    $tid = 'abn-t9-' + $case.name
    $st9 = New-AbandonState $tid 'SIN TAREA' @{}
    foreach ($k in $case.fields.Keys) { $st9.tasks[$tid][$k] = $case.fields[$k] }
    Save-State -State $st9
    Write-AbandonRequest $tid 'motivo'
    [void](Invoke-AbandonPoll -State $st9)
    $expected = if ($case.name -eq 'audited') { 'rejected-audited' } else { 'rejected-state' }
    $hist9 = Get-Content (Join-Path $script:AbandonmentsHistoryDir ('abandon-' + $tid + '.json')) -Raw | ConvertFrom-Json -AsHashtable
    Assert-Equal $hist9.outcome $expected ('9: rechazo ' + $case.name)
}

# ===== 10. supersededByTaskId materializada: SIEMPRE rechazada en v1, incluso con confirmacion =====
foreach ($confirm in @($false, $true)) {
    $tid = 'abn-t10-' + $(if ($confirm) { 'confirm' } else { 'noconfirm' })
    $st10 = New-AbandonState $tid 'SIN TAREA' @{ status = 'available'; supersededByTaskId = 't-nueva' }
    Save-State -State $st10
    Write-AbandonRequest $tid 'motivo' -ConfirmChain $confirm
    [void](Invoke-AbandonPoll -State $st10)
    Assert-Equal $st10.tasks[$tid].status 'available' ('10: no abandonada (supersededByTaskId) confirm=' + $confirm)
    Assert-Equal $st10.tasks[$tid].supersededByTaskId 't-nueva' ('10: cadena intacta confirm=' + $confirm)
    $hist10 = Get-Content (Join-Path $script:AbandonmentsHistoryDir ('abandon-' + $tid + '.json')) -Raw | ConvertFrom-Json -AsHashtable
    Assert-Equal $hist10.outcome 'rejected-chain-state' ('10: rechazo supersededByTaskId confirm=' + $confirm)
}

# ===== 11. supersedesTaskId materializada: rechazo sin confirmacion, aplicada con confirmacion =====
# (a) sin confirmacion -> rejected-chain, cadena intacta
$st11a = New-AbandonState 'abn-t11' 'TAREA DISPONIBLE' @{ status = 'available'; supersedesTaskId = 't-anterior' }
Save-State -State $st11a
Write-AbandonRequest 'abn-t11' 'motivo' -ConfirmChain $false
[void](Invoke-AbandonPoll -State $st11a)
Assert-Equal $st11a.tasks['abn-t11'].status 'available' '11: sin confirmacion NO se abandona'
Assert-Equal $st11a.tasks['abn-t11'].supersedesTaskId 't-anterior' '11: cadena intacta tras rechazo'
$hist11a = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t11.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist11a.outcome 'rejected-chain' '11: rechazada (cadena sin confirmacion)'

# (b) con confirmacion -> applied; se preserva la cadena y la tarea anterior NO se reactiva
$st11b = New-AbandonState 'abn-t12' 'TAREA DISPONIBLE' @{ status = 'available'; supersedesTaskId = 'abn-t-anterior' }
$st11b.tasks['abn-t-anterior'] = @{ taskId = 'abn-t-anterior'; status = 'available'; body = 'prev'; createdAt = '2026-08-17T00:00:00Z' }
Save-State -State $st11b
Write-AbandonRequest 'abn-t12' 'eslabon confirmado' -ConfirmChain $true
[void](Invoke-AbandonPoll -State $st11b)
Assert-Equal $st11b.tasks['abn-t12'].status 'abandoned' '11: con confirmacion se abandona'
Assert-Equal $st11b.tasks['abn-t12'].supersedesTaskId 'abn-t-anterior' '11: cadena preservada (supersedesTaskId intacto)'
Assert-Equal $st11b.tasks['abn-t-anterior'].status 'available' '11: la tarea anterior NO se reactiva ni se toca'
$hist11b = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t12.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist11b.outcome 'applied' '11: aplicada con confirmacion'
Assert-True $hist11b.ContainsKey('supersedes_task_id') '11: history guarda snapshot del pedido (supersedes_task_id)'

# ===== 12. inbox con superseded_by_task_id: rechazo conservador y NO se borra el inbox =====
$state12 = New-AbandonState 'abn-t13' 'SIN TAREA' @{}
$state12.tasks.Remove('abn-t13')
Save-State -State $state12
Write-InboxTask 'abn-t13' 'eslabon ya reemplazado' @{ superseded_by_task_id = 'otra' }
$inboxPath12 = Join-Path $script:InboxDir 'abn-t13.task.json'
Write-AbandonRequest 'abn-t13' 'motivo' -ConfirmChain $true
[void](Invoke-AbandonPoll -State $state12)
Assert-True (Test-Path -LiteralPath $inboxPath12) '12: eslabon superseded en inbox NO se borra'
$hist12 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t13.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist12.outcome 'rejected-chain-state' '12: rechazada (inbox superseded_by_task_id)'

# ===== 13. inbox con supersedes_task_id: rechazo sin confirmacion; descarte con confirmacion =====
# (a) sin confirmacion -> rejected-chain, NO se borra
$state13a = New-AbandonState 'abn-t14' 'SIN TAREA' @{}
$state13a.tasks.Remove('abn-t14')
Save-State -State $state13a
Write-InboxTask 'abn-t14' 'eslabon encadenado' @{ supersedes_task_id = 'anterior' }
$inboxPath13 = Join-Path $script:InboxDir 'abn-t14.task.json'
Write-AbandonRequest 'abn-t14' 'motivo' -ConfirmChain $false
[void](Invoke-AbandonPoll -State $state13a)
Assert-True (Test-Path -LiteralPath $inboxPath13) '13: sin confirmacion el inbox se conserva'
$hist13a = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t14.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist13a.outcome 'rejected-chain' '13: rechazada (inbox con supersede sin confirmacion)'

# (b) con confirmacion -> applied-inbox preservando payload
$state13b = New-AbandonState 'abn-t15' 'SIN TAREA' @{}
$state13b.tasks.Remove('abn-t15')
Save-State -State $state13b
Write-InboxTask 'abn-t15' 'eslabon encadenado' @{ supersedes_task_id = 'anterior' }
Write-AbandonRequest 'abn-t15' 'confirmado' -ConfirmChain $true
[void](Invoke-AbandonPoll -State $state13b)
Assert-False (Test-Path (Join-Path $script:InboxDir 'abn-t15.task.json')) '13: con confirmacion el inbox se descarta'
Assert-False $state13b.tasks.ContainsKey('abn-t15') '13: nunca materializada'
Assert-True (Test-Path (Join-Path $script:AbandonmentsHistoryDir 'inbox-abn-t15.task.json')) '13: payload encadenado conservado en history'
$hist13b = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t15.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist13b.outcome 'applied-inbox' '13: aplicada (inbox) con confirmacion'
$inboxPreserved13b = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'inbox-abn-t15.task.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $inboxPreserved13b.supersedes_task_id 'anterior' '13: snapshot conserva supersedes_task_id'

# ===== 14. persistencia: la solicitud pendiente se aplica tras un "reinicio" =====
$state14 = New-AbandonState 'abn-t16' 'TAREA DISPONIBLE' @{ status = 'available' }
Save-State -State $state14
Write-AbandonRequest 'abn-t16' 'se mantiene'
Assert-True (Test-Path (Join-Path $script:AbandonmentsDir 'abn-t16.abandon.json')) '14: solicitud persistente en disco'
[void](Invoke-AbandonPoll -State $state14)
Assert-Equal $state14.tasks['abn-t16'].status 'abandoned' '14: aplicada tras reinicio'

# ===== 15. rejected-started: declaracion defensiva ante posible inicio =====
$state15 = New-AbandonState 'abn-t17' 'TAREA DISPONIBLE' @{ status = 'available'; startedAt = '2026-08-17T00:08:00Z' }
Save-State -State $state15
Write-AbandonRequest 'abn-t17' 'motivo'
[void](Invoke-AbandonPoll -State $state15)
Assert-Equal $state15.tasks['abn-t17'].status 'available' '15: no se abandona si pudo comenzar'
$hist15 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t17.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist15.outcome 'rejected-started' '15: rechazada (posible inicio)'

# ===== 16. rejected-started por pid presente (aun sin startedAt) =====
$state16 = New-AbandonState 'abn-t18' 'TAREA DISPONIBLE' @{ status = 'available'; pid = 9999 }
Save-State -State $state16
Write-AbandonRequest 'abn-t18' 'motivo'
[void](Invoke-AbandonPoll -State $state16)
Assert-Equal $state16.tasks['abn-t18'].status 'available' '16: no se abandona si hay proceso asociado'
$hist16 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t18.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist16.outcome 'rejected-started' '16: rechazada (proceso presente)'

# ===== 17. una tarea ya abandoned NUNCA es iniciada por el mecanismo AUTO_TECNICA =====
$script:OpenCodeRunCalls = 0
$state17 = New-AbandonState 'abn-t19' 'SIN TAREA' @{ status = 'abandoned'; abandonedAt = '2026-08-17T00:10:00Z'; abandonReason = 'ya obsoleta'; abandonSource = 'mcp'; executionMode = 'AUTO_TECNICA'; expectedBranch = 'beta6'; expectedHead = 'c28ccf6942fd0b52fc1c84090f0a6df083b26488'; requireCleanWorktree = $true }
Save-State -State $state17
Invoke-AutoStartLite -State $state17
Assert-Equal $state17.tasks['abn-t19'].status 'abandoned' '17: tarea abandoned no pasa a running'
Assert-Equal $state17.status 'SIN TAREA' '17: el estado global no paso a TRABAJANDO'
Assert-True ($null -eq $state17.tasks['abn-t19'].startedAt) '17: sin startedAt'
Assert-True ($null -eq $state17.tasks['abn-t19'].pid) '17: sin pid'
Assert-Equal $script:OpenCodeRunCalls 0 '17: OpenCode no se lanzo'

# ===== 18. AUTO_TECNICA available con abandon pendiente: AbandonPoll ANTES de AutoStart =====
# Reproduce el orden real del executor (executor.ps1): Invoke-AbandonPoll ANTES de Invoke-AutoStart.
$script:OpenCodeRunCalls = 0
$state18 = New-AbandonState 'abn-t20' 'TAREA DISPONIBLE' @{ status = 'available'; executionMode = 'AUTO_TECNICA'; expectedBranch = 'beta6'; expectedHead = 'c28ccf6942fd0b52fc1c84090f0a6df083b26488'; requireCleanWorktree = $true }
Save-State -State $state18
$pre18 = Test-AutoExecutionPreconditions -State $state18 -Cfg $script:Cfg -Proj $script:Proj -Task $state18.tasks['abn-t20']
Assert-True $pre18.ok '18: la tarea AUTO_TECNICA es elegible para autoarranque (precondiciones ok)'
Write-AbandonRequest 'abn-t20' 'descartar antes de arrancar'
Assert-True (Test-Path (Join-Path $script:AbandonmentsDir 'abn-t20.abandon.json')) '18: solicitud pendiente presente'
[void](Invoke-AbandonPoll -State $state18)
Invoke-AutoStartLite -State $state18
Assert-Equal $state18.tasks['abn-t20'].status 'abandoned' '18: abandonada antes del autoarranque'
Assert-True ($null -eq $state18.tasks['abn-t20'].startedAt) '18: sin startedAt'
Assert-True ($null -eq $state18.tasks['abn-t20'].pid) '18: sin pid'
Assert-Equal $script:OpenCodeRunCalls 0 '18: OpenCode no se lanzo'
Assert-Equal $state18.status 'SIN TAREA' '18: SIN TAREA tras abandonar la unica disponible'
$hist18 = Get-Content (Join-Path $script:AbandonmentsHistoryDir 'abandon-abn-t20.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist18.outcome 'applied' '18: solicitud trazada (outcome=applied)'
Assert-Equal $hist18.reason 'descartar antes de arrancar' '18: traza conserva el motivo'

# ===== 19. precedencia AbandonPoll ANTES que CancelPoll sobre la misma tarea available =====
# La tarea es abandonada por AbandonPoll; CancelPoll luego la ve como 'abandoned' y la rechaza
# sin sobrescribir el estado.
$state19 = New-AbandonState 'abn-t21' 'TAREA DISPONIBLE' @{ status = 'available' }
Save-State -State $state19
Write-AbandonRequest 'abn-t21' 'abandonar primero'
$cancelReq = @{ task_id = 'abn-t21'; reason = 'cancelar despues'; created_at = '2026-08-17T00:05:00Z'; source = 'mcp' }
New-Item -ItemType Directory -Path $script:CancellationsDir -Force | Out-Null
$cancelReq | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:CancellationsDir 'abn-t21.cancel.json') -Encoding utf8
[void](Invoke-AbandonPoll -State $state19)
Assert-Equal $state19.tasks['abn-t21'].status 'abandoned' '19: abandono aplicado primero'
[void](Invoke-CancelPoll -State $state19)
Assert-Equal $state19.tasks['abn-t21'].status 'abandoned' '19: CancelPoll no revierte ni sobrescribe (quedo abandoned)'
Assert-True ($null -eq $state19.tasks['abn-t21'].cancelReason) '19: cancel no aplicada sobre abandoned'
$hist19c = Get-Content (Join-Path $script:CancellationsHistoryDir 'cancel-abn-t21.json') -Raw | ConvertFrom-Json -AsHashtable
Assert-Equal $hist19c.outcome 'rejected-state' '19: cancel rechazada (estado abandoned)'

# ===== 20. bulk: multiples solicitudes en una sola pasada =====
$state20 = New-AbandonState 'abn-t22' 'TAREA DISPONIBLE' @{ status = 'available' }
$state20.tasks['abn-t23'] = @{ taskId = 'abn-t23'; status = 'available'; body = 'z'; createdAt = '2026-08-17T00:01:00Z' }
Save-State -State $state20
Write-AbandonRequest 'abn-t22' 'uno'
Write-AbandonRequest 'abn-t23' 'dos'
[void](Invoke-AbandonPoll -State $state20)
Assert-Equal $state20.tasks['abn-t22'].status 'abandoned' '20: primera bulk abandonada'
Assert-Equal $state20.tasks['abn-t23'].status 'abandoned' '20: segunda bulk abandonada'
Assert-Equal $state20.status 'SIN TAREA' '20: SIN TAREA tras abandonar todo el lote'

# ===== 21. tras applied-inbox, si State.taskId apuntaba a la tarea abandonada, se recalcula =====
$state21 = New-AbandonState 'abn-t24' 'TAREA DISPONIBLE' @{}
$state21.tasks.Remove('abn-t24')
$state21.taskId = 'abn-t24'
$state21.commentId = 77
Save-State -State $state21
Write-InboxTask 'abn-t24' 'pendiente a descartar'
Write-AbandonRequest 'abn-t24' 'se va'
[void](Invoke-AbandonPoll -State $state21)
Assert-False $state21.tasks.ContainsKey('abn-t24') '21: nunca materializada'
Assert-Equal $state21.status 'SIN TAREA' '21: estado global recalculado tras descarte inbox'
Assert-Equal $state21.taskId $null '21: taskId liberado'
Assert-Equal $state21.commentId $null '21: commentId liberado'

Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($script:Failures -eq 0) {
    Write-Host 'RESULTADO ABANDON: TODOS LOS TESTS PASAN'
    exit 0
}
else {
    Write-Host ('RESULTADO ABANDON: ' + $script:Failures + ' FALLIDOS')
    exit 1
}