"""Native tool calls with durable plans and results: retries do not regenerate paid media."""
import hashlib,json,time,uuid
from fastapi import HTTPException
from . import db
from .ai_protocol import invoke,ModelReply
from .companion_config import profile,settings
from .companion_search import search,read_page
from . import companion_stickers as stickers

def definitions(row):
    cfg=json.loads(row['config']);tuning=profile(row['provider'])['tools'];descriptions=settings()['tool_descriptions']
    def tool(name,description,fields):return {'name':name,'description':descriptions[name],'parameters':{'type':'object','properties':{key:{'type':'string','description':desc} for key,desc in fields.items()},'required':list(fields),'additionalProperties':False}}
    result=[tool('search_web','搜索公开问题，聚合 Google、Bing，必要时 DuckDuckGo 备用。只返回实际取得的摘要与来源。',{'query':'具体、简洁的公开问题，最多 300 字'}),tool('read_webpage','精读搜索结果或用户提供的 HTTPS 网页，只提取与问题相关的正文，去除导航、广告和评论。',{'url':'完整 HTTPS 网页地址','query':'本轮需要核实的问题或主题'})]
    result=[t for t in result if tuning['search_enabled' if t['name']=='search_web' else 'read_enabled']]
    pack=stickers.catalog(row['provider']) if tuning['sticker_enabled'] else []
    if pack:
        choice=tool('send_sticker','',{'sticker_id':'从自己的表情包选择一个编号：'+'；'.join(v['id']+' '+v['name']+'（'+v['description']+'）' for v in pack)})
        choice['parameters']['properties']['sticker_id']['enum']=[v['id'] for v in pack];result.append(choice)
    if row['provider']=='grok':
        if cfg.get('image_model') and tuning['image_enabled']:result.append(tool('generate_image','',{'prompt':f"完整画面描述，最多 {tuning['prompt_chars']} 字"}))
        if cfg.get('video_model') and tuning['video_enabled']:result.append(tool('generate_video','',{'prompt':f"完整视频描述，最多 {tuning['prompt_chars']} 字；生成时长 {tuning['video_seconds']} 秒"}))
        if cfg.get('voice_enabled') and tuning['voice_enabled']:result.append(tool('send_voice','',{'text':f"你自己要说的话，最多 {tuning['voice_chars']} 字"}))
    return result

def stage(uid,turn_id,text):
    with db.connect(True) as d:d.execute("UPDATE companion_turns SET result=?,updated_at=? WHERE id=? AND user_id=?",(json.dumps({'stage':text},ensure_ascii=False),db.now(),turn_id,uid))

def load(uid,id):
    with db.connect() as d:r=d.execute('SELECT * FROM companion_actions WHERE id=? AND user_id=?',(id,uid)).fetchone()
    return dict(r) if r else None

def completed(uid,companion_id,turn_id,id,kind,name,args,result):
    with db.connect(True) as d:d.execute("INSERT INTO companion_actions(id,user_id,companion_id,turn_id,kind,name,input,result,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET result=excluded.result,status='completed',updated_at=excluded.updated_at",(id,uid,companion_id,turn_id,kind,name,json.dumps(args,ensure_ascii=False),json.dumps(result,ensure_ascii=False),'completed',db.now(),db.now()))

