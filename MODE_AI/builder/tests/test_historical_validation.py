"""The retained historical receipt is evidence of the old result, not current truth."""
import hashlib
import json
from pathlib import Path

from builder.core.build_validator import validate_python_artifacts


def test_retained_false_pass_is_currently_contradicted_without_rewriting_history():
    root = Path(__file__).resolve().parents[1] / 'outputs' / 'builds' / 'spec_interaction-004559b1f0894095bd78267595740b15'
    receipt = root / 'build_receipt.json'
    before = receipt.read_bytes()
    assert hashlib.sha256(before).hexdigest() == '1d6886e3a79e904e3d6364740646c88cb337815a3fd0358808016147c4f58a6f'
    assert json.loads(before)['final_status'] == 'PASS'
    checks = validate_python_artifacts(str(root), ['validation.py'])
    assert len(checks) == 1
    assert checks[0]['state'] == 'FAILED'
    assert checks[0]['executed'] is True
    assert checks[0]['error_type'] == 'SyntaxError'
    assert checks[0]['sha256'] == '5fb55faa95731ab053c20694e3bcc23bd53c0995359cc58c9c04a526ec678b88'
    assert receipt.read_bytes() == before
