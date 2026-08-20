"""Integracion minimalista y segura con el bridge VisorVideosDevBridge.

Solo lectura del estado del bridge y escritura atomica en el inbox del bridge.
NO ejecuta OpenCode, NO envia Telegram, NO toca C:\\prueba, NO usa red ni shell.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

DEFAULT_MAX_PROMPT_BYTES = 131072  # 128 KiB
MAX_TASK_ID_LEN = 128
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# B4: estados con atención pendiente (requieren la acción del usuario via "seguí")
STATUS_TERMINADO = "TERMINADO — ESPERANDO SEGUI"
STATUS_BLOQUEADA = "AUTOEJECUCIÓN BLOQUEADA"
STATUS_DECISION = "DECISIÓN DE USUARIO REQUERIDA"
STATUS_ERROR = "ERROR"

# CANCEL: estado de tarea cancelada (nunca se ejecutó). Diferenciado de
# superseded / failed / done / resolved / decision.
TASK_STATUS_CANCELLED = "cancelled"
# límite del motivo de cancelación
MAX_CANCEL_REASON_CHARS = 200

# B4: solo desde SIN TAREA se encola una tarea independiente sin previous_task_id.
# Desde TERMINADO / ERROR / AUTOEJECUCIÓN BLOQUEADA solo se encola una tarea
# RELACIONADA (corrección / siguiente etapa) mediante previous_task_id exacto y
# auditoría previa (post_audit con CORRECTION o NEXT_STAGE).
PLAIN_STATUSES = {"SIN TAREA"}
LINKED_STATUSES = {STATUS_TERMINADO, STATUS_ERROR, STATUS_BLOQUEADA}
RESULTING_STATUS = "TAREA DISPONIBLE"

# B3: modos de ejecucion
EXECUTION_MODE_MANUAL = "MANUAL"
EXECUTION_MODE_AUTO = "AUTO_TECNICA"
VALID_EXECUTION_MODES = {EXECUTION_MODE_MANUAL, EXECUTION_MODE_AUTO}
DEFAULT_EXECUTION_MODE = EXECUTION_MODE_MANUAL

# B3.1: para AUTO_TECNICA, expected_branch y expected_head son OBLIGATORIOS
# (no se usan defaults hardcodeados como HEAD permanente). require_clean_worktree
# conserva un default seguro.
DEFAULT_REQUIRE_CLEAN_WORKTREE = True

# B4: estados con atención pendiente (requieren la acción del usuario via "seguí")
ATTENTION_STATUSES = {STATUS_TERMINADO, STATUS_BLOQUEADA, STATUS_ERROR, STATUS_DECISION}
ATTENTION_KIND_BY_STATUS = {
    STATUS_TERMINADO: "AUDIT",
    STATUS_BLOQUEADA: "AUTO_BLOCKED",
    STATUS_ERROR: "ERROR",
    STATUS_DECISION: "USER_DECISION",
}

# B4: disposiciones de auditoría aceptadas por post_audit.
# APPROVED -> cierre controlado a SIN TAREA.
# CORRECTION / NEXT_STAGE -> registran la auditoría y habilitan queue_task(previous_task_id).
# USER_DECISION -> pasa a DECISIÓN DE USUARIO REQUERIDA con detalle para la persona.
VALID_AUDIT_DISPOSITIONS = {"APPROVED", "CORRECTION", "NEXT_STAGE", "USER_DECISION"}
# disposiciones que habilitan encolar la tarea siguiente (A/B del handoff)
QUEUEABLE_AUDIT_DISPOSITIONS = {"CORRECTION", "NEXT_STAGE"}

# B4.2: continuidad durable del contexto de auditoría.
# Los registros .audit.json se conservan en state/audits/history/ tras aplicarlos
# el executor (history dir). get_audit_context los lee (solo lectura).
AUDIT_CONTEXT_PROTOCOL_VERSION = "1.0.0"
PROJECT_NAME = "visor-videos"
REPOSITORY = "marcossfregola/visor-videos"

# scopes y estados de decisión
DECISION_SCOPE_BETA = "BETA"
DECISION_SCOPE_PERMANENT = "PERMANENT"
DECISION_STATUS_ACTIVE = "ACTIVE"
DECISION_STATUS_SUPERSEDED = "SUPERSEDED"
VALID_DECISION_SCOPES = {DECISION_SCOPE_BETA, DECISION_SCOPE_PERMANENT}

# límites B4.2 (evitar crecimiento ilimitado)
MAX_AUDIT_SUMMARY_CHARS = 2000
MAX_DECISION_CHARS = 2000
MAX_DECISIONS_PER_AUDIT = 20
MAX_SUPERSEDES_IDS = 20
MAX_RECENT_AUDIT_SUMMARIES = 5
MAX_CONTEXT_SCOPE_LEN = 64
MAX_STAGE_ID_LEN = 64
CONTEXT_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# bootstrap_rules: conjunto BREVE y estable de reglas esenciales para cualquier auditor nuevo.
# Mantener corto; NO copiar todas las instrucciones del proyecto.
BOOTSTRAP_RULES = [
    "ChatGPT es auditor/arquitecto; OpenCode es ejecutor.",
    "GitHub vivo es fuente de verdad del producto.",
    "Las afirmaciones no equivalen a evidencia.",
    "Los cambios UI/UX requieren validación real cuando corresponda.",
    "No commit/push/tag/release/merge sin autorización.",
    "No relajar tests para hacerlos pasar.",
    "Ante fallo: reproducir -> diagnosticar -> corregir mínimo -> repetir.",
    "El producto prioriza la exploración visual; el playback es secundario.",
    "Antes de auditar una tarea, consultá get_audit_context.",
    "Las decisiones contextuales no pueden prevalecer silenciosamente sobre GitHub si hay contradicción.",
    "El mensaje actual del usuario debe procesarse antes de post_audit o queue_task. Si contiene preguntas, observaciones, restricciones, validación manual o decisiones además de la intención de continuar, deben respetarse y resolverse antes de avanzar. 'seguí' no es una cadena rígida: el bridge no interpreta lenguaje natural y esta regla pertenece al auditor/bootstrap. Una validación aportada por el usuario es evidencia humana y NO debe presentarse como test automático de OpenCode.",
]


class BridgeError(Exception):
    pass


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    bridge_dir = cfg.get("bridge_dir")
    if not bridge_dir:
        bridge_dir = ""
    # Portable: expande variables de entorno estilo Windows antes de usar como ruta,
    # p.ej. %LOCALAPPDATA%\\VisorVideosDevBridge. No aplica si no hay variables.
    bridge_dir = os.path.expandvars(bridge_dir)
    if not os.path.isdir(bridge_dir):
        raise BridgeError("config invalida: bridge_dir no existe")
    cfg["bridge_dir"] = bridge_dir
    return cfg


def _state_path(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "state", "state.json")


def _inbox_dir(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "state", "inbox")


def _resolutions_dir(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "state", "resolutions")


def _audits_dir(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "state", "audits")


def _audit_history_dir(bridge_dir: str) -> str:
    return os.path.join(_audits_dir(bridge_dir), "history")


def _cancellations_dir(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "state", "cancellations")


def _cancellations_history_dir(bridge_dir: str) -> str:
    return os.path.join(_cancellations_dir(bridge_dir), "history")


def _reports_dir(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "reports")


def _logs_dir(bridge_dir: str) -> str:
    return os.path.join(bridge_dir, "logs")


def _read_utf8(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if text.startswith("\ufeff"):
            text = text[1:]
        return text
    except OSError:
        return ""


def _task_evidence_paths(bridge_dir: str, task: dict, task_id: str) -> tuple:
    """Devuelve (out_path, err_path) preferidos para una tarea.

    Usa las rutas persistidas en el estado si existen; si no, deriva de logs/.
    """
    out = task.get("outFile") or os.path.join(_logs_dir(bridge_dir), "opencode-" + task_id + ".out")
    err = task.get("errFile") or os.path.join(_logs_dir(bridge_dir), "opencode-" + task_id + ".err")
    return out, err


def read_bridge_state(bridge_dir: str) -> dict:
    path = _state_path(bridge_dir)
    if not os.path.exists(path):
        return {"status": "SIN TAREA", "tasks": {}}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def valid_task_id(task_id) -> bool:
    if not isinstance(task_id, str):
        return False
    return bool(TASK_ID_RE.match(task_id)) and len(task_id) <= MAX_TASK_ID_LEN


def validate_prompt(prompt, max_bytes: int) -> None:
    if not isinstance(prompt, str):
        raise BridgeError("prompt debe ser texto")
    if len(prompt.strip()) == 0:
        raise BridgeError("prompt vacio")
    size = len(prompt.encode("utf-8"))
    if size > max_bytes:
        raise BridgeError("prompt demasiado grande: {} bytes (max {})".format(size, max_bytes))


def validate_execution_mode(execution_mode) -> None:
    if execution_mode is None:
        return  # usa el default MANUAL
    if not isinstance(execution_mode, str) or execution_mode not in VALID_EXECUTION_MODES:
        raise BridgeError("execution_mode invalido: debe ser MANUAL o AUTO_TECNICA")


def validate_expected(mode, expected_branch, expected_head, require_clean_worktree) -> None:
    if mode != EXECUTION_MODE_AUTO:
        return
    # B3.1: para AUTO_TECNICA, expected_branch y expected_head son OBLIGATORIOS
    if not isinstance(expected_branch, str) or not expected_branch.strip():
        raise BridgeError("expected_branch es obligatorio para AUTO_TECNICA")
    if not isinstance(expected_head, str) or not expected_head.strip():
        raise BridgeError("expected_head es obligatorio para AUTO_TECNICA")
    if require_clean_worktree is not None and not isinstance(require_clean_worktree, bool):
        raise BridgeError("require_clean_worktree debe ser booleano")


# B4.2: validacion de metadatos opcionales de contexto (context_scope / stage_id).
def validate_meta(value, max_len: int, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise BridgeError("{} debe ser texto".format(name))
    if not value.strip():
        raise BridgeError("{} vacio".format(name))
    if len(value) > max_len:
        raise BridgeError("{} demasiado largo: {} caracteres (max {})".format(name, len(value), max_len))
    if not CONTEXT_SCOPE_RE.match(value):
        raise BridgeError("{} invalido: 1..{} caracteres alfanumericos, punto, guion o guion bajo"
                          .format(name, max_len))


def pending_inbox_has(bridge_dir: str, task_id: str) -> bool:
    return os.path.exists(os.path.join(_inbox_dir(bridge_dir), task_id + ".task.json"))


def pending_resolution_has(bridge_dir: str, task_id: str) -> bool:
    return os.path.exists(os.path.join(_resolutions_dir(bridge_dir), task_id + ".resolution.json"))


def _audit_file(bridge_dir: str, task_id: str) -> str:
    return os.path.join(_audits_dir(bridge_dir), task_id + ".audit.json")


def pending_audit_has(bridge_dir: str, task_id: str) -> bool:
    return os.path.exists(_audit_file(bridge_dir, task_id))


def read_pending_audit(bridge_dir: str, task_id: str):
    path = _audit_file(bridge_dir, task_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def pending_cancel_has(bridge_dir: str, task_id: str) -> bool:
    return os.path.exists(os.path.join(_cancellations_dir(bridge_dir), task_id + ".cancel.json"))


# --- B4.2: contexto durable de auditoría -------------------------------

def _audit_history_file(bridge_dir: str, task_id: str) -> str:
    return os.path.join(_audit_history_dir(bridge_dir), task_id + ".audit.json")


def _read_audit_record(path: str):
    """Lee con tolerancia un record .audit.json. Devuelve dict o None si corrupto/ilegible."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _iter_audit_records(bridge_dir: str):
    """Itera todos los records .audit.json: pendientes (state/audits) y aplicados
    (state/audits/history). Compatible con records B4/B4.2 de cualquier antigüedad."""
    seen = set()
    order = [
        (_audits_dir(bridge_dir), False),
        (_audit_history_dir(bridge_dir), True),
    ]
    for d, applied in order:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".audit.json") or fname.startswith(".tmp"):
                continue
            rec = _read_audit_record(os.path.join(d, fname))
            if not rec or not isinstance(rec, dict):
                continue
            tid = rec.get("task_id")
            if tid in seen:
                continue
            seen.add(tid)
            meta = dict(rec)
            meta.setdefault("applied", applied)
            yield meta


