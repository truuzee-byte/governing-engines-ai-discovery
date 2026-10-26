from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from builder.components.component_registry import is_registered_component
from builder.construction.code_constructor import construct_code
from builder.core.build_models import BuildPlan
from builder.core.build_validator import evaluate_validation_results
from builder.core.command_runner import run_approved_commands
from builder.core.file_writer import write_approved_files
from builder.kernel.kernel_client import HttpKernelClient


class BuilderUpgradeSmokeTests(unittest.TestCase):
    def _plan(self, **overrides):
        values = dict(
            build_id="build_test",
            spec_id="spec_test",
            snapshot_hash="abc123",
            target_name="test_component",
            tool_type="construction_tool",
            approved_components=["code_constructor", "file_writer", "validator"],
            required_files=["src/example.py"],
            required_directories=["src"],
            required_outputs=[],
            governance_constraints=["approved_files_only"],
            receipt_requirements=["build_receipt"],
            authorized_write_scope=["src/example.py"],
            authorized_create_scope=["src/example.py"],
            approved_commands=[],
            validation_commands=[],
            validation_requirements=[],
            approved_files={"src/example.py": "print('ok')\n"},
            existing_files=[],
        )
        values.update(overrides)
        return BuildPlan(**values)

    def test_component_registry_imports_and_contains_constructor(self):
        self.assertTrue(is_registered_component("code_constructor"))
        self.assertTrue(is_registered_component("kernel_gateway"))

    def test_constructor_uses_exact_approved_files(self):
        proposal = construct_code(self._plan())
        self.assertEqual(proposal.approved_file_map(), {"src/example.py": "print('ok')\n"})

    def test_file_writer_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                write_approved_files(root, {"../escape.py": "x"}, ["../escape.py"])

    def test_command_runner_rejects_unapproved_command(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                run_approved_commands([["python", "-c", "print(1)"]], [], root)

    def test_required_validation_without_result_is_unproven(self):
        plan = self._plan(validation_requirements=["required_validation_must_execute"])
        self.assertEqual(evaluate_validation_results(plan, [], []), "UNPROVEN")

    def test_http_kernel_client_fails_closed(self):
        client = HttpKernelClient("http://kernel.invalid", "token", "task")
        with self.assertRaises(RuntimeError):
            client.create_workspace([])


if __name__ == "__main__":
    unittest.main()
