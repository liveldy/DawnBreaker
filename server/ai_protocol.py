"""Provider-returned reasoning and native function calls, without invented thought text."""
import json,re,uuid
from fastapi import HTTPException

class ModelReply(str):
    def __new__(cls,text='',reasoning='',calls=None,wire=None,truncated=False):
        value=super().__new__(cls,text);value.reasoning=reasoning if isinstance(reasoning,str) else '';value.calls=calls or [];value.wire=wire;value.truncated=truncated;return value

def function(name,args,call_id=None):
    if isinstance(args,str):
        try:args=json.loads(args)
        except ValueError:args={}
    return {'id':call_id or uuid.uuid4().hex,'name':name,'arguments':args if isinstance(args,dict) else {}}

def invoke(config,key,messages,system,request,max_tokens=None,tools=None):
    model=config['model'];base=config['api_base'].rstrip('/');protocol=config['protocol'];limit=max_tokens or config['max_tokens']
    for suffix in ['/chat/completions','/responses','/messages']:
        if base.endswith(suffix):base=base[:-len(suffix)]
    thinking=config.get('show_reasoning',True);body={};headers={};url=''
    if protocol=='responses':
        inputs=[]
        for m in messages:
            if m.get('wire'):inputs.extend(m['wire'])
            elif m['role']=='tool':inputs.append({'type':'function_call_output','call_id':m['tool_call_id'],'output':m['content']})
            else:inputs.append({'role':m['role'],'content':m['content']})
        body={'model':model,'instructions':system,'input':inputs,'max_output_tokens':limit}
        if thinking and re.match(r'^(gpt-[56]|o[134])',model):body['reasoning']={'summary':'auto'}
        if tools:body['tools']=[{'type':'function','name':t['name'],'description':t['description'],'parameters':t['parameters']} for t in tools]
        url=base+'/responses';headers={'Authorization':'Bearer '+key}
    elif protocol=='anthropic':
        native=[]
        for m in messages:
            if m.get('wire'):native.append({'role':'assistant','content':m['wire']})
            elif m['role']=='tool':
                result={'type':'tool_result','tool_use_id':m['tool_call_id'],'content':m['content']}
                if native and native[-1]['role']=='user' and isinstance(native[-1]['content'],list):native[-1]['content'].append(result)
                else:native.append({'role':'user','content':[result]})
            else:native.append({'role':m['role'],'content':m['content']})
        body={'model':model,'system':system,'messages':native,'max_tokens':limit}
        if thinking and 'claude' in model.lower() and limit>=2048:
            body['thinking']={'type':'adaptive'} if re.search(r'(?:opus|sonnet)[-_.]([5-9]|4[-_.][6-9])',model) else {'type':'enabled','budget_tokens':max(1024,min(4096,limit//2))}
        elif config.get('temperature') is not None:body['temperature']=config['temperature']
        if tools:body['tools']=[{'name':t['name'],'description':t['description'],'input_schema':t['parameters']} for t in tools]
        url=base+'/messages';headers={'x-api-key':key,'anthropic-version':'2023-06-01'}
    elif protocol=='gemini':
        native=[]
        for m in messages:
            if m.get('wire'):native.append({'role':'model','parts':m['wire']})
            elif m['role']=='tool':
                part={'functionResponse':{'name':m['name'],'response':json.loads(m['content'])}}
                if m.get('provider_id'):part['functionResponse']['id']=m['provider_id']
                if native and native[-1]['role']=='user' and any('functionResponse' in p for p in native[-1]['parts']):native[-1]['parts'].append(part)
                else:native.append({'role':'user','parts':[part]})
            else:native.append({'role':'model' if m['role']=='assistant' else 'user','parts':[{'text':m['content']}]})
        generation={'maxOutputTokens':limit}
        if config.get('temperature') is not None:generation['temperature']=config['temperature']
        if thinking and re.search(r'gemini[-_.](2\.5|[3-9])',model):generation['thinkingConfig']={'includeThoughts':True}
        body={'systemInstruction':{'parts':[{'text':system}]},'contents':native,'generationConfig':generation}
        if tools:body['tools']=[{'functionDeclarations':[{'name':t['name'],'description':t['description'],'parameters':t['parameters']} for t in tools]}]
        from urllib.parse import quote
        url=base+'/models/'+quote(model.removeprefix('models/'),safe='')+':generateContent';headers={'x-goog-api-key':key}
    else:
        native=[]
        for m in messages:
            if m.get('wire'):native.append(m['wire'])
            elif m['role']=='tool':native.append({k:m[k] for k in ('role','content','tool_call_id')})
            else:native.append({'role':m['role'],'content':m['content']})
        body={'model':model,'messages':[{'role':'system','content':system}]+native,'max_tokens':limit,'stream':False}
        if config.get('family')=='gpt' and re.match(r'^(gpt-[56]|o[134])',model):body['max_completion_tokens']=body.pop('max_tokens')
        if config.get('temperature') is not None:body['temperature']=config['temperature']
        if config.get('family')=='deepseek' and model.lower().startswith('deepseek'):body['thinking']={'type':'enabled' if thinking else 'disabled'}
        if tools:body['tools']=[{'type':'function','function':t} for t in tools]
        url=base+'/chat/completions';headers={'Authorization':'Bearer '+key}
    data=request(config,key,url,body,headers)
    try:
        if protocol=='responses':
            output=data.get('output',[]);text='\n'.join(p.get('text','') for o in output for p in o.get('content',[]) if p.get('type')=='output_text')
            reasoning='\n'.join(s.get('text','') for o in output if o.get('type')=='reasoning' for s in o.get('summary',[]))
            calls=[function(o['name'],o.get('arguments',{}),o.get('call_id')) for o in output if o.get('type')=='function_call']
            return ModelReply(text,reasoning if thinking else '',calls,output,data.get('status')=='incomplete')
        if protocol=='anthropic':
            blocks=data.get('content',[]);return ModelReply('\n'.join(p.get('text','') for p in blocks if p['type']=='text'),'\n'.join(p.get('thinking','') for p in blocks if p['type']=='thinking') if thinking else '',[function(p['name'],p.get('input',{}),p.get('id')) for p in blocks if p['type']=='tool_use'],blocks,data.get('stop_reason')=='max_tokens')
        if protocol=='gemini':
            candidate=data.get('candidates',[{}])[0];parts=candidate.get('content',{}).get('parts',[])
            return ModelReply('\n'.join(p.get('text','') for p in parts if not p.get('thought')),'\n'.join(p.get('text','') for p in parts if p.get('thought')) if thinking else '',[function(p['functionCall']['name'],p['functionCall'].get('args',{}),p['functionCall'].get('id'))|{'provider_id':p['functionCall'].get('id')} for p in parts if p.get('functionCall')],parts,candidate.get('finishReason')=='MAX_TOKENS')
        choice=data['choices'][0];message=choice['message'];content=message.get('content') or '';text=content if isinstance(content,str) else '\n'.join(p.get('text','') for p in content)
        return ModelReply(text,(message.get('reasoning_content') or message.get('reasoning') or '') if thinking else '',[function(p['function']['name'],p['function'].get('arguments',{}),p.get('id')) for p in message.get('tool_calls',[])],message,choice.get('finish_reason')=='length')
    except (KeyError,TypeError,IndexError):raise HTTPException(502,'API 未返回可读取的回答，请检查协议和模型 ID')