def _scope_of_audit(rec: dict) -> str:
    return rec.get("context_scope") if isinstance(rec.get("context_scope"), str) else None


def _stage_of_audit(rec: dict) -> str:
    return rec.get("stage_id") if isinstance(rec.get("stage_id"), str) else None


def _decision_id(scope: str, context_scope, stage_id, statement: str) -> str:
    raw = "{}|{}|{}|{}".format(scope, context_scope or "", stage_id or "", statement)
    return "D-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _collect_decisions(bridge_dir: str, include_pending: bool = True):
    """Reconstruye el registro de decisiones durables a partir de los audit records.

    Devuelve: (decisiones, superseded_ids), donde:
      - decisiones: lista ordenada por audited_at/created_at (mas antiguas primero)
      - superseded_ids: conjunto de decision_id marcados como SUPERSEDED via
        supersedes_decision_ids en algún record posterior.
    Cada decision es un dict B4.2 (decision_id, context_scope, stage_id,
    origin_task_id, audited_at, statement, status ACTIVE/SUPERSEDED, scope BETA/PERMANENT).
    """
    decisions = []
    by_id = {}
    order_tags = []
    for rec in _iter_audit_records(bridge_dir):
        if not include_pending and not rec.get("applied"):
            continue
        tid = rec.get("task_id")
        scope = _scope_of_audit(rec)
        stage = _stage_of_audit(rec)
        audited_at = rec.get("audited_at") or rec.get("created_at") or ""
        for kind_key, kind_scope in (("beta_decisions", DECISION_SCOPE_BETA),
                                     ("permanent_decisions", DECISION_SCOPE_PERMANENT)):
            items = rec.get(kind_key) or []
            if not isinstance(items, list):
                continue
            for item in items:
                # Compatible con records nuevos (dict normalizado) y legacy (string).
                if isinstance(item, dict):
                    st = item.get("statement")
                else:
                    st = item
                if not isinstance(st, str) or not st.strip():
                    continue
                did = _decision_id(kind_scope, scope, stage, st)
                decisions.append({
                    "decision_id": did,
                    "context_scope": scope,
                    "stage_id": stage,
                    "origin_task_id": tid,
                    "audited_at": audited_at,
                    "statement": st,
                    "status": DECISION_STATUS_ACTIVE,
                    "scope": kind_scope,
                })
                by_id[did] = 1
        for did in (rec.get("supersedes_decision_ids") or []):
            if not isinstance(did, str) or not did.strip():
                continue
            order_tags.append(did)
    superseded_ids = {did for did in order_tags if did in by_id}
    _drop_duplicates(decisions)
    decisions.sort(key=lambda d: d["audited_at"])
    for d in decisions:
        if d["decision_id"] in superseded_ids:
            d["status"] = DECISION_STATUS_SUPERSEDED
    return decisions, superseded_ids


