param()

# B4 - Pruebas unitarias del handoff asistido (notificacion Telegram idempotente,
# Invoke-AuditPoll, supersedes_task_id e invitacion "seguí").
# Usa directorios temporales y stubs; SIN Telegram real, SIN OpenCode, SIN tocar C:\prueba.

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

function Assert-Contains {
    param($Haystack, $Needle, [string]$Label)
    if ($Haystack -like ('*' + $Needle + '*')) {
        Write-Host ('PASS ' + $Label)
    }
    else {
        Write-Host ('FAIL ' + $Label + ' no contiene [' + $Needle + ']')
        $script:Failures++
    }
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bridge-b4-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$script:StateDir = Join-Path $tempRoot 'state'
$script:StateFile = Join-Path $script:StateDir 'state.json'
$script:LogDir = Join-Path $tempRoot 'logs'
$script:LogFile = Join-Path $script:LogDir 'bridge.log'
$script:InboxDir = Join-Path $script:StateDir 'inbox'
$script:ResolutionsDir = Join-Path $script:StateDir 'resolutions'
$script:AuditsDir = Join-Path $script:StateDir 'audits'
$script:AuditsHistoryDir = Join-Path $script:AuditsDir 'history'
$script:ReportsDir = Join-Path $tempRoot 'reports'
$script:ConfigFile = Join-Path $tempRoot 'config.json'
New-Item -ItemType Directory -Path $script:StateDir, $script:LogDir, $script:AuditsDir -Force | Out-Null

$tempCfg = @{
    activeProjectId = 'visor-videos'
    projects = @(@{ projectId = 'visor-videos'; repo = 'x/y'; localRepo = 'C:\prueba'; issueControl = 1 })
    executor = @{ pollIntervalMs = 500; githubPollEverySec = 15; telegramPollTimeoutSec = 5; alarmAIntervalSec = 2; alarmBIntervalSec = 2; opencodeTimeoutMs = 900000; githubAuthor = 'marcossfregola' }
    telegram = @{ authorizedUserId = $null; authorizedChatId = $null }
}
Save-Config -Cfg $tempCfg

function New-B4State {
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

function Write-AuditFile {
    param([string]$TaskId, [string]$Disposition, [string]$Detail = $null,
          [string]$Summary = $null, [string]$ContextScope = $null, [string]$StageId = $null)
    $payload = @{ task_id = $TaskId; disposition = $Disposition; created_at = '2026-08-17T00:00:00Z'; source = 'mcp' }
    if ($Detail) { $payload.decision_detail = $Detail }
    if ($Summary) { $payload.audit_summary = $Summary }
    if ($ContextScope) { $payload.context_scope = $ContextScope }
    if ($StageId) { $payload.stage_id = $StageId }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:AuditsDir ($TaskId + '.audit.json')) -Encoding utf8
}

# ==== 1. textos de notificación ====

$tTerm = Get-TerminatedNotificationText -TaskId 'b4-01'
Assert-Contains $tTerm 'TASK_ID=b4-01' 'texto terminado menciona TASK_ID'
Assert-Contains $tTerm 'seguí' 'texto terminado invita a "seguí"'
Assert-Contains $tTerm 'Procesar' 'texto terminado advierte no pulsar Procesar'

$tErr = Get-ErrorNotificationText -TaskId 'b4-01'
Assert-Contains $tErr 'TASK_ID=b4-01' 'texto error menciona TASK_ID'
Assert-Contains $tErr 'seguí' 'texto error invita a "seguí"'

$tDec = Get-DecisionNotificationText -TaskId 'b4-02'
Assert-Contains $tDec 'DECISIÓN' 'texto decision menciona DECISIÓN'
Assert-Contains $tDec 'seguí' 'texto decision invita a "seguí"'

$tBlock = Get-AutoBlockedNotificationText -TaskId 'b4-03' -Reason 'HEAD incorrecto'
Assert-Contains $tBlock 'AUTOEJECUCIÓN BLOQUEADA' 'texto bloqueo menciona AUTOEJECUCIÓN BLOQUEADA'
Assert-Contains $tBlock 'HEAD incorrecto' 'texto bloqueo incluye el motivo'
Assert-Contains $tBlock 'seguí' 'texto bloqueo invita a "seguí"'

# ==== 2. Send-AttentionNotification idempotente ====

$stateAtt = New-B4State 'b4-01' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
$sent1 = Send-AttentionNotification -State $stateAtt -TaskId 'b4-01' -Kind 'TERMINADO' -Text $tTerm
Assert-Equal $sent1.duplicate $false 'notificacion 1 no es duplicada'
Assert-True ($script:TelegramSent.Count -eq 1) 'notificacion 1 enviada al stub'
Assert-Contains $script:TelegramSent[0] 'seguí' 'stub recibio la invitacion "seguí"'
$sent2 = Send-AttentionNotification -State $stateAtt -TaskId 'b4-01' -Kind 'TERMINADO' -Text $tTerm
Assert-True $sent2.duplicate $true 'notificacion repetida se ignora (idempotente)'
Assert-Equal $script:TelegramSent.Count 1 'no se reenvia Telegram en duplicado'
Assert-True $stateAtt.attentionNotificationState.ContainsKey('b4-01|TERMINADO') 'estado guarda la clave de idempotencia'
Save-State -State $stateAtt
$loadedAtt = Get-Content $script:StateFile -Raw | ConvertFrom-Json -AsHashtable
Assert-True $loadedAtt.attentionNotificationState.ContainsKey('b4-01|TERMINADO') 'idempotencia persistida en disco'

# distinto Kind para la misma tarea si es una transicion valida (ERROR despues de nada)
$stateErr = New-B4State 'b4-err' 'ERROR' @{ status = 'failed'; exitCode = 1 }
[void](Send-AttentionNotification -State $stateErr -TaskId 'b4-err' -Kind 'ERROR' -Text $tErr)
Assert-Equal $script:TelegramSent.Count 2 'cada (task,kind) nuevo envia'

# ==== 3. Invoke-AuditPoll: APPROVED -> SIN TAREA ====

$stateA = New-B4State 'b4-a' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateA
Write-AuditFile 'b4-a' 'APPROVED'
[void](Invoke-AuditPoll -State $stateA)
Assert-Equal $stateA.status 'SIN TAREA' 'AUDIT APPROVED -> SIN TAREA'
Assert-Equal $stateA.taskId $null 'AUDIT APPROVED libera taskId'
Assert-Equal $stateA.tasks['b4-a'].auditDisposition 'APPROVED' 'AUDIT APPROVED persiste la disposición'
Assert-True ($null -ne $stateA.tasks['b4-a'].auditedAt) 'AUDIT APPROVED persiste auditedAt'
Assert-Equal (Test-Path (Join-Path $script:AuditsDir 'b4-a.audit.json')) $false 'AUDIT APPROVED consume el archivo'

# B4.2: el archivo aplicado se ARCHIVA en history/ (contexto durable), no se borra
Assert-True (Test-Path (Join-Path $script:AuditsDir 'history\b4-a.audit.json')) 'AUDIT APPLIED archiva en history/'

# ==== 4. Invoke-AuditPoll: USER_DECISION -> DECISIÓN + alarma + notificacion ====

$stateD = New-B4State 'b4-d' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateD
Write-AuditFile 'b4-d' 'USER_DECISION' -Detail 'elegir A o B'
[void](Invoke-AuditPoll -State $stateD)
Assert-Equal $stateD.status 'DECISIÓN DE USUARIO REQUERIDA' 'AUDIT USER_DECISION -> DECISIÓN'
Assert-Equal $stateD.tasks['b4-d'].status 'decision' 'AUDIT USER_DECISION marca decision'
Assert-Equal $stateD.tasks['b4-d'].auditDecisionDetail 'elegir A o B' 'AUDIT USER_DECISION conserva detalle'
Assert-Contains ($script:AlarmCalls -join ',') 'B' 'AUDIT USER_DECISION toca alarma B'
Assert-Contains ($script:TelegramSent -join '|') 'DECISIÓN DE USUARIO REQUERIDA' 'AUDIT USER_DECISION notifica decision'

# ==== 5. Invoke-AuditPoll: CORRECTION / NEXT_STAGE registran y habilitan (no cambian estado) ====

$stateC = New-B4State 'b4-c' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateC
Write-AuditFile 'b4-c' 'CORRECTION'
[void](Invoke-AuditPoll -State $stateC)
Assert-Equal $stateC.status 'TERMINADO — ESPERANDO SEGUI' 'AUDIT CORRECTION conserva estado'
Assert-Equal $stateC.tasks['b4-c'].auditDisposition 'CORRECTION' 'AUDIT CORRECTION persiste disposición'

$stateN = New-B4State 'b4-n' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateN
Write-AuditFile 'b4-n' 'NEXT_STAGE'
[void](Invoke-AuditPoll -State $stateN)
Assert-Equal $stateN.tasks['b4-n'].auditDisposition 'NEXT_STAGE' 'AUDIT NEXT_STAGE persiste disposición'

# ==== 6. Invoke-AuditPoll: ignorados (estado/taskId/unauditable) ====

# sin tarea pendiente de auditoria
$stateSin = New-B4State 'b4-x' 'SIN TAREA' @{ status = 'done' }
Save-State -State $stateSin
Write-AuditFile 'b4-x' 'APPROVED'
[void](Invoke-AuditPoll -State $stateSin)
Assert-Equal $stateSin.status 'SIN TAREA' 'AUDIT ignorada en SIN TAREA'
Assert-Equal (Test-Path (Join-Path $script:AuditsDir 'b4-x.audit.json')) $false 'AUDIT ignorada consume el archivo'

# task_id no coincide
$stateMis = New-B4State 'b4-1' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done' }
Save-State -State $stateMis
Write-AuditFile 'b4-otra' 'APPROVED'
[void](Invoke-AuditPoll -State $stateMis)
Assert-Equal $stateMis.status 'TERMINADO — ESPERANDO SEGUI' 'AUDIT con task_id distinto no cambia'

# ya auditada
$stateYa = New-B4State 'b4-2' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; auditedAt = '2026-08-17T00:01:00Z'; auditDisposition = 'APPROVED' }
Save-State -State $stateYa
Write-AuditFile 'b4-2' 'CORRECTION'
[void](Invoke-AuditPoll -State $stateYa)
Assert-Equal $stateYa.tasks['b4-2'].auditDisposition 'APPROVED' 'AUDIT no reaudita una tarea ya auditada'

