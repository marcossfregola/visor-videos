"""Verifica tools/list y annotations de las seis herramientas MCP (INFRA 0.4.2 + B4.2)."""

import asyncio
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MCP_DIR = os.path.dirname(_HERE)


def _load_server():
    path = os.path.join(_MCP_DIR, "mcp-server.py")
    spec = importlib.util.spec_from_file_location("mcp_server_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class McpToolsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_server()
        tools = asyncio.run(cls.mod.server.list_tools())
        cls.tools = {t.name: t for t in tools}

    def test_tools_list_exactamente_seis(self):
        names = sorted(self.tools.keys())
        self.assertEqual(names, ["get_audit_context", "get_report", "get_status", "post_audit", "queue_task", "resolve_decision"])

    def test_get_status_annotations(self):
        a = self.tools["get_status"].annotations
        self.assertTrue(a.read_only_hint)
        self.assertFalse(a.destructive_hint)
        self.assertTrue(a.idempotent_hint)
        self.assertFalse(a.open_world_hint)

    def test_get_status_descripcion_documenta_related(self):
        desc = self.tools["get_status"].description
        self.assertIn("RELATED", desc)
        self.assertIn("queue_task con previous_task_id exacto", desc)
        self.assertIn("CORRECTION", desc)
        self.assertIn("NEXT_STAGE", desc)
        # RELATED debe quedar inequivocamente diferenciado de AUDIT.
        self.assertIn("AUDIT", desc)
        self.assertNotIn("RELATED", desc.split("AUDIT")[0])

    def test_queue_task_annotations(self):
        a = self.tools["queue_task"].annotations
        self.assertFalse(a.read_only_hint)
        self.assertFalse(a.destructive_hint)
        self.assertTrue(a.idempotent_hint)
        self.assertFalse(a.open_world_hint)

    def test_resolve_decision_annotations(self):
        a = self.tools["resolve_decision"].annotations
        self.assertFalse(a.read_only_hint)
        self.assertFalse(a.destructive_hint)
        self.assertFalse(a.idempotent_hint)
        self.assertFalse(a.open_world_hint)

    def test_get_report_annotations(self):
        a = self.tools["get_report"].annotations
        self.assertTrue(a.read_only_hint)
        self.assertFalse(a.destructive_hint)
        self.assertTrue(a.idempotent_hint)
        self.assertFalse(a.open_world_hint)

    def test_get_audit_context_annotations(self):
        a = self.tools["get_audit_context"].annotations
        self.assertTrue(a.read_only_hint)
        self.assertFalse(a.destructive_hint)
        self.assertTrue(a.idempotent_hint)
        self.assertFalse(a.open_world_hint)

    def test_post_audit_annotations(self):
        a = self.tools["post_audit"].annotations
        self.assertFalse(a.read_only_hint)
        self.assertFalse(a.destructive_hint)
        self.assertFalse(a.idempotent_hint)
        self.assertFalse(a.open_world_hint)

    def test_post_audit_descripcion_honesta(self):
        desc = self.tools["post_audit"].description
        self.assertIn("previous_task_id", desc)
        self.assertIn("USER_DECISION", desc)
        self.assertIn("audit_summary", desc)
        self.assertIn("supersedes_decision_ids", desc)

    def test_queue_task_descripcion_honesta(self):
        desc = self.tools["queue_task"].description
        self.assertIn("never executes OpenCode or shell commands", desc)
        self.assertIn("explicit human action", desc)
        self.assertIn("context_scope", desc)
        self.assertIn("stage_id", desc)

    def test_get_audit_context_descripcion_honesta(self):
        desc = self.tools["get_audit_context"].description
        self.assertIn("bootstrap_rules", desc)
        self.assertIn("include_history", desc)
        self.assertIn("UNKNOWN", desc)

    def test_schema_queue_task_incluye_contexto(self):
        schema = self.tools["queue_task"].input_schema
        props = schema.get("properties") or {}
        self.assertIn("context_scope", props)
        self.assertIn("stage_id", props)
        required = schema.get("required") or []
        self.assertNotIn("context_scope", required)
        self.assertNotIn("stage_id", required)

    def test_schema_post_audit_incluye_b42(self):
        schema = self.tools["post_audit"].input_schema
        props = schema.get("properties") or {}
        self.assertIn("audit_summary", props)
        self.assertIn("beta_decisions", props)
        self.assertIn("permanent_decisions", props)
        self.assertIn("supersedes_decision_ids", props)
        required = schema.get("required") or []
        self.assertIn("audit_summary", required)

    def test_schema_get_audit_context_opcional(self):
        schema = self.tools["get_audit_context"].input_schema
        props = schema.get("properties") or {}
        self.assertIn("task_id", props)
        self.assertIn("context_scope", props)
        self.assertIn("include_history", props)


if __name__ == "__main__":
    unittest.main(verbosity=2)