def _drop_duplicates(decisions) -> None:
    seen = set()
    keep = []
    for d in decisions:
        did = d["decision_id"]
        if did in seen:
            continue
        seen.add(did)
        keep.append(d)
    decisions[:] = keep


def _active_decisions_for_scope(decisions, scope: str, context_scope):
    """Decisiones activas no-superseded para un contexto (filtro por scope y betas).

    - BETA activas SOLO del mismo context_scope (aislamiento entre betas).
    - PERMANENT activas de cualquier contexto: pertenecen al ledger y deben
      verificarse contra la documentación oficial cuando proceda.
    """
    active = []
    for d in decisions:
        if d["status"] != DECISION_STATUS_ACTIVE:
            continue
        if d["scope"] == DECISION_SCOPE_BETA:
            if d["context_scope"] != context_scope:
                continue
        active.append(d)
    return active


def _recent_audit_summaries(bridge_dir: str, limit: int = MAX_RECENT_AUDIT_SUMMARIES):
    """Resúmenes de auditoría recientes (solo aplicados / pendientes aplicables)"""
    summed = []
    for rec in _iter_audit_records(bridge_dir):
        s = rec.get("audit_summary")
        if not isinstance(s, str) or not s.strip():
            continue
        summed.append({
            "task_id": rec.get("task_id"),
            "disposition": rec.get("disposition"),
            "audit_summary": s[:MAX_AUDIT_SUMMARY_CHARS],
            "audited_at": rec.get("audited_at") or rec.get("created_at") or "",
        })
    summed.sort(key=lambda x: x["audited_at"], reverse=True)
    return summed[:limit]


def _resolve_context_scope(bridge_dir: str, state: dict, task_id, context_scope):
    """Determina el context_scope a usar por get_audit_context.

    Prioridad de datos: si task_id corresponde a una tarea con context_scope,
    se usa ese scope. Si no, si viene context_scope explícito, se usa ese.
    Si no puede determinarse, devuelve ``None`` (get_audit_context lo reporta
    explícitamente como desconocido, sin inventar).
    """
    if task_id:
        t = (state.get("tasks") or {}).get(task_id)
        if t and isinstance(t, dict):
            scope = t.get("contextScope") or t.get("context_scope")
            stage = t.get("stageId") or t.get("stage_id")
            if isinstance(scope, str) and scope.strip():
                return scope, stage
    if isinstance(context_scope, str) and context_scope.strip():
        return context_scope.strip(), None
    return None, None


def _effective_audit_disposition(state: dict, bridge_dir: str, task_id: str):
    """Disposición de auditoría efectiva de una tarea: la persistida en el estado
    (ya aplicada por el executor) o la pendiente de aplicar (archivo audit)."""
    task = (state.get("tasks") or {}).get(task_id) or {}
    if task.get("auditedAt"):
        return task.get("auditDisposition")
    pending = read_pending_audit(bridge_dir, task_id)
    if pending and pending.get("disposition"):
        return pending.get("disposition")
    return None


def decide_acceptance(state: dict, task_id: str, previous_task_id=None, bridge_dir: str = None) -> dict:
    tasks = state.get("tasks") or {}
    status = state.get("status", "SIN TAREA")
    if task_id in tasks:
        return {"accepted": False, "duplicate": True, "resulting_state": status,
                "reason": "task_id ya existente (no se duplica)"}
    if status in PLAIN_STATUSES:
        if previous_task_id:
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "previous_task_id no aplica desde SIN TAREA (tarea independiente)"}
        return {"accepted": True, "duplicate": False, "resulting_state": RESULTING_STATUS,
                "reason": ""}
    if status == STATUS_DECISION:
        return {"accepted": False, "duplicate": False, "resulting_state": status,
                "reason": "decisión incompatible: resolvé la decisión pendiente antes de encolar"}
    if status == "TRABAJANDO":
        return {"accepted": False, "duplicate": False, "resulting_state": status,
                "reason": "hay una tarea en ejecución (TRABAJANDO)"}
    if status in LINKED_STATUSES:
        if not previous_task_id:
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "falta previous_task_id: la tarea anterior ({}) exige auditoría explícita".format(state.get("taskId"))}
        if previous_task_id != state.get("taskId"):
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "previous_task_id no coincide con la tarea vigente ({}). Debe ser la tarea anterior exacta".format(state.get("taskId"))}
        prev = tasks.get(previous_task_id)
        if prev is None:
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "previous_task_id no encontrado en el historial"}
        if prev.get("status") == "running":
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "la tarea anterior sigue TRABAJANDO: no se puede superseder"}
        if prev.get("supersededByTaskId"):
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "TASK_ID ya supersedido por {}".format(prev.get("supersededByTaskId"))}
        eff = _effective_audit_disposition(state, bridge_dir, previous_task_id)
        if eff not in QUEUEABLE_AUDIT_DISPOSITIONS:
            return {"accepted": False, "duplicate": False, "resulting_state": status,
                    "reason": "la tarea anterior no está auditada con CORRECTION/NEXT_STAGE (efectiva={}): usá post_audit primero".format(eff)}
        return {"accepted": True, "duplicate": False, "resulting_state": RESULTING_STATUS,
                "reason": ""}
    return {"accepted": False, "duplicate": False, "resulting_state": status,
            "reason": "estado actual {} no permite encolar".format(status)}


