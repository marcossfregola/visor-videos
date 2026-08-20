$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bridge-lib.ps1')

$fs = New-ExecutorLock
if ($null -eq $fs) {
    Write-Host 'ERROR: otra instancia del ejecutor ya esta en ejecucion (lock no disponible).'
    exit 1
}

$script:OpenCodeProc = $null
$script:JobOut = $null
$script:JobErr = $null

function Set-State {
    param([string]$Status, [string]$Detail)
    $script:State.status = $Status
    $script:State.statusDetail = $Detail
}

function Invoke-MuteAlarm {
    $script:State.alarmSilenced = $true
    Save-State -State $script:State
    Send-TelegramMessage 'Alarma silenciada.'
    Write-BridgeLog 'INFO' 'ALARMA SILENCIADA (el estado logico no se modifico)'
}

function Start-PendingTask {
    $cfg = $script:Cfg
    $proj = $script:Proj
    if ($script:State.status -eq 'TRABAJANDO') {
        Send-TelegramMessage 'Ya hay una tarea en ejecución.'
        Write-BridgeLog 'INFO' 'trigger ignorado: ya hay una tarea en ejecucion'
        return
    }
    $task = Get-OldestAvailableTask -State $script:State
    if ($null -eq $task) {
        Send-TelegramMessage 'No hay tarea pendiente.'
        Write-BridgeLog 'INFO' 'trigger sin tarea pendiente'
        return
    }
    Set-State 'TRABAJANDO' ('Ejecutando tarea ' + $task.taskId)
    $script:State.taskId = $task.taskId
    $script:State.commentId = $task.commentId
    $script:State.tasks[$task.taskId].status = 'running'
    Save-State -State $script:State
    Send-TelegramMessage ('TAREA INICIADA: ' + $task.taskId)
    Write-BridgeLog 'INFO' ('TAREA INICIADA comment={0} task={1}' -f $task.commentId, $task.taskId)
    try {
        $outFile = Join-Path $script:LogDir ('opencode-' + $task.taskId + '.out')
        $errFile = Join-Path $script:LogDir ('opencode-' + $task.taskId + '.err')
        $prompt = Add-ReportProtocolInstructions -Prompt $task.body -TaskId $task.taskId
        # B3: inyección obligatoria de la política de seguridad para AUTO_TECNICA
        $mode = if ($task.executionMode) { [string]$task.executionMode } else { 'MANUAL' }
        if ($mode -eq 'AUTO_TECNICA') {
            $prompt = Add-AutoTechnicalPolicy -Prompt $prompt -TaskId $task.taskId
            $script:State.tasks[$task.taskId].autoStarted = $true
        }
        $script:State.tasks[$task.taskId].startedAt = (Get-Date).ToUniversalTime().ToString('o')
        $script:State.tasks[$task.taskId].outFile = $outFile
        $script:State.tasks[$task.taskId].errFile = $errFile
        Save-State -State $script:State
        $run = Start-OpenCodeRun -Proj $proj -Prompt $prompt -OutFile $outFile -ErrFile $errFile
        $script:OpenCodeProc = $run.Process
        $script:JobOut = $run.JobOut
        $script:JobErr = $run.JobErr
        $script:State.tasks[$task.taskId].pid = $run.Process.Id
        Save-State -State $script:State
        Write-BridgeLog 'INFO' ('opencode run iniciado pid=' + $run.Process.Id)
    }
    catch {
        $script:OpenCodeProc = $null
        $script:JobOut = $null
        $script:JobErr = $null
        $script:State.alarmSilenced = $false
        Set-State 'ERROR' ('No se pudo iniciar opencode para ' + $task.taskId + ': ' + $_.Exception.Message)
        $script:State.tasks[$task.taskId].status = 'failed'
        Save-State -State $script:State
        Send-TelegramActionable ('ERROR: no se pudo iniciar opencode para ' + $task.taskId)
        Write-BridgeLog 'ERROR' ('fallo al iniciar opencode: ' + $_.Exception.Message)
    }
}

