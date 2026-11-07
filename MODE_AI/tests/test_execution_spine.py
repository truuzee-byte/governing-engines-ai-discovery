import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from integration.build_runtime import BuildRuntime, digest
from integration.mode_generation import ModeGenerationProvider
from interactive_mode_ai import ModeRuntime, RuntimeState
from runtime_observation import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from understanding import UnderstandingEngine, UnderstandingStore


CONTENTS = {"calculator.py": "def add(a, b):\n    return a + b\n",
            "main.py": "from calculator import add\nprint(add(2, 3))\n",
            "test_calculator.py": "from calculator import add\nassert add(2, 3) == 5\nassert add(-2, 2) == 0\n"}


class Model:
    def generate(self, **kwargs):
        target = json.loads(kwargs["user_input"])["target_path"]
        return NS(final_response=json.dumps({"path": target, "content": CONTENTS[target]}))


def envelope(root):
    request = {"request_id": "calculator-1", "operator_input": "Build a Python calculator application.",
        "system_name": "calculator", "system_purpose": "Add two numbers", "tool_type": "python",
        "construction_scope": list(CONTENTS), "approved_components": [], "governance_constraints": [],
        "execution_authority": "operator_confirmed", "receipt_requirements": [],
        "runtime_target": "local", "source_trace_reference": "operator:calculator-1",
        "authority_state": "handoff_approved", "validation_state": "valid", "readiness_state": "ready_for_build",
        "save_ready_state": True, "clarification_required": False,
        "artifact_structure": {"files": list(CONTENTS), "directories": [], "existing_files": [],
                               "approved_files": {}, "required_outputs": list(CONTENTS)},
        "execution": {"repository_target": str(root), "authorized_read_scope": [], "authorized_write_scope": [],
                      "authorized_create_scope": list(CONTENTS), "authorized_delete_scope": [], "approved_commands": []},
        "validation": {"requirements": ["validation commands passed"],
                       "commands": [[sys.executable, "-B", "test_calculator.py"]]},
        "evidence": {"requirements": ["command results"]},
        "completion": {"requirements": ["file:calculator.py", "file:main.py", "file:test_calculator.py"]}}
    data = {"subject_id": "calculator", "meaning": "The operator requires a calculator that adds two numbers.",
            "semantic_domain": "OPERATOR", "system_request": True, "objective": "Add two numbers",
            "source_references": ["operator:calculator-1"], "actors": ["operator"], "components": list(CONTENTS),
            "requirements": [{"requirement_id": "add", "text": "Add two numbers", "completion_condition": "validation commands passed"}],
            "relationships": [{"source": "main.py", "target": "calculator.py", "type": "DEPENDS_ON", "requirement_ids": ["add"]}],
            "completion_conditions": request["completion"]["requirements"]}
    return {"request": request, "understanding": data,
            "authorization": {"operator_id": "operator", "thread_id": "thread", "decision": "APPROVE",
                              "request_hash": digest({"request": request, "understanding": data})}}


def authorize(e):
    e["authorization"]["request_hash"] = digest({"request": e["request"], "understanding": e["understanding"]})
    return e


def runtime(root):
    r = ModeRuntime.__new__(ModeRuntime)
    r.context = NS(identity=NS(operator_id="operator"), active_thread=NS(thread_id="thread"), runtime_state=RuntimeState.INTERPRETING)
    r.understanding_engine = UnderstandingEngine(UnderstandingStore(root / "understanding.sqlite"))
    r.runtime_observation_collector = RuntimeObservationCollector(store=RuntimeObservationStore(root / "observations"))
    r.build_runtime = BuildRuntime(r, ModeGenerationProvider(Model()))
    return r


def test_chat_never_builds(tmp_path):
    r = runtime(tmp_path)
    assert r.handle_build_request("How does a build work?") is None


def test_incomplete_requests_clarify(tmp_path):
    r = runtime(tmp_path)
    assert r.handle_build_request("Build something") ["state"] == "SPECIFICATION_NOT_READY"
    assert r.handle_build_request('/build {}')["state"] == "SPECIFICATION_NOT_READY"