def write_inbox_atomic(bridge_dir: str, task_id: str, prompt: str,
                       execution_mode: str = DEFAULT_EXECUTION_MODE,
                       expected_branch=None, expected_head=None,
                       require_clean_worktree=None,
                       supersedes_task_id=None,
                       context_scope=None, stage_id=None) -> None:
    d = _inbox_dir(bridge_dir)
    os.makedirs(d, exist_ok=True)
    payload = {
        "task_id": task_id,
        "prompt": prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "mcp",
        "execution_mode": execution_mode,
        "expected_branch": expected_branch,
        "expected_head": expected_head,
        "require_clean_worktree": require_clean_worktree,
        "supersedes_task_id": supersedes_task_id,
        "context_scope": context_scope,
        "stage_id": stage_id,
    }
    tmp = os.path.join(d, ".tmp-" + uuid.uuid4().hex)
    final = os.path.join(d, task_id + ".task.json")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)


def queue_task(bridge_dir: str, task_id: str, prompt: str,
               max_prompt_bytes: int = DEFAULT_MAX_PROMPT_BYTES,
               execution_mode: str = DEFAULT_EXECUTION_MODE,
               expected_branch=None, expected_head=None,
               require_clean_worktree=None,
               previous_task_id=None,
               context_scope=None, stage_id=None) -> dict:
    base = {"task_id": task_id, "accepted": False, "duplicate": False,
            "resulting_state": None, "reason": ""}
    if not valid_task_id(task_id):
        base["reason"] = "task_id invalido: 1..128 caracteres alfanumericos, punto, guion o guion bajo"
        return base
    if previous_task_id is not None and not valid_task_id(previous_task_id):
        base["reason"] = "previous_task_id invalido: 1..128 caracteres alfanumericos, punto, guion o guion bajo"
        return base
    try:
        validate_prompt(prompt, max_prompt_bytes)
        validate_execution_mode(execution_mode)
        validate_expected(execution_mode, expected_branch, expected_head, require_clean_worktree)
        # B4.2: metadatos de contexto opcionales (compatibilidad para tareas históricas)
        validate_meta(context_scope, MAX_CONTEXT_SCOPE_LEN, "context_scope")
        validate_meta(stage_id, MAX_STAGE_ID_LEN, "stage_id")
    except BridgeError as exc:
        base["reason"] = str(exc)
        return base
    if execution_mode is None or execution_mode not in VALID_EXECUTION_MODES:
        execution_mode = DEFAULT_EXECUTION_MODE
    if execution_mode == EXECUTION_MODE_AUTO:
        # B3.1: expected_branch/expected_head ya validados como obligatorios en validate_expected.
        # require_clean_worktree conserva un default seguro.
        if require_clean_worktree is None:
            require_clean_worktree = DEFAULT_REQUIRE_CLEAN_WORKTREE
    state = read_bridge_state(bridge_dir)
    if pending_inbox_has(bridge_dir, task_id):
        base["duplicate"] = True
        base["resulting_state"] = state.get("status", "SIN TAREA")
        base["reason"] = "tarea pendiente en inbox"
        return base
    dec = decide_acceptance(state, task_id, previous_task_id, bridge_dir)
    base["resulting_state"] = dec["resulting_state"]
    if not dec["accepted"]:
        base["duplicate"] = dec["duplicate"]
        base["reason"] = dec["reason"]
        return base
    write_inbox_atomic(bridge_dir, task_id, prompt, execution_mode,
                       expected_branch, expected_head, require_clean_worktree,
                       supersedes_task_id=previous_task_id,
                       context_scope=context_scope, stage_id=stage_id)
    base["accepted"] = True
    base["resulting_state"] = RESULTING_STATUS
    base["execution_mode"] = execution_mode
    base["context_scope"] = context_scope
    base["stage_id"] = stage_id
    base["reason"] = ""
    return base


# --- CANCEL: solicitud durable de cancelación de tarea pendiente -------------

def validate_cancel_reason(reason) -> str:
    """Valida el motivo de cancelación: obligatorio, con trim, no vacío, max 200."""
    if not isinstance(reason, str):
        raise BridgeError("reason debe ser texto")
    trimmed = reason.strip()
    if not trimmed:
        raise BridgeError("reason vacio")
    if len(trimmed) > MAX_CANCEL_REASON_CHARS:
        raise BridgeError("reason demasiado grande: max {} caracteres".format(MAX_CANCEL_REASON_CHARS))
    return trimmed


def write_cancel_atomic(bridge_dir: str, task_id: str, reason: str) -> None:
    """Escribe atómicamente la solicitud de cancelación en state/cancellations.

    El MCP jamás escribe state.json; el executor es el único que aplica.
    """
    d = _cancellations_dir(bridge_dir)
    os.makedirs(d, exist_ok=True)
    payload = {
        "task_id": task_id,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "mcp",
    }
    tmp = os.path.join(d, ".tmp-" + uuid.uuid4().hex)
    final = os.path.join(d, task_id + ".cancel.json")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)


def _cancel_incompatible_reason(state: dict, task_id: str) -> str:
    """Motivo de rechazo si la tarea ya materializada no es cancelable (o "" si es cancelable)."""
    tasks = state.get("tasks") or {}
    t = tasks.get(task_id) or {}
    tstatus = t.get("status")
    if tstatus == TASK_STATUS_CANCELLED:
        return "la tarea ya fue cancelada"
    if tstatus == "running":
        return "la tarea esta TRABAJANDO: no se puede cancelar"
    if tstatus in ("done", "resolved", "failed", "decision", "superseded"):
        return "estado incompatible de la tarea ({}): no se puede cancelar".format(tstatus)
    if tstatus != "available":
        return "estado incompatible de la tarea ({}): no se puede cancelar".format(tstatus)
    if t.get("startedAt"):
        return "la tarea ya comenzo (startedAt presente): no se puede cancelar"
    if t.get("pid"):
        return "la tarea tiene un proceso asociado (pid presente): no se puede cancelar"
    if t.get("auditedAt"):
        return "la tarea ya fue auditada: no se puede cancelar"
    if t.get("supersedesTaskId"):
        return "la tarea pertenece a una cadena de supersesion (supersedesTaskId)"
    if t.get("supersededByTaskId"):
        return "la tarea pertenece a una cadena de supersesion (supersededByTaskId)"
    return ""


