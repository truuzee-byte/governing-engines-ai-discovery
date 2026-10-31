"""Requirement-bound measurement comparison; external RP retains truth authority.

BLACK_FRAME, NONBLACK_FRAME and NONSILENT_PCM are narrow measurable predicates.
No pixel detector for identity/intent is implied; those remain UNRESOLVED.
"""
from runtime_observation.frame_inspection import inspect_frames
from runtime_observation.audio_inspection import inspect_pcm
from system_layer.contracts import digest


def compare(requirement, *, frame_contents=None, pcm=None, pcm_hash=None):
    frames = inspect_frames(frame_contents) if frame_contents is not None else None
    audio = inspect_pcm(pcm, pcm_hash) if pcm is not None else None
    checks = []
    for predicate in requirement.required_evidence:
        state = 'UNRESOLVED'; reason = 'SEMANTIC_VALIDATOR_REQUIRED'
        if predicate in {'BLACK_FRAME', 'NONBLACK_FRAME', 'CHARACTER_VISIBLE', 'ACTION_VISIBLE'}:
            measured = frames and frames['state'] == 'MEASURED' and frames['frames']
            if measured:
                black = [all(high == 0 for low, high in f['rgb_extrema']) for f in frames['frames']]
                satisfied = all(black) if predicate == 'BLACK_FRAME' else all(not b for b in black)
                if predicate in {'CHARACTER_VISIBLE', 'ACTION_VISIBLE'}:
                    # Black contradicts required visible content. Nonblack alone
                    # cannot establish who/what is visible.
                    state = 'UNRESOLVED' if satisfied else 'MISMATCH'
                    reason = 'SEMANTIC_VALIDATOR_REQUIRED' if satisfied else 'BLACK_FRAME_CONTRADICTS_VISIBILITY'
                else:
                    state = 'MATCH' if satisfied else 'MISMATCH'; reason = 'EXACT_RGB_EXTREMA'
            else: reason = 'FRAME_MEASUREMENT_UNAVAILABLE'
        elif predicate == 'NONSILENT_PCM':
            if audio and audio['state'] == 'MEASURED' and audio['metrics']['sample_frames'] > 0:
                state = 'MATCH' if any(audio['metrics']['nonzero_samples']) else 'MISMATCH'
                reason = 'PCM_NONZERO_SAMPLES_NOT_PLAYBACK'
            else: reason = 'PCM_MEASUREMENT_UNAVAILABLE'
        checks.append({'requirement_id': requirement.object_id, 'expected_evidence': predicate,
            'observed_evidence_hash': digest({'frames': frames, 'audio': audio}), 'comparison': state, 'reason': reason})
    result = 'MISMATCH' if any(c['comparison'] == 'MISMATCH' for c in checks) else 'UNRESOLVED' if not checks or any(c['comparison'] == 'UNRESOLVED' for c in checks) else 'MATCH'
    return {'contract': 'CinematicEvidenceComparison/1', 'requirement_id': requirement.object_id,
        'requirement_hash': digest(requirement.to_dict()), 'source_references': requirement.source_references,
        'measurements': {'frames': frames, 'audio': audio}, 'checks': checks, 'comparison': result,
        'claim_state': 'PENDING_VALIDATION', 'external_rp_required': True, 'render_execution_proven': False,
        'character_visibility_proven': False, 'cinematic_success_proven': False, 'execution_authority': False}