def test_real_builder_spine(tmp_path):
    r = runtime(tmp_path)
    out = r.build_runtime.execute(envelope(tmp_path / "artifact"))
    assert out["state"] == "BUILD_PASS_RP_PENDING", out
    assert out["build"]["validation_status"] == "PASS"
    assert len(out["observation_ids"]) == 3
    for path, contents in CONTENTS.items():
        assert (tmp_path / "artifact" / path).read_text() == contents
    assert r.build_runtime.execute(envelope(tmp_path / "artifact"))["state"] == "SPECIFICATION_NOT_READY"


@pytest.mark.parametrize("block", ["required_outputs", "evidence", "completion"])
def test_missing_proof_is_unproven(tmp_path, block):
    e = envelope(tmp_path / "artifact")
    if block == "required_outputs": e["request"]["artifact_structure"][block].append("absent.txt")
    else: e["request"][block]["requirements"].append("independent evidence not supplied")
    out = runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out["state"] == "BUILD_UNPROVEN", out


def test_create_cannot_overwrite(tmp_path):
    target = tmp_path / "artifact"
    target.mkdir()
    (target / "calculator.py").write_text("original")
    out = runtime(tmp_path).build_runtime.execute(envelope(target))
    assert out["state"] == "CONSTRUCTION_BLOCKED", out
    assert (target / "calculator.py").read_text() == "original"


def test_generation_failure(tmp_path):
    r = runtime(tmp_path)
    r.build_runtime.provider.agent.generate = lambda **k: NS(final_response="prose")
    out = r.build_runtime.execute(envelope(tmp_path / "artifact"))
    assert out["state"] == "GENERATION_FAILED", out


@pytest.mark.parametrize("verifier,expected", [
    ("from calculator import add; import json; print(json.dumps({'sum':add(2,3)}))", "BUILD_PASS_RP_CONFIRMED"),
    ("from calculator import add; import json; print(json.dumps({'sum':add(3,3)}))", "BUILD_PASS_RP_DISCONFIRMED"),
    (None, "BUILD_PASS_RP_PENDING"),
    ("print('PASS')", "BUILD_PASS_RP_PENDING"),
])
def test_external_rp_spine(tmp_path, verifier, expected):
    sys.path.insert(0, r"C:\REALITY_PRIMACY")
    from reality_primacy.build_validation import BuildValidationSession
    from reality_primacy import DecisionLedger
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from integration.reality_primacy import RealityAcceptanceClient
    r = runtime(tmp_path)
    e = envelope(tmp_path / "artifact")
    key = Ed25519PrivateKey.generate()
    grant = {"operator_id": "operator", "thread_id": "thread", "request_hash": digest(e),
             "root": str(tmp_path / "artifact"), "claim_text": "Calculator adds 2 and 3 to 5 and -2 and 2 to 0.",
             "required_files": list(CONTENTS), "authority_reference": "operator:calculator-validation",
             "expected_observation": {"sum": 5},
             "verification_command": [sys.executable, "-B", "-c", verifier] if verifier else [str(tmp_path / "absent-executor")]}
    external = BuildValidationSession(grant=grant, ledger=DecisionLedger(tmp_path / "rp.sqlite"), signing_key=key, key_id="test")
    r.prepare_build_reality_request = external.prepare
    r.reality_acceptance_client = RealityAcceptanceClient(external.evaluate,
        {"test": key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)})
    out = r.build_runtime.execute(e)
    assert out["state"] == expected, out
    assert (r.context.runtime_state == RuntimeState.COMPLETE) == (expected == "BUILD_PASS_RP_CONFIRMED")
    assert out["rp"]["receipt_id"]
    assert out["rp"]["chain_id"]
    assert r.understanding_engine._rp_outcomes[-1]["rp_state"] == out["rp"]["rp_state"]
    record = r.runtime_observation_collector.store.load_record("operator", out["observation_ids"][-1])
    assert record.metadata["observed_outcome"]["rp"]["receipt_id"] == out["rp"]["receipt_id"]