def cancel_task(bridge_dir: str, task_id: str, reason: str) -> dict:
    """Solicita durablemente la cancelación de una tarea pendiente.

    NO ejecuta OpenCode, NO toca state.json. Solo registra la solicitud en
    state/cancellations/<task_id>.cancel.json; el executor la aplica de forma
    asíncrona (available -> cancelled) en su siguiente ciclo.

    La respuesta inmediata solo informa que la SOLICITUD fue registrada, no que
    la tarea quedó cancelada.
    """
    base = {"task_id": task_id, "accepted": False, "duplicate": False,
            "resulting_state": None, "reason": ""}
    if not valid_task_id(task_id):
        base["reason"] = "task_id invalido: 1..128 caracteres alfanumericos, punto, guion o guion bajo"
        return base
    try:
        clean_reason = validate_cancel_reason(reason)
    except BridgeError as exc:
        base["reason"] = str(exc)
        return base
    state = read_bridge_state(bridge_dir)
    status = state.get("status", "SIN TAREA")
    base["resulting_state"] = status
    if pending_cancel_has(bridge_dir, task_id):
        base["duplicate"] = True
        base["reason"] = "solicitud de cancelación ya registrada (pendiente de aplicar)"
        return base
    if not pending_inbox_has(bridge_dir, task_id) and task_id not in (state.get("tasks") or {}):
        base["reason"] = "tarea inexistente (no está en inbox ni en el estado)"
        return base
    # Prevalidación conservadora si la tarea ya está materializada. El executor
    # re-valida como autoridad antes de aplicar; ante cualquier duda RECHAZA.
    if task_id in (state.get("tasks") or {}):
        incompat = _cancel_incompatible_reason(state, task_id)
        if incompat:
            base["reason"] = incompat
            return base
    write_cancel_atomic(bridge_dir, task_id, clean_reason)
    base["accepted"] = True
    base["reason"] = ""
    return base


def _validate_decisions(values, name: str) -> None:
    if values is None:
        return
    if not isinstance(values, list):
        raise BridgeError("{} debe ser una lista de strings".format(name))
    if len(values) > MAX_DECISIONS_PER_AUDIT:
        raise BridgeError("{} excede el maximo de {} decisiones".format(name, MAX_DECISIONS_PER_AUDIT))
    for d in values:
        if not isinstance(d, str) or not d.strip():
            raise BridgeError("{}: cada decision debe ser un string no vacio".format(name))
        if len(d) > MAX_DECISION_CHARS:
            raise BridgeError("{}: decision demasiado grande (max {} caracteres)".format(name, MAX_DECISION_CHARS))


def _record_decisions(scope: str, values, context_scope, stage_id, origin_task_id, audited_at):
    out = []
    for st in (values or []):
        out.append({
            "decision_id": _decision_id(scope, context_scope, stage_id, st),
            "context_scope": context_scope,
            "stage_id": stage_id,
            "origin_task_id": origin_task_id,
            "audited_at": audited_at,
            "statement": st,
            "status": DECISION_STATUS_ACTIVE,
            "scope": scope,
        })
    return out


def _validate_supersede(bridge_dir: str, bridge_supersede_ids, new_decisions, context_scope) -> dict:
    """Valida supersedes_decision_ids contra el ledger durable.

    Reglas de compatibilidad B4.2:
      - cada decision_id debe existir en el ledger (activo o superseded).
      - no puede supersederse una decision cuyo context_scope sea incompatible
        con el contexto actual (BETA/BETA del mismo scope; PERMANENT puede
        supersederse desde otro scope, pero nunca se fabrica).
      - no puede supersederse una decision con el propio trabajo nuevo.
    """
    if bridge_supersede_ids is None:
        return {"ok": True, "superseded_ids": []}
    if not isinstance(bridge_supersede_ids, list):
        return {"ok": False, "reason": "supersedes_decision_ids debe ser una lista"}
    if len(bridge_supersede_ids) > MAX_SUPERSEDES_IDS:
        return {"ok": False, "reason": "supersedes_decision_ids excede el maximo de {} ids".format(MAX_SUPERSEDES_IDS)}
    decisions, _sup = _collect_decisions(bridge_dir, include_pending=True)
    by_id = {d["decision_id"]: d for d in decisions}
    new_ids = {d["decision_id"] for d in new_decisions}
    valid = []
    for did in bridge_supersede_ids:
        if not isinstance(did, str) or not did.strip():
            return {"ok": False, "reason": "supersedes_decision_ids contiene un id invalido"}
        if did in new_ids:
            return {"ok": False, "reason": "no se puede superseder una decision recien creada ({})".format(did)}
        target = by_id.get(did)
        if target is None:
            return {"ok": False, "reason": "supersedes_decision_ids hace referencia a un decision_id inexistente ({})".format(did)}
        if target["scope"] == DECISION_SCOPE_BETA:
            if target["context_scope"] != context_scope:
                return {"ok": False,
                        "reason": "supersede incompatible: decision {} es BETA de {} y el contexto actual es {}".format(
                            did, target["context_scope"], context_scope)}
        valid.append(did)
    return {"ok": True, "superseded_ids": valid}


