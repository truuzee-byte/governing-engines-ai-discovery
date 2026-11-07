"""No last-key-wins interpretation of governed Operator command envelopes."""
import json


def load_payload(text):
    if type(text) is not str or len(text)>20*1024*1024:raise ValueError('Command payload exceeds supported bound')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate command field: '+key)
            result[key]=value
        return result
    def invalid(value):raise ValueError('Non-finite command value')
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid)
