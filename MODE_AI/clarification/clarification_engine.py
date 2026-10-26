from __future__ import annotations

from typing import Any, Dict

from models.runtime_models import CanonicalInteractionState


IRREVERSIBLE_ACTION_TERMS = (
    "deploy",
    "publish",
    "delete",
    "commit",
    "override",
    "bypass",
    "merge",
    "push",
    "send",
)


def evaluate_clarification_state(
    state: CanonicalInteractionState,
) -> Dict[str, Any]:
    """
    Evaluates clarification and halt governance for Mode AI runtime slice v1.3.

    HALT is reserved for consequence-risk or execution-risk.
    Ambiguity score alone does not create HALT.
    """

    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    if state.ambiguity_score is None:
        raise ValueError("ambiguity_score must exist before clarification evaluation")

    prior = {k:getattr(state,k) for k in ('clarification_required','halt_required','downstream_authority_allowed')}
    def recorded(decision, rule):
        from runtime_observation.transformation_provenance import emit, digest
        emit(component=__name__, stage='evaluate_clarification_state', interaction=state.interaction_id,
            prior=prior,event={'kind':'controller_clarification_evaluation','input_hash':digest(state.normalized_input)},
            context={'ambiguity_score':state.ambiguity_score,'ambiguity_profile':state.ambiguity_profile},
            rules=rule,transformation='assign_controller_flags',
            result={**decision,'downstream_authority_allowed':state.downstream_authority_allowed},
            reason=decision['clarification_reason'],consumers=['core.mode_controller.process_interaction'])
        return decision

    clarification_state: Dict[str, Any] = {
        "clarification_required": False,
        "halt_required": False,
        "clarification_reason": "",
        "clarification_depth": 0,
        "disposition": "NO_CLARIFICATION_REQUIRED",
    }

    if _halt_risk_present(state):
        state.clarification_required = True
        state.halt_required = True
        state.downstream_authority_allowed = False

        clarification_state.update(
            {
                "clarification_required": True,
                "halt_required": True,
                "clarification_reason": "consequence_or_execution_risk_detected",
                "disposition": "HALT_REQUIRED",
            }
        )

        return recorded(clarification_state, '_halt_risk_present(state) == True')

    if state.ambiguity_score > 0.50:
        state.clarification_required = True
        state.halt_required = False
        state.downstream_authority_allowed = False

        clarification_state.update(
            {
                "clarification_required": True,
                "halt_required": False,
                "clarification_reason": "ambiguity_score_above_clarification_threshold",
                "disposition": "CLARIFICATION_REQUIRED",
            }
        )

        return recorded(clarification_state, '_halt_risk_present(state) == False; ambiguity_score > 0.50')

    state.clarification_required = False
    state.halt_required = False
    # Absence of ambiguity permits conversation, never grants execution consent.
    state.downstream_authority_allowed = False

    return recorded(clarification_state, '_halt_risk_present(state) == False; ambiguity_score <= 0.50; absence of ambiguity never grants execution consent')


def controlled_action_requests(text: str) -> list[str]:
    """Bounded lexical intent guard, not an execution authorization.

    Exact verbs in operative clauses remain fail-closed. Evidence quotations,
    identifiers and explicitly negated/informational clauses are not commands.
    Ambiguous unclassified action clauses stay protected.
    """
    import re
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    # A quoted command is still operative if the surrounding request delegates
    # execution of that quotation. Otherwise quotes carry evidence/data roles.
    quoted = re.compile(r'"[^"\n]*"|`[^`\n]*`|\u2018[^\u2019\n]*\u2019|(?<!\w)\'[^\'\n]*\'(?!\w)')
    def quote_role(match):
        before = text[max(0, match.start()-100):match.start()]
        if re.search(r'\b(?:please|can you|could you|would you|i want you to|you must)\s*$', before) or re.search(r'\b(?:execute|run|follow|perform|carry out|do)\s+(?:(?:the|this|following|quoted)\s+)*(?:command|instruction|action)?\s*:?\s*$', before):
            return match.group()[1:-1]
        return ' ' * len(match.group())
    text = quoted.sub(quote_role, text)
    # File/path/identifier tokens cannot supply imperative verbs.
    text = re.sub(r'(?<!\w)[\w:-]*(?:[./\\_][\w:-]+)+(?!\w)', ' ', text)
    actions = []
    for clause in re.split(r'[.!?;\n]+|\b(?:but|then|and then|however)\b|,\s*(?:and\s+)?', text):
        for match in re.finditer(r'(?<![\w-])(?:'+'|'.join(IRREVERSIBLE_ACTION_TERMS)+r')(?![\w-])', clause):
            before = clause[:match.start()]
            # Negation belongs only to this clause; later affirmative clauses
            # are evaluated independently ("do not publish, but send this").
            if re.search(r"\b(?:do not|don't|never|must not|shall not|should not|cannot|can't|will not|won't)\s+(?:(?:ever|actually|immediately|automatically|yet)\s+)*$", before):
                continue
            if re.match(r'\s*(?:please\s+)?(?:explain|describe|discuss|inspect|read|analyze|analyse|report|compare|review)\b', clause) and not re.search(r'\b(?:also|and|now)\s*$', before):
                continue
            actions.append(match.group())
    return actions


def _halt_risk_present(state: CanonicalInteractionState) -> bool:
    # An actual protected action cannot escape because a separate ambiguity
    # vocabulary omitted its phrasing. This guard never grants action authority.
    return bool(controlled_action_requests(state.normalized_input))