# archivo invalido se elimina
$stateInv = New-B4State 'b4-3' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done' }
Save-State -State $stateInv
Set-Content -LiteralPath (Join-Path $script:AuditsDir 'b4-3.audit.json') -Value '{ no json' -Encoding utf8
[void](Invoke-AuditPoll -State $stateInv)
Assert-Equal (Test-Path (Join-Path $script:AuditsDir 'b4-3.audit.json')) $false 'AUDIT archivo invalido se elimina'

# en ejecucion no se audita
$stateRun = New-B4State 'b4-4' 'TRABAJANDO' @{ status = 'running' }
$stateRun.status = 'TRABAJANDO'
Save-State -State $stateRun
Write-AuditFile 'b4-4' 'APPROVED'
[void](Invoke-AuditPoll -State $stateRun)
Assert-Equal $stateRun.status 'TRABAJANDO' 'AUDIT ignorada mientras TRABAJANDO'

# B4.2: audit_summary / context_scope / stage_id se persisten en la tarea y se archiva el record
$stateB42 = New-B4State 'b4-42' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateB42
Write-AuditFile 'b4-42' 'APPROVED' -Summary 'contexto durable verificado' -ContextScope 'INFRA_B4' -StageId 'B4.2'
[void](Invoke-AuditPoll -State $stateB42)
Assert-Equal $stateB42.tasks['b4-42'].auditSummary 'contexto durable verificado' 'B4.2 persiste auditSummary'
Assert-Equal $stateB42.tasks['b4-42'].contextScope 'INFRA_B4' 'B4.2 persiste contextScope'
Assert-Equal $stateB42.tasks['b4-42'].stageId 'B4.2' 'B4.2 persiste stageId'
Assert-True (Test-Path (Join-Path $script:AuditsDir 'history\b4-42.audit.json')) 'B4.2 archiva record con metadata'

