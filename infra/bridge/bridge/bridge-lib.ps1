$ErrorActionPreference = 'Stop'

$script:BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:LogDir = Join-Path $script:BaseDir 'logs'
$script:StateDir = Join-Path $script:BaseDir 'state'
$script:CommandsDir = Join-Path $script:StateDir 'commands'
$script:InboxDir = Join-Path $script:StateDir 'inbox'
$script:ResolutionsDir = Join-Path $script:StateDir 'resolutions'
$script:AuditsDir = Join-Path $script:StateDir 'audits'
$script:AuditsHistoryDir = Join-Path $script:AuditsDir 'history'
$script:SecretsDir = Join-Path $script:BaseDir 'secrets'
$script:ReportsDir = Join-Path $script:BaseDir 'reports'
$script:ConfigFile = Join-Path $script:BaseDir 'config.json'
$script:StateFile = Join-Path $script:StateDir 'state.json'
$script:LogFile = Join-Path $script:LogDir 'bridge.log'
$script:TokenFile = Join-Path $script:SecretsDir 'token.bin'
$script:ExecutorLockFile = Join-Path $script:StateDir 'executor.lock'
$script:ExecutorPidFile = Join-Path $script:StateDir 'executor.pid'
$script:UiPidFile = Join-Path $script:StateDir 'ui.pid'

$script:LastTelegramErrorLog = [DateTime]::MinValue

function Get-GhPath {
    if (-not $script:GhPath) {
        $cmd = Get-Command gh -ErrorAction SilentlyContinue
        if (-not $cmd) { throw 'gh no encontrado en PATH' }
        $script:GhPath = $cmd.Source
    }
    return $script:GhPath
}

function Get-OpenCodePath {
    if (-not $script:OpenCodePath) {
        $cmd = Get-Command opencode -ErrorAction SilentlyContinue
        if (-not $cmd) { throw 'opencode no encontrado en PATH' }
        $candidate = $cmd.Source
        if ($candidate -match '\.(ps1|cmd)$') {
            $pkgExe = Join-Path (Split-Path $candidate -Parent) 'node_modules\opencode-ai\bin\opencode.exe'
            if (Test-Path -LiteralPath $pkgExe) { $candidate = $pkgExe }
        }
        $script:OpenCodePath = $candidate
    }
    return $script:OpenCodePath
}

function Write-BridgeLog {
    param([string]$Level, [string]$Message)
    New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try { Add-Content -LiteralPath $script:LogFile -Value $line -Encoding utf8 } catch {}
    Write-Host $line
}

function Invoke-External {
    param([string]$FilePath, [string[]]$ArgsList, [string]$WorkingDir, [int]$TimeoutMs = 120000)
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    if ($WorkingDir) { $psi.WorkingDirectory = $WorkingDir }
    foreach ($a in $ArgsList) { [void]$psi.ArgumentList.Add($a) }
    $p = [System.Diagnostics.Process]::new()
    $p.StartInfo = $psi
    [void]$p.Start()
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    $finished = $p.WaitForExit($TimeoutMs)
    if (-not $finished) {
        try { $p.Kill() } catch {}
        $p.WaitForExit()
    }
    return @{
        Finished = $finished
        ExitCode = $p.ExitCode
        StdOut   = $outTask.Result
        StdErr   = $errTask.Result
    }
}

function Invoke-GhApi {
    param([string[]]$ArgsList)
    $gh = Get-GhPath
    return Invoke-External -FilePath $gh -ArgsList $ArgsList -TimeoutMs 60000
}

function Get-Config {
    if (Test-Path -LiteralPath $script:ConfigFile) {
        try {
            return Get-Content -LiteralPath $script:ConfigFile -Raw | ConvertFrom-Json -AsHashtable
        }
        catch { throw 'config.json invalido' }
    }
    $default = @{
        activeProjectId = 'visor-videos'
        projects = @(@{ projectId = 'visor-videos'; repo = 'marcossfregola/visor-videos'; localRepo = 'C:\prueba'; issueControl = 1 })
        executor = @{ pollIntervalMs = 500; githubPollEverySec = 15; telegramPollTimeoutSec = 5; alarmAIntervalSec = 120; alarmBIntervalSec = 60; opencodeTimeoutMs = 900000; githubAuthor = 'marcossfregola'; reportCheckRetries = 4; reportCheckRetryDelaySec = 5; reportMaxBytes = 1048576; durableRetryBaseSec = 30; durableRetryFactor = 2; durableRetryMaxSec = 3600 }
        telegram = @{ authorizedUserId = $null; authorizedChatId = $null }
    }
    Save-Config -Cfg $default
    return $default
}

function Save-Config {
    param([hashtable]$Cfg)
    New-Item -ItemType Directory -Path $script:BaseDir -Force | Out-Null
    $tmp = $script:ConfigFile + '.tmp'
    $Cfg | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $script:ConfigFile -Force
}

function Get-ActiveProject {
    param([hashtable]$Cfg)
    $proj = @($Cfg.projects) | Where-Object { $_.projectId -eq $Cfg.activeProjectId } | Select-Object -First 1
    if ($null -eq $proj) { throw ('proyecto activo no definido: ' + $Cfg.activeProjectId) }
    return $proj
}

function New-InitialState {
    param([string]$ProjectId)
    return @{
        projectId = $ProjectId
        status = 'SIN TAREA'
        statusDetail = ''
        taskId = $null
        commentId = $null
        lastAlarmPlay = $null
        alarmSilenced = $false
        seenComments = @{}
        tasks = @{}
        telegramOffset = 0
        daemonStopped = $false
        attentionNotificationState = @{}
    }
}

function Load-State {
    if (Test-Path -LiteralPath $script:StateFile) {
        try {
            return Get-Content -LiteralPath $script:StateFile -Raw | ConvertFrom-Json -AsHashtable
        }
        catch { return $null }
    }
    return $null
}

function Save-State {
    param([hashtable]$State)
    New-Item -ItemType Directory -Path $script:StateDir -Force | Out-Null
    $tmp = $script:StateFile + '.tmp'
    $State | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $tmp -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $script:StateFile -Force
}

