"""Manual live-model build. No provider calls without an explicit --approve."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from integration.build_runtime import BuildRuntime, digest
from integration.mode_generation import ModeGenerationProvider
from integration.rp_process import ExternalRPProcess
from interactive_mode_ai import ModeRuntime, RuntimeState
from runtime_observation import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from understanding import UnderstandingEngine, UnderstandingStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="JSON with request and understanding")
    parser.add_argument("--rp-grant", required=True, help="Explicit independent verifier grant JSON")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--thread", required=True)
    parser.add_argument("--state-dir", required=True, help="Dedicated state for this live attempt")
    parser.add_argument("--rp-repository", default=r"C:\REALITY_PRIMACY")
    parser.add_argument("--approve", action="store_true", help="Authorize this exact request and independent verifier; permits model charges")
    args = parser.parse_args()
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    if set(payload) != {"request", "understanding"}:
        parser.error("Request file must contain exactly request and understanding")
    envelope = {**payload, "authorization": {"operator_id": args.operator, "thread_id": args.thread,
        "decision": "APPROVE", "request_hash": digest(payload)}}
    grant = json.loads(Path(args.rp_grant).read_text(encoding="utf-8"))
    if Path(grant["root"]).resolve() != Path(payload["request"]["execution"]["repository_target"]).resolve():
        parser.error("RP grant root must match the operator's canonical repository target")
    print(json.dumps({"request": payload, "independent_verifier": grant, "request_hash": digest(envelope)}, indent=2))
    if not args.approve:
        print("Review only. Re-run with --approve to authorize this exact request and verifier.")
        return
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=False)
    grant.update(operator_id=args.operator, thread_id=args.thread, request_hash=digest(envelope))
    grant_path = state / "rp_grant.json"
    grant_path.write_text(json.dumps(grant, indent=2), encoding="utf-8")
    runtime = ModeRuntime.__new__(ModeRuntime)
    runtime.context = SimpleNamespace(identity=SimpleNamespace(operator_id=args.operator),
        active_thread=SimpleNamespace(thread_id=args.thread), runtime_state=RuntimeState.INTERPRETING)
    runtime.understanding_engine = UnderstandingEngine(UnderstandingStore(state / "understanding.sqlite"))
    runtime.runtime_observation_collector = RuntimeObservationCollector(store=RuntimeObservationStore(state / "observations"))
    from agents.reasoning_agent import ReasoningAgent
    from runtime_economics.economic_telemetry_store import EconomicTelemetryStore
    agent = ReasoningAgent(config_path=str(Path(__file__).resolve().parents[1] / "data" / "model_config.json"),
                           telemetry_store=EconomicTelemetryStore(str(state / "provider_requests.jsonl")))
    runtime.build_runtime = BuildRuntime(runtime, ModeGenerationProvider(agent))
    external = ExternalRPProcess(args.rp_repository, grant_path, state / "rp_decisions.sqlite")
    try:
        external.attach(runtime)
        result = runtime.handle_build_request("/build " + json.dumps(envelope))
        (state / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        external.close()


if __name__ == "__main__":
    main()
