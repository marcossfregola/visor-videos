"""Servidor MCP real del puente ChatGPT <-> OpenCode (INFRA 0.4.2 + B4.2 + CANCEL + ABANDON).

Expone ocho herramientas:
  - get_status: lectura del estado del bridge (incluye campos de atención B4).
  - queue_task: encola una tarea en el bridge (TAREA DISPONIBLE). NO ejecuta OpenCode.
    Desde SIN TAREA encola tareas independientes; desde TERMINADO/ERROR/AUTOEJECUCIÓN
    BLOQUEADA solo encola una tarea RELACIONADA con previous_task_id exacto tras
    post_audit(CORRECTION/NEXT_STAGE). B4.2 agrega metadatos opcionales context_scope
    y stage_id para continuidad de auditoría.
  - post_audit: registra el resultado de la auditoría de ChatGPT (APPROVED /
    CORRECTION / NEXT_STAGE / USER_DECISION). Lo aplica el executor. B4.2 extiende la
    firma con audit_summary (obligatorio), beta_decisions, permanent_decisions,
    supersedes_decision_ids y metadatos de contexto.
  - resolve_decision: registra la resolucion humana de una decision pendiente y libera el state machine.
  - cancel_task: registra una solicitud durable de cancelación de una tarea pendiente
    (available o aun en inbox); la aplica el executor (available -> cancelled). NO
    ejecuta OpenCode y nunca cancela una tarea TRABAJANDO.
  - abandon_task: registra una solicitud durable de abandono administrativo de una tarea
    pendiente que nunca comenzó (available o aun en inbox); la aplica el executor
    (available -> abandoned; inbox -> descarte preservando el payload). NO ejecuta
    OpenCode y nunca abandona una tarea TRABAJANDO ni una tarea ya iniciada.
  - get_report: recupera la evidencia local de una tarea (solo lectura).
  - get_audit_context: reconstruye el contexto durable de auditoría para una tarea o
    contexto (solo lectura, sin red/shell/git/GitHub).

Las annotations describen el comportamiento REAL de cada herramienta
(readOnlyHint / destructiveHint / idempotentHint / openWorldHint del SDK MCP).

Transporte por defecto: stdio (lo lanza el tunnel-client).
"""

from __future__ import annotations

import argparse
import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from bridge_client import (  # noqa: E402
    load_config, queue_task, get_status, get_report, resolve_decision, post_audit,
    get_audit_context, cancel_task, abandon_task,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_HERE, "config.json")
_config = load_config(_CONFIG_PATH)
_BRIDGE_DIR = _config["bridge_dir"]
_MAX_PROMPT_BYTES = int(_config.get("max_prompt_bytes", 131072))

server = MCPServer("chatgpt-opencode-bridge-mcp")


