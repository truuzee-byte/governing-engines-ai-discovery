"""Persisted custody data has no last-key-wins or non-finite interpretation."""
import json


def load(stream):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('CUSTODY_JSON_DUPLICATE_FIELD')
            result[key]=value
        return result
    def invalid(value):raise ValueError('CUSTODY_JSON_NONFINITE_VALUE')
    return json.load(stream,object_pairs_hook=unique,parse_constant=invalid)
