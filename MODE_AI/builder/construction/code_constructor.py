from __future__ import annotations

from typing import Any, Mapping, Protocol

from builder.construction.construction_models import (
    CommandProposal,
    ConstructionProposal,
    FileProposal,
)
from builder.core.build_models import BuildPlan


class ConstructionProviderRequired(RuntimeError):
    pass


class CodeGenerationProvider(Protocol):
    def generate(
        self,
        build_plan: BuildPlan,
        repository_context: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


def construct_code(
    build_plan: BuildPlan,
    repository_context: Mapping[str, Any] | None = None,
    provider: CodeGenerationProvider | None = None,
) -> ConstructionProposal:
    """Create a proposal. This function never writes files.

    Bootstrap behavior:
    - If MODE already supplied exact approved file contents in the BuildSpec,
      those are used as the proposal.
    - Otherwise a generation provider must be injected. That provider is the
      one integration hook that must be connected to MODE's existing model
      invocation path.
    """
    if not isinstance(build_plan, BuildPlan):
        raise ValueError("invalid build_plan")

    context = dict(repository_context or {})

    if build_plan.approved_files:
        files = []
        for path, content in build_plan.approved_files.items():
            operation = "MODIFY" if path in set(build_plan.existing_files) else "CREATE"
            files.append(
                FileProposal(
                    path=path,
                    operation=operation,
                    content=content,
                    reason="approved content supplied by MODE BuildSpec",
                    spec_requirement="approved_files",
                )
            )
        return ConstructionProposal(
            files=files,
            commands=[CommandProposal(argv=list(cmd), purpose="approved build command") for cmd in build_plan.approved_commands],
        )

    if provider is None:
        raise ConstructionProviderRequired(
            "no approved_files supplied and no CodeGenerationProvider connected"
        )

    generated = provider.generate(build_plan, context)
    if not isinstance(generated, Mapping):
        raise ValueError("generation provider returned invalid payload")

    raw_files = generated.get("files", [])
    raw_commands = generated.get("commands", [])
    unresolved = generated.get("unresolved_conditions", [])
    boundary_state = generated.get("boundary_state")

    if not isinstance(raw_files, list):
        raise ValueError("generated files must be a list")
    if not isinstance(raw_commands, list):
        raise ValueError("generated commands must be a list")
    if not isinstance(unresolved, list):
        raise ValueError("unresolved_conditions must be a list")

    files: list[FileProposal] = []
    for item in raw_files:
        if not isinstance(item, Mapping):
            raise ValueError("invalid generated file proposal")
        files.append(
            FileProposal(
                path=str(item.get("path", "")),
                operation=str(item.get("operation", "CREATE")).upper(),
                content=item.get("content", ""),
                reason=str(item.get("reason", "")),
                spec_requirement=str(item.get("spec_requirement", "")),
            )
        )

    commands: list[CommandProposal] = []
    for item in raw_commands:
        if not isinstance(item, Mapping):
            raise ValueError("invalid generated command proposal")
        commands.append(
            CommandProposal(
                argv=list(item.get("argv", [])),
                purpose=str(item.get("purpose", "")),
            )
        )

    return ConstructionProposal(
        files=files,
        commands=commands,
        unresolved_conditions=[str(value) for value in unresolved],
        boundary_state=str(boundary_state) if boundary_state is not None else None,
    )