def act(row,turn,call,generate):
    uid=row['user_id'];turn_id=turn['id'];name=call['name'];args=call['arguments'];id=hashlib.sha256((turn_id+':'+call['id']).encode()).hexdigest();old=load(uid,id)
    if old and old['status']=='completed':return json.loads(old['result'])
    if old and old['status']=='failed' and not old['provider_job']:return {'error':old['error']}
    if name not in {v['name'] for v in definitions(row)}:return {'error':'当前没有配置这个功能'}
    with db.connect(True) as d:
        # A model repeating a paid call cannot silently charge for a second copy.
        prior=d.execute("SELECT id,result,status,error FROM companion_actions WHERE turn_id=? AND user_id=? AND kind='tool' AND name=? ORDER BY created_at LIMIT 1",(turn_id,uid,name)).fetchone()
        if name in ('generate_image','generate_video','send_voice') and prior and prior['id']!=id:
            return json.loads(prior['result']) if prior['status']=='completed' else {'error':prior['error'] or '本轮已有同类生成任务，不重复创建'}
        if name=='send_sticker':
            previous=d.execute("SELECT result FROM companion_actions WHERE turn_id=? AND user_id=? AND name='send_sticker' AND status='completed' ORDER BY created_at LIMIT 1",(turn_id,uid)).fetchone()
            if previous:return json.loads(previous['result'])
        d.execute("INSERT OR IGNORE INTO companion_actions(id,user_id,companion_id,turn_id,kind,name,input,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(id,uid,row['id'],turn_id,'tool',name,json.dumps(args,ensure_ascii=False),'running',db.now(),db.now()))
    labels={'search_web':'正在搜索多个来源…','read_webpage':'正在阅读相关网页…','generate_image':'正在画图…','generate_video':'正在生成视频…','send_voice':'正在发语音…','send_sticker':'正在发一个表情…'}
    stage(uid,turn_id,labels[name])
    try:
        if name=='search_web':result=search(args.get('query',''))
        elif name=='read_webpage':result=read_page(args.get('url',''),args.get('query',''))
        elif name=='send_sticker':
            chosen=args.get('sticker_id','');stickers.path(row['provider'],chosen)
            result={'status':'sent','kind':'sticker','sticker_id':chosen,'name':stickers.PACKS[row['provider']][int(chosen)-1][0]}
        else:
            kind={'generate_image':'image','generate_video':'video','send_voice':'voice'}[name];text=args.get('text' if kind=='voice' else 'prompt','')
            if not isinstance(text,str) or not text.strip() or len(text)>(profile(row['provider'])['tools']['voice_chars'] if kind=='voice' else profile(row['provider'])['tools']['prompt_chars']):raise HTTPException(422,'工具内容为空或超过长度限制')
            generated=generate(row,{'id':turn_id,'kind':kind,'provider_job':old['provider_job'] if old else None,'action_id':id},{'text':text})
            result={'status':'sent','kind':kind,'media_ids':generated['media_ids'],'spoken_text':text if kind=='voice' else ''}
        completed(uid,row['id'],turn_id,id,'tool',name,args,result);return result
    except Exception as error:
        message=str(error.detail) if isinstance(error,HTTPException) else '工具暂时无法完成，请稍后再试'
        with db.connect(True) as d:d.execute("UPDATE companion_actions SET status='failed',error=?,updated_at=? WHERE id=? AND user_id=?",(message[:600],db.now(),id,uid))
        if name=='generate_video' and isinstance(error,HTTPException) and error.status_code==504:raise
        return {'error':message}

def converse(row,turn,messages,system,config,key,request,generate):
    uid=row['user_id'];tuning=profile(row['provider'])['tools'];tools=definitions(row);media=[];chosen_stickers=[];sources=[];spoken={};actions=0;errors=[];search_results={};web_failures=set();read_ok=False
    if any(t['name']=='send_sticker' for t in tools):system+='\n你可以自然地自行发送自己的专属表情包，按当前话题、性格和情绪选择，不必等用户要求，也不要每轮都发。每轮最多一张，发送后不必再用文字描述图片；可只发表情（bubbles 为空），也可以搭配短句。'
    def source(item):
        if not item.get('url'):return
        previous=next((v for v in sources if v['url']==item['url']),None)
        if previous:return previous['id']
        result={'id':len(sources)+1,'title':item.get('title') or item['url'],'url':item['url']};sources.append(result);return result['id']
    for step in range(tuning['max_rounds']):
        id=turn['id']+':plan:'+str(step);cached=load(uid,id)
        if cached and cached['status']=='completed':
            v=json.loads(cached['result']);reply=ModelReply(v['text'],calls=v['calls'],wire=v['wire'])
        else:
            stage(uid,turn['id'],'正在回复…')
            reply=invoke(config,key,messages,system,request,tools=tools if step<tuning['max_rounds']-1 and actions<tuning['max_calls'] else None)
            completed(uid,row['id'],turn['id'],id,'plan','model',{}, {'text':str(reply),'calls':reply.calls,'wire':reply.wire})
        if not reply.calls:
            notices=['部分来源正文暂不可读，本次仅使用可取得的搜索摘要；摘要未经全文核实。'] if web_failures and not read_ok and search_results else ['本次未能读取来源正文，请稍后重试或提供其他来源。'] if web_failures and not read_ok else []
            return {'raw':reply,'media_ids':media,'stickers':chosen_stickers,'sources':sources[:8],'spoken':spoken,'tool_errors':list(dict.fromkeys(errors)),'web_notices':notices}
        if step==tuning['max_rounds']-1:raise HTTPException(502,'本轮工具调用次数已达到上限，请分成下一条消息继续')
        messages.append({'role':'assistant','wire':reply.wire})
        for call in reply.calls[:tuning['max_calls']]:
            actions+=1
            result=act(row,turn,call,generate) if actions<=tuning['max_calls'] else {'error':'本轮工具调用次数已达到上限'}
            if result.get('sticker_id') and not chosen_stickers:chosen_stickers.append(result['sticker_id'])
            if call['name']=='search_web' and not result.get('results'):web_failures.add('search')
            for item in result.get('results',[]):
                item['source_id']=source(item);search_results[item['url']]=item
            if call['name']=='read_webpage' and result.get('error'):
                url=call['arguments'].get('url','');web_failures.add(url);snippet=search_results.get(url)
                if snippet and snippet.get('snippet'):
                    result={'url':url,'title':snippet['title'],'content':snippet['snippet'],'relevant':True,'snippet_only':True,'note':'正文无法访问，以上仅为搜索摘要，不是完整正文；可继续读取其他来源，不能声称已核实全文。'}
                else:result=result|{'note':'此来源不可用，不要重复读取相同地址，请换用搜索结果中的其他来源。'}
            if result.get('relevant'):
                result['source_id']=source(result)
                if call['name']=='read_webpage' and not result.get('snippet_only'):read_ok=True
            for token in result.get('media_ids',[]):
                if token not in media:media.append(token)
                if result.get('spoken_text'):spoken[token]=result['spoken_text']
            if result.get('error') and call['name'] not in ('search_web','read_webpage'):errors.append(result['error'])
            messages.append({'role':'tool','tool_call_id':call['id'],'name':call['name'],'content':json.dumps(result,ensure_ascii=False)})
    raise HTTPException(502,'没有收到最终回复，请重试')
