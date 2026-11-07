"""
Runtime Observation Package

Purpose
-------
Runtime Observation records how the runtime actually executed.

Observation is the runtime evidence layer.

Responsibilities
----------------
• Record runtime execution.
• Preserve execution evidence.
• Capture context custody.
• Capture knowledge custody.
• Capture decision custody.
• Preserve runtime traces.
• Persist observation records.

Runtime Observation never:

• Interprets execution.
• Learns from execution.
• Updates Understanding.
• Governs runtime behavior.
• Changes runtime execution.

Those responsibilities belong to downstream governed systems.
"""

from runtime_observation.observation_record import (
    RuntimeObservationRecord,
    RuntimeObservationType,
    generate_observation_id,
    utc_now_iso,
)

from runtime_observation.observation_builder import (
    RuntimeObservationBuilder,
)

from runtime_observation.observation_store import (
    RuntimeObservationStore,
    ObservationRetrievalError,
)

from runtime_observation.observation_classifier import (
    RuntimeObservationClassifier,
    RuntimeObservationClassification,
)

from runtime_observation.observation_collector import (
    RuntimeObservationCollector,
)

__all__ = [
    # Record
    "RuntimeObservationRecord",
    "RuntimeObservationType",

    # Builder
    "RuntimeObservationBuilder",

    # Store
    "RuntimeObservationStore",
    "ObservationRetrievalError",

    # Classifier
    "RuntimeObservationClassifier",
    "RuntimeObservationClassification",

    # Collector
    "RuntimeObservationCollector",

    # Helpers
    "generate_observation_id",
    "utc_now_iso",
]