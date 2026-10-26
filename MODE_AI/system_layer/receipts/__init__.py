"""One canonical capability receipt representation for every accepted mutation."""
from ..contracts import digest, now


def create_receipt(subject, value, action, authorization, previous, references, metadata):
    record = {'subject': subject, 'value': value, 'action': action,
        'previous_receipt': previous.get('receipt_id'), 'previous_value': previous.get('value'),
        'authorization': authorization, 'references': list(references), 'timestamp': now(),
        'governed_metadata': metadata}
    record['receipt_id'] = 'system-receipt:' + digest(record)
    return record