# ==== 7. Block-AutoExecution notifica AUTO_BLOCKED una sola vez ====

$stateBlock = New-B4State 'b4-block' 'TAREA DISPONIBLE' @{ status = 'available'; executionMode = 'AUTO_TECNICA' }
Save-State -State $stateBlock
$before = $script:TelegramSent.Count
Block-AutoExecution -State $stateBlock -Task $stateBlock.tasks['b4-block'] -Reason 'HEAD incorrecto'
Assert-Equal $stateBlock.status 'AUTOEJECUCIÓN BLOQUEADA' 'block: estado AUTOEJECUCIÓN BLOQUEADA'
Assert-Equal $stateBlock.tasks['b4-block'].autoBlocked $true 'block: autoBlocked=true'
Assert-Equal ($script:TelegramSent.Count) ($before + 1) 'block: notifica AUTO_BLOCKED'
Block-AutoExecution -State $stateBlock -Task $stateBlock.tasks['b4-block'] -Reason 'HEAD incorrecto'
Assert-Equal ($script:TelegramSent.Count) ($before + 1) 'block: notificacion idempotente (no reenvia)'

# ==== 8. supersedes_task_id via Invoke-InboxPoll ====

$stateSup = New-B4State 'b4-prev' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; auditedAt = '2026-08-17T00:01:00Z'; auditDisposition = 'CORRECTION' }
$stateSup.status = 'TERMINADO — ESPERANDO SEGUI'
$stateSup.taskId = 'b4-prev'
Save-State -State $stateSup
New-Item -ItemType Directory -Path $script:InboxDir -Force | Out-Null
$inboxPayload = @{
    task_id = 'b4-siguiente'; prompt = 'tarea correctiva'; created_at = '2026-08-17T00:02:00Z'
    source = 'mcp'; execution_mode = 'MANUAL'; supersedes_task_id = 'b4-prev'
}
$inboxPayload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:InboxDir 'b4-siguiente.task.json') -Encoding utf8
[void](Invoke-InboxPoll -State $stateSup)
Assert-True $stateSup.tasks.ContainsKey('b4-siguiente') 'supersede: tarea nueva agregada'
Assert-Equal $stateSup.tasks['b4-siguiente'].supersedesTaskId 'b4-prev' 'supersede: nueva referencia a la anterior'
Assert-Equal $stateSup.tasks['b4-prev'].supersededByTaskId 'b4-siguiente' 'supersede: previa marcada supersedida'
Assert-Equal $stateSup.status 'TAREA DISPONIBLE' 'supersede: hay exactamente una disponible'
$avail = @(@($stateSup.tasks.Values) | Where-Object { $_.status -eq 'available' })
Assert-Equal $avail.Count 1 'supersede: nunca dos tareas available'

Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($script:Failures -eq 0) {
    Write-Host 'RESULTADO B4: TODOS LOS TESTS PASAN'
    exit 0
}
else {
    Write-Host ('RESULTADO B4: ' + $script:Failures + ' FALLIDOS')
    exit 1
}