@pytest.mark.parametrize("change", ["authority", "ambiguity", "missing_files", "structural_gap", "unknown_field"])
def test_eligibility_blocks_before_builder(tmp_path, change):
    r = runtime(tmp_path)
    e = envelope(tmp_path / "artifact")
    if change == "authority": e["authorization"]["decision"] = "DENY"
    if change == "ambiguity": e["request"]["operator_input"] = "Build that thing like before"
    if change == "missing_files": e["request"]["artifact_structure"]["files"] = []
    if change == "structural_gap": e["understanding"]["relationships"] = []
    if change == "unknown_field": e["request"]["artifact_structure"]["unknown_required_field"] = "must preserve"
    if change != "authority": authorize(e)
    calls = []
    r.build_runtime.builder = lambda *a, **k: calls.append(a)
    out = r.build_runtime.execute(e)
    assert out["state"] == "SPECIFICATION_NOT_READY", out
    assert calls == []


def test_builder_called_once_and_only_core(tmp_path):
    from builder.core.build_entry import run_builder_core
    r = runtime(tmp_path)
    calls = []
    def counted(*a, **k):
        calls.append(1)
        return run_builder_core(*a, **k)
    r.build_runtime.builder = counted
    e = envelope(tmp_path / "artifact")
    assert r.handle_build_request('/build ' + json.dumps(e))["state"] == "BUILD_PASS_RP_PENDING"
    r.handle_build_request('/build ' + json.dumps(e))
    assert calls == [1]
    import inspect
    assert "builder.execution" not in inspect.getsource(BuildRuntime)


def test_validation_failure_never_passes(tmp_path):
    e = envelope(tmp_path / "artifact")
    e["request"]["validation"]["commands"] = [[sys.executable, "-B", "-c", "raise SystemExit(2)"]]
    out = runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out["state"] == "BUILD_FAIL", out
    assert json.loads(Path(out["build"]["receipt_path"]).read_text())["final_status"] == "FAIL"


@pytest.mark.parametrize("kind", ["wrong_target", "empty", "prose", "placeholder", "unexpected"])
def test_generation_rejects_nonimplementation(tmp_path, kind):
    r = runtime(tmp_path)
    values = {"wrong_target": {"path": "elsewhere.py", "content": "x=1"},
              "empty": {"path": "calculator.py", "content": ""},
              "prose": {"path": "calculator.py", "content": "Here is your implementation"},
              "placeholder": {"path": "calculator.py", "content": "def add(a,b): pass"},
              "unexpected": {"path": "calculator.py", "content": "x=1", "extra_file": "x"}}
    r.build_runtime.provider.agent.generate = lambda **k: NS(final_response=json.dumps(values[kind]))
    out = r.build_runtime.execute(envelope(tmp_path / "artifact"))
    assert out["state"] == "GENERATION_FAILED", out
    assert not (tmp_path / "artifact" / "calculator.py").exists()


def test_generation_only_returns_contents(tmp_path):
    from builder.core.build_plan_generator import generate_build_plan
    from specs.spec_engine import create_specification_object
    from specs.handoff_gate import approve_builder_handoff
    from specs.spec_snapshot import create_spec_snapshot
    request = envelope(tmp_path / "artifact")["request"]
    request.pop("operator_input")
    spec = create_specification_object(request)
    spec['metadata']['operator_authorization']={'operator_id':'operator','thread_id':'thread','decision':'APPROVE'}
    plan = generate_build_plan(approve_builder_handoff(spec, create_spec_snapshot(spec)))
    result = ModeGenerationProvider(Model()).generate(plan, {"specification": spec})
    assert {f["path"]: f["content"] for f in result["files"]} == CONTENTS
    assert not (tmp_path / "artifact").exists()


@pytest.mark.parametrize("operation,present,allowed", [("CREATE",False,True),("CREATE",True,False),
                                                     ("MODIFY",True,True),("MODIFY",False,False)])