function Invoke-AutoStart {
    # B3: autoejecución de tareas AUTO_TECNICA válidas sin interacción del operador.
    # Reutiliza exactamente el mismo camino de Procesar (Start-PendingTask).
    if ($script:State.status -eq 'TRABAJANDO') { return }
    if ($script:State.status -eq 'DECISIÓN DE USUARIO REQUERIDA') { return }
    $task = Get-OldestAvailableTask -State $script:State
    if ($null -eq $task) { return }
    $mode = if ($task.executionMode) { [string]$task.executionMode } else { 'MANUAL' }
    if ($mode -ne 'AUTO_TECNICA') { return }
    $pre = Test-AutoExecutionPreconditions -State $script:State -Cfg $script:Cfg -Proj $script:Proj -Task $task
    if (-not $pre.ok) {
        Block-AutoExecution -State $script:State -Task $task -Reason $pre.reason
        return
    }
    Write-BridgeLog 'INFO' ('AUTOEJECUCION AUTO_TECNICA task=' + $task.taskId)
    Start-PendingTask
}

function Complete-RunningTask {
    $cfg = $script:Cfg
    $proj = $script:Proj
    $taskId = $script:State.taskId
    $exitCode = $script:OpenCodeProc.ExitCode
    $pidRun = $script:OpenCodeProc.Id
    $startedAt = $null
    if ($script:State.tasks[$taskId].startedAt) {
        try { $startedAt = [datetime]$script:State.tasks[$taskId].startedAt } catch { $startedAt = $null }
    }
    $script:State.alarmSilenced = $false
    $outFile = Join-Path $script:LogDir ('opencode-' + $taskId + '.out')
    $errFile = Join-Path $script:LogDir ('opencode-' + $taskId + '.err')
    $evidence = @{
        Pid = $pidRun
        StartedAt = $startedAt
        OutFile = $outFile
        ErrFile = $errFile
        JobOut = $script:JobOut
        JobErr = $script:JobErr
    }
    $result = Complete-Execution -Cfg $cfg -Proj $proj -State $script:State -TaskId $taskId -ExitCode $exitCode -Evidence $evidence
    $report = $result.Report
    $script:OpenCodeProc = $null
    $script:JobOut = $null
    $script:JobErr = $null
    Write-BridgeLog 'INFO' ('opencode run termino task=' + $taskId + ' exit=' + $exitCode)
    Save-State -State $script:State
    $outcome = $result.Outcome
    switch ($outcome.outcome) {
        'error-execution' {
            Set-State 'ERROR' $outcome.detail
            $script:State.tasks[$taskId].status = 'failed'
            Save-State -State $script:State
            [void](Send-AttentionNotification -State $script:State -TaskId $taskId -Kind 'ERROR' -Text (Get-ErrorNotificationText -TaskId $taskId))
            Write-BridgeLog 'ERROR' ('EXIT CODE != 0 task=' + $taskId + ' exit=' + $exitCode)
            Invoke-Alarm 'B'
            $script:State.lastAlarmPlay = (Get-Date).ToString('o')
            Save-State -State $script:State
        }
        'error-invalid-decision' {
            Set-State 'ERROR' $outcome.detail
            $script:State.tasks[$taskId].status = 'failed'
            Save-State -State $script:State
            [void](Send-AttentionNotification -State $script:State -TaskId $taskId -Kind 'ERROR' -Text (Get-ErrorNotificationText -TaskId $taskId))
            Write-BridgeLog 'ERROR' ('INFORME INVALIDO (SI sin detalle) task=' + $taskId)
            Invoke-Alarm 'B'
            $script:State.lastAlarmPlay = (Get-Date).ToString('o')
            Save-State -State $script:State
        }
        'decision' {
            Set-State 'DECISIÓN DE USUARIO REQUERIDA' ($outcome.detail + ' (TASK_ID=' + $taskId + ')')
            $script:State.tasks[$taskId].status = 'decision'
            Save-State -State $script:State
            [void](Send-AttentionNotification -State $script:State -TaskId $taskId -Kind 'DECISION' -Text (Get-DecisionNotificationText -TaskId $taskId))
            Write-BridgeLog 'INFO' ('DECISION REQUERIDA task=' + $taskId)
            Invoke-Alarm 'B'
            $script:State.lastAlarmPlay = (Get-Date).ToString('o')
            Save-State -State $script:State
        }
        default {
            Set-State 'TERMINADO — ESPERANDO SEGUI' ($outcome.detail + ': ' + $taskId)
            $script:State.tasks[$taskId].status = 'done'
            Save-State -State $script:State
            [void](Send-AttentionNotification -State $script:State -TaskId $taskId -Kind 'TERMINADO' -Text (Get-TerminatedNotificationText -TaskId $taskId))
            Write-BridgeLog 'INFO' ('TERMINADO task=' + $taskId)
            Invoke-Alarm 'A'
            $script:State.lastAlarmPlay = (Get-Date).ToString('o')
            Save-State -State $script:State
        }
    }
    # B2: recibo durable del bridge (no critico; si falla queda pendiente y se reintenta)
    try {
        [void](Publish-BridgeExecutionReport -Cfg $cfg -Proj $proj -State $script:State -TaskId $taskId)
    }
    catch {
        Write-BridgeLog 'ERROR' ('fallo al publicar registro durable task=' + $taskId + ': ' + $_.Exception.Message)
    }
}

