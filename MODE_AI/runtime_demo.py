from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core.mode_controller import process_interaction
from runtime_logging.response_logger import write_response_log 
from models.runtime_models import OperatorInput
from builder.handoff.mode_to_builder_adapter import mode_to_builder_handoff
from builder.handoff.specification_receiver import receive_specification

def main() -> None:
    session_id = f"runtime-demo-{uuid4().hex}"

    while True:
        raw_input = input("Mode AI input> ")

        if raw_input.strip().lower() == "exit":
            break

        operator_input = OperatorInput(
            raw_input=raw_input,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="runtime_demo",
        )

        result = process_interaction(operator_input)

        try:
            handoff_payload = mode_to_builder_handoff(result)

            print("BUILDER HANDOFF READY")

            received_spec = receive_specification(handoff_payload)

            print("BUILDER RECEIVED SPECIFICATION")
            print(received_spec.to_dict())

        except Exception as error:
            print(f"BUILDER HANDOFF BLOCKED: {error}")

        print(f"success: {result.success}")

        if result.interaction_manifest is not None:
            manifest = result.interaction_manifest

            response_text = (
                f"[{manifest.selected_posture}] "
                f"Mode AI processed the exchange."
            )

            response_log_path = write_response_log(
                interaction_id=manifest.interaction_id,
                session_id=manifest.session_id,
                response_text=response_text,
            )

            print(f"selected_mode: {manifest.selected_mode}")
            print(f"selected_posture: {manifest.selected_posture}")
            print(f"ambiguity_score: {manifest.ambiguity_score}")
            print(
                "interpretation_stability_score: "
                f"{manifest.interpretation_stability_score}"
            )
            print(
                "operator_alignment_score: "
                f"{manifest.operator_alignment_score}"
            )
            print(f"clarification_required: {manifest.clarification_required}")
            print(f"halt_required: {manifest.halt_required}")
            print(
                "downstream_authority_allowed: "
                f"{manifest.downstream_authority_allowed}"
            )
            print(f"trace_reference: {manifest.trace_reference}")
            print(f"response_text: {response_text}")
            print(f"response_log_path: {response_log_path}")

        else:
            print(f"trace_reference: {result.trace_reference}")

        if not result.success:
            print(f"failure_state: {result.failure_state}")

        print("-" * 50)


if __name__ == "__main__":
    main()