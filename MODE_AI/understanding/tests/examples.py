"""Reproduce review examples using synthetic, explicitly supplied evidence.

Run: python -B -m understanding.tests.examples --output <review.json>
No model, Builder, external service, or real capability validation is invoked.
"""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from understanding import UnderstandingEngine, UnderstandingStore
from .test_understanding_v12 import system_request, supplied_mechanisms, request_for, interpreted


def examples():
    with TemporaryDirectory(prefix="mode-understanding-example-") as temporary:
        engine = UnderstandingEngine(UnderstandingStore(Path(temporary) / "understanding.sqlite3"))
        incomplete = engine.process(system_request())
        ready = engine.process(system_request(mechanisms=supplied_mechanisms(incomplete)))
        engine.process(request_for(interpreted("Project term means Alpha.", "Alpha")))
        blocked = engine.process(request_for(interpreted("Project term means Beta.", "Beta")))
        assert not ready.errors and ready.specification_readiness.value == "READY_FOR_SPECIFICATION"
        assert incomplete.specification_readiness.value == "STRUCTURALLY_INCOMPLETE"
        assert blocked.custody_decision.permitted is False
        return {
            "evidence_notice": "Synthetic acceptance fixtures, not proof that Mode's restoration mechanisms exist.",
            "ready_for_specification": ready.to_dict(),
            "structurally_incomplete": incomplete.to_dict(),
            "blocked_by_semantic_custody": blocked.to_dict(),
            "specification_handoff": ready.specification_handoff(),
            "ready_explanation": ready.explain(),
            "incomplete_explanation": incomplete.explain(),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(examples(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote complete UnderstandingResult examples to {target.resolve()}")