def post_audit(bridge_dir: str, task_id: str, disposition: str,
               decision_detail: str = None,
               audit_summary: str = None,
               beta_decisions=None,
               permanent_decisions=None,
               supersedes_decision_ids=None,
               context_scope=None, stage_id=None) -> dict:
    """Registra el resultado de la auditoría de ChatGPT sobre la tarea pendiente.

    Solo escritura atómica en state/audits (lo aplica el executor via Invoke-AuditPoll).
    NO ejecuta OpenCode ni shell, NO toca state.json.
    Disposiciones: APPROVED (-> SIN TAREA), CORRECTION/NEXT_STAGE (habilita
    queue_task con previous_task_id), USER_DECISION (-> DECISIÓN DE USUARIO REQUERIDA).

    B4.2 (contexto durable):
      - audit_summary es OBLIGATORIO para nuevas auditorías bajo B4.2 (<=2000 chars).
      - beta_decisions / permanent_decisions: listas de strings (<=2000 chars cada una,
        max 20 por auditoría) que se persisten con decision_id estable en el record.
      - supersedes_decision_ids: decision_ids previos que dejan de estar vigentes.
      - context_scope / stage_id: metadata opcional de contexto (heredada de la tarea
        si no se pasa explícitamente).
    """
    base = {"task_id": task_id, "accepted": False, "duplicate": False,
            "resulting_state": None, "reason": ""}
    if not valid_task_id(task_id):
        base["reason"] = "task_id invalido: 1..128 caracteres alfanumericos, punto, guion o guion bajo"
        return base
    if not isinstance(disposition, str) or disposition not in VALID_AUDIT_DISPOSITIONS:
        base["reason"] = "disposition invalida: debe ser APPROVED, CORRECTION, NEXT_STAGE o USER_DECISION"
        return base
    if disposition == "USER_DECISION":
        if not isinstance(decision_detail, str) or not decision_detail.strip():
            base["reason"] = "decision_detail es obligatorio para USER_DECISION"
            return base
    elif decision_detail is not None:
        base["reason"] = "decision_detail solo aplica para disposition USER_DECISION"
        return base
    try:
        # B4.2: audit_summary obligatorio para nuevas auditorías
        if not isinstance(audit_summary, str) or not audit_summary.strip():
            base["reason"] = "audit_summary es obligatorio (resumen corto del contexto que un auditor futuro necesita)"
            return base
        if len(audit_summary) > MAX_AUDIT_SUMMARY_CHARS:
            base["reason"] = "audit_summary demasiado grande: max {} caracteres".format(MAX_AUDIT_SUMMARY_CHARS)
            return base
        validate_meta(context_scope, MAX_CONTEXT_SCOPE_LEN, "context_scope")
        validate_meta(stage_id, MAX_STAGE_ID_LEN, "stage_id")
        _validate_decisions(beta_decisions, "beta_decisions")
        _validate_decisions(permanent_decisions, "permanent_decisions")
    except BridgeError as exc:
        base["reason"] = str(exc)
        return base
    state = read_bridge_state(bridge_dir)
    status = state.get("status", "SIN TAREA")
    base["resulting_state"] = status
    if status not in ATTENTION_STATUSES:
        base["reason"] = "no hay tarea pendiente de auditoría (estado: {})".format(status)
        return base
    if status == STATUS_DECISION:
        base["reason"] = "ya hay una decisión pendiente: usá resolve_decision"
        return base
    if state.get("taskId") != task_id:
        base["reason"] = "task_id no coincide con la tarea vigente ({})".format(state.get("taskId"))
        return base
    task = (state.get("tasks") or {}).get(task_id)
    if task is None:
        base["reason"] = "tarea desconocida"
        return base
    if task.get("status") == "running":
        base["reason"] = "la tarea está TRABAJANDO: no se puede auditar"
        return base
    if task.get("auditedAt"):
        base["duplicate"] = True
        base["reason"] = "la tarea ya fue auditada"
        return base
    if task.get("supersededByTaskId"):
        base["duplicate"] = True
        base["reason"] = "la tarea ya fue supersedida por {}".format(task.get("supersededByTaskId"))
        return base
    if pending_audit_has(bridge_dir, task_id):
        base["duplicate"] = True
        base["reason"] = "auditoría ya registrada (pendiente de aplicar)"
        return base
    if disposition == "APPROVED":
        resulting = "SIN TAREA"
    elif disposition == "USER_DECISION":
        resulting = STATUS_DECISION
    else:
        resulting = status
    # B4.2: contexto efectivo de la auditoría (heredado de la tarea si no viene explícito)
    if context_scope is None:
        context_scope = task.get("contextScope") or task.get("context_scope")
    if stage_id is None:
        stage_id = task.get("stageId") or task.get("stage_id")
    audited_at = datetime.now(timezone.utc).isoformat()
    beta_recs = _record_decisions(DECISION_SCOPE_BETA, beta_decisions, context_scope, stage_id, task_id, audited_at)
    perm_recs = _record_decisions(DECISION_SCOPE_PERMANENT, permanent_decisions, context_scope, stage_id, task_id, audited_at)
    all_new = beta_recs + perm_recs
    if isinstance(supersedes_decision_ids, list) and supersedes_decision_ids:
        check = _validate_supersede(bridge_dir, supersedes_decision_ids, all_new, context_scope)
        if not check["ok"]:
            base["reason"] = check["reason"]
            return base
    d = _audits_dir(bridge_dir)
    os.makedirs(d, exist_ok=True)
    payload = {
        "task_id": task_id,
        "disposition": disposition,
        "decision_detail": decision_detail,
        "created_at": audited_at,
        "source": "mcp",
        "audit_summary": audit_summary,
        "context_scope": context_scope,
        "stage_id": stage_id,
        "beta_decisions": beta_recs,
        "permanent_decisions": perm_recs,
        "supersedes_decision_ids": supersedes_decision_ids if isinstance(supersedes_decision_ids, list) else [],
    }
    tmp = os.path.join(d, ".tmp-" + uuid.uuid4().hex)
    final = os.path.join(d, task_id + ".audit.json")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)
    base["accepted"] = True
    base["resulting_state"] = resulting
    base["audit_summary"] = audit_summary
    base["reason"] = ""
    return base


def get_status(bridge_dir: str) -> dict:
    state = read_bridge_state(bridge_dir)
    status = state.get("status", "SIN TAREA")
    tasks = state.get("tasks") or {}
    pending = None
    avail = [(tid, t.get("createdAt", "")) for tid, t in tasks.items()
             if t.get("status") == "available"]
    if avail:
        pending = sorted(avail, key=lambda x: x[1])[0][0]
    if pending is None and status == "TAREA DISPONIBLE":
        pending = state.get("taskId")
    task_id_decision = None
    task_id_terminado = None
    report_available = False
    execution_mode = DEFAULT_EXECUTION_MODE
    auto_execute = False
    auto_blocked = False
    auto_block_reason = None
    pending_task = tasks.get(pending) or {}
    if pending_task:
        execution_mode = pending_task.get("executionMode", DEFAULT_EXECUTION_MODE)
        auto_execute = execution_mode == EXECUTION_MODE_AUTO
        auto_blocked = bool(pending_task.get("autoBlocked"))
        auto_block_reason = pending_task.get("autoBlockReason")
    if status == "DECISIÓN DE USUARIO REQUERIDA" and state.get("taskId"):
        task_id_decision = state.get("taskId")
    if status == "TERMINADO — ESPERANDO SEGUI" and state.get("taskId"):
        task_id_terminado = state.get("taskId")
        t = tasks.get(task_id_terminado) or {}
        if bool(t.get("reportOverflow")):
            report_available = True  # hay evidencia local aunque el report sustantivo exceda el limite
        else:
            out_path, err_path = _task_evidence_paths(bridge_dir, t, task_id_terminado)
            report_available = (
                t.get("reportStored")
                or os.path.exists(out_path)
                or os.path.exists(err_path)
                or t.get("exitCode") is not None
            )
    path = _state_path(bridge_dir)
    updated = None
    if os.path.exists(path):
        updated = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()
    attention_kind = ATTENTION_KIND_BY_STATUS.get(status, "NONE")
    attention_required = attention_kind != "NONE"
    attention_task_id = state.get("taskId") if attention_required else None
    # Fix B4: tras una CORRECTION/NEXT_STAGE YA aplicada, el estado global sigue siendo
    # un estado linked (TERMINADO/ERROR/BLOQUEADA), pero la tarea en atención ya NO
    # requiere post_audit: corresponde encolar la tarea correctiva relacionada.
    if attention_task_id and status in LINKED_STATUSES:
        eff = _effective_audit_disposition(state, bridge_dir, attention_task_id)
        if eff in QUEUEABLE_AUDIT_DISPOSITIONS:
            attention_kind = "RELATED"
            attention_required = True
    next_user_action = _next_user_action(status, attention_task_id, attention_kind)
    # B4.2: metadatos de contexto de la tarea en atención (context_scope / stage_id)
    task_context_scope = None
    task_stage_id = None
    if attention_task_id:
        t = tasks.get(attention_task_id) or {}
        task_context_scope = t.get("contextScope") or t.get("context_scope")
        task_stage_id = t.get("stageId") or t.get("stage_id")
    elif pending:
        t = tasks.get(pending) or {}
        task_context_scope = t.get("contextScope") or t.get("context_scope")
        task_stage_id = t.get("stageId") or t.get("stage_id")
    return {
        "estado": status,
        "task_id_pendiente": pending,
        "task_id_decision": task_id_decision,
        "task_id_terminado": task_id_terminado,
        "report_available": report_available,
        "trabajando": status == "TRABAJANDO",
        "execution_mode": execution_mode,
        "auto_execute": auto_execute,
        "auto_blocked": auto_blocked,
        "auto_block_reason": auto_block_reason,
        "attention_required": attention_required,
        "attention_kind": attention_kind,
        "attention_task_id": attention_task_id,
        "context_scope": task_context_scope,
        "stage_id": task_stage_id,
        "next_user_action": next_user_action,
        "updated_at": updated,
    }


