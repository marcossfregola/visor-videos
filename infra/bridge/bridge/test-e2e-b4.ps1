param()

# B4 - Prueba end-to-end determinista del handoff asistido (Telegram -> "seguí" -> ChatGPT).
# Simula el ciclo del ejecutor (Invoke-AuditPoll ANTES de Invoke-InboxPoll), el encolado
# MCP con previous_task_id y el autoarranque de la correccion AUTO_TECNICA.
# Usa directorios temporales y stubs; SIN Telegram real, SIN OpenCode, SIN tocar C:\prueba.
# Escenarios:
#   A. TERMINADO -> notificacion "seguí" -> post_audit(CORRECTION) -> queue_task(previous) -> supersede
#   B. TERMINADO -> post_audit(APPROVED) -> SIN TAREA controlado (no queda cola muerta)
#   C. TERMINADO -> post_audit(USER_DECISION) -> DECISION + alarma + se bloquea el encolado
#   D. ERROR -> solo con auditoria explícita se encola la correccion (supersede)
#   E. la correccion AUTO_TECNICA encolada arranca sola (autoarranque sin botón)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-lib.ps1')

$script:Failures = 0
$script:TelegramSent = @()
$script:AlarmCalls = @()
$script:B3Facts = @{ branch = 'beta6'; head = '8b6f19fbbddee6ce6099495b7682188fc8665293'; clean = $true; remoteUrl = 'https://github.com/marcossfregola/visor-videos.git' }

function Send-TelegramActionable {
    param([string]$Text)
    $script:TelegramSent += $Text
}

function Send-TelegramMessage {
    param([string]$Text)
    $script:TelegramSent += $Text
}

function Send-TelegramAnswerCallback {
    param([string]$CallbackQueryId, [string]$Text)
}

function Invoke-Alarm {
    param([string]$Type)
    $script:AlarmCalls += $Type
}

function Get-GitRepoFacts {
    param([hashtable]$Proj)
    return $script:B3Facts
}

function Get-OpenCodePath {
    return 'opencode-stub.exe'
}