@server.tool(
    name="get_status",
    title="Ver estado del bridge",
    description=(
        "Consulta el estado actual del bridge local (solo lectura): estado, tarea pendiente, "
        "tarea en decision, si el ejecutor esta trabajando y timestamp. Incluye los campos de "
        "atencion B4: attention_required, attention_kind (AUDIT / AUTO_BLOCKED / ERROR / "
        "USER_DECISION / RELATED / NONE), attention_task_id y next_user_action. "
        "Semantica de attention_kind: AUDIT = la tarea vigente todavia necesita auditoria "
        "(post_audit pendiente); RELATED = la tarea vigente YA fue auditada con una disposicion "
        "que habilita continuidad relacionada (CORRECTION o NEXT_STAGE) y la accion correcta es "
        "queue_task con previous_task_id exacto (no post_audit); AUTO_BLOCKED / ERROR / "
        "USER_DECISION / NONE segun corresponda. "
        "No ejecuta nada, no modifica nada y no devuelve secretos ni prompts."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_status_tool() -> dict:
    return get_status(_BRIDGE_DIR)


@server.tool(
    name="queue_task",
    title="Encolar tarea",
    description=(
        "Stores a task as pending in the local bridge. It never executes OpenCode or shell commands. "
        "execution_mode=MANUAL (default) requires an explicit human action (Process button). "
        "execution_mode=AUTO_TECNICA is an explicit structured authorization for safe technical "
        "tasks: expected_branch and expected_head are REQUIRED (mandatory), require_clean_worktree "
        "defaults to true. The executor auto-starts it when preconditions (repo identity, branch, "
        "HEAD, clean worktree, no other active execution, no pending resolution) hold. The prompt "
        "is only stored locally as a pending task; nothing from it is executed here.\n"
        "B4 handoff: from SIN TAREA any independent task is accepted. From TERMINADO -- ESPERANDO "
        "SEGUI / ERROR / AUTOEJECUCION BLOQUEADA, a task is accepted ONLY as the related "
        "correction/next-stage: previous_task_id must equal the current task and it must have been "
        "audited first via post_audit with CORRECTION or NEXT_STAGE. A repeated task_id is "
        "deduplicated and rejected.\n"
        "B4.2: context_scope and stage_id are OPTIONAL metadata for audit continuity "
        "(e.g. context_scope=B6, stage_id=B6.2). They are persisted with the task and exposed by "
        "get_status/get_report when available. The stage is NEVER inferred from the task_id."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def queue_task_tool(task_id: str, prompt: str,
                    execution_mode: str = "MANUAL",
                    expected_branch: str = None,
                    expected_head: str = None,
                    require_clean_worktree: bool = None,
                    previous_task_id: str = None,
                    context_scope: str = None,
                    stage_id: str = None) -> dict:
    return queue_task(_BRIDGE_DIR, task_id, prompt, _MAX_PROMPT_BYTES,
                      execution_mode, expected_branch, expected_head,
                      require_clean_worktree, previous_task_id,
                      context_scope, stage_id)


@server.tool(
    name="post_audit",
    title="Registrar auditoría de ChatGPT",
    description=(
        "Records the audit outcome for the task currently awaiting audit (B4). Operates only on "
        "the exact current task (task_id must match). Dispositions: APPROVED (approved with no "
        "next task -> controlled close to SIN TAREA), CORRECTION (close the previous task as "
        "audited/correction and enable queueing the related corrective task), NEXT_STAGE (same, "
        "approved, for the next stage), USER_DECISION (requires decision_detail; moves to "
        "DECISION DE USUARIO REQUERIDA so the human decides). It never executes OpenCode or shell, "
        "never writes state.json directly, and never creates a task. Rejects when task_id is not "
        "the current task, the task is TRABAJANDO, already audited, already superseded, or a "
        "decision is pending. After CORRECTION/NEXT_STAGE, call queue_task with "
        "previous_task_id=<task_id> to enqueue the related task.\n"
        "B4.2: audit_summary is REQUIRED for new audits (short summary, <=2000 chars). "
        "beta_decisions / permanent_decisions are optional lists of statements to persist as "
        "durable decisions (each <=2000 chars, max 20 per audit). supersedes_decision_ids marks "
        "previous decision_ids as SUPERSEDED (never deleted). context_scope / stage_id are "
        "optional metadata inherited from the task when omitted."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def post_audit_tool(task_id: str, disposition: str, audit_summary: str,
                    decision_detail: str = None,
                    beta_decisions: list = None,
                    permanent_decisions: list = None,
                    supersedes_decision_ids: list = None,
                    context_scope: str = None,
                    stage_id: str = None) -> dict:
    return post_audit(_BRIDGE_DIR, task_id, disposition, decision_detail,
                      audit_summary, beta_decisions, permanent_decisions,
                      supersedes_decision_ids, context_scope, stage_id)


@server.tool(
    name="resolve_decision",
    title="Resolver decision pendiente",
    description=(
        "Records a human resolution for the pending DECISIÓN DE USUARIO REQUERIDA task and releases "
        "the local state machine. It never executes OpenCode, shell or any task, and it never creates "
        "a new task. Requires the exact pending task_id and a non-empty resolution. "
        "Accepted only while a decision is pending for that task_id."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def resolve_decision_tool(task_id: str, resolution: str) -> dict:
    return resolve_decision(_BRIDGE_DIR, task_id, resolution, _MAX_PROMPT_BYTES)


@server.tool(
    name="cancel_task",
    title="Solicitar cancelación de tarea pendiente",
    description=(
        "Registra una solicitud durable de cancelación. La aplicación efectiva es asíncrona y "
        "corresponde al executor. Solo aplica a tareas pendientes que todavía no comenzaron: "
        "aún en inbox (state/inbox) o materializadas como 'available' en el estado. Solo tareas "
        "independientes: se rechaza una tarea que pertenezca a una cadena de supersesión "
        "(con supersedesTaskId / supersededByTaskId / supersedes_task_id) o que esté auditada. "
        "Nunca cancela una tarea TRABAJANDO, nunca mata procesos y nunca ejecuta OpenCode.\n"
        "task_id es obligatorio (sin comodines ni 'cancelar la actual'). reason es obligatorio, "
        "con trim, no vacío y hasta 200 caracteres. Esta tool NUNCA escribe state.json: solo "
        "escribe la solicitud atómica en state/cancellations/<task_id>.cancel.json y devuelve "
        "que la SOLICITUD fue registrada. La respuesta inmediata no afirma que la tarea quedó "
        "cancelada; el executor la aplica (available -> cancelled) en su siguiente ciclo y el "
        "resultado se observa luego con get_status/get_report."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def cancel_task_tool(task_id: str, reason: str) -> dict:
    return cancel_task(_BRIDGE_DIR, task_id, reason)


@server.tool(
    name="abandon_task",
    title="Solicitar abandono administrativo de tarea pendiente",
    description=(
        "Registra una solicitud durable de abandono administrativo. La aplicación efectiva es "
        "asíncrona y corresponde al executor. Solo aplica a tareas pendientes que todavía no "
        "comenzaron: aún en inbox (state/inbox) o materializadas como 'available' en el estado. "
        "v1: solo se abandona un eslabón con supersedesTaskId cuando se confirma explícitamente "
        "con confirm_chain_abandon=true (cadena preservada íntegra, la tarea anterior nunca se "
        "reactiva); una tarea con supersededByTaskId (ya reemplazada por otra) se rechaza SIEMPRE. "
        "Nunca abandona una tarea TRABAJANDO, una tarea ya iniciada (startedAt/pid), una tarea "
        "auditada ni una tarea con estado no pendiente. Nunca mata procesos y nunca ejecuta "
        "OpenCode.\n"
        "task_id es obligatorio (sin comodines ni 'abandonar la actual'). reason es obligatorio, "
        "con trim, no vacío y hasta 200 caracteres. confirm_chain_abandon es opcional (bool, "
        "default False). Esta tool NUNCA escribe state.json: solo escribe la solicitud atómica "
        "en state/abandonments/<task_id>.abandon.json y devuelve que la SOLICITUD fue registrada. "
        "La respuesta inmediata no afirma que la tarea quedó abandonada; el executor la aplica "
        "(available -> abandoned; inbox -> descarte preservando el payload) en su siguiente ciclo "
        "y el resultado se observa luego con get_status/get_report."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def abandon_task_tool(task_id: str, reason: str, confirm_chain_abandon: bool = False) -> dict:
    return abandon_task(_BRIDGE_DIR, task_id, reason, confirm_chain_abandon=confirm_chain_abandon)


@server.tool(
    name="get_report",
    title="Obtener evidencia de una tarea",
    description=(
        "Returns the local evidence (stdout, stderr and exit code) stored for a task_id, "
        "together with whether a GitHub [OPENCODE_REPORT] comment was found for it. "
        "A terminated task can be audited even when no GitHub report exists. Strictly "
        "read-only: no shell, no OpenCode, no git, no network, and it does not modify state "
        "or reports. Also exposes decision_requerida / decision_detalle, the GitHub report comment id "
        "when present, and the B4 audit trace (audited_at, audit_disposition, audit_decision_detail, "
        "supersedes_task_id, superseded_by_task_id)."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_report_tool(task_id: str) -> dict:
    return get_report(_BRIDGE_DIR, task_id)


@server.tool(
    name="get_audit_context",
    title="Obtener contexto durable de auditoría",
    description=(
        "Reconstructs the durable audit context for a task or scope (B4.2). Strictly read-only: "
        "no shell, no OpenCode, no git, no GitHub, no network and no writes. Reads the persisted "
        ".audit.json records (pending and applied in state/audits/history). Returns "
        "protocol_version, project (visor-videos), repository (marcossfregola/visor-videos), "
        "bootstrap_rules (short stable rules for any new auditor), the effective context_scope "
        "(or UNKNOWN when it cannot be determined, without inventing), current_stage when "
        "determinable, active_beta_decisions (same scope only, isolation between betas), "
        "active_permanent_decisions (any scope; must be verified against GitHub docs), "
        "recent_audit_summaries, and superseded_decisions only when include_history=true. "
        "If task_id is given and that task has a context_scope, it wins; otherwise the explicit "
        "context_scope is used.\n"
        "Recommended audit order when attention_kind=AUDIT: 1) get_audit_context(task_id); "
        "2) get_report(task_id); 3) verify live GitHub when applicable; 4) audit and record "
        "durable decisions if any arose; 5) post_audit."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_audit_context_tool(task_id: str = None,
                           context_scope: str = None,
                           include_history: bool = False) -> dict:
    return get_audit_context(_BRIDGE_DIR, task_id, context_scope, include_history)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP server del bridge (INFRA 0.4.2 + B4.2 + CANCEL + ABANDON)")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    if args.transport == "streamable-http":
        server.run(transport="streamable-http", host=args.host, port=args.port,
                   streamable_http_path="/mcp")
    else:
        server.run(transport="stdio")