function Invoke-GitHubPoll {
    $comments = Get-AllIssueComments -Proj $script:Proj
    if ($null -eq $comments) { return }
    $changed = $false
    foreach ($c in @($comments)) {
        $cid = [string]$c.id
        if ($script:State.seenComments.ContainsKey($cid)) { continue }
        $dec = Get-TaskDecision -Comment $c
        if ($dec.isTask) {
            $tid = $dec.taskId
            if (-not $script:State.tasks.ContainsKey($tid)) {
                $script:State.tasks[$tid] = @{
                    taskId = $tid
                    commentId = $cid
                    createdAt = $c.created_at
                    status = 'available'
                    body = $c.body
                    reportCommentId = $null
                }
                Write-BridgeLog 'INFO' ('TAREA DISPONIBLE task=' + $tid + ' comment=' + $cid)
                Send-TelegramActionable ('Nueva tarea disponible: ' + $tid)
            }
            else {
                Write-BridgeLog 'INFO' ('tarea duplicada ignorada task=' + $tid + ' comment=' + $cid)
            }
            $script:State.seenComments[$cid] = @{ kind = 'task'; taskId = $tid; when = (Get-Date -Format o) }
        }
        elseif ($dec.reason -eq 'es un reporte opencode') {
            # B2: reconciliación tardía de un [OPENCODE_REPORT] para tarea conocida
            $rec = Invoke-ReportReconciliation -Cfg $script:Cfg -Proj $script:Proj -State $script:State -Comment $c
            if ($rec.reconciled) {
                # estado operativo solo si es inequívocamente seguro (DECISION_REQUERIDA valida + tarea vigente)
                $tid = if ([string]([string]$c.body) -match 'TASK_ID:\s*(\S+)') { $Matches[1] } else { $null }
                if (-not $rec.decisionInvalid -and $rec.decisionRequired -and $tid -eq $script:State.taskId -and $script:State.status -eq 'TERMINADO — ESPERANDO SEGUI') {
                    Set-State 'DECISIÓN DE USUARIO REQUERIDA' ('Se requiere la participación de Marcos para continuar (TASK_ID=' + $tid + ')')
                    $script:State.tasks[$tid].status = 'decision'
                    Save-State -State $script:State
                    [void](Send-AttentionNotification -State $script:State -TaskId $tid -Kind 'DECISION' -Text (Get-DecisionNotificationText -TaskId $tid))
                    Write-BridgeLog 'INFO' ('DECISION REQUERIDA por reconciliacion task=' + $tid)
                    Invoke-Alarm 'B'
                    $script:State.lastAlarmPlay = (Get-Date).ToString('o')
                    Save-State -State $script:State
                }
                $changed = $true
            }
            $script:State.seenComments[$cid] = @{ kind = 'report'; when = (Get-Date -Format o) }
        }
        elseif (Is-BridgeExecutionReportComment -Body ([string]$c.body)) {
            # B2.1: comentario propio del bridge (BRIDGE_EXECUTION_REPORT).
            # Se reconoce explicitamente y se ignora de forma intencional:
            # NO crea tarea, NO cambia estado, NO entra en reconciliacion OpenCode, NO ERROR.
            $script:State.seenComments[$cid] = @{ kind = 'bridge_report'; when = (Get-Date -Format o) }
            Write-BridgeLog 'INFO' ('comentario del bridge ignorado (BRIDGE_EXECUTION_REPORT) comment=' + $cid)
        }
        else {
            $script:State.seenComments[$cid] = @{ kind = 'ignored'; reason = $dec.reason; when = (Get-Date -Format o) }
            Write-BridgeLog 'INFO' ('comentario ignorado comment=' + $cid + ' reason=' + $dec.reason)
        }
        $changed = $true
    }
    if ($changed) {
        $firstAvail = Get-OldestAvailableTask -State $script:State
        if ($null -ne $firstAvail -and $script:State.status -ne 'TRABAJANDO') {
            Set-State 'TAREA DISPONIBLE' ('Tarea pendiente: ' + $firstAvail.taskId)
            $script:State.taskId = $firstAvail.taskId
            $script:State.commentId = $firstAvail.commentId
        }
        Save-State -State $script:State
    }
}