def _next_user_action(status: str, task_id, attention_kind: str = ""):
    if task_id is None:
        task_id = "(pendiente)"
    if attention_kind == "RELATED":
        return ("ChatGPT debe encolar la tarea correctiva relacionada: queue_task(nueva_tarea, "
                "previous_task_id={}, ...). La tarea {} ya fue auditada y su disposición quedó "
                "aplicada; la auditoría de esa tarea ya está cerrada. previous_task_id debe ser "
                "exacto; una tarea independiente no puede pisar la cadena").format(task_id, task_id)
    if status == STATUS_TERMINADO:
        return ("ChatGPT debe: 1) get_audit_context({}); 2) get_report({}); 3) verificar "
                "GitHub vivo cuando corresponda; 4) auditar y registrar decisiones durables "
                "si surgieron; 5) post_audit para cerrar (APPROVED), encolar "
                "(CORRECTION/NEXT_STAGE y queue_task con previous_task_id) o escalar "
                "(USER_DECISION)").format(task_id, task_id)
    if status == STATUS_BLOQUEADA:
        return ("ChatGPT debe revisar auto_block_reason y, si corresponde, "
                "post_audit(CORRECTION/NEXT_STAGE) + queue_task(previous_task_id) "
                "para reemplazar la tarea bloqueada").format(task_id)
    if status == STATUS_ERROR:
        return ("ChatGPT debe auditar la evidencia con get_report({}) y encolar la "
                "corrección: post_audit(CORRECTION) + queue_task(previous_task_id)").format(task_id)
    if status == STATUS_DECISION:
        return ("El usuario debe decidir; ChatGPT aplica resolve_decision({}, <resolución>) "
                "con la elección").format(task_id)
    return ""


def get_report(bridge_dir: str, task_id: str) -> dict:
    """Recupera la evidencia local de una tarea (solo lectura, sin red ni shell).

    B1: una tarea cuyo proceso OpenCode terminó debe poder auditarse aunque NO exista
    un comentario [OPENCODE_REPORT] en GitHub. Devuelve stdout, stderr y exit code
    locales por TASK_ID y reporta la existencia (o no) del informe GitHub por separado.
    """
    base = {
        "task_id": task_id,
        "status": None,
        "resultado": None,
        "exit_code": None,
        "stdout": None,
        "stderr": None,
        "report_available": False,
        "github_report_found": False,
        "report_comment_id": None,
        "bridge_report_comment_id": None,
        "bridge_report_published": False,
        "bridge_report_pending": False,
        "bridge_report_adopted": False,
        "bridge_report_duplicates_detected": None,
        "reconciled_at": None,
        "github_report_resultado": None,
        "decision_requerida": False,
        "decision_detalle": None,
        "started_at": None,
        "completed_at": None,
        "out_file": None,
        "err_file": None,
        "report_bytes": None,
        "overflow": False,
        "execution_mode": None,
        "auto_started": False,
        "auto_blocked": False,
        "auto_block_reason": None,
        "audited_at": None,
        "audit_disposition": None,
        "audit_decision_detail": None,
        "supersedes_task_id": None,
        "superseded_by_task_id": None,
        "context_scope": None,
        "stage_id": None,
        "audit_summary": None,
        "cancelled_at": None,
        "cancel_reason": None,
        "cancel_source": None,
        "reason": "",
    }
    if not valid_task_id(task_id):
        base["status"] = "invalid_task_id"
        base["reason"] = "task_id invalido"
        return base
    state = read_bridge_state(bridge_dir)
    tasks = state.get("tasks") or {}
    if task_id not in tasks:
        base["status"] = "unknown"
        base["reason"] = "task desconocida"
        return base
    t = tasks[task_id] or {}
    tstatus = t.get("status", "unknown")
    base["status"] = tstatus
    base["execution_mode"] = t.get("executionMode", DEFAULT_EXECUTION_MODE)
    base["auto_started"] = bool(t.get("autoStarted"))
    base["auto_blocked"] = bool(t.get("autoBlocked"))
    base["auto_block_reason"] = t.get("autoBlockReason")
    base["audited_at"] = t.get("auditedAt")
    base["audit_disposition"] = t.get("auditDisposition")
    base["audit_decision_detail"] = t.get("auditDecisionDetail")
    base["supersedes_task_id"] = t.get("supersedesTaskId")
    base["superseded_by_task_id"] = t.get("supersededByTaskId")
    # B4.2: metadatos de contexto de la tarea (heredados de queue_task context_scope/stage_id)
    base["context_scope"] = t.get("contextScope") or t.get("context_scope")
    base["stage_id"] = t.get("stageId") or t.get("stage_id")
    # B4.2: audit_summary queda persistido en el estado (aplicado por el executor)
    base["audit_summary"] = t.get("auditSummary")
    base["cancelled_at"] = t.get("cancelledAt")
    base["cancel_reason"] = t.get("cancelReason")
    base["cancel_source"] = t.get("cancelSource")
    base["exit_code"] = t.get("exitCode")
    base["started_at"] = t.get("startedAt")
    base["completed_at"] = t.get("completedAt")
    base["report_comment_id"] = t.get("reportCommentId")
    base["bridge_report_comment_id"] = t.get("bridgeReportCommentId")
    base["bridge_report_published"] = bool(t.get("bridgeReportPublished")) or bool(t.get("bridgeReportCommentId"))
    base["bridge_report_pending"] = bool(t.get("bridgeReportPending"))
    base["bridge_report_adopted"] = bool(t.get("bridgeReportAdopted"))
    base["bridge_report_duplicates_detected"] = t.get("bridgeReportDuplicatesDetected")
    base["reconciled_at"] = t.get("reconciledAt")
    base["github_report_resultado"] = t.get("githubReportResultado")
    base["decision_detalle"] = t.get("decisionDetalle")
    base["decision_requerida"] = (tstatus == "decision")
    base["github_report_found"] = bool(t.get("githubReportFound")) or bool(t.get("reportCommentId"))

    out_path, err_path = _task_evidence_paths(bridge_dir, t, task_id)
    base["out_file"] = out_path if os.path.exists(out_path) else None
    base["err_file"] = err_path if os.path.exists(err_path) else None
    stdout = _read_utf8(out_path)
    stderr = _read_utf8(err_path)
    # si no hay .out (legacy), se cae al .report.txt basado en stdout
    if not stdout:
        stdout = _read_utf8(os.path.join(_reports_dir(bridge_dir), task_id + ".report.txt"))
    base["stdout"] = stdout
    base["stderr"] = stderr

    if tstatus in ("done", "resolved"):
        base["resultado"] = "TERMINADO"
    elif tstatus == "decision":
        base["resultado"] = "DECISION_REQUERIDA"
    elif tstatus == "running":
        base["resultado"] = "EN_EJECUCION"
    elif tstatus == "available":
        base["resultado"] = "PENDIENTE"
    elif tstatus == "failed":
        base["resultado"] = "ERROR"
    elif tstatus == TASK_STATUS_CANCELLED:
        base["resultado"] = "CANCELADA"

    # CANCEL: una tarea cancelada nunca tuvo evidencia de ejecución.
    if tstatus == TASK_STATUS_CANCELLED:
        base["report_available"] = False
        base["reason"] = ""
        return base

    if t.get("reportOverflow"):
        base["overflow"] = True
        base["report_bytes"] = t.get("reportBytes")
        base["status"] = "overflow"
        base["reason"] = "report excede el limite de almacenamiento"
        return base

    # evidencia local disponible = hay stdout, stderr o exit code registrado
    has_evidence = bool(stdout) or bool(stderr) or base["exit_code"] is not None
    base["report_available"] = has_evidence

    if tstatus in ("running", "available"):
        base["reason"] = "tarea todavia trabajando o pendiente"
        return base

    if not has_evidence:
        base["status"] = "no_report"
        base["reason"] = "no hay evidencia local para esta tarea"
        return base

    if t.get("reportStored"):
        base["report_bytes"] = t.get("reportBytes")
    base["reason"] = ""
    return base


