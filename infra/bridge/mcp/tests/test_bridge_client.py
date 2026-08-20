"""Pruebas unitarias de la integracion MCP -> bridge (INFRA 0.4).

Usan directorios temporales como bridge falso. No envian Telegram, no ejecutan
OpenCode y no tocan C:\\prueba. No usan subprocess en ningun camino probado.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge_client import (  # noqa: E402
    DEFAULT_MAX_PROMPT_BYTES,
    load_config,
    BridgeError,
    queue_task,
    get_status,
    get_report,
    resolve_decision,
    post_audit,
    get_audit_context,
    pending_audit_has,
    pending_inbox_has,
    cancel_task,
    pending_cancel_has,
    read_bridge_state,
    write_inbox_atomic,
)

_BRIDGE_TASKS = {
    "t-old": {"status": "done", "createdAt": "2026-08-16T10:00:00Z", "taskId": "t-old"},
}


def _write_state(bridge_dir, status, tasks=None):
    state_dir = os.path.join(bridge_dir, "state")
    os.makedirs(state_dir, exist_ok=True)
    payload = {"status": status, "tasks": tasks if tasks is not None else {}}
    with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


class BridgeClientTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bridge-mcp-test-")
        self.addCleanup(_rmtree, self.tmp)
        self.inbox = os.path.join(self.tmp, "state", "inbox")

    def _state(self, status, tasks=None):
        _write_state(self.tmp, status, tasks)

    def _inbox_files(self):
        if not os.path.isdir(self.inbox):
            return []
        return [f for f in os.listdir(self.inbox) if f.endswith(".task.json")]

    def _inbox_payload(self, task_id):
        with open(os.path.join(self.inbox, task_id + ".task.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)

    # 1. queue_task acepta una tarea valida estando SIN TAREA
    def test_acepta_en_sin_tarea(self):
        self._state("SIN TAREA", {})
        resp = queue_task(self.tmp, "task-001", "haz algo")
        self.assertTrue(resp["accepted"])
        self.assertEqual(resp["task_id"], "task-001")
        self.assertEqual(resp["resulting_state"], "TAREA DISPONIBLE")
        self.assertFalse(resp["duplicate"])
        self.assertEqual(self._inbox_files(), ["task-001.task.json"])

    # 2. conserva saltos de linea y Unicode exactos
    def test_conserva_unicode_y_saltos(self):
        self._state("SIN TAREA", {})
        prompt = "línea uno: ñoño éste\nlínea dos\r\nlínea tres — em dash ✅\n"
        resp = queue_task(self.tmp, "task-uni", prompt)
        self.assertTrue(resp["accepted"])
        payload = self._inbox_payload("task-uni")
        self.assertEqual(payload["prompt"], prompt)
        self.assertEqual(len(payload["prompt"]), len(prompt))

    # 3. task_id duplicado no genera otra tarea
    def test_duplicado_no_genera_otra(self):
        self._state("SIN TAREA", {})
        r1 = queue_task(self.tmp, "task-dup", "a")
        r2 = queue_task(self.tmp, "task-dup", "b")
        self.assertTrue(r1["accepted"])
        self.assertFalse(r2["accepted"])
        self.assertTrue(r2["duplicate"])
        self.assertEqual(self._inbox_files(), ["task-dup.task.json"])
        self.assertEqual(self._inbox_payload("task-dup")["prompt"], "a")

    # 3b. task_id ya existente en estado (persistido) no se re-encola
    def test_duplicado_persistente(self):
        self._state("SIN TAREA", dict(_BRIDGE_TASKS))
        r = queue_task(self.tmp, "t-old", "x")
        self.assertFalse(r["accepted"])
        self.assertTrue(r["duplicate"])

    # 4. segunda tarea diferente no sobrescribe tarea pendiente
    def test_segunda_tarea_no_sobrescribe(self):
        self._state("SIN TAREA", {})
        queue_task(self.tmp, "task-a", "a")
        self._state("TAREA DISPONIBLE", {"task-a": {"status": "available", "taskId": "task-a"}})
        r = queue_task(self.tmp, "task-b", "b")
        self.assertFalse(r["accepted"])
        self.assertFalse(r["duplicate"])
        self.assertEqual(r["resulting_state"], "TAREA DISPONIBLE")
        self.assertEqual(self._inbox_files(), ["task-a.task.json"])

    # 5. TRABAJANDO rechaza nueva tarea
    def test_trabajando_rechaza(self):
        self._state("TRABAJANDO", {"task-run": {"status": "running", "taskId": "task-run"}})
        r = queue_task(self.tmp, "task-nuevo", "x")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["resulting_state"], "TRABAJANDO")
        self.assertEqual(self._inbox_files(), [])

    # 6. DECISION rechaza nueva tarea
    def test_decision_rechaza(self):
        self._state("DECISIÓN DE USUARIO REQUERIDA", {})
        r = queue_task(self.tmp, "task-x", "x")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["resulting_state"], "DECISIÓN DE USUARIO REQUERIDA")

    # 7. ERROR no se pisa silenciosamente
    def test_error_no_se_pisa(self):
        self._state("ERROR", {})
        r = queue_task(self.tmp, "task-x", "x")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["resulting_state"], "ERROR")
        self.assertEqual(self._inbox_files(), [])

    # 8. get_status es solo lectura (no crea ni modifica archivos)
    def test_get_status_read_only(self):
        self._state("TRABAJANDO", {"t1": {"status": "running", "taskId": "t1"}})
        before = self._snapshot()
        st = get_status(self.tmp)
        after = self._snapshot()
        self.assertEqual(st["estado"], "TRABAJANDO")
        self.assertTrue(st["trabajando"])
        self.assertEqual(st["task_id_pendiente"], None)
        self.assertEqual(before, after)

    def _snapshot(self):
        items = {}
        for root, _dirs, files in os.walk(self.tmp):
            for f in files:
                p = os.path.join(root, f)
                items[os.path.relpath(p, self.tmp)] = (os.path.getsize(p),
                                                       os.path.getmtime(p))
        return items

    # 9. no aparecen secretos en las respuestas MCP
    def test_sin_secretos_en_respuestas(self):
        self._state("SIN TAREA", {})
        resp = queue_task(self.tmp, "task-sec", "prompt con contenido interno")
        joined = json.dumps(resp).lower()
        for secret in ("token", "api_key", "apikey", "password", "secret",
                       "authorizedUserId", "authorizedChatId"):
            self.assertNotIn(secret, joined)
        st = get_status(self.tmp)
        self.assertNotIn("prompt", json.dumps(st))
        # la respuesta de queue_task no debe incluir el prompt completo
        self.assertNotIn("prompt con contenido interno", json.dumps(resp))

    # 10. payload grande (>= 64 KiB) se conserva correctamente
    def test_payload_grande_64k(self):
        self._state("SIN TAREA", {})
        prompt = "A" * (64 * 1024)
        r = queue_task(self.tmp, "task-big", prompt)
        self.assertTrue(r["accepted"])
        self.assertEqual(self._inbox_payload("task-big")["prompt"], prompt)

    # 11. payload por encima del limite se rechaza explicitamente
    def test_payload_sobre_limite(self):
        self._state("SIN TAREA", {})
        prompt = "B" * (DEFAULT_MAX_PROMPT_BYTES + 1)
        r = queue_task(self.tmp, "task-toobig", prompt)
        self.assertFalse(r["accepted"])
        self.assertIn("demasiado grande", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    # 11b. el limite configurable se respeta
    def test_limite_configurable(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-x", "X" * 2048, max_prompt_bytes=1024)
        self.assertFalse(r["accepted"])
        self.assertIn("demasiado grande", r["reason"])

    # 12. ninguna prueba dispara opencode run ni telegram
    def test_no_ejecuta_opencode_ni_telegram(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-no", "haz la tarea sin abrir nada")
        self.assertTrue(r["accepted"])
        # solo debe existir el archivo de inbox; no hay logs ni salidas de opencode
        self.assertEqual(self._inbox_files(), ["task-no.task.json"])
        extra = [f for f in os.listdir(os.path.join(self.tmp, "state"))
                 if f not in ("state.json", "inbox")]
        self.assertEqual(extra, [])
        self.assertNotIn("opencode", json.dumps(r).lower())
        self.assertNotIn("telegram", json.dumps(r).lower())

    # 13. ningun test toca C:\prueba (todo usa directorios temporales)
    def test_no_toca_c_prueba(self):
        self.assertFalse(self.tmp.lower().startswith("c:\\prueba"))
        self.assertIn("temp", self.tmp.lower())

    # validaciones de input
    def test_task_id_invalido(self):
        self._state("SIN TAREA", {})
        for bad in ("", "a b", "a/b", "..", ".hidden", "x" * 129, None, 42):
            r = queue_task(self.tmp, bad, "x")
            self.assertFalse(r["accepted"], "deberia rechazar task_id={!r}".format(bad))
            self.assertTrue(r["reason"])

    def test_prompt_vacio(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-x", "   ")
        self.assertFalse(r["accepted"])
        self.assertIn("vacio", r["reason"])

    # --- resolve_decision ---

    def _decision_state(self):
        tasks = {"t1": {"status": "decision", "taskId": "t1",
                        "reportCommentId": "123", "createdAt": "2026-08-16T00:00:00Z"}}
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        payload = {"status": "DECISIÓN DE USUARIO REQUERIDA", "taskId": "t1",
                   "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    def _resolution_files(self):
        d = os.path.join(self.tmp, "state", "resolutions")
        if not os.path.isdir(d):
            return []
        return [f for f in os.listdir(d) if f.endswith(".resolution.json")]

    def _resolution_payload(self, task_id):
        with open(os.path.join(self.tmp, "state", "resolutions", task_id + ".resolution.json"),
                  "r", encoding="utf-8") as fh:
            return json.load(fh)

    # 5. resolve_decision fuera de ese estado -> reject
    def test_resolve_fuera_de_estado_reject(self):
        self._state("SIN TAREA", {})
        r = resolve_decision(self.tmp, "t1", "eleccion A")
        self.assertFalse(r["accepted"])
        self.assertIn("decision pendiente", r["reason"])

    def test_resolve_en_trabajando_reject(self):
        self._state("TRABAJANDO", {"t1": {"status": "running", "taskId": "t1"}})
        r = resolve_decision(self.tmp, "t1", "x")
        self.assertFalse(r["accepted"])

    # 6. task_id incorrecto -> reject
    def test_resolve_task_id_incorrecto(self):
        self._decision_state()
        r = resolve_decision(self.tmp, "otro-task", "x")
        self.assertFalse(r["accepted"])
        self.assertIn("no coincide", r["reason"])
        self.assertEqual(self._resolution_files(), [])

    # 7. resolution vacio -> reject
    def test_resolve_resolution_vacio(self):
        self._decision_state()
        for bad in ("", "   ", None, 42):
            r = resolve_decision(self.tmp, "t1", bad)
            self.assertFalse(r["accepted"], "deberia rechazar resolution={!r}".format(bad))
        self.assertEqual(self._resolution_files(), [])

    # 8. resolucion valida conserva el payload exacto (historial lo aplica el executor)
    def test_resolve_valido_escribe_payload(self):
        self._decision_state()
        r = resolve_decision(self.tmp, "t1", "usuario eligió: opción A ✅\ncon detalle")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["resulting_state"], "SIN TAREA")
        payload = self._resolution_payload("t1")
        self.assertEqual(payload["task_id"], "t1")
        self.assertEqual(payload["resolution"], "usuario eligió: opción A ✅\ncon detalle")
        self.assertEqual(payload["source"], "mcp")

    # 10. resolve_decision no ejecuta nada: solo crea el archivo de resolucion
    def test_resolve_no_ejecuta_nada(self):
        self._decision_state()
        r = resolve_decision(self.tmp, "t1", "ok")
        self.assertTrue(r["accepted"])
        extra = [f for f in os.listdir(os.path.join(self.tmp, "state"))
                 if f not in ("state.json", "inbox", "resolutions")]
        self.assertEqual(extra, [])
        self.assertEqual(self._resolution_files(), ["t1.resolution.json"])
        self.assertNotIn("opencode", json.dumps(r).lower())
        self.assertNotIn("shell", json.dumps(r).lower())

    def test_resolve_duplicado_pendiente(self):
        self._decision_state()
        resolve_decision(self.tmp, "t1", "primera")
        r2 = resolve_decision(self.tmp, "t1", "segunda")
        self.assertFalse(r2["accepted"])
        self.assertTrue(r2["duplicate"])
        self.assertEqual(self._resolution_payload("t1")["resolution"], "primera")

    # 11. queue_task sigue bloqueada mientras la decision este pendiente
    def test_queue_bloqueado_con_decision_pendiente(self):
        self._decision_state()
        r = queue_task(self.tmp, "task-nuevo", "x")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["resulting_state"], "DECISIÓN DE USUARIO REQUERIDA")
        self.assertEqual(self._inbox_files(), [])

    # 12. queue_task funciona despues de resolverla (simulando la aplicacion del executor)
    def test_queue_funciona_despues_de_resolver(self):
        self._decision_state()
        resolve_decision(self.tmp, "t1", "usuario decidió continuar")
        state = read_bridge_state(self.tmp)
        state["status"] = "SIN TAREA"
        state["taskId"] = None
        state["commentId"] = None
        state["tasks"]["t1"]["status"] = "resolved"
        state["tasks"]["t1"]["resolution"] = "usuario decidió continuar"
        with open(os.path.join(self.tmp, "state", "state.json"), "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
        r = queue_task(self.tmp, "task-posterior", "nueva")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["resulting_state"], "TAREA DISPONIBLE")
        self.assertEqual(self._inbox_files(), ["task-posterior.task.json"])

    # --- get_report ---

    def _write_full_state(self, status, task_id, task_fields):
        tasks = {task_id: dict({"taskId": task_id, "status": "done"}, **task_fields)}
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        payload = {"status": status, "taskId": task_id, "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    def _write_report_file(self, task_id, text):
        d = os.path.join(self.tmp, "reports")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, task_id + ".report.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)

    # 3. task_id invalido (incl. path traversal)
    def test_get_report_task_id_invalido(self):
        self._state("SIN TAREA", {})
        for bad in ("", "a b", "../secrets", "..\\..\\x", "x" * 129, None):
            r = get_report(self.tmp, bad)
            self.assertEqual(r["status"], "invalid_task_id", "deberia rechazar {!r}".format(bad))

    # 5. task inexistente
    def test_get_report_task_inexistente(self):
        self._state("SIN TAREA", {})
        r = get_report(self.tmp, "no-existe")
        self.assertEqual(r["status"], "unknown")
        self.assertFalse(r["report_available"])

    # 6. task trabajando sin report final
    def test_get_report_trabajando(self):
        self._write_full_state("TRABAJANDO", "t1", {"status": "running"})
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["status"], "running")
        self.assertFalse(r["report_available"])
        self.assertEqual(r["stdout"], "")
        self.assertEqual(r["stderr"], "")

    # 7. task terminada con evidencia local (stdout/stderr/exit) + informe GitHub -> auditable
    def test_get_report_terminada_con_report(self):
        texto = "HALLAZGO 1: el uninstaller borra biblioteca.db\nHALLAZGO 2: ñoño ✅\nConclusión: riesgo."
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1",
                               {"status": "done", "reportStored": True, "reportBytes": 10,
                                "reportCommentId": "555", "completedAt": "2026-08-16T00:00:00Z",
                                "exitCode": 0, "githubReportFound": True})
        self._write_report_file("t1", texto)
        r = get_report(self.tmp, "t1")
        self.assertTrue(r["report_available"])
        self.assertEqual(r["status"], "done")
        self.assertEqual(r["stdout"], texto)
        self.assertEqual(r["resultado"], "TERMINADO")
        self.assertEqual(r["report_comment_id"], "555")
        self.assertTrue(r["github_report_found"])
        self.assertEqual(r["exit_code"], 0)

    # 8. task decision con report + decision_detalle
    def test_get_report_decision_con_report(self):
        self._write_full_state("DECISIÓN DE USUARIO REQUERIDA", "t1",
                               {"status": "decision", "reportStored": True, "reportBytes": 10,
                                "reportCommentId": "666", "decisionDetalle": "elegir A o B",
                                "completedAt": "2026-08-16T00:00:00Z"})
        self._write_report_file("t1", "texto de la decision")
        r = get_report(self.tmp, "t1")
        self.assertTrue(r["decision_requerida"])
        self.assertEqual(r["decision_detalle"], "elegir A o B")
        self.assertEqual(r["resultado"], "DECISION_REQUERIDA")
        self.assertEqual(r["stdout"], "texto de la decision")

    # 9. get_report no modifica state
    def test_get_report_no_modifica(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1",
                               {"status": "done", "reportStored": True, "reportBytes": 10})
        self._write_report_file("t1", "x" * 20)
        before = self._snapshot()
        get_report(self.tmp, "t1")
        self.assertEqual(before, self._snapshot())

    # 10/11. get_report no ejecuta shell ni opencode: solo lee
    def test_get_report_no_ejecuta_nada(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1",
                               {"status": "done", "reportStored": True, "reportBytes": 10})
        self._write_report_file("t1", "ok")
        r = get_report(self.tmp, "t1")
        self.assertNotIn("opencode", json.dumps(r).lower())
        self.assertNotIn("shell", json.dumps(r).lower())

    # 12/13. exceso de limite -> overflow explicito, sin truncar
    def test_get_report_overflow(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1",
                               {"status": "done", "reportStored": False, "reportOverflow": True,
                                "reportBytes": 999999})
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["status"], "overflow")
        self.assertTrue(r["overflow"])
        self.assertFalse(r["report_available"])
        self.assertIn("limite", r["reason"])

    # task conocida sin report -> no_report
    def test_get_report_no_report(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {"status": "done"})
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["status"], "no_report")
        self.assertFalse(r["report_available"])

    # 14/15. get_status expone tarea terminada y report_available
    def test_get_status_tarea_terminada(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1",
                               {"status": "done", "reportStored": True, "reportBytes": 10})
        st = get_status(self.tmp)
        self.assertEqual(st["task_id_terminado"], "t1")
        self.assertTrue(st["report_available"])
        self.assertIsNone(st["task_id_pendiente"])

    # --- B1: auditar una ejecución TERMINADA sin informe GitHub ---

    def _write_full_evidence(self, task_id, task_fields, stdout, stderr):
        logs = os.path.join(self.tmp, "logs")
        os.makedirs(logs, exist_ok=True)
        out = os.path.join(logs, "opencode-" + task_id + ".out")
        err = os.path.join(logs, "opencode-" + task_id + ".err")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(stdout)
        with open(err, "w", encoding="utf-8") as fh:
            fh.write(stderr)
        return out, err

    # B1-1: TERMINADA sin informe GitHub -> auditable con stdout/stderr/exit, github_report_found=False
    def test_get_report_sin_informe_github(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T01:00:00Z"})
        self._write_full_evidence("t1", {}, "resumen sustantivo local\nconclusion",
                                  "permission requested: external_directory (...) auto-rejecting")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["status"], "done")
        self.assertTrue(r["report_available"])
        self.assertFalse(r["github_report_found"])
        self.assertIsNone(r["report_comment_id"])
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["stdout"], "resumen sustantivo local\nconclusion")
        self.assertIn("permission requested", r["stderr"])
        self.assertEqual(r["resultado"], "TERMINADO")

    # B1-2: TERMINADA con informe GitHub -> github_report_found=True y report_comment_id
    def test_get_report_con_informe_github(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "reportCommentId": "777",
            "githubReportFound": True, "completedAt": "2026-08-16T01:00:00Z"})
        self._write_full_evidence("t1", {}, "stdout ok", "stderr ok")
        r = get_report(self.tmp, "t1")
        self.assertTrue(r["github_report_found"])
        self.assertEqual(r["report_comment_id"], "777")
        self.assertTrue(r["report_available"])

    # B1-3: stderr vacío se devuelve explícitamente como cadena vacía, no se inventa
    def test_get_report_stderr_vacio_explicito(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T01:00:00Z"})
        self._write_full_evidence("t1", {}, "solo stdout", "")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["stderr"], "")
        self.assertEqual(r["stdout"], "solo stdout")

    # B1-4: aislamiento: la evidencia de una tarea no contamina a otra
    def test_get_report_aislamiento_entre_tareas(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {
            "t1": {"taskId": "t1", "status": "done", "exitCode": 0,
                   "completedAt": "2026-08-16T01:00:00Z"},
            "t2": {"taskId": "t2", "status": "done", "exitCode": 1,
                   "completedAt": "2026-08-16T02:00:00Z"},
        }
        payload = {"status": "TERMINADO — ESPERANDO SEGUI", "taskId": "t1",
                   "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        self._write_full_evidence("t1", {}, "evidencia de t1", "err t1")
        self._write_full_evidence("t2", {}, "evidencia de t2", "err t2")
        r1 = get_report(self.tmp, "t1")
        r2 = get_report(self.tmp, "t2")
        self.assertEqual(r1["stdout"], "evidencia de t1")
        self.assertEqual(r2["stdout"], "evidencia de t2")
        self.assertNotEqual(r1["exit_code"], r2["exit_code"])

    # B1.1: tarea failed por exit!=0 conserva la evidencia recuperable via get_report
    def test_get_report_exit_code_no_cero(self):
        self._write_full_state("ERROR", "t1", {
            "status": "failed", "exitCode": 1, "completedAt": "2026-08-16T03:00:00Z"})
        self._write_full_evidence("t1", {}, "stdout parcial de ejecucion fallida",
                                  "error real del proceso: comando no encontrado")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["resultado"], "ERROR")
        self.assertTrue(r["report_available"])
        self.assertEqual(r["exit_code"], 1)
        self.assertIn("stdout parcial", r["stdout"])
        self.assertIn("error real del proceso", r["stderr"])
        self.assertFalse(r["github_report_found"])

    # --- B2: registro durable y reconciliacion tardia expuestos en get_report ---

    # B2: bridge_report_comment_id y bridge_report_published tras publicar el recibo durable
    def test_get_report_bridge_report_publicado(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T04:00:00Z",
            "bridgeReportCommentId": "900001", "bridgeReportPublished": True})
        self._write_full_evidence("t1", {}, "stdout", "stderr")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["bridge_report_comment_id"], "900001")
        self.assertTrue(r["bridge_report_published"])
        self.assertFalse(r["bridge_report_pending"])

    # B2: publicacion durable pendiente (GitHub caido) es visible
    def test_get_report_bridge_report_pendiente(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T04:00:00Z",
            "bridgeReportPending": True, "bridgeReportRetryAt": "2026-08-16T05:00:00Z"})
        self._write_full_evidence("t1", {}, "stdout", "stderr")
        r = get_report(self.tmp, "t1")
        self.assertTrue(r["bridge_report_pending"])
        self.assertFalse(r["bridge_report_published"])

    # B2: reconciliacion tardia expone reconciled_at y github_report_resultado
    def test_get_report_reconciliado(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T04:00:00Z",
            "reportCommentId": "888111", "githubReportFound": True,
            "reconciledAt": "2026-08-16T06:00:00Z", "githubReportResultado": "OK"})
        self._write_full_evidence("t1", {}, "stdout", "stderr")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["reconciled_at"], "2026-08-16T06:00:00Z")
        self.assertEqual(r["github_report_resultado"], "OK")
        self.assertTrue(r["github_report_found"])
        self.assertEqual(r["report_comment_id"], "888111")

    # B2: get_report conserva los campos B1 junto a los nuevos (compatibilidad)
    def test_get_report_b2_conserva_b1(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T04:00:00Z",
            "reportCommentId": "888222", "githubReportFound": True,
            "bridgeReportCommentId": "900002", "reconciledAt": "2026-08-16T07:00:00Z"})
        self._write_full_evidence("t1", {}, "evidencia stdout", "evidencia stderr")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["stdout"], "evidencia stdout")
        self.assertEqual(r["stderr"], "evidencia stderr")
        self.assertEqual(r["exit_code"], 0)
        self.assertTrue(r["report_available"])
        self.assertEqual(r["report_comment_id"], "888222")
        self.assertEqual(r["bridge_report_comment_id"], "900002")

    # B2.1: get_report expone adopcion del BRIDGE_EXECUTION_REPORT existente y duplicados detectados
    def test_get_report_bridge_report_adoptado(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T04:00:00Z",
            "bridgeReportCommentId": "5310555001", "bridgeReportPublished": True,
            "bridgeReportAdopted": True, "bridgeReportDuplicatesDetected": 2})
        self._write_full_evidence("t1", {}, "stdout", "stderr")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["bridge_report_comment_id"], "5310555001")
        self.assertTrue(r["bridge_report_published"])
        self.assertTrue(r["bridge_report_adopted"])
        self.assertEqual(r["bridge_report_duplicates_detected"], 2)

    # --- B3: AUTO_TECNICA ---

    # B3: execution_mode invalido es rechazado
    def test_execution_mode_invalido_rechazado(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-x", "prompt", execution_mode="INVALIDO")
        self.assertFalse(r["accepted"])
        self.assertIn("execution_mode", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    # B3: default MANUAL se persiste como tal
    def test_execution_mode_default_manual(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-man", "prompt")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["execution_mode"], "MANUAL")
        payload = self._inbox_payload("task-b3-man")
        self.assertEqual(payload["execution_mode"], "MANUAL")

    # B3: AUTO_TECNICA valida con precondiciones obligatorias
    def test_execution_mode_auto_tecnica(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-auto", "prompt", execution_mode="AUTO_TECNICA",
                       expected_branch="beta6",
                       expected_head="8b6f19fbbddee6ce6099495b7682188fc8665293",
                       require_clean_worktree=True)
        self.assertTrue(r["accepted"])
        self.assertEqual(r["execution_mode"], "AUTO_TECNICA")
        payload = self._inbox_payload("task-b3-auto")
        self.assertEqual(payload["execution_mode"], "AUTO_TECNICA")
        self.assertEqual(payload["expected_branch"], "beta6")
        self.assertEqual(payload["expected_head"], "8b6f19fbbddee6ce6099495b7682188fc8665293")
        self.assertTrue(payload["require_clean_worktree"])

    # B3.1-9: AUTO_TECNICA sin expected_branch -> rechazado
    def test_execution_mode_auto_sin_branch_rechazado(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-nobranch", "prompt", execution_mode="AUTO_TECNICA",
                       expected_head="8b6f19fbbddee6ce6099495b7682188fc8665293")
        self.assertFalse(r["accepted"])
        self.assertIn("expected_branch", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    # B3.1-10: AUTO_TECNICA sin expected_head -> rechazado
    def test_execution_mode_auto_sin_head_rechazado(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-nohead", "prompt", execution_mode="AUTO_TECNICA",
                       expected_branch="beta6")
        self.assertFalse(r["accepted"])
        self.assertIn("expected_head", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    # B3.1-11: MANUAL sin expected_branch/head -> valido (compatibilidad)
    def test_execution_mode_manual_sin_expected_valido(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-manual", "prompt", execution_mode="MANUAL")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["execution_mode"], "MANUAL")

    # B3: AUTO_TECNICA con expected explicito se conserva
    def test_execution_mode_auto_expected_explicito(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-b3-exp", "prompt", execution_mode="AUTO_TECNICA",
                       expected_branch="beta6",
                       expected_head="8b6f19fbbddee6ce6099495b7682188fc8665293",
                       require_clean_worktree=True)
        self.assertTrue(r["accepted"])
        payload = self._inbox_payload("task-b3-exp")
        self.assertEqual(payload["expected_branch"], "beta6")
        self.assertEqual(payload["expected_head"], "8b6f19fbbddee6ce6099495b7682188fc8665293")
        self.assertTrue(payload["require_clean_worktree"])

    # B3: get_status expone execution_mode / auto_execute
    def test_get_status_expone_modo(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {"t-auto": {"taskId": "t-auto", "status": "available",
                            "createdAt": "2026-08-16T10:00:00Z", "executionMode": "AUTO_TECNICA"}}
        payload = {"status": "TAREA DISPONIBLE", "taskId": "t-auto",
                   "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        st = get_status(self.tmp)
        self.assertEqual(st["execution_mode"], "AUTO_TECNICA")
        self.assertTrue(st["auto_execute"])
        self.assertFalse(st["auto_blocked"])

    # B3: get_status expone bloqueo
    def test_get_status_expone_bloqueo(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {"t-b": {"taskId": "t-b", "status": "available",
                         "createdAt": "2026-08-16T10:00:00Z", "executionMode": "AUTO_TECNICA",
                         "autoBlocked": True, "autoBlockReason": "HEAD incorrecto"}}
        payload = {"status": "AUTOEJECUCIÓN BLOQUEADA", "taskId": "t-b",
                   "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        st = get_status(self.tmp)
        self.assertEqual(st["estado"], "AUTOEJECUCIÓN BLOQUEADA")
        self.assertTrue(st["auto_blocked"])
        self.assertEqual(st["auto_block_reason"], "HEAD incorrecto")

    # B3: get_report conserva compatibilidad B1/B2 y expone metadata AUTO
    def test_get_report_conserva_b1_b2_y_auto(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T04:00:00Z",
            "reportCommentId": "888333", "githubReportFound": True,
            "bridgeReportCommentId": "900003", "executionMode": "AUTO_TECNICA",
            "autoStarted": True})
        self._write_full_evidence("t1", {}, "stdout ok", "stderr ok")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["stdout"], "stdout ok")
        self.assertEqual(r["stderr"], "stderr ok")
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["report_comment_id"], "888333")
        self.assertEqual(r["bridge_report_comment_id"], "900003")
        self.assertEqual(r["execution_mode"], "AUTO_TECNICA")
        self.assertTrue(r["auto_started"])
        self.assertFalse(r["auto_blocked"])

    # --- B4: atención (get_status) ---

    def _attention_state(self, status, task_id, task_fields=None):
        tasks = {task_id: dict({"taskId": task_id, "status": "done"}, **(task_fields or {}))}
        if status == "DECISIÓN DE USUARIO REQUERIDA":
            tasks[task_id]["status"] = "decision"
        elif status == "ERROR":
            tasks[task_id]["status"] = "failed"
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        payload = {"status": status, "taskId": task_id, "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    def test_get_status_attention_audit(self):
        self._attention_state("TERMINADO — ESPERANDO SEGUI", "t1")
        st = get_status(self.tmp)
        self.assertTrue(st["attention_required"])
        self.assertEqual(st["attention_kind"], "AUDIT")
        self.assertEqual(st["attention_task_id"], "t1")
        self.assertIn("get_report", st["next_user_action"])

    def test_get_status_attention_auto_blocked(self):
        self._attention_state("AUTOEJECUCIÓN BLOQUEADA", "t1",
                              {"executionMode": "AUTO_TECNICA", "autoBlocked": True,
                               "autoBlockReason": "HEAD incorrecto"})
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "AUTO_BLOCKED")
        self.assertTrue(st["attention_required"])
        self.assertIn("post_audit", st["next_user_action"])

    def test_get_status_attention_error(self):
        self._attention_state("ERROR", "t1", {"exitCode": 1})
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "ERROR")
        self.assertTrue(st["attention_required"])
        self.assertIn("queue_task", st["next_user_action"])

    def test_get_status_attention_user_decision(self):
        self._attention_state("DECISIÓN DE USUARIO REQUERIDA", "t1")
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "USER_DECISION")
        self.assertTrue(st["attention_required"])
        self.assertIn("resolve_decision", st["next_user_action"])

    def test_get_status_attention_none(self):
        self._state("SIN TAREA", {})
        st = get_status(self.tmp)
        self.assertFalse(st["attention_required"])
        self.assertEqual(st["attention_kind"], "NONE")
        self.assertIsNone(st["attention_task_id"])
        self.assertEqual(st["next_user_action"], "")

    def test_get_status_atencion_no_rompe_read_only(self):
        self._attention_state("TERMINADO — ESPERANDO SEGUI", "t1")
        before = self._snapshot()
        get_status(self.tmp)
        self.assertEqual(before, self._snapshot())

    def test_get_status_correction_aplicada_no_es_audit(self):
        # B4: tras CORRECTION aplicada el estado global sigue TERMINADO, pero la
        # tarea ya está auditada: NO debe aparecer como auditoría pendiente.
        self._attention_state("TERMINADO — ESPERANDO SEGUI", "t1",
                              {"auditedAt": "2026-08-16T00:01:00Z",
                               "auditDisposition": "CORRECTION"})
        st = get_status(self.tmp)
        self.assertTrue(st["attention_required"])
        self.assertEqual(st["attention_kind"], "RELATED")
        self.assertEqual(st["attention_task_id"], "t1")
        self.assertIn("queue_task", st["next_user_action"])
        self.assertIn("previous_task_id=t1", st["next_user_action"])
        self.assertNotIn("post_audit", st["next_user_action"])

    def test_get_status_next_stage_aplicado_no_es_audit(self):
        self._attention_state("TERMINADO — ESPERANDO SEGUI", "t1",
                              {"auditedAt": "2026-08-16T00:01:00Z",
                               "auditDisposition": "NEXT_STAGE"})
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "RELATED")
        self.assertIn("previous_task_id=t1", st["next_user_action"])

    def test_get_status_correction_pendiente_no_es_audit(self):
        # entre post_audit y la aplicación del executor existe el archivo pendiente:
        # ya no debería insistir con post_audit.
        self._attention_state("TERMINADO — ESPERANDO SEGUI", "t1")
        self._pending_audit("t1", "CORRECTION")
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "RELATED")
        self.assertNotIn("post_audit", st["next_user_action"])

    def test_get_status_approved_aplicada_seguira_sin_tarea(self):
        # APPROVED aplicada va a SIN TAREA → sin atención (no se toca el contrato).
        self._attention_state("TERMINADO — ESPERANDO SEGUI", "t1",
                              {"auditedAt": "2026-08-16T00:01:00Z",
                               "auditDisposition": "APPROVED"})
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "AUDIT")
        self.assertTrue(st["attention_required"])
        self.assertIn("post_audit", st["next_user_action"])

    def test_get_status_bloqueada_correction_aplicada_related(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {"t1": {"taskId": "t1", "status": "available",
                        "auditedAt": "2026-08-16T00:01:00Z",
                        "auditDisposition": "CORRECTION"}}
        payload = {"status": "AUTOEJECUCIÓN BLOQUEADA", "taskId": "t1",
                   "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "RELATED")
        self.assertIn("previous_task_id=t1", st["next_user_action"])

    def test_get_status_error_correction_aplicada_related(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {"t1": {"taskId": "t1", "status": "failed", "exitCode": 1,
                        "auditedAt": "2026-08-16T00:01:00Z",
                        "auditDisposition": "CORRECTION"}}
        payload = {"status": "ERROR", "taskId": "t1", "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        st = get_status(self.tmp)
        self.assertEqual(st["attention_kind"], "RELATED")
        self.assertIn("previous_task_id=t1", st["next_user_action"])

    # --- B4: get_report expone trazabilidad ---

    def test_get_report_expone_trazabilidad(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1", {
            "status": "done", "exitCode": 0, "completedAt": "2026-08-16T00:00:00Z",
            "auditedAt": "2026-08-16T00:01:00Z", "auditDisposition": "CORRECTION",
            "auditDecisionDetail": None, "supersedesTaskId": None,
            "supersededByTaskId": "t2"})
        self._write_full_evidence("t1", {}, "x", "y")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["audited_at"], "2026-08-16T00:01:00Z")
        self.assertEqual(r["audit_disposition"], "CORRECTION")
        self.assertIsNone(r["audit_decision_detail"])
        self.assertIsNone(r["supersedes_task_id"])
        self.assertEqual(r["superseded_by_task_id"], "t2")

    # --- B4: queue_task con previous_task_id (protección y flujo A/B) ---

    def _linked_state(self, status, task_id, task_fields=None):
        tasks = {task_id: dict({"taskId": task_id, "status": "done"}, **(task_fields or {}))}
        if status == "ERROR":
            tasks[task_id]["status"] = "failed"
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        payload = {"status": status, "taskId": task_id, "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    def _pending_audit(self, task_id, disposition, detail=None):
        d = os.path.join(self.tmp, "state", "audits")
        os.makedirs(d, exist_ok=True)
        payload = {"task_id": task_id, "disposition": disposition,
                   "decision_detail": detail, "source": "mcp"}
        with open(os.path.join(d, task_id + ".audit.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    def test_terminado_requiere_previous_task_id(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = queue_task(self.tmp, "task-nuevo", "x")
        self.assertFalse(r["accepted"])
        self.assertIn("previous_task_id", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    def test_terminado_previous_no_coincide(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="otra")
        self.assertFalse(r["accepted"])
        self.assertIn("no coincide", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    def test_terminado_previous_sin_auditar(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertFalse(r["accepted"])
        self.assertIn("post_audit", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    def test_terminado_previous_auditada_correction_acepta(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1",
                           {"auditedAt": "2026-08-16T00:01:00Z", "auditDisposition": "CORRECTION"})
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["resulting_state"], "TAREA DISPONIBLE")
        payload = self._inbox_payload("task-nuevo")
        self.assertEqual(payload["supersedes_task_id"], "t1")

    def test_terminado_previous_auditada_pendiente_acepta(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        self._pending_audit("t1", "NEXT_STAGE")
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertTrue(r["accepted"])
        self.assertTrue(pending_audit_has(self.tmp, "t1"))

    def test_terminado_previous_disposicion_approved_no_encola(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1",
                           {"auditedAt": "2026-08-16T00:01:00Z", "auditDisposition": "APPROVED"})
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertFalse(r["accepted"])
        self.assertIn("CORRECTION", r["reason"])
        self.assertEqual(self._inbox_files(), [])

    def test_previous_supersedida_rechaza(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1",
                           {"auditedAt": "2026-08-16T00:01:00Z", "auditDisposition": "CORRECTION",
                            "supersededByTaskId": "t2"})
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertFalse(r["accepted"])
        self.assertIn("supersedido", r["reason"])

    def test_previous_trabajando_rechaza(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {"t1": {"taskId": "t1", "status": "running"}}
        payload = {"status": "TRABAJANDO", "taskId": "t1", "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertFalse(r["accepted"])
        self.assertEqual(self._inbox_files(), [])

    def test_error_sin_previous_rechaza_y_con_auditoria_acepta(self):
        # El test historico "no se pisa un ERROR" se mantiene: un queue_task comun
        # desde ERROR sigue siendo rechazado.
        self._linked_state("ERROR", "t1")
        r = queue_task(self.tmp, "task-nuevo", "x")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["resulting_state"], "ERROR")
        self.assertEqual(self._inbox_files(), [])
        # La transición auditada explícita desde ERROR sí se acepta.
        self._pending_audit("t1", "CORRECTION")
        r2 = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertTrue(r2["accepted"])
        self.assertEqual(self._inbox_payload("task-nuevo")["supersedes_task_id"], "t1")

    def test_bloqueada_sin_previous_rechaza(self):
        self._linked_state("AUTOEJECUCIÓN BLOQUEADA", "t1",
                           {"executionMode": "AUTO_TECNICA", "autoBlocked": True})
        r = queue_task(self.tmp, "task-nuevo", "x")
        self.assertFalse(r["accepted"])
        self.assertIn("previous_task_id", r["reason"])

    def test_bloqueada_auditada_acepta_y_supersede(self):
        self._linked_state("AUTOEJECUCIÓN BLOQUEADA", "t1",
                           {"executionMode": "AUTO_TECNICA", "autoBlocked": True,
                            "autoBlockReason": "HEAD incorrecto", "status": "available",
                            "auditedAt": "2026-08-16T00:01:00Z", "auditDisposition": "CORRECTION"})
        r = queue_task(self.tmp, "task-nuevo", "x", previous_task_id="t1")
        self.assertTrue(r["accepted"])
        self.assertEqual(self._inbox_payload("task-nuevo")["supersedes_task_id"], "t1")

    def test_sin_tarea_con_previous_rechaza(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-x", "x", previous_task_id="t1")
        self.assertFalse(r["accepted"])
        self.assertIn("previous_task_id no aplica", r["reason"])

    def test_previous_task_id_invalido(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "task-x", "x", previous_task_id="a b/..")
        self.assertFalse(r["accepted"])
        self.assertIn("previous_task_id invalido", r["reason"])

    # --- B4: post_audit ---

    def _audit_files(self):
        d = os.path.join(self.tmp, "state", "audits")
        if not os.path.isdir(d):
            return []
        return [f for f in os.listdir(d) if f.endswith(".audit.json")]

    def _audit_payload(self, task_id):
        with open(os.path.join(self.tmp, "state", "audits", task_id + ".audit.json"),
                  "r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_post_audit_fuera_de_atencion_reject(self):
        self._state("SIN TAREA", {})
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertFalse(r["accepted"])
        self.assertIn("pendiente de auditoría", r["reason"])

    def test_post_audit_disposition_invalida(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        for bad in ("", "FOO", None, 42):
            r = post_audit(self.tmp, "t1", bad)
            self.assertFalse(r["accepted"], "deberia rechazar disposition={!r}".format(bad))

    def test_post_audit_task_id_incorrecto(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "otra", "APPROVED", audit_summary="resumen")
        self.assertFalse(r["accepted"])
        self.assertIn("no coincide", r["reason"])

    def test_post_audit_ya_auditada_reject(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1",
                           {"auditedAt": "2026-08-16T00:01:00Z", "auditDisposition": "CORRECTION"})
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertFalse(r["accepted"])
        self.assertTrue(r["duplicate"])
        self.assertIn("ya fue auditada", r["reason"])

    def test_post_audit_ya_supersedida_reject(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1",
                           {"supersededByTaskId": "t2"})
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertFalse(r["accepted"])
        self.assertIn("supersedida", r["reason"])

    def test_post_audit_approved_escribe_archivo(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["resulting_state"], "SIN TAREA")
        self.assertEqual(self._audit_files(), ["t1.audit.json"])
        self.assertEqual(self._audit_payload("t1")["disposition"], "APPROVED")

    def test_post_audit_correction_resulting_state_conservado(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "CORRECTION", audit_summary="resumen")
        self.assertTrue(r["accepted"])
        self.assertEqual(r["resulting_state"], "TERMINADO — ESPERANDO SEGUI")

    def test_post_audit_user_decision_requiere_detalle(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "USER_DECISION")
        self.assertFalse(r["accepted"])
        self.assertIn("decision_detail", r["reason"])
        r2 = post_audit(self.tmp, "t1", "USER_DECISION", decision_detail="elegir A o B", audit_summary="resumen")
        self.assertTrue(r2["accepted"])
        self.assertEqual(r2["resulting_state"], "DECISIÓN DE USUARIO REQUERIDA")
        self.assertEqual(self._audit_payload("t1")["decision_detail"], "elegir A o B")

    def test_post_audit_detalle_en_disposicion_no_user_reject(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "APPROVED", decision_detail="detalle")
        self.assertFalse(r["accepted"])
        self.assertIn("solo aplica", r["reason"])

    def test_post_audit_duplicado_pendiente(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        post_audit(self.tmp, "t1", "CORRECTION", audit_summary="resumen")
        r2 = post_audit(self.tmp, "t1", "CORRECTION", audit_summary="resumen")
        self.assertFalse(r2["accepted"])
        self.assertTrue(r2["duplicate"])
        self.assertEqual(self._audit_payload("t1")["disposition"], "CORRECTION")

    def test_post_audit_no_toca_state_json(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        state_dir = os.path.join(self.tmp, "state")
        before = self._snapshot()
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertTrue(r["accepted"])
        # el unico cambio debe ser el archivo de auditoria (nuevo)
        after = self._snapshot()
        new_files = [k for k in after if k not in before]
        self.assertEqual(new_files, [os.path.join("state", "audits", "t1.audit.json")])
        # state.json intacto
        st = read_bridge_state(self.tmp)
        self.assertEqual(st["status"], "TERMINADO — ESPERANDO SEGUI")

    def test_post_audit_no_ejecuta_nada(self):
        self._linked_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertNotIn("opencode", json.dumps(r).lower())
        self.assertNotIn("shell", json.dumps(r).lower())

    def test_post_audit_trabajando_reject(self):
        state_dir = os.path.join(self.tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        tasks = {"t1": {"taskId": "t1", "status": "running"}}
        payload = {"status": "TRABAJANDO", "taskId": "t1", "commentId": None, "tasks": tasks}
        with open(os.path.join(state_dir, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="resumen")
        self.assertFalse(r["accepted"])
        self.assertIn("pendiente de auditoría", r["reason"])

    # --- B4.2: contexto durable de auditoría ---

    def _write_audit_history(self, task_id, record):
        d = os.path.join(self.tmp, "state", "audits", "history")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, task_id + ".audit.json"), "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)

    def _apply_audit(self, task_id, disposition, detail=None, summary=None,
                     context_scope=None, stage_id=None, beta=None, permanent=None,
                     supersedes=None):
        """Simula: post_audit + aplicacion del executor (mueve a history/)."""
        # pasamos por la funcion real post_audit para validar y escribir
        r = post_audit(self.tmp, task_id, disposition, detail, summary,
                       beta, permanent, supersedes, context_scope, stage_id)
        self.assertTrue(r["accepted"], "post_audit deberia aceptar: {!r}".format(r["reason"]))
        # mover a history como hace el executor
        src = os.path.join(self.tmp, "state", "audits", task_id + ".audit.json")
        dst = os.path.join(self.tmp, "state", "audits", "history", task_id + ".audit.json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        rec = json.load(io.open(src, encoding="utf-8"))
        rec["applied"] = True
        rec["audited_at"] = rec["created_at"]
        os.replace(src, dst)
        # simular la aplicacion al estado (tarea auditada -> SIN TAREA para proseguir)
        state = read_bridge_state(self.tmp)
        state["tasks"][task_id]["auditedAt"] = rec["audited_at"]
        state["tasks"][task_id]["auditDisposition"] = disposition
        if context_scope:
            state["tasks"][task_id]["contextScope"] = context_scope
        if stage_id:
            state["tasks"][task_id]["stageId"] = stage_id
        state["status"] = "SIN TAREA"
        state["taskId"] = None
        with open(os.path.join(self.tmp, "state", "state.json"), "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
        return rec

    def _b42_state(self, status, task_id, task_fields=None):
        # estado con tarea context_scope/stage_id (como la persistiria el executor)
        fields = {"status": "done"}
        if task_fields:
            fields.update(task_fields)
        self._attention_state(status, task_id, fields)

    def test_b42_post_audit_requiere_audit_summary(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "APPROVED")
        self.assertFalse(r["accepted"])
        self.assertIn("audit_summary", r["reason"])

    def test_b42_post_audit_persiste_summary(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t1")
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary="B6.2 aprobada tras corregir el ordenamiento SQL global.")
        self.assertTrue(r["accepted"])
        rec = self._audit_payload("t1")
        self.assertEqual(rec["audit_summary"], "B6.2 aprobada tras corregir el ordenamiento SQL global.")
        self.assertEqual(rec["beta_decisions"], [])
        self.assertEqual(rec["permanent_decisions"], [])
        self.assertEqual(rec["supersedes_decision_ids"], [])

    def test_b42_audit_summary_tamano_limitado(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t1")
        big = "x" * (2001)
        r = post_audit(self.tmp, "t1", "APPROVED", audit_summary=big)
        self.assertFalse(r["accepted"])
        self.assertIn("audit_summary", r["reason"])

    def test_b42_queue_task_persiste_contexto(self):
        self._state("SIN TAREA", {})
        r = queue_task(self.tmp, "t-b62", "prompt", execution_mode="AUTO_TECNICA",
                       expected_branch="beta6", expected_head="abc123",
                       context_scope="B6", stage_id="B6.2")
        self.assertTrue(r["accepted"])
        payload = self._inbox_payload("t-b62")
        self.assertEqual(payload["context_scope"], "B6")
        self.assertEqual(payload["stage_id"], "B6.2")
        # opcionales para compatibilidad
        r2 = queue_task(self.tmp, "t-legacy", "prompt")
        self.assertTrue(r2["accepted"])
        self.assertEqual(self._inbox_payload("t-legacy")["context_scope"], None)

    def test_b42_context_scope_invalido_rechazado(self):
        self._state("SIN TAREA", {})
        for bad in ("", "  ", "a b", "a/b", "x" * 65, None if False else 42):
            r = queue_task(self.tmp, "t-x", "p", context_scope=bad)
            self.assertFalse(r["accepted"], "deberia rechazar context_scope={!r}".format(bad))
        for bad in ("", "  ", "a/b", "x" * 65):
            r = queue_task(self.tmp, "t-y", "p", stage_id=bad)
            self.assertFalse(r["accepted"], "deberia rechazar stage_id={!r}".format(bad))

    def test_b42_get_status_expone_contexto(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t1",
                        {"contextScope": "B6", "stageId": "B6.2"})
        st = get_status(self.tmp)
        self.assertEqual(st["context_scope"], "B6")
        self.assertEqual(st["stage_id"], "B6.2")
        self.assertIn("get_audit_context", st["next_user_action"])

    def test_b42_get_report_expone_contexto(self):
        self._write_full_state("TERMINADO — ESPERANDO SEGUI", "t1",
                               {"contextScope": "B6", "stageId": "B6.5",
                                "auditSummary": "summary persistido", "status": "done",
                                "exitCode": 0})
        self._write_report_file("t1", "evidencia")
        r = get_report(self.tmp, "t1")
        self.assertEqual(r["context_scope"], "B6")
        self.assertEqual(r["stage_id"], "B6.5")
        self.assertEqual(r["audit_summary"], "summary persistido")

    def test_b42_get_audit_context_read_only(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t1", {"contextScope": "B6"})
        before = self._snapshot()
        ctx = get_audit_context(self.tmp, task_id="t1")
        self.assertEqual(before, self._snapshot())

    def test_b42_get_audit_context_bootstrap(self):
        ctx = get_audit_context(self.tmp, context_scope="B6")
        self.assertEqual(ctx["project"], "visor-videos")
        self.assertEqual(ctx["repository"], "marcossfregola/visor-videos")
        self.assertTrue(ctx["bootstrap_rules"])
        self.assertEqual(ctx["context_scope"], "B6")
        self.assertTrue(all(isinstance(r, str) for r in ctx["bootstrap_rules"]))
        self.assertTrue(any("El mensaje actual del usuario debe procesarse antes de post_audit o queue_task" in r
                            and "seguí" in r
                            and "el bridge no interpreta lenguaje natural" in r
                            and "evidencia humana" in r
                            for r in ctx["bootstrap_rules"]),
                        "bootstrap debe incluir la regla de procesar el mensaje del usuario antes de post_audit/queue_task")

    def test_b42_get_audit_context_scope_desconocido(self):
        ctx = get_audit_context(self.tmp)
        self.assertEqual(ctx["context_scope"], "UNKNOWN")
        self.assertIn("UNKNOWN", ctx["warnings"][0])

    def test_b42_e2e_b62_a_b65(self):
        # B6.2 audita y persiste D1
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="B6.2 aprobada",
                          context_scope="B6", stage_id="B6.2",
                          beta=["NULL siempre al final en ASC y DESC."])
        # B6.5 (otro estado; en realidad otra tarea) pide contexto
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b65",
                        {"contextScope": "B6", "stageId": "B6.5"})
        ctx = get_audit_context(self.tmp, task_id="t-b65")
        self.assertEqual(ctx["context_scope"], "B6")
        self.assertEqual(ctx["current_stage"], "B6.5")
        decs = [d["statement"] for d in ctx["active_beta_decisions"]]
        self.assertIn("NULL siempre al final en ASC y DESC.", decs)

    def test_b42_aislamiento_b6_b7(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="B6.2",
                          context_scope="B6", stage_id="B6.2",
                          beta=["regla beta de B6"])
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b7",
                        {"contextScope": "B7", "stageId": "B7.1"})
        ctx = get_audit_context(self.tmp, task_id="t-b7")
        self.assertEqual(ctx["context_scope"], "B7")
        self.assertEqual(ctx["active_beta_decisions"], [])

    def test_b42_permanent_se_ve_en_otra_beta(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="B6.2",
                          context_scope="B6", stage_id="B6.2",
                          permanent=["regla permanente global"])
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b7",
                        {"contextScope": "B7", "stageId": "B7.1"})
        ctx = get_audit_context(self.tmp, task_id="t-b7")
        decs = [d["statement"] for d in ctx["active_permanent_decisions"]]
        self.assertIn("regla permanente global", decs)
        self.assertTrue(any("GitHub" in w for w in ctx["warnings"]))

    def test_b42_supersede_d1_por_d2(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="D1",
                          context_scope="B6", stage_id="B6.2",
                          beta=["D1: null al final"])
        ctx_b62 = get_audit_context(self.tmp, context_scope="B6")
        d1 = ctx_b62["active_beta_decisions"][0]
        self.assertEqual(d1["status"], "ACTIVE")
        # B6.3 crea D2 y supersede D1
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b63",
                        {"contextScope": "B6", "stageId": "B6.3"})
        self._apply_audit("t-b63", "APPROVED", summary="D2",
                          context_scope="B6", stage_id="B6.3",
                          beta=["D2: null al final excepto en indices"],
                          supersedes=[d1["decision_id"]])
        ctx = get_audit_context(self.tmp, context_scope="B6")
        active = [d["statement"] for d in ctx["active_beta_decisions"]]
        self.assertIn("D2: null al final excepto en indices", active)
        self.assertNotIn("D1: null al final", active)
        # history lo muestra SUPERSEDED
        hist = get_audit_context(self.tmp, context_scope="B6", include_history=True)
        sup = {d["statement"] for d in hist["superseded_decisions"]}
        self.assertIn("D1: null al final", sup)

    def test_b42_supersede_id_inexistente_rechazado(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b63",
                        {"contextScope": "B6", "stageId": "B6.3"})
        r = post_audit(self.tmp, "t-b63", "APPROVED", audit_summary="x",
                       context_scope="B6", stage_id="B6.3",
                       beta_decisions=["D2"],
                       supersedes_decision_ids=["D-no-existe"])
        self.assertFalse(r["accepted"])
        self.assertIn("inexistente", r["reason"])

    def test_b42_supersede_scope_incompatible_rechazado(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="D1",
                          context_scope="B6", stage_id="B6.2",
                          beta=["D1 beta de B6"])
        ctx = get_audit_context(self.tmp, context_scope="B6")
        d1 = ctx["active_beta_decisions"][0]
        # intentar superseder desde B7 (contexto incompatible)
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b7",
                        {"contextScope": "B7", "stageId": "B7.1"})
        r = post_audit(self.tmp, "t-b7", "APPROVED", audit_summary="x",
                       context_scope="B7", stage_id="B7.1",
                       beta_decisions=["D7"],
                       supersedes_decision_ids=[d1["decision_id"]])
        self.assertFalse(r["accepted"])
        self.assertIn("incompatible", r["reason"])

    def test_b42_records_legacy_legibles(self):
        # records B4 sin campos nuevos deben seguir siendo legibles
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._write_audit_history("t-b62", {
            "task_id": "t-b62", "disposition": "APPROVED",
            "decision_detail": None, "created_at": "2026-08-16T10:00:00Z", "source": "mcp"})
        ctx = get_audit_context(self.tmp, context_scope="B6")
        self.assertEqual(ctx["active_beta_decisions"], [])
        self.assertEqual(ctx["active_permanent_decisions"], [])

    def test_b42_record_corrupto_no_rompe(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="ok",
                          context_scope="B6", stage_id="B6.2",
                          beta=["regla valida"])
        d = os.path.join(self.tmp, "state", "audits", "history")
        with open(os.path.join(d, "t-corrupto.audit.json"), "w", encoding="utf-8") as fh:
            fh.write("{ esto no es json")
        ctx = get_audit_context(self.tmp, context_scope="B6")
        decs = [x["statement"] for x in ctx["active_beta_decisions"]]
        self.assertIn("regla valida", decs)

    def test_b42_decision_vacia_rechazada(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        for bad_list in ([""], ["   "], [None], [42]):
            r = post_audit(self.tmp, "t-b62", "APPROVED", audit_summary="x",
                           context_scope="B6", stage_id="B6.2",
                           beta_decisions=bad_list)
            self.assertFalse(r["accepted"], "deberia rechazar beta_decisions={!r}".format(bad_list))

    def test_b42_decision_tamano_excesivo(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        r = post_audit(self.tmp, "t-b62", "APPROVED", audit_summary="x",
                       context_scope="B6", stage_id="B6.2",
                       beta_decisions=["z" * 2001])
        self.assertFalse(r["accepted"])
        self.assertIn("demasiado grande", r["reason"])

    def test_b42_unicode_conservado(self):
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        r = post_audit(self.tmp, "t-b62", "APPROVED", audit_summary="resumen ✅ con acentos",
                       context_scope="B6", stage_id="B6.2",
                       beta_decisions=["ñandú → orden estable ✅"])
        self.assertTrue(r["accepted"])
        rec = self._audit_payload("t-b62")
        self.assertEqual(rec["audit_summary"], "resumen ✅ con acentos")
        self.assertEqual(rec["beta_decisions"][0]["statement"], "ñandú → orden estable ✅")

    def test_b42_persistencia_despues_de_reinicio(self):
        # simula reinicio: reconstruye el contexto leyendo solo los archivos
        self._b42_state("TERMINADO — ESPERANDO SEGUI", "t-b62",
                        {"contextScope": "B6", "stageId": "B6.2"})
        self._apply_audit("t-b62", "APPROVED", summary="B6.2",
                          context_scope="B6", stage_id="B6.2",
                          beta=["regla durable"])
        # nuevo bridge_dir "post-reinicio": la lectura sigue leyendo los mismos archivos
        ctx = get_audit_context(self.tmp, context_scope="B6")
        self.assertEqual(len(ctx["active_beta_decisions"]), 1)
        decs = [x["audit_summary"] for x in ctx["recent_audit_summaries"]]
        self.assertEqual(decs, ["B6.2"])

    # ---- CANCEL: cancel_task (solicitud durable; aplica el executor) ----

    def _cancel_dir(self):
        return os.path.join(self.tmp, "state", "cancellations")

    def _cancel_files(self):
        d = self._cancel_dir()
        if not os.path.isdir(d):
            return []
        return [f for f in os.listdir(d) if f.endswith(".cancel.json")]

    def _cancel_payload(self, task_id):
        with open(os.path.join(self._cancel_dir(), task_id + ".cancel.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_cancel_available_independiente_registra_solicitud(self):
        # tarea available e independiente: la solicitud durable se registra sin tocar state.json
        self._state("TAREA DISPONIBLE", {"task-c": {"status": "available", "taskId": "task-c"}})
        with open(os.path.join(self.tmp, "state", "state.json"), "rb") as fh:
            before = fh.read()
        r = cancel_task(self.tmp, "task-c", "reemplazada por tarea nueva")
        self.assertTrue(r["accepted"])
        self.assertFalse(r["duplicate"])
        self.assertEqual(r["resulting_state"], "TAREA DISPONIBLE")
        self.assertEqual(self._cancel_files(), ["task-c.cancel.json"])
        p = self._cancel_payload("task-c")
        self.assertEqual(p["task_id"], "task-c")
        self.assertEqual(p["reason"], "reemplazada por tarea nueva")
        self.assertEqual(p["source"], "mcp")
        with open(os.path.join(self.tmp, "state", "state.json"), "rb") as fh:
            after = fh.read()
        self.assertEqual(after, before, "cancel_task NO debe modificar state.json")

    def test_cancel_durante_ventana_inbox(self):
        # tarea todavía solo en inbox: la cancelación puede solicitarse y se archiva
        self._state("SIN TAREA", {})
        write_inbox_atomic(self.tmp, "task-inb", "prompt pendiente")
        self.assertTrue(pending_inbox_has(self.tmp, "task-inb"))
        r = cancel_task(self.tmp, "task-inb", "obsoleta en inbox")
        self.assertTrue(r["accepted"])
        self.assertEqual(self._cancel_files(), ["task-inb.cancel.json"])

    def test_cancel_reason_vacio_rechazado(self):
        self._state("TAREA DISPONIBLE", {"task-c": {"status": "available", "taskId": "task-c"}})
        r = cancel_task(self.tmp, "task-c", "   ")
        self.assertFalse(r["accepted"])
        self.assertEqual(self._cancel_files(), [])
        r2 = cancel_task(self.tmp, "task-c", "")
        self.assertFalse(r2["accepted"])

    def test_cancel_reason_demasiado_largo_rechazado(self):
        self._state("TAREA DISPONIBLE", {"task-c": {"status": "available", "taskId": "task-c"}})
        r = cancel_task(self.tmp, "task-c", "x" * 201)
        self.assertFalse(r["accepted"])
        self.assertEqual(self._cancel_files(), [])
        # 200 exactos es aceptado
        r2 = cancel_task(self.tmp, "task-c", "y" * 200)
        self.assertTrue(r2["accepted"])

    def test_cancel_task_id_invalido_rechazado(self):
        self._state("SIN TAREA", {})
        r = cancel_task(self.tmp, "comodín!*", "motivo")
        self.assertFalse(r["accepted"])
        self.assertEqual(self._cancel_files(), [])

    def test_cancel_duplicado_pendiente(self):
        # una segunda solicitud para la misma tarea no debe duplicar el archivo
        self._state("TAREA DISPONIBLE", {"task-c": {"status": "available", "taskId": "task-c"}})
        r1 = cancel_task(self.tmp, "task-c", "primera")
        r2 = cancel_task(self.tmp, "task-c", "segunda")
        self.assertTrue(r1["accepted"])
        self.assertFalse(r2["accepted"])
        self.assertTrue(r2["duplicate"])
        self.assertEqual(self._cancel_files(), ["task-c.cancel.json"])
        self.assertEqual(self._cancel_payload("task-c")["reason"], "primera")

    def test_cancel_tarea_inexistente(self):
        self._state("SIN TAREA", {})
        r = cancel_task(self.tmp, "task-noexiste", "motivo")
        self.assertFalse(r["accepted"])
        self.assertEqual(r["reason"], "tarea inexistente (no está en inbox ni en el estado)")
        self.assertEqual(self._cancel_files(), [])

    def test_cancel_trabajando_rechazado(self):
        # CANCEL nunca debe solicitarse/rechazarse para la tarea TRABAJANDO
        self._state("TRABAJANDO", {"task-run": {"status": "running", "taskId": "task-run"}})
        r = cancel_task(self.tmp, "task-run", "motivo")
        self.assertFalse(r["accepted"])
        self.assertEqual(self._cancel_files(), [])

    def test_cancel_done_failed_resolved_decision_rechazado(self):
        for st in ("done", "failed", "resolved", "decision"):
            self._state("SIN TAREA", {"t": {"status": st, "taskId": "t"}})
            r = cancel_task(self.tmp, "t", "motivo")
            self.assertFalse(r["accepted"], "estado {} debe rechazar".format(st))
            self.assertEqual(self._cancel_files(), [], "estado {} no debe escribir solicitud".format(st))

    def test_cancel_auditada_rechazado(self):
        self._state("SIN TAREA",
                    {"t-aud": {"status": "available", "taskId": "t-aud",
                               "auditedAt": "2026-08-16T10:00:00Z"}})
        r = cancel_task(self.tmp, "t-aud", "motivo")
        self.assertFalse(r["accepted"])
        self.assertEqual(self._cancel_files(), [])

    def test_cancel_superseded_y_cadena_rechazado(self):
        chain_cases = [
            {"status": "available", "supersededByTaskId": "t-nueva"},  # superseded
            {"status": "available", "supersedesTaskId": "t-anterior"},  # pertenece a cadena
            {"status": "available", "supersededByTaskId": "t-x"},
        ]
        for i, fields in enumerate(chain_cases):
            tid = "t-chain-{}".format(i)
            t = dict(fields)
            t["status"] = "available"
            t["taskId"] = tid
            self._state("TAREA DISPONIBLE", {tid: t})
            r = cancel_task(self.tmp, tid, "motivo")
            self.assertFalse(r["accepted"], "cadena {} debe rechazar".format(i))
            self.assertEqual(self._cancel_files(), [], "cadena {} no debe escribir solicitud".format(i))

    def test_cancel_solicitud_persiste_tras_reinicio(self):
        # la solicitud dura sobrevive: un "reinicio" la sigue viendo pendiente
        self._state("TAREA DISPONIBLE", {"task-c": {"status": "available", "taskId": "task-c"}})
        cancel_task(self.tmp, "task-c", "reemplazada")
        self.assertTrue(pending_cancel_has(self.tmp, "task-c"))
        self.assertEqual(self._cancel_files(), ["task-c.cancel.json"])

    def test_cancel_no_ejecuta_opencode(self):
        # solo debe existir el archivo de cancelación; sin logs ni salidas de opencode
        self._state("TAREA DISPONIBLE", {"task-c": {"status": "available", "taskId": "task-c"}})
        cancel_task(self.tmp, "task-c", "motivo")
        self.assertEqual(self._cancel_files(), ["task-c.cancel.json"])
        logs = os.path.join(self.tmp, "logs")
        self.assertFalse(os.path.isdir(logs))

    def test_get_report_tarea_cancelada(self):
        # get_report de una tarea materializada cancelled expone trazabilidad y sin reporte
        self._state("TAREA DISPONIBLE",
                    {"t-cancel": {"status": "cancelled", "taskId": "t-cancel",
                                  "cancelledAt": "2026-08-18T12:00:00Z",
                                  "cancelReason": "obsoleta", "cancelSource": "mcp"}})
        r = get_report(self.tmp, "t-cancel")
        self.assertEqual(r["status"], "cancelled")
        self.assertEqual(r["resultado"], "CANCELADA")
        self.assertEqual(r["cancelled_at"], "2026-08-18T12:00:00Z")
        self.assertEqual(r["cancel_reason"], "obsoleta")
        self.assertEqual(r["cancel_source"], "mcp")
        self.assertFalse(r["report_available"])
        self.assertIsNone(r["started_at"])
        self.assertIsNone(r["exit_code"])

    def test_load_config_expande_localappdata(self):
        # load_config debe expandir %LOCALAPPDATA% para resolver el LocalAppData real
        # del usuario y NO quedar conteniendo el placeholder literalmente.
        local = os.environ.get("LOCALAPPDATA")
        if not local or not os.path.isdir(local):
            self.skipTest("LOCALAPPDATA no disponible")
        # crea un config temporal cuyo bridge_dir usa el placeholder %LOCALAPPDATA%
        seg = os.path.basename(self.tmp.rstrip("\\/"))
        sample_name = "bridge-loadconfig-demo-" + seg
        sample_dir = os.path.join(local, sample_name)
        os.makedirs(sample_dir, exist_ok=True)
        self.addCleanup(_rmtree, sample_dir)
        cfg_file = os.path.join(self.tmp, "config.json")
        with open(cfg_file, "w", encoding="utf-8") as fh:
            json.dump({"bridge_dir": "%LOCALAPPDATA%\\" + os.path.basename(sample_dir),
                       "max_prompt_bytes": 9000}, fh, ensure_ascii=False)
        cfg = load_config(cfg_file)
        self.assertEqual(cfg["max_prompt_bytes"], 9000)
        # la ruta efectiva debe apuntar al LocalAppData real, sin '%LOCALAPPDATA%' literal
        self.assertNotIn("%LOCALAPPDATA%", cfg["bridge_dir"])
        self.assertTrue(os.path.isdir(cfg["bridge_dir"]))
        self.assertEqual(os.path.normpath(os.path.realpath(cfg["bridge_dir"])),
                         os.path.normpath(os.path.realpath(sample_dir)))

    def test_load_config_rechaza_bridge_dir_inexistente(self):
        cfg_file = os.path.join(self.tmp, "config.json")
        with open(cfg_file, "w", encoding="utf-8") as fh:
            json.dump({"bridge_dir": os.path.join(self.tmp, "no-existe")}, fh, ensure_ascii=False)
        with self.assertRaises(BridgeError):
            load_config(cfg_file)


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
