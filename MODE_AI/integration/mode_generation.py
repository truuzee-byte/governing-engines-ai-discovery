"""Proposal-only adapter to Mode's existing reasoning infrastructure."""
import ast
import hashlib
import json


class GenerationFailure(RuntimeError):
    pass


class ModeGenerationProvider:
    def __init__(self, agent=None):
        self.agent = agent
        self.generated = []
        self.learning_advisory_loader = None

    def generate(self, build_plan, repository_context):
        if self.agent is None:
            from agents.reasoning_agent import ReasoningAgent
            self.agent = ReasoningAgent()
        files = []
        for path in build_plan.required_files:
            correction = repository_context.get('corrective_analysis')
            if correction and path not in correction['adjustment']['paths']:
                files.append({'path': path, 'content': repository_context['existing_files'][path],
                              'operation': 'MODIFY'})
                continue
            admitted=None;result=None
            context = {"specification": repository_context["specification"],
                       "build_plan": build_plan.to_dict(), "target_path": path,
                       "existing_content": repository_context.get("existing_files", {}).get(path)}
            if correction:
                context['provisional_corrective_analysis'] = correction
            try:
                from data_governance.context_admission import Admission
                from learning.contracts import digest
                authorization=context['specification'].get('metadata',{}).get('operator_authorization',{})
                owner=authorization.get('operator_id');thread=authorization.get('thread_id')
                admission=Admission(owner,thread)
                if authorization.get('decision')!='APPROVE':raise PermissionError('Generation requires authorized specification')
                basis={'verified':context['specification'].get('spec_id')==build_plan.spec_id,
                       'governance_state':'APPROVED','lineage':[build_plan.spec_id,build_plan.snapshot_hash],
                       'validation_state':'NOT_REQUIRED','authority':'OPERATOR','classification':'UNDERSTANDING_DATA'}
                basis['scope']={'spec_id':build_plan.spec_id,'repository_target':build_plan.repository_target}
                if not admission.consider('SPECIFICATION',build_plan.spec_id,json.dumps(context,ensure_ascii=False),
                        source='Canonical Builder handoff',basis=basis):raise PermissionError('Generation context admission failed')
                if self.learning_advisory_loader is not None:
                    advisory = self.learning_advisory_loader()
                    if advisory:
                        admission.parts.append('\n')
                        admission.include(advisory)
                admitted=admission.finish()
                result = self.agent.generate(
                    active_pack_name="Mode", active_mode_name="Development",
                    mode_definition={"purpose": "Generate complete implementation contents as a proposal",
                        "schema": ["Return only JSON with exactly path and content string fields"],
                        "constraints": ["Do not execute commands or write files", "No markdown fences or placeholder implementations",
                                        "Return only the requested target; preserve the canonical specification"]},
                    user_input=admitted, input_kind="build_request",
                    response_posture="technical", interaction_id=build_plan.build_id)
                value = json.loads(result.final_response)
                if type(value) is not dict or set(value) != {"path", "content"} or value["path"] != path:
                    raise ValueError("Wrong target or unexpected proposal fields")
                content = value["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Empty generated contents")
                if path.endswith(".py"):
                    tree = ast.parse(content)
                    if not tree.body or all(isinstance(n, ast.Expr) for n in tree.body):
                        raise ValueError("Prose or empty implementation")
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Pass) or (isinstance(node, ast.Constant) and node.value is Ellipsis):
                            raise ValueError("Placeholder implementation")
                        if isinstance(node, ast.Name) and node.id == "NotImplementedError":
                            raise ValueError("Unimplemented proposal")
                if any(marker in content.lower() for marker in ("todo: implement", "your code here", "placeholder implementation")):
                    raise ValueError("Placeholder implementation")
            except Exception as exc:
                self.generated.append({'path':path,'generation_status':'FAILED',
                    'context_admission':admitted.decisions if admitted is not None else [],
                    'reasoning_context_admission':getattr(result,'context_admission',[]),'error_type':type(exc).__name__})
                raise GenerationFailure(f"Generation failed for {path}: {exc}") from exc
            operation = "MODIFY" if path in build_plan.existing_files else "CREATE"
            files.append({"path": path, "content": content, "operation": operation,
                          "reason": "Mode generated proposal", "spec_requirement": build_plan.spec_id})
            self.generated.append({"path": path, "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "context_admission":admitted.decisions,
                "reasoning_context_admission":getattr(result,'context_admission',[]),
                "reasoning_id": getattr(result, "reasoning_id", None),
                "provider": getattr(result, "provider", None), "model": getattr(result, "model", None),
                "telemetry_evidence_references": getattr(result, "telemetry_evidence_references", [])})
        return {"files": files, "commands": [{"argv": c, "purpose": "Approved build command"}
                                               for c in build_plan.approved_commands]}
