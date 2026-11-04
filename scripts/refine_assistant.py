from pathlib import Path
p=Path(__file__).resolve().parents[1]/'server/plugins/constellation.py';s=p.read_text(encoding='utf-8')
s=s.replace("protocol:Literal['openai','anthropic','gemini']", "protocol:Literal['openai','responses','anthropic','gemini']")
s=s.replace('temperature:float=Field(default=.7','temperature:float|None=Field(default=None')
s=s.replace("    if protocol=='anthropic':",'''    if protocol=='responses':
        data=request_json(base+'/responses',{'model':model,'instructions':system,'input':messages,'max_output_tokens':limit},{'Authorization':'Bearer '+key})
        return '\\n'.join(part.get('text','') for output in data.get('output',[]) for part in output.get('content',[]) if part.get('type')=='output_text')
    if protocol=='anthropic':''',1)
for fragment in ["        data=request_json(base+'/messages'","    data=request_json(base+'/chat/completions'"]:
    indentation=fragment[:len(fragment)-len(fragment.lstrip())]
    s=s.replace(fragment,indentation+"if body.get('temperature') is None:body.pop('temperature',None)\n"+fragment,1)
s=s.replace("        data=request_json(base+'/models/'", "        if body['generationConfig'].get('temperature') is None:body['generationConfig'].pop('temperature',None)\n        data=request_json(base+'/models/'",1)
s=s.replace('        if documents:\n','        complete_docs=set()\n        if documents:\n',1)
s=s.replace("                text=doc['markdown'][:budget];budget-=len(text)","                text=doc['markdown'][:budget];budget-=len(text)\n                if len(text)==len(doc['markdown']):complete_docs.add(doc['id'])",1)
s=s.replace("                if doc and type(edit.get('revision'))", "                if doc and doc['id'] in complete_docs and type(edit.get('revision'))",1)
p.write_text(s,encoding='utf-8')