function Start-OpenCodeRun {
    param([hashtable]$Proj, [string]$Prompt, [string]$OutFile, [string]$ErrFile)
    throw 'E2E-B4: Start-OpenCodeRun no debe ejecutarse durante la simulacion'
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

function New-B4E2eState {
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

function Invoke-CycleOnce {
    param([hashtable]$State)
    # Misma secuencia del executor.ps1: AuditPoll -> InboxPoll -> ResolutionPoll -> AutoStart
    [void](Invoke-AuditPoll -State $State)
    [void](Invoke-InboxPoll -State $State)
    [void](Invoke-ResolutionPoll -State $State)
    Invoke-AutoStartLite -State $State
}

# E2E-B4: version determinista de Invoke-AutoStart (executor.ps1). Verifica las precondiciones
# B3 de una AUTO_TECNICA pendiente y transiciona a TRABAJANDO, sin ejecutar opencode real.
function Invoke-AutoStartLite {
    param([hashtable]$State)
    if ($State.status -eq 'TRABAJANDO') { return }
    if ($State.status -eq 'DECISIÓN DE USUARIO REQUERIDA') { return }
    $task = Get-OldestAvailableTask -State $State
    if ($null -eq $task) { return }
    $mode = if ($task.executionMode) { [string]$task.executionMode } else { 'MANUAL' }
    if ($mode -ne 'AUTO_TECNICA') { return }
    $pre = Test-AutoExecutionPreconditions -State $State -Cfg $cfg -Proj $proj -Task $task
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

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('bridge-e2e-b4-' + [guid]::NewGuid().ToString('N'))
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
$script:CommandsDir = Join-Path $script:StateDir 'commands'
$script:ConfigFile = Join-Path $tempRoot 'config.json'
New-Item -ItemType Directory -Path $script:StateDir, $script:LogDir, $script:AuditsDir, $script:CommandsDir -Force | Out-Null

$cfg = @{
    executor = @{ pollIntervalMs = 500; githubPollEverySec = 15; telegramPollTimeoutSec = 5; alarmAIntervalSec = 2; alarmBIntervalSec = 2; opencodeTimeoutMs = 900000; githubAuthor = 'marcossfregola'; reportCheckRetries = 1; reportCheckRetryDelaySec = 1 }
    telegram = @{ authorizedUserId = $null; authorizedChatId = $null }
}
$proj = @{ projectId = 'visor-videos'; repo = 'marcossfregola/visor-videos'; localRepo = 'C:\prueba'; issueControl = 1 }

function Write-AuditFile {
    param([string]$TaskId, [string]$Disposition, [string]$Detail = $null)
    $payload = @{ task_id = $TaskId; disposition = $Disposition; created_at = '2026-08-17T00:00:00Z'; source = 'mcp' }
    if ($Detail) { $payload.decision_detail = $Detail }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:AuditsDir ($TaskId + '.audit.json')) -Encoding utf8
}

function Write-McpTask {
    param([string]$TaskId, [string]$Prompt, [string]$Mode = 'MANUAL', [string]$Supersedes = $null)
    $payload = @{ task_id = $TaskId; prompt = $Prompt; created_at = '2026-08-17T00:02:00Z'; source = 'mcp'; execution_mode = $Mode; expected_branch = 'beta6'; expected_head = '8b6f19fbbddee6ce6099495b7682188fc8665293'; require_clean_worktree = $true }
    if ($Supersedes) { $payload.supersedes_task_id = $Supersedes }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:InboxDir ($TaskId + '.task.json')) -Encoding utf8
}

# ===== A. TERMINADO -> notificacion -> CORRECTION + queue_task(previous) -> supersede =====
Write-Host '--- ESCENARIO A: TERMINADO con correccion ---'
$stateA = New-B4E2eState 'b4-e2e-A' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateA
# el executor (Complete-RunningTask) notifica TERMINADO al terminar la ejecucion
[void](Send-AttentionNotification -State $stateA -TaskId 'b4-e2e-A' -Kind 'TERMINADO' -Text (Get-TerminatedNotificationText -TaskId 'b4-e2e-A'))
Invoke-CycleOnce -State $stateA | Out-Null
Assert-Equal $stateA.status 'TERMINADO — ESPERANDO SEGUI' 'A: sigue esperando "seguí" sin accion MCP'
$hasSegu = $false
foreach ($t in $script:TelegramSent) { if ($t -match 'seguí') { $hasSegu = $true } }
Assert-True $hasSegu 'A: se invito a escribir "seguí"'
# ChatGPT audita y decide CORRECTION (firma = archivo de auditoria)
Write-AuditFile 'b4-e2e-A' 'CORRECTION'
Invoke-CycleOnce -State $stateA | Out-Null
Assert-Equal $stateA.tasks['b4-e2e-A'].auditDisposition 'CORRECTION' 'A: auditoria CORRECTION aplicada'
Assert-Equal $stateA.status 'TERMINADO — ESPERANDO SEGUI' 'A: CORRECTION no cierra todavia (habilita encolado)'
# ChatGPT encola la correccion con previous_task_id exacto
Write-McpTask 'b4-e2e-A-fix' 'corregir hallazgo A' -Supersedes 'b4-e2e-A'
Invoke-CycleOnce -State $stateA | Out-Null
Assert-True $stateA.tasks.ContainsKey('b4-e2e-A-fix') 'A: tarea correctiva encolada'
Assert-Equal $stateA.tasks['b4-e2e-A-fix'].supersedesTaskId 'b4-e2e-A' 'A: correctiva referencia a la anterior'
Assert-Equal $stateA.tasks['b4-e2e-A'].supersededByTaskId 'b4-e2e-A-fix' 'A: anterior marcada supersedida'
Assert-Equal $stateA.status 'TAREA DISPONIBLE' 'A: hay exactamente una disponible'
$availA = @(@($stateA.tasks.Values) | Where-Object { $_.status -eq 'available' })
Assert-Equal $availA.Count 1 'A: nunca dos tareas available'
Assert-Equal $stateA.status 'TAREA DISPONIBLE' 'A: correccion MANUAL queda disponible'

# ===== B. TERMINADO -> APPROVED -> SIN TAREA controlado =====
Write-Host '--- ESCENARIO B: TERMINADO aprobado ---'
$script:TelegramSent = @()
$stateB = New-B4E2eState 'b4-e2e-B' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateB
Write-AuditFile 'b4-e2e-B' 'APPROVED'
Invoke-CycleOnce -State $stateB | Out-Null
Assert-Equal $stateB.status 'SIN TAREA' 'B: APPROVED -> SIN TAREA controlado'
Assert-Equal $stateB.taskId $null 'B: taskId liberado'
Assert-Equal (@($stateB.tasks.Values) | Where-Object { $_.status -eq 'available' }).Count 0 'B: no queda tarea disponible'

# ===== C. TERMINADO -> USER_DECISION -> DECISION + alarma + resolucion humana =====
Write-Host '--- ESCENARIO C: TERMINADO -> decision de usuario ---'
$script:AlarmCalls = @()
$stateC = New-B4E2eState 'b4-e2e-C' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateC
Write-AuditFile 'b4-e2e-C' 'USER_DECISION' -Detail 'elegir entre A y B'
Invoke-CycleOnce -State $stateC | Out-Null
Assert-Equal $stateC.status 'DECISIÓN DE USUARIO REQUERIDA' 'C: USER_DECISION -> DECISION'
Assert-Equal $stateC.tasks['b4-e2e-C'].status 'decision' 'C: tarea queda en decision'
Assert-Contains ($script:AlarmCalls -join ',') 'B' 'C: toca alarma B'
Assert-Equal $stateC.tasks['b4-e2e-C'].auditDecisionDetail 'elegir entre A y B' 'C: detalle conservado'
# la persona responde en Telegram; ChatGPT registra la decision (resolve_decision) y el
# executor la aplica via Invoke-ResolutionPoll -> SIN TAREA
$resC = @{ task_id = 'b4-e2e-C'; resolution = 'se elige A'; created_at = '2026-08-17T00:03:00Z'; source = 'mcp' }
$resC | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $script:ResolutionsDir 'b4-e2e-C.resolution.json') -Encoding utf8
Invoke-CycleOnce -State $stateC | Out-Null
Assert-Equal $stateC.status 'SIN TAREA' 'C: resolver la decision libera a SIN TAREA'
Assert-Equal $stateC.tasks['b4-e2e-C'].status 'resolved' 'C: historial conserva la tarea como resolved'