def resolve_decision(bridge_dir: str, task_id: str, resolution: str,
                     max_resolution_bytes: int = DEFAULT_MAX_PROMPT_BYTES) -> dict:
    """Registra una resolucion humana para la decision pendiente y libera el state machine.

    Solo escritura atomica en state/resolutions. NO ejecuta OpenCode ni shell.
    """
    base = {"task_id": task_id, "accepted": False, "duplicate": False,
            "resulting_state": None, "reason": ""}
    if not valid_task_id(task_id):
        base["reason"] = "task_id invalido: 1..128 caracteres alfanumericos, punto, guion o guion bajo"
        return base
    if not isinstance(resolution, str) or len(resolution.strip()) == 0:
        base["reason"] = "resolution vacio"
        return base
    size = len(resolution.encode("utf-8"))
    if size > max_resolution_bytes:
        base["reason"] = "resolution demasiado grande: {} bytes (max {})".format(size, max_resolution_bytes)
        return base
    state = read_bridge_state(bridge_dir)
    status = state.get("status", "SIN TAREA")
    base["resulting_state"] = status
    if status != "DECISIÓN DE USUARIO REQUERIDA":
        base["reason"] = "no hay una decision pendiente (estado: {})".format(status)
        return base
    if state.get("taskId") != task_id:
        base["reason"] = "task_id no coincide con la decision pendiente"
        return base
    if pending_resolution_has(bridge_dir, task_id):
        base["duplicate"] = True
        base["reason"] = "resolucion ya registrada (pendiente de aplicar)"
        return base
    d = _resolutions_dir(bridge_dir)
    os.makedirs(d, exist_ok=True)
    payload = {
        "task_id": task_id,
        "resolution": resolution,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "mcp",
    }
    tmp = os.path.join(d, ".tmp-" + uuid.uuid4().hex)
    final = os.path.join(d, task_id + ".resolution.json")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final)
    base["accepted"] = True
    base["resulting_state"] = "SIN TAREA"
    base["reason"] = ""
    return base


def get_audit_context(bridge_dir: str, task_id=None, context_scope=None,
                      include_history: bool = False) -> dict:
    """Reconstruye el contexto durable de auditoría para una tarea o contexto.

    ESTRICTAMENTE read-only: NO ejecuta OpenCode, shell, git, GitHub, red ni
    modificaciones. No escribe nada. El contexto se reconstruye leyendo los
    registros .audit.json (pendientes y aplicados en state/audits/history).

    Retorna (compacto):
      protocol_version, project, repository, bootstrap_rules,
      context_scope (o "UNKNOWN" si no se puede determinar, sin inventar),
      current_stage, active_beta_decisions, active_permanent_decisions,
      recent_audit_summaries, superseded_decisions (solo include_history=true),
      warnings.
    """
    base = {
        "protocol_version": AUDIT_CONTEXT_PROTOCOL_VERSION,
        "project": PROJECT_NAME,
        "repository": REPOSITORY,
        "bootstrap_rules": list(BOOTSTRAP_RULES),
        "context_scope": None,
        "current_stage": None,
        "active_beta_decisions": [],
        "active_permanent_decisions": [],
        "recent_audit_summaries": [],
        "superseded_decisions": [] if include_history else None,
        "warnings": [],
        "reason": "",
    }
    if task_id is not None and not valid_task_id(task_id):
        base["reason"] = "task_id invalido"
        base["context_scope"] = "UNKNOWN"
        return base
    state = read_bridge_state(bridge_dir)
    scope, stage = _resolve_context_scope(bridge_dir, state, task_id, context_scope)
    warnings = []
    if scope is None:
        scope = "UNKNOWN"
        warnings.append("context_scope no determinado: se reporta UNKNOWN (sin inventar)")
    base["context_scope"] = scope
    base["current_stage"] = stage

    decisions, superseded_ids = _collect_decisions(bridge_dir, include_pending=True)
    active = _active_decisions_for_scope(decisions, scope, scope)
    beta_act = [d for d in active if d["scope"] == DECISION_SCOPE_BETA]
    perm_act = [d for d in active if d["scope"] == DECISION_SCOPE_PERMANENT]
    # orden: mas recientes primero para facilitar la lectura
    beta_act.sort(key=lambda d: d["audited_at"], reverse=True)
    perm_act.sort(key=lambda d: d["audited_at"], reverse=True)
    base["active_beta_decisions"] = beta_act
    base["active_permanent_decisions"] = perm_act
    base["recent_audit_summaries"] = _recent_audit_summaries(bridge_dir)
    if include_history:
        hist = [d for d in decisions if d["decision_id"] in superseded_ids]
        hist.sort(key=lambda d: d["audited_at"], reverse=True)
        base["superseded_decisions"] = hist
    if perm_act:
        warnings.append("las decisiones PERMANENT deben verificarse/promoverse contra la "
                        "documentación autoridad de GitHub cuando proceda")
    base["warnings"] = warnings
    base["reason"] = ""
    return base