function Invoke-AlarmCheck {
    $type = Test-AlarmDue -State $script:State -Cfg $script:Cfg
    if ($null -ne $type) {
        Invoke-Alarm $type
        $script:State.lastAlarmPlay = (Get-Date).ToString('o')
        Save-State -State $script:State
    }
}

function Invoke-TelegramLoop {
    $cfg = $script:Cfg
    $updates = Invoke-TelegramPoll -Offset $script:State.telegramOffset
    if ($null -eq $updates) { return }
    foreach ($u in @($updates)) {
        $newOffset = $u.update_id + 1
        if ($newOffset -gt $script:State.telegramOffset) { $script:State.telegramOffset = $newOffset }
        if ($u.callback_query) {
            $cq = $u.callback_query
            if (-not (Test-TelegramAuthorized -From $cq.from)) {
                Write-BridgeLog 'INFO' ('callback ignorado de user_id ' + $cq.from.id)
                continue
            }
            switch ($cq.data) {
                'process' {
                    Send-TelegramAnswerCallback -CallbackQueryId $cq.id -Text 'Procesando tarea pendiente...'
                    Enqueue-Command 'process'
                }
                'mute' {
                    Send-TelegramAnswerCallback -CallbackQueryId $cq.id -Text 'Silenciando alarma...'
                    Enqueue-Command 'mute'
                }
                'status' {
                    Send-TelegramAnswerCallback -CallbackQueryId $cq.id -Text 'Estado actual'
                    Send-TelegramMessage (Get-StatusText -State $script:State -Cfg $cfg)
                }
            }
        }
        elseif ($u.message) {
            $m = $u.message
            $c = $m.chat
            if (-not (Test-TelegramAuthorized -From $m.from -Chat $c)) {
                Write-BridgeLog 'INFO' ('mensaje ignorado chat_type=' + $c.type + ' chat_id=' + $c.id + ' from=' + $m.from.id)
                continue
            }
            $text = [string]$m.text
            if ($text -match '^/estado') {
                Send-TelegramMessage (Get-StatusText -State $script:State -Cfg $cfg)
            }
            else {
                Send-TelegramKeyboard
            }
        }
    }
    Save-State -State $script:State
}