# ===== D. ERROR -> solo con auditoria EXPLICITA se encola la correccion =====
Write-Host '--- ESCENARIO D: ERROR -> correccion auditada explicita ---'
$script:TelegramSent = @()
$stateD = New-B4E2eState 'b4-e2e-D' 'ERROR' @{ status = 'failed'; exitCode = 1 }
Save-State -State $stateD
# sin scoop de auditoría el ERROR permanece (el MCP jamás escribe un inbox sin firma)
Invoke-CycleOnce -State $stateD | Out-Null
Assert-Equal $stateD.status 'ERROR' 'D: ERROR no se pisa silenciosamente'
Assert-True (-not $stateD.tasks.ContainsKey('b4-e2e-D-fix')) 'D: sin auditoria no hay correccion encolada'
# auditoria explicita CORRECTION habilita el encolado
Write-AuditFile 'b4-e2e-D' 'CORRECTION'
Invoke-CycleOnce -State $stateD | Out-Null
Assert-Equal $stateD.tasks['b4-e2e-D'].auditDisposition 'CORRECTION' 'D: auditoria CORRECTION aplicada'
# y ahora sí, ChatGPT encola la correccion (la firma ya existe cuando escribe el inbox)
Write-McpTask 'b4-e2e-D-fix' 'corregir D' -Supersedes 'b4-e2e-D'
Invoke-CycleOnce -State $stateD | Out-Null
Assert-True $stateD.tasks.ContainsKey('b4-e2e-D-fix') 'D: con auditoria CORRECTION la correccion entra'
Assert-Equal $stateD.tasks['b4-e2e-D'].supersededByTaskId 'b4-e2e-D-fix' 'D: ERROR supersedido por la correccion'

# ===== E. la correccion AUTO_TECNICA encolada arranca sola =====
Write-Host '--- ESCENARIO E: autoarranque de la correccion ---'
$stateE = New-B4E2eState 'b4-e2e-E' 'TERMINADO — ESPERANDO SEGUI' @{ status = 'done'; exitCode = 0 }
Save-State -State $stateE
Write-AuditFile 'b4-e2e-E' 'NEXT_STAGE'
Invoke-CycleOnce -State $stateE | Out-Null
Write-McpTask 'b4-e2e-E-next' 'siguiente etapa' -Mode 'AUTO_TECNICA' -Supersedes 'b4-e2e-E'
Invoke-CycleOnce -State $stateE | Out-Null
Assert-Equal $stateE.status 'TRABAJANDO' 'E: NEXT_STAGE encolada AUTO_TECNICA arranca sola (sin boton)'
Assert-Equal $stateE.tasks['b4-e2e-E-next'].status 'running' 'E: la tarea correctiva queda en ejecucion'

Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($script:Failures -eq 0) {
    Write-Host 'RESULTADO E2E-B4: TODOS LOS TESTS PASAN'
    exit 0
}
else {
    Write-Host ('RESULTADO E2E-B4: ' + $script:Failures + ' FALLIDOS')
    exit 1
}
