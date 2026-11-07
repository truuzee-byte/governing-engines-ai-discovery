from __future__ import annotations

from mode_operator.operator_requirement_models import (
    OperatorRequirementDefinition,
    OperatorRequirementDomain,
    OperatorRequirementSensitivity,
)


DOMAIN_REQUIREMENTS: dict[
    OperatorRequirementDomain,
    list[OperatorRequirementDefinition],
] = {
    OperatorRequirementDomain.GENERAL: [],

    OperatorRequirementDomain.HEALTH: [
        OperatorRequirementDefinition(
            field_name="age",
            label="Age",
            required=True,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="Age may be required for responsible health guidance.",
        ),
        OperatorRequirementDefinition(
            field_name="height",
            label="Height",
            required=True,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="Height required for health calculations.",
        ),
        OperatorRequirementDefinition(
            field_name="weight",
            label="Weight",
            required=True,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="Weight required for health calculations.",
        ),
        OperatorRequirementDefinition(
            field_name="activity_level",
            label="Activity Level",
            required=True,
            sensitivity=OperatorRequirementSensitivity.MEDIUM,
            reason="Required to personalize recommendations.",
        ),
        OperatorRequirementDefinition(
            field_name="injuries",
            label="Injuries",
            required=False,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="May affect recommendations.",
        ),
        OperatorRequirementDefinition(
            field_name="medical_conditions",
            label="Medical Conditions",
            required=False,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="May affect recommendations.",
        ),
    ],

    OperatorRequirementDomain.FINANCIAL_PLANNING: [
        OperatorRequirementDefinition(
            field_name="income",
            label="Income",
            required=True,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="Required for financial planning.",
        ),
        OperatorRequirementDefinition(
            field_name="debt",
            label="Debt",
            required=False,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="Improves planning accuracy.",
        ),
        OperatorRequirementDefinition(
            field_name="assets",
            label="Assets",
            required=False,
            sensitivity=OperatorRequirementSensitivity.HIGH,
            reason="Improves planning accuracy.",
        ),
        OperatorRequirementDefinition(
            field_name="financial_goals",
            label="Financial Goals",
            required=True,
            sensitivity=OperatorRequirementSensitivity.MEDIUM,
            reason="Defines planning objective.",
        ),
        OperatorRequirementDefinition(
            field_name="risk_tolerance",
            label="Risk Tolerance",
            required=False,
            sensitivity=OperatorRequirementSensitivity.MEDIUM,
            reason="Supports investment discussions.",
        ),
    ],

    OperatorRequirementDomain.LEGAL_ASSISTANCE: [
        OperatorRequirementDefinition(
            field_name="jurisdiction",
            label="Jurisdiction",
            required=True,
            reason="Legal guidance depends on jurisdiction.",
        ),
        OperatorRequirementDefinition(
            field_name="legal_role",
            label="Legal Role",
            required=False,
            reason="Provides execution context.",
        ),
        OperatorRequirementDefinition(
            field_name="case_type",
            label="Case Type",
            required=True,
            reason="Determines applicable legal domain.",
        ),
    ],

    OperatorRequirementDomain.EDUCATION: [
        OperatorRequirementDefinition(
            field_name="grade_level",
            label="Grade Level",
            required=True,
            reason="Required for educational adaptation.",
        ),
        OperatorRequirementDefinition(
            field_name="learning_goal",
            label="Learning Goal",
            required=True,
            reason="Defines educational objective.",
        ),
    ],

    OperatorRequirementDomain.PROFESSIONAL: [
        OperatorRequirementDefinition(
            field_name="occupation",
            label="Occupation",
            required=False,
            reason="Provides professional context.",
        ),
        OperatorRequirementDefinition(
            field_name="certifications",
            label="Certifications",
            required=False,
            reason="Determines professional capability.",
        ),
    ],

    OperatorRequirementDomain.ENGINEERING: [
        OperatorRequirementDefinition(
            field_name="system_type",
            label="System Type",
            required=True,
            reason="Defines engineering context.",
        ),
        OperatorRequirementDefinition(
            field_name="constraints",
            label="Constraints",
            required=True,
            reason="Required before engineering recommendations.",
        ),
        OperatorRequirementDefinition(
            field_name="environment",
            label="Environment",
            required=False,
            reason="Provides deployment context.",
        ),
        OperatorRequirementDefinition(
            field_name="safety_requirements",
            label="Safety Requirements",
            required=False,
            reason="Supports safe engineering decisions.",
        ),
    ],

    OperatorRequirementDomain.ENTERPRISE_WORKFLOW: [
        OperatorRequirementDefinition(
            field_name="organization_role",
            label="Organization Role",
            required=True,
            reason="Determines execution authority.",
        ),
        OperatorRequirementDefinition(
            field_name="authority_level",
            label="Authority Level",
            required=True,
            reason="Required before enterprise actions.",
        ),
        OperatorRequirementDefinition(
            field_name="department",
            label="Department",
            required=False,
            reason="Provides organizational context.",
        ),
        OperatorRequirementDefinition(
            field_name="compliance_requirements",
            label="Compliance Requirements",
            required=False,
            reason="Supports governed execution.",
        ),
    ],
}


def get_domain_requirements(
    domain: OperatorRequirementDomain,
) -> list[OperatorRequirementDefinition]:
    return DOMAIN_REQUIREMENTS[OperatorRequirementDomain(domain)]