function New-ExecutorLock {
    New-Item -ItemType Directory -Path $script:StateDir -Force | Out-Null
    for ($i = 0; $i -lt 2; $i++) {
        try {
            $fs = [System.IO.File]::Open($script:ExecutorLockFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            $data = [System.Text.Encoding]::UTF8.GetBytes([string]$PID)
            $fs.Write($data, 0, $data.Length)
            $fs.Flush()
            return $fs
        }
        catch {
            $existing = $null
            if (Test-Path -LiteralPath $script:ExecutorLockFile) {
                try { $existing = [int]((Get-Content -LiteralPath $script:ExecutorLockFile -Raw).Trim()) } catch {}
            }
            if ($existing -and (Get-Process -Id $existing -ErrorAction SilentlyContinue)) {
                return $null
            }
            Remove-Item -LiteralPath $script:ExecutorLockFile -Force -ErrorAction SilentlyContinue
        }
    }
    return $null
}

function Enqueue-Command {
    param([string]$Name)
    New-Item -ItemType Directory -Path $script:CommandsDir -Force | Out-Null
    $file = Join-Path $script:CommandsDir (([guid]::NewGuid().ToString('N')) + '.cmd')
    Set-Content -LiteralPath $file -Value $Name -Encoding ascii
}

function Get-PendingCommands {
    New-Item -ItemType Directory -Path $script:CommandsDir -Force | Out-Null
    $cmds = @()
    foreach ($f in @(Get-ChildItem -LiteralPath $script:CommandsDir -Filter '*.cmd' -File)) {
        try {
            $name = (Get-Content -LiteralPath $f.FullName -Raw).Trim()
            if ($name) { $cmds += $name }
        }
        catch {}
        Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
    }
    return $cmds
}

function Save-TokenProtected {
    param([string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { throw 'token vacio' }
    New-Item -ItemType Directory -Path $script:SecretsDir -Force | Out-Null
    Add-Type -AssemblyName System.Security
    $data = [System.Text.Encoding]::UTF8.GetBytes($Token)
    $enc = [System.Security.Cryptography.ProtectedData]::Protect($data, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    [System.IO.File]::WriteAllBytes($script:TokenFile, $enc)
}

function Get-TelegramToken {
    if (-not (Test-Path -LiteralPath $script:TokenFile)) { return $null }
    Add-Type -AssemblyName System.Security
    $enc = [System.IO.File]::ReadAllBytes($script:TokenFile)
    try {
        $data = [System.Security.Cryptography.ProtectedData]::Unprotect($enc, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
        return [System.Text.Encoding]::UTF8.GetString($data)
    }
    catch { throw 'no se pudo desproteger el token' }
}

function Send-TelegramRequest {
    param([string]$Method, [hashtable]$Params)
    $token = Get-TelegramToken
    if ($null -eq $token) { return $null }
    $uri = 'https://api.telegram.org/bot{0}/{1}' -f $token, $Method
    try {
        if ($Params) {
            return Invoke-RestMethod -Uri $uri -Method Post -ContentType 'application/json' -Body ($Params | ConvertTo-Json -Depth 10) -TimeoutSec 30
        }
        return Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 30
    }
    catch {
        if (((Get-Date) - $script:LastTelegramErrorLog).TotalSeconds -gt 60) {
            $script:LastTelegramErrorLog = Get-Date
            $safeMsg = ($_.Exception.Message -replace [regex]::Escape($token), '***')
            Write-BridgeLog 'ERROR' ('Telegram ' + $Method + ' fallo: ' + $safeMsg)
        }
        return $null
    }
}

function Send-TelegramMessage {
    param([string]$Text)
    $cfg = Get-Config
    if ($null -eq $cfg.telegram.authorizedChatId) { return }
    [void](Send-TelegramRequest -Method 'sendMessage' -Params @{ chat_id = $cfg.telegram.authorizedChatId; text = $Text })
}

function Get-TelegramKeyboardMarkup {
    return @{
        inline_keyboard = @(
            @(@{ text = '▶ Procesar tarea pendiente'; callback_data = 'process' }),
            @(@{ text = '🔕 Silenciar alarma'; callback_data = 'mute' }),
            @(@{ text = '📋 Ver estado'; callback_data = 'status' })
        )
    }
}

function Send-TelegramKeyboard {
    $cfg = Get-Config
    if ($null -eq $cfg.telegram.authorizedChatId) { return }
    [void](Send-TelegramRequest -Method 'sendMessage' -Params @{ chat_id = $cfg.telegram.authorizedChatId; text = 'Control del ejecutor:'; reply_markup = (Get-TelegramKeyboardMarkup) })
}

function Send-TelegramActionable {
    param([string]$Text)
    $cfg = Get-Config
    if ($null -eq $cfg.telegram.authorizedChatId) { return $null }
    return (Send-TelegramRequest -Method 'sendMessage' -Params @{ chat_id = $cfg.telegram.authorizedChatId; text = $Text; reply_markup = (Get-TelegramKeyboardMarkup) })
}

function Send-TelegramAnswerCallback {
    param([string]$CallbackQueryId, [string]$Text)
    if (-not $CallbackQueryId) { return }
    [void](Send-TelegramRequest -Method 'answerCallbackQuery' -Params @{ callback_query_id = $CallbackQueryId; text = $Text })
}

# ---- B4: notificaciones de atención (idempotentes por TASK_ID + Kind) ----

function Get-TerminatedNotificationText {
    param([string]$TaskId)
    return ("✅ OpenCode terminó TASK_ID=" + $TaskId + ".`nVolvé a ChatGPT y escribí: seguí`n(No pulses Procesar; la siguiente tarea arrancará sola).")
}

function Get-ErrorNotificationText {
    param([string]$TaskId)
    return ("❌ OpenCode falló TASK_ID=" + $TaskId + ".`nVolvé a ChatGPT y escribí: seguí para auditar la evidencia y encolar la corrección.`n(No pulses Procesar.)")
}

function Get-DecisionNotificationText {
    param([string]$TaskId)
    return ("⚠️ DECISIÓN DE USUARIO REQUERIDA TASK_ID=" + $TaskId + ".`nVolvé a ChatGPT y escribí: seguí, revisá la evidencia y elegí entre las opciones.`n(No pulses Procesar.)")
}

function Get-AutoBlockedNotificationText {
    param([string]$TaskId, [string]$Reason)
    return ("⚠️ AUTOEJECUCIÓN BLOQUEADA TASK_ID=" + $TaskId + ".`nMotivo: " + $Reason + ".`nVolvé a ChatGPT y escribí: seguí.`n(No pulses Procesar.)")
}

function Send-AttentionNotification {
    param([hashtable]$State, [string]$TaskId, [string]$Kind, [string]$Text)
    # B4: notificación lógica idempotente por (TASK_ID, Kind) persistida en el estado.
    # Fallo de Telegram NO es camino crítico: se reintenta una vez y se registra igualmente.
    if (-not $State.ContainsKey('attentionNotificationState') -or $null -eq $State.attentionNotificationState) {
        $State.attentionNotificationState = @{}
    }
    $key = $TaskId + '|' + $Kind
    if ($State.attentionNotificationState.ContainsKey($key)) {
        Write-BridgeLog 'INFO' ('notificacion atencion duplicada ignorada key=' + $key)
        return @{ sent = $false; duplicate = $true }
    }
    $cfg = Get-Config
    $telegramEnabled = ($null -ne $cfg.telegram.authorizedChatId)
    $sent = $true
    if ($telegramEnabled) {
        $result = Send-TelegramActionable -Text $Text
        if ($null -eq $result) {
            Start-Sleep -Milliseconds 1500
            $result = Send-TelegramActionable -Text $Text
            $sent = ($null -ne $result)
        }
    }
    else {
        Send-TelegramActionable -Text $Text
    }
    $State.attentionNotificationState[$key] = @{ sentAt = (Get-Date).ToUniversalTime().ToString('o'); taskId = $TaskId; kind = $Kind }
    Save-State -State $State
    Write-BridgeLog 'INFO' ('notificacion atencion enviada key=' + $key + ' sent=' + $sent)
    return @{ sent = $sent; duplicate = $false }
}

function Invoke-TelegramPoll {
    param([int]$Offset = 0)
    $cfg = Get-Config
    if ($null -eq $cfg.telegram.authorizedChatId) { return $null }
    $r = Send-TelegramRequest -Method 'getUpdates' -Params @{ timeout = $cfg.executor.telegramPollTimeoutSec; offset = $Offset }
    if ($null -eq $r) { return $null }
    return $r.result
}

function Get-OldestAvailableTask {
    param([hashtable]$State)
    $avail = @($State.tasks.Values) | Where-Object { $_.status -eq 'available' } | Sort-Object @{ Expression = {
        try { return [datetime]$_.createdAt } catch { return [datetime]::MinValue }
    } }
    if (@($avail).Count -eq 0) { return $null }
    return @($avail)[0]
}

function Invoke-InboxPoll {
    param([hashtable]$State)
    New-Item -ItemType Directory -Path $script:InboxDir -Force | Out-Null
    $changed = $false
    foreach ($f in @(Get-ChildItem -LiteralPath $script:InboxDir -Filter '*.task.json' -File)) {
        $tid = $null
        $prompt = $null
        try {
            $payload = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json -AsHashtable
            $tid = [string]$payload.task_id
            $prompt = [string]$payload.prompt
        }
        catch {
            Write-BridgeLog 'WARN' ('inbox invalido, se elimina: ' + $f.Name)
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
        if ([string]::IsNullOrWhiteSpace($tid) -or [string]::IsNullOrWhiteSpace($prompt)) {
            Write-BridgeLog 'WARN' ('inbox sin task_id/prompt valido: ' + $f.Name)
            continue
        }
        if ($State.tasks.ContainsKey($tid)) {
            Write-BridgeLog 'INFO' ('tarea MCP duplicada ignorada task=' + $tid)
            continue
        }
        $execMode = 'MANUAL'
        if ($payload.ContainsKey('execution_mode') -and $payload.execution_mode) { $execMode = [string]$payload.execution_mode }
        $supId = $null
        if ($payload.ContainsKey('supersedes_task_id') -and $payload.supersedes_task_id) { $supId = [string]$payload.supersedes_task_id }
        # B4.2: metadatos de contexto opcionales
        $ctxScope = $null
        $stageId = $null
        if ($payload.ContainsKey('context_scope') -and $payload.context_scope) { $ctxScope = [string]$payload.context_scope }
        if ($payload.ContainsKey('stage_id') -and $payload.stage_id) { $stageId = [string]$payload.stage_id }
        $State.tasks[$tid] = @{
            taskId = $tid
            commentId = $null
            createdAt = (Get-Date).ToUniversalTime().ToString('o')
            status = 'available'
            body = $prompt
            reportCommentId = $null
            executionMode = $execMode
            expectedBranch = $(if ($payload.ContainsKey('expected_branch') -and $payload.expected_branch) { [string]$payload.expected_branch } else { $null })
            expectedHead = $(if ($payload.ContainsKey('expected_head') -and $payload.expected_head) { [string]$payload.expected_head } else { $null })
            requireCleanWorktree = $(if ($payload.ContainsKey('require_clean_worktree') -and $null -ne $payload.require_clean_worktree) { [bool]$payload.require_clean_worktree } else { $null })
            supersedesTaskId = $supId
            contextScope = $ctxScope
            stageId = $stageId
        }
        # B4: trazabilidad de supersesión. La tarea anterior queda supersedida y nunca
        # coexisten dos tareas available simultáneamente.
        if ($supId) {
            if ($State.tasks.ContainsKey($supId)) {
                $prev = $State.tasks[$supId]
                if ($prev.status -eq 'available') { $prev.status = 'superseded' }
                if (-not $prev.auditedAt) { $prev.auditedAt = (Get-Date).ToUniversalTime().ToString('o') }
                if (-not $prev.auditDisposition) { $prev.auditDisposition = 'APPROVED' }
                $prev.supersededByTaskId = $tid
                Write-BridgeLog 'INFO' ('SUPERSEDE task=' + $supId + ' -> ' + $tid)
            }
            else {
                Write-BridgeLog 'WARN' ('supersedes_task_id desconocido: ' + $supId)
            }
        }
        Write-BridgeLog 'INFO' ('TAREA DISPONIBLE (MCP) task=' + $tid + ' mode=' + $execMode)
        Send-TelegramActionable ('Nueva tarea disponible: ' + $tid + ' [' + $execMode + ']')
        $changed = $true
    }
    if ($changed) {
        $firstAvail = Get-OldestAvailableTask -State $State
        if ($null -ne $firstAvail -and $State.status -ne 'TRABAJANDO') {
            $State.status = 'TAREA DISPONIBLE'
            $State.statusDetail = 'Tarea pendiente: ' + $firstAvail.taskId
            $State.taskId = $firstAvail.taskId
            $State.commentId = $firstAvail.commentId
        }
        Save-State -State $State
    }
    return $changed
}

function Get-StatusText {
    param([hashtable]$State, [hashtable]$Cfg)
    $proj = Get-ActiveProject -Cfg $Cfg
    $running = if ($State.status -eq 'TRABAJANDO') { 'si' } else { 'no' }
    $alarmState = 'no activa'
    if ($State.status -eq 'TERMINADO — ESPERANDO SEGUI' -or $State.status -eq 'DECISIÓN DE USUARIO REQUERIDA' -or $State.status -eq 'ERROR') {
        $alarmState = if ($State.alarmSilenced) { 'silenciada' } else { 'activa' }
    }
    $mode = '-'
    if ($State.taskId -and $State.tasks.ContainsKey($State.taskId) -and $State.tasks[$State.taskId].executionMode) {
        $mode = [string]$State.tasks[$State.taskId].executionMode
    }
    return (
        'Proyecto: ' + $proj.projectId + "`n" +
        'Estado: ' + $State.status + "`n" +
        'TASK_ID: ' + ($(if ($State.taskId) { $State.taskId } else { '-' })) + "`n" +
        'Modo: ' + $mode + "`n" +
        'OpenCode ejecutándose: ' + $running + "`n" +
        'Alarma: ' + $alarmState
    )
}

function Get-FirstContentLine {
    param([string]$Body)
    foreach ($line in ($Body -split "`r?`n")) {
        if ($line.Trim() -ne '') { return $line.Trim() }
    }
    return ''
}

function Get-TaskDecision {
    param([object]$Comment)
    $cfg = Get-Config
    $proj = Get-ActiveProject -Cfg $cfg
    $author = [string]$Comment.user.login
    $body = [string]$Comment.body
    $first = Get-FirstContentLine -Body $body
    if ($first -eq '[OPENCODE_REPORT]') { return @{ isTask = $false; reason = 'es un reporte opencode' } }
    if ($first -ne '[CHATGPT_TASK]') { return @{ isTask = $false; reason = 'marker incorrecto o ausente' } }
    if ($author -ne $cfg.executor.githubAuthor) { return @{ isTask = $false; reason = ('autor no autorizado: ' + $author) } }
    if ($body -notmatch 'PROTOCOLO_VERSION:\s*0\.3\b') { return @{ isTask = $false; reason = 'protocolo incorrecto' } }
    if ($body -notmatch 'TASK_ID:\s*(\S+)') { return @{ isTask = $false; reason = 'TASK_ID ausente' } }
    $taskId = $Matches[1]
    if ($body -notmatch 'PROJECT_ID:\s*(\S+)') { return @{ isTask = $false; reason = 'PROJECT_ID ausente' } }
    $projectId = $Matches[1]
    if ($projectId -ne $proj.projectId) { return @{ isTask = $false; reason = ('PROJECT_ID incorrecto: ' + $projectId) } }
    if ($body -notmatch ('REPO:\s*' + [regex]::Escape($proj.repo))) { return @{ isTask = $false; reason = 'repo incorrecto' } }
    if ($body -notmatch ('ISSUE_CONTROL:\s*' + [regex]::Escape([string]$proj.issueControl) + '\b')) { return @{ isTask = $false; reason = 'issue de control incorrecto' } }
    if ($body -notmatch 'TIPO:\s*\S+') { return @{ isTask = $false; reason = 'TIPO ausente' } }
    return @{ isTask = $true; taskId = $taskId; reason = 'tarea valida' }
}

function Get-AllIssueComments {
    param([hashtable]$Proj)
    $r = Invoke-GhApi -ArgsList @('api', ('repos/{0}/issues/{1}/comments?per_page=100' -f $Proj.repo, $Proj.issueControl))
    if ($r.ExitCode -ne 0) {
        Write-BridgeLog 'ERROR' ('gh api fallo exit=' + $r.ExitCode + ' ' + (($r.StdErr + ' ' + $r.StdOut) -replace '\s+', ' '))
        return $null
    }
    try { return ($r.StdOut | ConvertFrom-Json) } catch { Write-BridgeLog 'ERROR' 'respuesta JSON invalida de gh api'; return $null }
}

function Is-ReportForTask {
    param([string]$Body, [string]$TaskId)
    if ([string]::IsNullOrWhiteSpace($Body) -or [string]::IsNullOrWhiteSpace($TaskId)) { return $false }
    return (Get-FirstContentLine -Body $Body) -eq '[OPENCODE_REPORT]' -and
        $Body -match ('TASK_ID:\s*' + [regex]::Escape($TaskId) + '\b')
}

function Is-BridgeExecutionReportForTask {
    param([string]$Body, [string]$TaskId)
    if ([string]::IsNullOrWhiteSpace($Body) -or [string]::IsNullOrWhiteSpace($TaskId)) { return $false }
    return (Get-FirstContentLine -Body $Body) -eq '[BRIDGE_EXECUTION_REPORT]' -and
        $Body -match 'PROTOCOLO_VERSION:\s*0\.3\b' -and
        $Body -match ('TASK_ID:\s*' + [regex]::Escape($TaskId) + '\b')
}

function Is-BridgeExecutionReportComment {
    param([string]$Body)
    # Reconoce el marker propio del bridge (sin exigir TASK_ID) para el polling.
    if ([string]::IsNullOrWhiteSpace($Body)) { return $false }
    return (Get-FirstContentLine -Body $Body) -eq '[BRIDGE_EXECUTION_REPORT]'
}

function Find-BridgeExecutionReport {
    param([hashtable]$Proj, [hashtable]$Cfg, [string]$TaskId)
    # B2.1: búsqueda read-only en GitHub Issue #1 de un BRIDGE_EXECUTION_REPORT válido
    # para un TASK_ID exacto. Devuelve:
    #   @{ found=$true; canonical=@{commentId; created_at}; count=N; comments=@(...) }   (N>=1)
    #   @{ found=$false; count=0; comments=@() }
    #   $null si GitHub no está disponible (consulta fallida).
    $comments = Get-AllIssueComments -Proj $Proj
    if ($null -eq $comments) { return $null }
    $valid = @($comments) | Where-Object {
        $_.user.login -eq $cfg.executor.githubAuthor -and
        (Is-BridgeExecutionReportForTask -Body ([string]$_.body) -TaskId $TaskId)
    }
    if (@($valid).Count -eq 0) {
        return @{ found = $false; count = 0; comments = @() }
    }
    # Política B2.1: el canónico es el MÁS ANTIGUO válido (determinista y seguro).
    $sorted = @($valid) | Sort-Object @{ Expression = {
        try { return [datetime]$_.created_at } catch { return [datetime]::MaxValue }
    } }
    $canonical = $sorted[0]
    return @{
        found = $true
        count = @($sorted).Count
        canonical = @{ commentId = [string]$canonical.id; created_at = [string]$canonical.created_at }
        comments = @($sorted | ForEach-Object { @{ commentId = [string]$_.id; created_at = [string]$_.created_at } })
    }
}

function New-BridgeExecutionReportBody {
    param(
        [string]$TaskId,
        [int]$ExitCode,
        [string]$ExecutionStatus,   # 'TERMINATED' | 'ERROR'
        [bool]$OpencodeReportFound,
        [string]$OpencodeReportCommentId,
        [string]$StartedAt,
        [string]$CompletedAt
    )
    $openReport = if ($OpencodeReportFound) { 'SI' } else { 'NO' }
    $openComment = if ($OpencodeReportCommentId) { $OpencodeReportCommentId } else { 'NINGUNO' }
    $lines = @(
        '[BRIDGE_EXECUTION_REPORT]'
        'PROTOCOLO_VERSION: 0.3'
        'TASK_ID: ' + $TaskId
        'EXECUTION_STATUS: ' + $ExecutionStatus
        'EXIT_CODE: ' + [string]$ExitCode
        'OPENCODE_REPORT_FOUND: ' + $openReport
        'OPENCODE_REPORT_COMMENT_ID: ' + $openComment
        'STARTED_AT: ' + $StartedAt
        'COMPLETED_AT: ' + $CompletedAt
        'LOCAL_EVIDENCE: STORED'
    )
    return ($lines -join "`n")
}

function Invoke-GhIssueComment {
    param([hashtable]$Proj, [string]$Body)
    # Publica un comentario en el issue de control. Devuelve @{ commentId } o null.
    $gh = Get-GhPath
    $r = Invoke-External -FilePath $gh -ArgsList @('issue', 'comment', [string]$Proj.issueControl, '--repo', $Proj.repo, '--body', $Body) -TimeoutMs 60000
    if ($r.ExitCode -ne 0) {
        Write-BridgeLog 'ERROR' ('gh issue comment fallo exit=' + $r.ExitCode + ' ' + (($r.StdErr + ' ' + $r.StdOut) -replace '\s+', ' '))
        return $null
    }
    $url = ($r.StdOut + ' ' + $r.StdErr).Trim()
    if ($url -match '#issuecomment-(\d+)') {
        $cid = $Matches[1]
        Write-BridgeLog 'INFO' ('BRIDGE_EXECUTION_REPORT publicado comment=' + $cid)
        return @{ commentId = $cid }
    }
    Write-BridgeLog 'WARN' 'gh issue comment devolvio exito pero sin url/comment id parseable'
    return @{ commentId = $null }
}

function Get-DurableRetryAt {
    param([hashtable]$Cfg, [int]$Attempts)
    $base = if ($Cfg.executor.durableRetryBaseSec) { [int]$Cfg.executor.durableRetryBaseSec } else { 30 }
    $factor = if ($Cfg.executor.durableRetryFactor) { [int]$Cfg.executor.durableRetryFactor } else { 2 }
    $max = if ($Cfg.executor.durableRetryMaxSec) { [int]$Cfg.executor.durableRetryMaxSec } else { 3600 }
    try {
        $delay = [Math]::Min([long]($base * [Math]::Pow($factor, [Math]::Max(0, $Attempts - 1))), $max)
    }
    catch { $delay = $base }
    return (Get-Date).AddSeconds($delay)
}

function Publish-BridgeExecutionReport {
    param([hashtable]$Cfg, [hashtable]$Proj, [hashtable]$State, [string]$TaskId)
    # B2 + B2.1: idempotente por TASK_ID. NO depende del camino crítico.
    # B2.1: antes de publicar, busca en GitHub un BRIDGE_EXECUTION_REPORT ya existente
    # para el TASK_ID (cubre caída entre POST y persistencia, y respuesta perdida).
    $t = $State.tasks[$TaskId]
    if ($null -eq $t) { return $null }
    if ($t.bridgeReportCommentId) { return @{ published = $true; duplicate = $true; source = 'local' } }
    # 1) Búsqueda remota previa (adopción si ya existe)
    $existing = Find-BridgeExecutionReport -Proj $Proj -Cfg $Cfg -TaskId $TaskId
    if ($null -ne $existing) {
        if ($existing.found) {
            if ($existing.count -gt 1) {
                Write-BridgeLog 'WARN' ('B2.1: multiples BRIDGE_EXECUTION_REPORT detectados task=' + $TaskId + ' count=' + $existing.count + ' (se adopta el mas antiguo, no se borra nada)')
                $t.bridgeReportDuplicatesDetected = $existing.count
            }
            $t.bridgeReportCommentId = $existing.canonical.commentId
            $t.bridgeReportPublished = $true
            $t.bridgeReportPending = $false
            $t.bridgeReportAttempts = 0
            $t.bridgeReportAdopted = $true
            Save-State -State $State
            Write-BridgeLog 'INFO' ('B2.1: BRIDGE_EXECUTION_REPORT adoptado task=' + $TaskId + ' comment=' + $existing.canonical.commentId)
            return @{ published = $true; duplicate = $true; source = 'remote' }
        }
        # no existe remoto -> publicar normalmente
    }
    try {
        $status = if ($t.status -eq 'failed') { 'ERROR' } else { 'TERMINATED' }
        $exitCode = if ($null -ne $t.exitCode) { [int]$t.exitCode } else { -1 }
        $started = if ($t.startedAt) { [string]$t.startedAt } else { 'DESCONOCIDO' }
        $completed = if ($t.completedAt) { [string]$t.completedAt } else { (Get-Date).ToUniversalTime().ToString('o') }
        $opReportFound = [bool]$t.githubReportFound
        $opComment = if ($t.reportCommentId) { [string]$t.reportCommentId } else { $null }
        $body = New-BridgeExecutionReportBody -TaskId $TaskId -ExitCode $exitCode -ExecutionStatus $status -OpencodeReportFound $opReportFound -OpencodeReportCommentId $opComment -StartedAt $started -CompletedAt $completed
        $res = Invoke-GhIssueComment -Proj $Proj -Body $body
        if ($null -ne $res -and $res.commentId) {
            $t.bridgeReportCommentId = $res.commentId
            $t.bridgeReportPublished = $true
            $t.bridgeReportPending = $false
            $t.bridgeReportAttempts = 0
            Save-State -State $State
            return @{ published = $true; duplicate = $false; source = 'post' }
        }
        # POST sin comment id parseable (pudo haberse creado remotamente):
        # en el retry, la búsqueda remota previa detectará y adoptará sin republicar.
        $attempts = if ($null -eq $t.bridgeReportAttempts) { 1 } else { [int]$t.bridgeReportAttempts + 1 }
        $t.bridgeReportAttempts = $attempts
        $t.bridgeReportPending = $true
        $t.bridgeReportRetryAt = (Get-DurableRetryAt -Cfg $Cfg -Attempts $attempts).ToString('o')
        Save-State -State $State
        Write-BridgeLog 'WARN' ('BRIDGE_EXECUTION_REPORT pendiente task=' + $TaskId + ' intento=' + $attempts)
        return @{ published = $false; pending = $true }
    }
    catch {
        # Posible caso "respuesta perdida": GitHub pudo haber creado el comentario.
        # Queda pendiente; el retry hará búsqueda remota previa (adopta, no republica).
        $attempts = if ($null -eq $t.bridgeReportAttempts) { 1 } else { [int]$t.bridgeReportAttempts + 1 }
        $t.bridgeReportAttempts = $attempts
        $t.bridgeReportPending = $true
        $t.bridgeReportRetryAt = (Get-DurableRetryAt -Cfg $Cfg -Attempts $attempts).ToString('o')
        Save-State -State $State
        Write-BridgeLog 'ERROR' ('BRIDGE_EXECUTION_REPORT error task=' + $TaskId + ': ' + $_.Exception.Message)
        return @{ published = $false; pending = $true }
    }
}

function Invoke-DurableRetry {
    param([hashtable]$Cfg, [hashtable]$Proj, [hashtable]$State)
    # Reintenta registros durables pendientes cuyo retryAt haya vencido. Idempotente.
    $now = Get-Date
    foreach ($tid in @($State.tasks.Keys)) {
        $t = $State.tasks[$tid]
        if (-not $t.bridgeReportPending) { continue }
        if ($t.bridgeReportCommentId) { $t.bridgeReportPending = $false; continue }
        $retryAt = $null
        if ($t.bridgeReportRetryAt) { try { $retryAt = [datetime]$t.bridgeReportRetryAt } catch {} }
        if ($null -ne $retryAt -and $retryAt -gt $now) { continue }
        Write-BridgeLog 'INFO' ('reintento BRIDGE_EXECUTION_REPORT task=' + $tid)
        [void](Publish-BridgeExecutionReport -Cfg $Cfg -Proj $Proj -State $State -TaskId $tid)
    }
}

function Invoke-ReportReconciliation {
    param([hashtable]$Cfg, [hashtable]$Proj, [hashtable]$State, [object]$Comment)
    # Reconciliación tardía de un [OPENCODE_REPORT] para un TASK_ID conocido.
    # NO reejecuta, NO duplica, NO convierte TERMINADO en APROBADO.
    $body = [string]$Comment.body
    $author = [string]$Comment.user.login
    $cid = [string]$Comment.id
    if ($author -ne $cfg.executor.githubAuthor) {
        Write-BridgeLog 'WARN' ('reconciliacion: autor no autorizado comment=' + $cid)
        return @{ reconciled = $false; reason = 'autor no autorizado' }
    }
    if ($body -notmatch 'TASK_ID:\s*(\S+)') {
        Write-BridgeLog 'WARN' ('reconciliacion: TASK_ID ausente comment=' + $cid)
        return @{ reconciled = $false; reason = 'TASK_ID ausente' }
    }
    $tid = $Matches[1]
    if (-not $State.tasks.ContainsKey($tid)) {
        Write-BridgeLog 'INFO' ('reconciliacion: tarea desconocida, se ignora comment=' + $cid + ' task=' + $tid)
        return @{ reconciled = $false; reason = 'tarea desconocida' }
    }
    if (-not (Is-ReportForTask -Body $body -TaskId $tid)) {
        Write-BridgeLog 'WARN' ('reconciliacion: marker/protocolo invalido comment=' + $cid)
        return @{ reconciled = $false; reason = 'marker/protocolo invalido' }
    }
    $t = $State.tasks[$tid]
    if ($t.reportCommentId) {
        # ya reconciliado: solo registramos como visto, sin duplicar
        return @{ reconciled = $false; reason = 'ya reconciliado' }
    }
    $flags = Get-ReportDecisionFlags -Body $body
    $t.reportCommentId = $cid
    $t.githubReportFound = $true
    $t.reconciledAt = (Get-Date).ToUniversalTime().ToString('o')
    if ($body -match 'RESULTADO:\s*(\S+)') { $t.githubReportResultado = $Matches[1] }
    $t.decisionDetalle = $flags.decisionDetalle
    if ($flags.decisionInvalid) {
        $t.githubReportInvalid = $true
        Write-BridgeLog 'WARN' ('reconciliacion: informe tardio invalido (SI sin detalle) task=' + $tid + ' comment=' + $cid)
        Save-State -State $State
        return @{ reconciled = $true; decisionInvalid = $true }
    }
    Save-State -State $State
    Write-BridgeLog 'INFO' ('RECONCILIADO task=' + $tid + ' comment=' + $cid)
    return @{ reconciled = $true; decisionRequired = $flags.decisionRequired; decisionInvalid = $false }
}

function Add-ReportProtocolInstructions {
    param([string]$Prompt, [string]$TaskId)
    $block = @"

---

REPORTE DEL BRIDGE (obligatorio, no lo omitas):
Al terminar tu trabajo, publicá tu informe como comentario en el issue #1 del repositorio marcossfregola/visor-videos (gh ya está autenticado).
El informe debe comenzar EXACTAMENTE con la primera línea: [OPENCODE_REPORT]
y debe incluir estas líneas:
PROTOCOLO_VERSION: 0.3
TASK_ID: $TaskId
RESULTADO: OK
DECISION_REQUERIDA: NO

REGLAS DE DECISION_REQUERIDA:
- El valor normal es DECISION_REQUERIDA: NO.
- Usá SI únicamente si tu tarea NO PUEDE cerrar sin que una persona elija explícitamente entre opciones concretas.
- Si es SI, es OBLIGATORIO incluir además la línea: DECISION_DETALLE: <pregunta concreta para la persona>
- Recomendaciones, pasos futuros o notas para el usuario NO son decisiones: dejá DECISION_REQUERIDA: NO.
- Un SI sin DECISION_DETALLE invalida el informe.

Ejecutá EXACTAMENTE este comando (no uses gh issue create ni --body-file):
gh issue comment 1 --repo marcossfregola/visor-videos --body "[OPENCODE_REPORT]
PROTOCOLO_VERSION: 0.3
TASK_ID: $TaskId
RESULTADO: OK
DECISION_REQUERIDA: NO"

Al finalizar, tu RESPUESTA FINAL debe ser la URL que devolvió gh y, debajo, un RESUMEN SUSTANTIVO de lo que hiciste, inspeccionaste y concluiste (resultados, hallazgos, riesgos, recomendaciones). Ese texto será el report auditable que se conserva localmente. No reveles secretos ni credenciales.
"@
    return ($Prompt.TrimEnd() + "`n" + $block)
}

function Add-AutoTechnicalPolicy {
    param([string]$Prompt, [string]$TaskId)
    # B3: política de seguridad obligatoria inyectada por la infraestructura a toda
    # ejecución AUTO_TECNICA. NO depende de que el prompt humano la incluya.
    $block = @"

---

POLITICA DE SEGURIDAD AUTO_TECNICA (obligatoria, impuesta por el bridge):
Esta ejecucion fue autorizada como tarea tecnica automatica no destructiva.
PROHIBIDO SIN NUEVA AUTORIZACION HUMANA EXPLICITA:
- commit
- push
- tag
- release
- merge
- rebase
- force push
- reset destructivo (hard/mixed en repositorio)
- cambiar visibilidad de repositorios o issues
- borrar datos reales de usuario
- borrar cache/base de datos real
- instalar/desinstalar software real del sistema
- tocar secretos/tokens/credenciales
- modificar infraestructura fuera del alcance declarado de la tarea
Si tu tarea parece requerir cualquiera de estas acciones, DETENETE,
NO la ejecutes, y reporta la necesidad en tu respuesta final.
Limitate a operaciones tecnicas de solo lectura o no destructivas.
TASK_ID: $TaskId
"@
    return ($Prompt.TrimEnd() + "`n" + $block)
}

function Get-GitRepoFacts {
    param([hashtable]$Proj)
    # Consulta read-only del estado git del repo local. Devuelve hashtable o $null si git falla.
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) { return $null }
    try {
        $branch = (& git -C $Proj.localRepo rev-parse --abbrev-ref HEAD 2>$null).Trim()
        $head = (& git -C $Proj.localRepo rev-parse HEAD 2>$null).Trim()
        $status = & git -C $Proj.localRepo status --porcelain 2>$null
        $clean = @($status).Count -eq 0
        $remoteUrl = (& git -C $Proj.localRepo remote get-url origin 2>$null).Trim()
        return @{ branch = $branch; head = $head; clean = $clean; remoteUrl = $remoteUrl }
    }
    catch { return $null }
}

function Test-BridgeOpencodeRunning {
    param([hashtable]$State)
    # B3.1: detecta si el bridge tiene evidencia de una ejecución OpenCode propia todavía viva.
    # Prefiere el PID persistido/asociado por el bridge (State.tasks[].pid), NO heurísticas amplias
    # que puedan confundir una sesión manual de OpenCode ajena al bridge.
    foreach ($tid in @($State.tasks.Keys)) {
        $t = $State.tasks[$tid]
        if ($null -eq $t.pid) { continue }
        $pidVal = $null
        try { $pidVal = [int]$t.pid } catch { continue }
        if ($pidVal -le 0) { continue }
        $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
        if ($null -ne $proc) {
            # Solo consideramos vivo si el proceso sigue siendo el binario de opencode del bridge
            try {
                $p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pidVal) -ErrorAction SilentlyContinue
                if ($null -ne $p -and $p.Name -match 'opencode') {
                    return @{ running = $true; pid = $pidVal; taskId = $tid }
                }
            }
            catch { return @{ running = $true; pid = $pidVal; taskId = $tid } }
        }
    }
    return @{ running = $false; pid = $null; taskId = $null }
}

function Test-PendingResolution {
    param([hashtable]$State)
    # B3.1: detecta si existe una resolución pendiente en state/resolutions que pueda
    # cambiar el destino/autorización de la tarea. NO la consume ni descarta.
    $files = @(Get-ChildItem -LiteralPath $script:ResolutionsDir -Filter '*.resolution.json' -File -ErrorAction SilentlyContinue)
    if (@($files).Count -gt 0) {
        $names = @($files | ForEach-Object { $_.Name })
        return @{ pending = $true; files = $names }
    }
    return @{ pending = $false; files = @() }
}

function Test-AutoExecutionPreconditions {
    param([hashtable]$State, [hashtable]$Cfg, [hashtable]$Proj, [hashtable]$Task)
    # B3 + B3.1: verifica las precondiciones para autoejecutar una tarea AUTO_TECNICA.
    # Devuelve @{ ok = $true } o @{ ok = $false; reason = '<motivo concreto>' }.
    if ($Task.executionMode -ne 'AUTO_TECNICA') {
        return @{ ok = $false; reason = 'no es una tarea AUTO_TECNICA' }
    }
    # A. no estado TRABAJANDO
    if ($State.status -eq 'TRABAJANDO') {
        return @{ ok = $false; reason = 'ya hay una tarea en ejecucion (TRABAJANDO)' }
    }
    # B. no proceso opencode del bridge todavía vivo (usa PID persistido por el bridge)
    $bridgeProc = Test-BridgeOpencodeRunning -State $State
    if ($bridgeProc.running) {
        return @{ ok = $false; reason = ('proceso OpenCode del bridge todavía activo (pid=' + $bridgeProc.pid + ', task=' + $bridgeProc.taskId + ')') }
    }
    # C. no DECISIÓN DE USUARIO REQUERIDA
    if ($State.status -eq 'DECISIÓN DE USUARIO REQUERIDA') {
        return @{ ok = $false; reason = 'hay una DECISIÓN DE USUARIO REQUERIDA pendiente' }
    }
    # D. no resolución pendiente incompatible
    $pendingRes = Test-PendingResolution -State $State
    if ($pendingRes.pending) {
        return @{ ok = $false; reason = ('hay resolución pendiente que podría cambiar la autorización de la tarea: ' + ($pendingRes.files -join ', ')) }
    }
    # E. tarea vigente available
    if ($State.tasks[$Task.taskId].status -ne 'available') {
        return @{ ok = $false; reason = 'la tarea no esta disponible (estado=' + $State.tasks[$Task.taskId].status + ')' }
    }
    # F. TASK_ID no ejecutado anteriormente (implícito: solo available es elegible)
    if ($State.taskId -and $State.taskId -ne $Task.taskId) {
        return @{ ok = $false; reason = 'la tarea vigente es otra (' + $State.taskId + ')' }
    }
    # Contrato AUTO_TECNICA B3.1: expected_branch y expected_head OBLIGATORIOS
    # (no se usan defaults hardcodeados como HEAD permanente).
    $expectedBranch = [string]$Task.expectedBranch
    $expectedHead = [string]$Task.expectedHead
    if ([string]::IsNullOrWhiteSpace($expectedBranch)) {
        return @{ ok = $false; reason = 'expected_branch es obligatorio para AUTO_TECNICA' }
    }
    if ([string]::IsNullOrWhiteSpace($expectedHead)) {
        return @{ ok = $false; reason = 'expected_head es obligatorio para AUTO_TECNICA' }
    }
    $requireClean = if ($null -ne $Task.requireCleanWorktree) { [bool]$Task.requireCleanWorktree } else { $true }
    $facts = Get-GitRepoFacts -Proj $Proj
    if ($null -eq $facts) {
        return @{ ok = $false; reason = 'no se pudo consultar el estado git del repo' }
    }
    # G. identidad del repo: remote origin debe coincidir con el proyecto esperado
    $remoteUrl = [string]$facts.remoteUrl
    $expectedRemote = 'https://github.com/' + $Proj.repo + '.git'
    if ([string]::IsNullOrWhiteSpace($remoteUrl) -or $remoteUrl -ne $expectedRemote) {
        return @{ ok = $false; reason = ('repo incorrecto: esperado=' + $expectedRemote + ' real=' + $remoteUrl) }
    }
    # H. branch correcta
    if ($facts.branch -ne $expectedBranch) {
        return @{ ok = $false; reason = ('branch incorrecta: esperada=' + $expectedBranch + ' real=' + $facts.branch) }
    }
    # I. HEAD correcto
    if ($facts.head -ne $expectedHead) {
        return @{ ok = $false; reason = ('HEAD incorrecto: esperado=' + $expectedHead + ' real=' + $facts.head) }
    }
    # J. working tree correcto
    if ($requireClean -and -not $facts.clean) {
        return @{ ok = $false; reason = 'working tree sucio (require_clean_worktree=true)' }
    }
    return @{ ok = $true }
}

function Block-AutoExecution {
    param([hashtable]$State, [hashtable]$Task, [string]$Reason)
    # B3: registra una autoejecución bloqueada de forma persistente y recuperable.
    $Task.autoBlocked = $true
    $Task.autoBlockReason = $Reason
    $Task.autoBlockedAt = (Get-Date).ToUniversalTime().ToString('o')
    $State.status = 'AUTOEJECUCIÓN BLOQUEADA'
    $State.statusDetail = 'Bloqueada: ' + $Reason + ' (TASK_ID=' + $Task.taskId + ')'
    Save-State -State $State
    Write-BridgeLog 'WARN' ('AUTOEJECUCIÓN BLOQUEADA task=' + $Task.taskId + ': ' + $Reason)
    # B4: notificación idempotente para el handoff ("seguí")
    [void](Send-AttentionNotification -State $State -TaskId $Task.taskId -Kind 'AUTO_BLOCKED' -Text (Get-AutoBlockedNotificationText -TaskId $Task.taskId -Reason $Reason))
}

function Get-CompletionOutcome {
    param($Report, [string]$TaskId, [int]$ExitCode)
    # B1: la existencia del informe GitHub NO condiciona el cierre de la ejecución.
    # B1.1: exit code distinto de 0 es un fallo real de ejecución -> ERROR, sin importar el informe.
    if ($ExitCode -ne 0) {
        return @{ outcome = 'error-execution'; detail = ('OpenCode terminó con exit code distinto de 0 (exit=' + $ExitCode + ', TASK_ID=' + $TaskId + '). La evidencia local quedó conservada.') }
    }
    if ($null -ne $Report -and $Report.decisionInvalid) {
        return @{ outcome = 'error-invalid-decision'; detail = ('Informe con DECISION_REQUERIDA: SI pero sin DECISION_DETALLE (TASK_ID=' + $TaskId + ')') }
    }
    if ($null -ne $Report -and $Report.decisionRequired) {
        return @{ outcome = 'decision'; detail = 'Se requiere la participación de Marcos para continuar' }
    }
    return @{ outcome = 'done'; detail = 'OpenCode terminó de ejecutar y la evidencia local quedó persistida' }
}

function Complete-Execution {
    param(
        [hashtable]$Cfg,
        [hashtable]$Proj,
        [hashtable]$State,
        [string]$TaskId,
        [int]$ExitCode,
        [hashtable]$Evidence
    )
    # B1: decide y registra el cierre local de una ejecución (misma lógica que usa
    # Complete-RunningTask en executor.ps1, aislada para poder probarla de forma
    # determinista). No emite Telegram ni alarmas; el llamador lo hace según el outcome.
    # $Evidence debe contener al menos: pid, startedAt, outFile, errFile, jobs.
    $jobs = @()
    if ($Evidence.JobOut) { $jobs += $Evidence.JobOut }
    if ($Evidence.JobErr) { $jobs += $Evidence.JobErr }
    foreach ($j in $jobs) {
        [void](Wait-Job -Job $j -Timeout 5 -ErrorAction SilentlyContinue)
        Remove-Job -Job $j -Force -ErrorAction SilentlyContinue
    }

    $report = $null
    for ($i = 0; $i -lt $Cfg.executor.reportCheckRetries; $i++) {
        $report = Find-ReportForTask -Proj $Proj -Cfg $Cfg -TaskId $TaskId
        if ($null -ne $report) { break }
        if ($i -lt ($Cfg.executor.reportCheckRetries - 1)) {
            Write-BridgeLog 'INFO' ('informe aun no detectado, reintento ' + ($i + 1))
            Start-Sleep -Seconds $Cfg.executor.reportCheckRetryDelaySec
        }
    }

    $reportContent = ''
    if (Test-Path -LiteralPath $Evidence.OutFile) { $reportContent = Get-Content -LiteralPath $Evidence.OutFile -Raw }
    $maxBytes = if ($Cfg.executor.reportMaxBytes) { [long]$Cfg.executor.reportMaxBytes } else { 1048576 }
    $saved = Save-TaskReport -TaskId $TaskId -Content $reportContent -MaxBytes $maxBytes

    $t = $State.tasks[$TaskId]
    $t.reportStored = $saved.stored
    $t.reportBytes = $saved.bytes
    $t.reportOverflow = $saved.overflow
    $t.completedAt = (Get-Date).ToUniversalTime().ToString('o')
    $t.exitCode = $ExitCode
    $t.pid = $Evidence.Pid
    if ($Evidence.StartedAt) {
        if ($Evidence.StartedAt -is [datetime]) {
            $t.startedAt = $Evidence.StartedAt.ToUniversalTime().ToString('o')
        }
        else {
            $t.startedAt = [string]$Evidence.StartedAt
        }
    }
    $t.outFile = $Evidence.OutFile
    $t.errFile = $Evidence.ErrFile
    $t.githubReportFound = ($null -ne $report)
    if ($null -ne $report) {
        $t.reportCommentId = [string]$report.comment.id
        $t.decisionDetalle = $report.decisionDetalle
    }
    else {
        $t.reportCommentId = $null
        $t.decisionDetalle = $null
    }

    $outcome = Get-CompletionOutcome -Report $report -TaskId $TaskId -ExitCode $ExitCode
    return @{ Outcome = $outcome; Report = $report; Saved = $saved }
}

function Get-ReportDecisionFlags {
    param([string]$Body)
    $decisionMarked = $Body -match 'DECISION_REQUERIDA:\s*(SI|SÍ|YES|TRUE)\b'
    $hasDetail = $Body -match 'DECISION_DETALLE:\s*\S+'
    $detalle = $null
    if ($Body -match 'DECISION_DETALLE:\s*(.+)') { $detalle = $Matches[1].Trim() }
    return @{
        decisionMarked = $decisionMarked
        hasDetail = $hasDetail
        decisionRequired = ($decisionMarked -and $hasDetail)
        decisionInvalid = ($decisionMarked -and -not $hasDetail)
        decisionDetalle = $detalle
    }
}

function Save-TaskReport {
    param([string]$TaskId, [string]$Content, [long]$MaxBytes = 1048576)
    New-Item -ItemType Directory -Path $script:ReportsDir -Force | Out-Null
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $bytes = $utf8NoBom.GetByteCount([string]$Content)
    if ($bytes -le $MaxBytes) {
        $tmp = Join-Path $script:ReportsDir ('.tmp-' + [guid]::NewGuid().ToString('N'))
        $final = Join-Path $script:ReportsDir ($TaskId + '.report.txt')
        [IO.File]::WriteAllText($tmp, [string]$Content, $utf8NoBom)
        Move-Item -LiteralPath $tmp -Destination $final -Force
        return @{ stored = $true; overflow = $false; bytes = $bytes }
    }
    $marker = Join-Path $script:ReportsDir ($TaskId + '.report.overflow')
    $info = ('REPORT_OVERFLOW task=' + $TaskId + ' bytes=' + $bytes + ' limite=' + $MaxBytes) + "`n"
    [IO.File]::WriteAllText($marker, $info, $utf8NoBom)
    Write-BridgeLog 'ERROR' ('REPORT OVERFLOW task=' + $TaskId + ' bytes=' + $bytes + ' limite=' + $MaxBytes)
    return @{ stored = $false; overflow = $true; bytes = $bytes }
}

function Read-TaskReport {
    param([string]$TaskId)
    $final = Join-Path $script:ReportsDir ($TaskId + '.report.txt')
    if (Test-Path -LiteralPath $final) {
        return @{ available = $true; content = (Get-Content -LiteralPath $final -Raw) }
    }
    return @{ available = $false; content = $null }
}

function Find-ReportForTask {
    param([hashtable]$Proj, [hashtable]$Cfg, [string]$TaskId)
    $comments = Get-AllIssueComments -Proj $Proj
    if ($null -eq $comments) { return $null }
    $report = @($comments) | Where-Object {
        (Is-ReportForTask -Body $_.body -TaskId $TaskId) -and
        $_.user.login -eq $cfg.executor.githubAuthor
    } | Select-Object -First 1
    if ($null -eq $report) { return $null }
    $flags = Get-ReportDecisionFlags -Body $report.body
    return @{
        comment = $report
        decisionRequired = $flags.decisionRequired
        decisionInvalid = $flags.decisionInvalid
        decisionDetalle = $flags.decisionDetalle
    }
}

function Invoke-ResolutionPoll {
    param([hashtable]$State)
    New-Item -ItemType Directory -Path $script:ResolutionsDir -Force | Out-Null
    foreach ($f in @(Get-ChildItem -LiteralPath $script:ResolutionsDir -Filter '*.resolution.json' -File)) {
        $tid = $null
        $res = $null
        try {
            $payload = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json -AsHashtable
            $tid = [string]$payload.task_id
            $res = [string]$payload.resolution
        }
        catch {
            Write-BridgeLog 'WARN' ('resolution invalida, se elimina: ' + $f.Name)
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
        if ($State.status -ne 'DECISIÓN DE USUARIO REQUERIDA') {
            Write-BridgeLog 'WARN' ('resolution ignorada: no hay decision pendiente (' + $f.Name + ')')
            continue
        }
        if ($State.taskId -ne $tid) {
            Write-BridgeLog 'WARN' ('resolution ignorada: task_id no coincide (' + $f.Name + ')')
            continue
        }
        if ([string]::IsNullOrWhiteSpace($res)) {
            Write-BridgeLog 'WARN' ('resolution ignorada: resolution vacia (' + $f.Name + ')')
            continue
        }
        $State.tasks[$tid].status = 'resolved'
        $State.tasks[$tid].resolution = $res
        $State.tasks[$tid].resolvedAt = (Get-Date -Format o)
        $State.status = 'SIN TAREA'
        $State.statusDetail = ''
        $State.taskId = $null
        $State.commentId = $null
        Save-State -State $State
        Write-BridgeLog 'INFO' ('DECISION RESUELTA task=' + $tid)
    }
}

function Invoke-AuditPoll {
    param([hashtable]$State)
    # B4: aplica el resultado de post_audit (archivos state/audits/*.audit.json).
    # B4.2: los audit records APLICADOS se archivan en state/audits/history/ (contexto durable).
    # El MCP jamás escribe state.json; el executor es el único escritor.
    New-Item -ItemType Directory -Path $script:AuditsDir, $script:AuditsHistoryDir -Force | Out-Null
    $attentionStates = @('TERMINADO — ESPERANDO SEGUI', 'ERROR', 'AUTOEJECUCIÓN BLOQUEADA')
    foreach ($f in @(Get-ChildItem -LiteralPath $script:AuditsDir -Filter '*.audit.json' -File)) {
        $tid = $null
        $disp = $null
        $detail = $null
        $summary = $null
        $ctxScope = $null
        $stageId = $null
        try {
            $payload = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json -AsHashtable
            $tid = [string]$payload.task_id
            $disp = [string]$payload.disposition
            if ($payload.ContainsKey('decision_detail') -and $payload.decision_detail) { $detail = [string]$payload.decision_detail }
            if ($payload.ContainsKey('audit_summary') -and $payload.audit_summary) { $summary = [string]$payload.audit_summary }
            if ($payload.ContainsKey('context_scope') -and $payload.context_scope) { $ctxScope = [string]$payload.context_scope }
            if ($payload.ContainsKey('stage_id') -and $payload.stage_id) { $stageId = [string]$payload.stage_id }
        }
        catch {
            Write-BridgeLog 'WARN' ('audit invalido, se elimina: ' + $f.Name)
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        if (-not $attentionStates.Contains($State.status)) {
            Write-BridgeLog 'WARN' ('audit ignorada: no hay tarea pendiente de auditoria (' + $f.Name + ')')
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        if ($State.taskId -ne $tid) {
            Write-BridgeLog 'WARN' ('audit ignorada: task_id no coincide (' + $f.Name + ')')
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        if (-not $State.tasks.ContainsKey($tid)) {
            Write-BridgeLog 'WARN' ('audit ignorada: tarea desconocida (' + $f.Name + ')')
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        $t = $State.tasks[$tid]
        if ($t.status -eq 'running') {
            Write-BridgeLog 'WARN' ('audit ignorada: tarea en ejecucion (' + $f.Name + ')')
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        if ($t.auditedAt) {
            Write-BridgeLog 'WARN' ('audit ignorada: tarea ya auditada (' + $f.Name + ')')
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        if ($t.supersededByTaskId) {
            Write-BridgeLog 'WARN' ('audit ignorada: tarea ya supersedida (' + $f.Name + ')')
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        $t.auditedAt = (Get-Date).ToUniversalTime().ToString('o')
        $t.auditDisposition = $disp
        if ($summary) { $t.auditSummary = $summary }
        if ($ctxScope) { $t.contextScope = $ctxScope }
        if ($stageId) { $t.stageId = $stageId }
        switch ($disp) {
            'APPROVED' {
                $State.status = 'SIN TAREA'
                $State.statusDetail = ''
                $State.taskId = $null
                $State.commentId = $null
                Send-TelegramMessage ('Auditoría aprobada. TASK_ID=' + $tid + ' cerrado. Estado: SIN TAREA.')
                Write-BridgeLog 'INFO' ('AUDITORIA APROBADA task=' + $tid + ' -> SIN TAREA')
            }
            'USER_DECISION' {
                $t.auditDecisionDetail = $detail
                $t.status = 'decision'
                $State.status = 'DECISIÓN DE USUARIO REQUERIDA'
                $State.statusDetail = 'Decisión requerida tras auditoría (TASK_ID=' + $tid + ')'
                [void](Send-AttentionNotification -State $State -TaskId $tid -Kind 'DECISION' -Text (Get-DecisionNotificationText -TaskId $tid))
                Invoke-Alarm 'B'
                $State.lastAlarmPlay = (Get-Date).ToString('o')
                Write-BridgeLog 'INFO' ('AUDITORIA USER_DECISION task=' + $tid)
            }
            default {
                # CORRECTION / NEXT_STAGE: registra la auditoría y habilita queue_task(previous_task_id)
                Write-BridgeLog 'INFO' ('AUDITORIA ' + $disp + ' task=' + $tid + ' (habilita encolado)')
            }
        }
        Save-State -State $State
        # B4.2: archivar el record aplicado (historial reconstruible, nunca se borra)
        try {
            Move-Item -LiteralPath $f.FullName -Destination (Join-Path $script:AuditsHistoryDir $f.Name) -Force
        }
        catch {
            Write-BridgeLog 'WARN' ('no se pudo archivar audit aplicado (' + $f.Name + '): ' + $_.Exception.Message)
        }
    }
}

function Start-OpenCodeRun {
    param([hashtable]$Proj, [string]$Prompt, [string]$OutFile, [string]$ErrFile)
    $opencode = Get-OpenCodePath
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $opencode
    $psi.WorkingDirectory = $Proj.localRepo
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $model = $null
    $cfg = Get-Config
    if ($cfg.executor.model) { $model = $cfg.executor.model }
    $args = @('run', '--dir', $Proj.localRepo)
    if ($model) { $args += @('-m', $model) }
    $args += $Prompt
    foreach ($a in $args) { [void]$psi.ArgumentList.Add($a) }
    $p = [System.Diagnostics.Process]::new()
    $p.StartInfo = $psi
    [void]$p.Start()
    $swOut = [System.IO.StreamWriter]::new($OutFile, $false, [System.Text.Encoding]::UTF8)
    $swErr = [System.IO.StreamWriter]::new($ErrFile, $false, [System.Text.Encoding]::UTF8)
    $jobOut = Start-ThreadJob -ArgumentList $p, $swOut -ScriptBlock {
        param($proc, $writer)
        try {
            $line = $null
            while ($null -ne ($line = $proc.StandardOutput.ReadLine())) {
                $writer.WriteLine($line)
            }
        }
        catch {}
        finally { $writer.Dispose() }
    }
    $jobErr = Start-ThreadJob -ArgumentList $p, $swErr -ScriptBlock {
        param($proc, $writer)
        try {
            $line = $null
            while ($null -ne ($line = $proc.StandardError.ReadLine())) {
                $writer.WriteLine($line)
            }
        }
        catch {}
        finally { $writer.Dispose() }
    }
    return @{ Process = $p; JobOut = $jobOut; JobErr = $jobErr }
}

function Test-TelegramAuthorized {
    param([object]$From, [object]$Chat)
    $cfg = Get-Config
    if ($null -eq $cfg.telegram.authorizedUserId -or $null -eq $cfg.telegram.authorizedChatId) { return $false }
    if ($null -ne $From) {
        if ([int64]$From.id -ne [int64]$cfg.telegram.authorizedUserId) { return $false }
    }
    if ($null -ne $Chat) {
        if ($Chat.type -ne 'private') { return $false }
        if ([int64]$Chat.id -ne [int64]$cfg.telegram.authorizedChatId) { return $false }
    }
    return $true
}

function Test-AlarmDue {
    param([hashtable]$State, [hashtable]$Cfg)
    $isA = $State.status -eq 'TERMINADO — ESPERANDO SEGUI'
    $isB = ($State.status -eq 'DECISIÓN DE USUARIO REQUERIDA') -or ($State.status -eq 'ERROR')
    if (($isA -or $isB) -and -not $State.alarmSilenced) {
        $type = if ($isA) { 'A' } else { 'B' }
        $interval = if ($type -eq 'A') { $Cfg.executor.alarmAIntervalSec } else { $Cfg.executor.alarmBIntervalSec }
        $last = $null
        if ($State.lastAlarmPlay) {
            try { $last = [datetime]$State.lastAlarmPlay } catch { $last = $null }
        }
        if ($null -eq $last -or ((Get-Date) - $last).TotalSeconds -ge $interval) {
            return $type
        }
    }
    return $null
}

function Invoke-Alarm {
    param([string]$Type)
    if ($Type -eq 'A') {
        [System.Media.SystemSounds]::Asterisk.Play()
        Write-BridgeLog 'INFO' 'ALARMA A sonando (opencode termino)'
    }
    else {
        [System.Media.SystemSounds]::Exclamation.Play()
        Write-BridgeLog 'INFO' 'ALARMA B sonando (decision requerida)'
    }
}
