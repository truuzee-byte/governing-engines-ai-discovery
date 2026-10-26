"""Required validation dimensions; truth assessment remains external."""
DIMENSIONS = frozenset({'dependency', 'integration', 'functional', 'runtime', 'governance', 'operational'})


def require_dimensions(requests, value):
    if type(requests) is not dict or set(requests) != DIMENSIONS:
        raise PermissionError('Complete external validation dimensions required')
    for dimension, request in requests.items():
        scope = request['scope']
        if scope.get('validation_dimension') != dimension:
            raise PermissionError('Validation dimension substitution')
        if (scope.get('build_id') != value['build_outcome']['build']['build_id'] or
                scope.get('artifact_hashes') != value['rollback_snapshot']['after']):
            raise PermissionError('Validation does not bind the constructed artifact snapshot')
