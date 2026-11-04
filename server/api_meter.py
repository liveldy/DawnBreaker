import hashlib
from contextvars import ContextVar
from .core import emit,today
from .db import connect
from .outbound import request_json
owner=ContextVar('api_meter_owner',default=None)
def fingerprint(key):return hashlib.sha256(key.encode()).hexdigest()
def metered(uid,base,key,model,url,body,headers):
    data=request_json(url,body,headers)
    usage=data.get('usage',data.get('usageMetadata',{})) or {}
    tokens=usage.get('total_tokens',usage.get('totalTokenCount'))
    if tokens is None and 'input_tokens' in usage and 'output_tokens' in usage:tokens=usage['input_tokens']+usage['output_tokens']
    with connect(True) as d:emit(d,uid,'api-usage',{'date':today(),'base':base.rstrip('/'),'key_hash':fingerprint(key),'model':model,'tokens':tokens,'output_tokens':usage.get('completion_tokens',usage.get('output_tokens',usage.get('candidatesTokenCount'))),'cost':usage.get('cost')})
    return data