try {
    $script:Cfg = Get-Config
    $script:Proj = Get-ActiveProject -Cfg $script:Cfg

    $script:State = Load-State
    if ($null -eq $script:State) {
        $script:State = New-InitialState -ProjectId $script:Proj.projectId
        Save-State -State $script:State
    }
    $script:State.daemonStopped = $false
    Save-State -State $script:State

    if ($script:State.status -eq 'TRABAJANDO') {
        $script:State.alarmSilenced = $false
        Set-State 'ERROR' 'El ejecutor se reinició durante una tarea. Verificá en GitHub si opencode alcanzó a publicar el informe.'
        Save-State -State $script:State
        $restartTaskId = if ($script:State.taskId) { [string]$script:State.taskId } else { 'desconocido' }
        [void](Send-AttentionNotification -State $script:State -TaskId $restartTaskId -Kind 'ERROR' -Text (Get-ErrorNotificationText -TaskId $restartTaskId))
        Write-BridgeLog 'ERROR' 'recuperación: ejecutor reiniciado con tarea en curso'
    }
    elseif ($script:State.status -eq 'SIN TAREA') {
        $firstAvail = Get-OldestAvailableTask -State $script:State
        if ($null -ne $firstAvail) {
            Set-State 'TAREA DISPONIBLE' ('Tarea pendiente: ' + $firstAvail.taskId)
            Save-State -State $script:State
        }
    }

    New-Item -ItemType Directory -Path $script:StateDir -Force | Out-Null
    $PID | Set-Content -LiteralPath $script:ExecutorPidFile -Encoding ascii

    Write-BridgeLog 'INFO' ('EJECUTOR INICIADO pid=' + $PID + ' proyecto=' + $script:Proj.projectId)
    Send-TelegramMessage ('Ejecutor iniciado. Proyecto: ' + $script:Proj.projectId + '. Estado: ' + $script:State.status + '.')

    $lastGithubPoll = (Get-Date).AddSeconds(-9999)
    $loop = $true
    while ($loop) {
        try {
            foreach ($cmd in (Get-PendingCommands)) {
                switch ($cmd) {
                    'process' {
                        Write-BridgeLog 'INFO' 'comando PROCESAR recibido'
                        Start-PendingTask
                    }
                    'mute' {
                        Write-BridgeLog 'INFO' 'comando SILENCIAR recibido'
                        Invoke-MuteAlarm
                    }
                    'stop' {
                        Write-BridgeLog 'INFO' 'comando DETENER recibido'
                        if ($script:State.status -eq 'TRABAJANDO') {
                            Send-TelegramMessage 'No se puede detener el ejecutor mientras hay una tarea en ejecución.'
                            Write-BridgeLog 'INFO' 'stop ignorado: tarea en ejecucion'
                        }
                        else {
                            $script:State.daemonStopped = $true
                            Save-State -State $script:State
                            Send-TelegramMessage 'Ejecutor detenido.'
                            $loop = $false
                        }
                    }
                }
                if (-not $loop) { break }
            }

            # B4: aplica post_audit (APPROVED/CORRECTION/NEXT_STAGE/USER_DECISION) ANTES del inbox
            # para que el supersede de InboxPoll vea la auditoría ya aplicada.
            [void](Invoke-AuditPoll -State $script:State)

            # CANCEL: aplica solicitudes de cancelación ANTES de materializar el inbox y de
            # autoarrancar, para descartar tareas pendientes que todavía no comenzaron.
            [void](Invoke-CancelPoll -State $script:State)

            [void](Invoke-InboxPoll -State $script:State)

            [void](Invoke-ResolutionPoll -State $script:State)

            # B3: autoejecución de AUTO_TECNICA (sin botón Procesar / sin comando manual)
            Invoke-AutoStart

            if ($script:State.status -eq 'TRABAJANDO' -and $null -ne $script:OpenCodeProc) {
                if ($script:OpenCodeProc.HasExited) {
                    Complete-RunningTask
                }
            }

            if (((Get-Date) - $lastGithubPoll).TotalSeconds -ge $script:Cfg.executor.githubPollEverySec) {
                $lastGithubPoll = Get-Date
                Invoke-GitHubPoll
            }

            [void](Invoke-DurableRetry -Cfg $script:Cfg -Proj $script:Proj -State $script:State)

            Invoke-AlarmCheck

            Invoke-TelegramLoop
        }
        catch {
            Write-BridgeLog 'ERROR' ('fallo en ciclo del ejecutor: ' + $_.Exception.Message)
            Start-Sleep -Seconds 5
        }
        Start-Sleep -Milliseconds $script:Cfg.executor.pollIntervalMs
    }

    Write-BridgeLog 'INFO' 'EJECUTOR DETENIDO'
}
finally {
    try { $fs.Dispose() } catch {}
    Remove-Item -LiteralPath $script:ExecutorLockFile -Force -ErrorAction SilentlyContinue
}