def test_actual_file_operation_authority(tmp_path, operation, present, allowed):
    from builder.core.execution_contract import validate_operations
    from builder.core.file_writer import write_approved_files
    p = tmp_path / "a.py"
    if present: p.write_text("old")
    if not allowed:
        with pytest.raises(ValueError): validate_operations([NS(path="a.py", operation=operation)], str(tmp_path))
    else:
        validate_operations([NS(path="a.py", operation=operation)], str(tmp_path))
        write_approved_files(str(tmp_path), {"a.py": "new"}, ["a.py"], operations={"a.py": operation})
        assert p.read_text() == "new"


@pytest.mark.parametrize("change", ["root", "scope", "traversal"])
def test_execution_boundary_fail_closed(tmp_path, change):
    from builder.tests.test_builder_entry import _valid_handoff_payload
    from builder.core.build_entry import run_builder_core
    from specs.handoff_gate import approve_builder_handoff
    from specs.spec_snapshot import create_spec_snapshot
    root = tmp_path / "authorized"
    handoff = _valid_handoff_payload(root=root)
    spec = handoff["specification_object"]
    actual = root
    if change == "root": actual = tmp_path / "other"
    if change == "scope": spec["execution"]["authorized_create_scope"] = []
    if change == "traversal": spec["artifact_structure"]["files"] = ["../escape.py"]
    handoff = approve_builder_handoff(spec, create_spec_snapshot(spec))
    with pytest.raises(ValueError): run_builder_core(handoff, str(actual))
    assert not (actual / "reports" / "result.txt").exists()
    if change == "root": assert not actual.exists()


def test_separate_rp_process_runtime_path(tmp_path):
    from integration.rp_process import ExternalRPProcess
    e = envelope(tmp_path / "artifact")
    grant = {"operator_id": "operator", "thread_id": "thread", "request_hash": digest(e),
        "root": str(tmp_path / "artifact"), "claim_text": "Calculator adds 2 and 3 to 5.",
        "required_files": list(CONTENTS), "authority_reference": "operator:separate-process",
        "expected_observation": {"sum": 5},
        "verification_command": [sys.executable, "-B", "-c", "from calculator import add; import json; print(json.dumps({'sum':add(2,3)}))"]}
    path = tmp_path / "grant.json"
    path.write_text(json.dumps(grant))
    process = ExternalRPProcess(r"C:\REALITY_PRIMACY", path, tmp_path / "rp.sqlite")
    try:
        r = runtime(tmp_path)
        process.attach(r)
        out = r.handle_build_request('/build ' + json.dumps(e))
        assert out["state"] == "BUILD_PASS_RP_CONFIRMED", out
        assert process.process.pid != __import__('os').getpid()
    finally:
        process.close()
    assert process.process.poll() is not None


def test_rp_outcome_survives_nontrivial_understanding(tmp_path):
    r = runtime(tmp_path)
    from understanding import UnderstandingRequest, AuthorityContext, AuthorityLevel
    r.understanding_engine.receive_rp_outcome({"rp_state": "DISCONFIRMED",
        "request": {"scope": {"operator_id": "operator", "thread_id": "thread"}}})
    result = r.understanding_engine.process(UnderstandingRequest("operator", "thread", "I prefer concise answers.",
        authority_context=AuthorityContext("operator", AuthorityLevel.AUTHORIZED_OPERATOR, "OPERATOR", authenticated=True)))
    assert result.metadata["external_reality_outcomes"][0]["rp_state"] == "DISCONFIRMED"


def test_unknown_requirement_and_missing_output_in_receipt(tmp_path):
    e = envelope(tmp_path / "artifact")
    e["request"]["evidence"]["requirements"].append("independent approval")
    out = runtime(tmp_path).build_runtime.execute(authorize(e))
    receipt = json.loads(Path(out["build"]["receipt_path"]).read_text())
    check = next(c for c in receipt["validation_results"] if c.get("requirement") == "independent approval")
    assert check["state"] == "UNPROVEN"
    assert receipt["final_status"] == "UNPROVEN"


def test_command_completion_without_requirements_is_unproven(tmp_path):
    from builder.tests.test_builder_entry import _valid_handoff_payload
    from builder.core.build_entry import run_builder_core
    out = run_builder_core(_valid_handoff_payload(root=tmp_path, requirements=[]), str(tmp_path))
    assert out.validation_status == "UNPROVEN"
