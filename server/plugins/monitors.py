"""Private, encrypted API monitors. Unknown provider statistics remain unavailable."""
import json,time,uuid,math,threading
from urllib.parse import urlsplit
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from ..core import require_plugin
from ..db import connect,now
from ..outbound import endpoint,request_json
from ..ai_endpoints import api_base,is_xai,models_url
from ..secret_store import seal,open_secret
from ..api_meter import metered,fingerprint
from ..providers import PROVIDERS
from datetime import datetime,timedelta,timezone
router=APIRouter(prefix='/monitors');user=require_plugin('atlas');LIMIT=threading.BoundedSemaphore(4)
class Config(BaseModel):
    provider_id:str=Field(default='custom',max_length=40)
    billing_key:str=Field(default='',max_length=2000)
    clear_billing_key:bool=False
    name:str=Field(min_length=1,max_length=80)
    api_base:str=Field(min_length=1,max_length=500)
    api_key:str=Field(default='',max_length=2000)
    protocol:Literal['openai','responses','anthropic','gemini']='openai'
def owned(d,uid,id):
    r=d.execute('SELECT * FROM api_monitors WHERE user_id=? AND id=?',(uid,id)).fetchone()
    if not r:raise HTTPException(404,'监视卡片不存在')
    return dict(r)
def public(row):
    with connect() as d:
        counts=d.execute("SELECT COUNT(*),SUM(json_extract(payload,'$.tokens')),SUM(CASE WHEN json_extract(payload,'$.tokens') IS NULL THEN 1 ELSE 0 END) FROM events WHERE user_id=? AND kind='api-usage' AND json_extract(payload,'$.key_hash')=? AND json_extract(payload,'$.base') IN (?,?)",(row['user_id'],fingerprint(open_secret(row['secret'])),row['api_base'],api_base(row['api_base']))).fetchone()
    return {k:row[k] for k in ('id','name','api_base','protocol','updated_at','provider_id')}|{'has_billing_key':bool(row['billing_secret'])}|{'has_key':bool(row['secret']),'report':json.loads(row['report']),'local_usage':{'requests':counts[0],'tokens':0 if not counts[0] else counts[1],'missing_token_reports':counts[2] or 0}}
def number(value):
    try:v=float(value);return v if math.isfinite(v) and v>=0 else None
    except (TypeError,ValueError):return None
def auth(row,key):
    return {'x-goog-api-key':key} if row['protocol']=='gemini' else {'x-api-key':key,'anthropic-version':'2023-06-01'} if row['protocol']=='anthropic' else {'Authorization':'Bearer '+key}
def probe(row,key):
    base=api_base(row['api_base']);host=urlsplit(base).hostname
    report={'provider':host,'balance':None,'spent':None,'requests':None,'tokens':None,'currency':None,'models':[],'statistics_note':'此平台未提供通用账单接口；空缺项目表示不可获取。','fetched_at':now(),'errors':[]}
    start=time.perf_counter()
    try:
        data=request_json(models_url(base),headers=auth(row,key));report['latency_ms']=round((time.perf_counter()-start)*1000)
        rows=data.get('data',data.get('models'))
        if not isinstance(rows,list):raise HTTPException(502,'未返回兼容的模型列表，请参照运营商文档填写模型 ID')
        report['models_available']=True
        for m in rows[:2000]:
            if not isinstance(m,dict):continue
            id=m.get('id') or str(m.get('name','')).removeprefix('models/')
            if not id:continue
            price=m.get('pricing',{});price=price if isinstance(price,dict) else {}
            input_price=number(price.get('prompt'));output_price=number(price.get('completion'))
            input_price=input_price*1e6 if input_price is not None else None
            output_price=output_price*1e6 if output_price is not None else None
            if is_xai(base):
                # xAI publishes USD cents per 100 million tokens, not dollars/token.
                raw_in=number(m.get('prompt_text_token_price'));raw_out=number(m.get('completion_text_token_price'))
                if raw_in is not None:input_price=raw_in/10000
                if raw_out is not None:output_price=raw_out/10000
            report['models'].append({'id':id,'provider':m.get('owned_by'),'input_price':input_price,'output_price':output_price})
    except HTTPException as e:report['errors'].append('模型列表：'+str(e.detail))
    try:
        if host=='api.deepseek.com':
            report['provider']='DeepSeek';data=request_json('https://api.deepseek.com/user/balance',headers=auth(row,key));balances=data.get('balance_infos',[])
            if balances:report.update(balance=number(balances[0].get('total_balance')),currency=balances[0].get('currency'),balances=balances,statistics_note='余额来自 DeepSeek；平台不提供此密钥的累计请求数、Token 与消费总额。')
        elif host=='openrouter.ai':
            report['provider']='OpenRouter';data=request_json('https://openrouter.ai/api/v1/key',headers=auth(row,key))['data']
            report.update(spent=number(data.get('usage')),balance=number(data.get('limit_remaining')),currency='USD',balance_label='密钥剩余额度',statistics_note='消费为此 API 密钥累计消费；未设置额度上限时，剩余额度不可获取。请求与 Token 总量需平台额外权限。')
    except HTTPException as e:report['errors'].append('平台统计：'+str(e.detail))
    provider_statistics(row,key,report)
    return report
def provider_statistics(row,key,report):
    provider=PROVIDERS.get(row['provider_id'])
    if not provider:return
    report['provider']=provider['name'];report['docs']=provider['docs'];report['statistics_note']=provider['note']
    base=api_base(row['api_base'])
    if urlsplit(base).netloc!=urlsplit(provider['base']).netloc:
        report['statistics_note']+=' 自定义地域 / 中转地址未匹配预设，未转发管理密钥。';return
    adapter=provider['billing']
    try:
        if adapter=='moonshot':
            data=request_json(base+'/users/me/balance',headers=auth(row,key)).get('data',{});report.update(balance=number(data.get('available_balance')),currency='USD',balance_label='账户可用余额')
        if adapter=='302ai':
            origin=urlsplit(base);data=request_json(origin.scheme+'://'+origin.netloc+'/dashboard/balance',headers=auth(row,key)).get('data',{});report.update(balance=number(data.get('balance')),currency='USD',balance_label='账户余额')
        if adapter not in ('openai','anthropic') or not row['billing_secret']:return
        admin=open_secret(row['billing_secret']);end=datetime.now(timezone.utc);start=end-timedelta(days=30)
        def pages(path,params,headers):
            result=[]
            for _ in range(5):
                data=request_json(base+path,params=params,headers=headers);result.extend(r for bucket in data.get('data',[]) for r in bucket.get('results',[]))
                if not data.get('has_more'):return result
                if not data.get('next_page'):raise HTTPException(502,'账单分页返回不完整')
                params=params|{'page':data['next_page']}
            raise HTTPException(502,'账单分页超出上限，未显示不完整合计')
        if adapter=='openai':
            headers={'Authorization':'Bearer '+admin};params={'start_time':int(start.timestamp()),'end_time':int(end.timestamp()),'bucket_width':'1d','limit':31}
            costs=pages('/organization/costs',params,headers);report.update(spent=sum(float(r['amount']['value']) for r in costs if r.get('amount',{}).get('currency','').lower()=='usd'),currency='USD',spent_label='组织近 30 天费用')
            usage=pages('/organization/usage/completions',params,headers);report.update(requests=sum(r.get('num_model_requests',0) for r in usage),tokens=sum(r.get('input_tokens',0)+r.get('output_tokens',0) for r in usage),usage_scope='组织近30天，非当前密钥全生命周期')
        else:
            headers={'x-api-key':admin,'anthropic-version':'2026-10-21'};params={'starting_at':start.isoformat().replace('+00:00','Z'),'ending_at':end.isoformat().replace('+00:00','Z'),'bucket_width':'1d','limit':31}
            costs=pages('/organizations/cost_report',params,headers);report.update(spent=sum(float(r.get('amount',0)) for r in costs if r.get('currency','USD').upper()=='USD')/100,currency='USD',spent_label='组织近 30 天费用')
            usage=pages('/organizations/usage_report/messages',params,headers);report.update(tokens=sum(r.get('uncached_input_tokens',0)+r.get('cache_read_input_tokens',0)+r.get('output_tokens',0)+sum(v for k,v in (r.get('cache_creation',{}) or {}).items() if k.endswith('input_tokens') and isinstance(v,(int,float))) for r in usage),usage_scope='组织近30天；费用接口不含优先级套餐')
    except HTTPException as e:report['errors'].append('运营商统计：'+str(e.detail))
    except (ValueError,TypeError,KeyError):report['errors'].append('运营商统计返回格式已变化，请参照官方文档核对')

@router.get('')
def listing(u=Depends(user)):
    with connect() as d:return {'providers':list(PROVIDERS.values()),'monitors':[public(dict(r)) for r in d.execute('SELECT * FROM api_monitors WHERE user_id=? ORDER BY updated_at DESC',(u['id'],))]}
@router.post('',status_code=201)
def create(body:Config,u=Depends(user)):
    endpoint(body.api_base)
    if body.provider_id!='custom' and body.provider_id not in PROVIDERS:raise HTTPException(422,'运营商不存在')
    if any(c in body.billing_key for c in '\r\n'):raise HTTPException(422,'管理密钥格式无效')
    if not body.api_key or any(c in body.api_key for c in '\r\n'):raise HTTPException(422,'请输入有效 API 密钥')
    with connect(True) as d:
        if d.execute('SELECT COUNT(*) FROM api_monitors WHERE user_id=?',(u['id'],)).fetchone()[0]>=30:raise HTTPException(409,'最多添加 30 个监视卡片')
        id=uuid.uuid4().hex;d.execute('INSERT INTO api_monitors(id,user_id,name,api_base,secret,protocol,report,updated_at,provider_id,billing_secret) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,u['id'],body.name,body.api_base.rstrip('/'),seal(body.api_key),body.protocol,'{}',now(),body.provider_id,seal(body.billing_key)));return public(owned(d,u['id'],id))
@router.put('/{id}')
def update(id:str,body:Config,u=Depends(user)):
    endpoint(body.api_base)
    if body.provider_id!='custom' and body.provider_id not in PROVIDERS:raise HTTPException(422,'运营商不存在')
    if any(c in body.billing_key for c in '\r\n'):raise HTTPException(422,'管理密钥格式无效')
    if any(c in body.api_key for c in '\r\n'):raise HTTPException(422,'密钥格式无效')
    with connect(True) as d:
        old=owned(d,u['id'],id)
        if body.api_base.rstrip('/')!=old['api_base'] and not body.api_key:raise HTTPException(422,'更换平台地址时请重新填写密钥')
        billing=seal(body.billing_key) if body.billing_key else '' if body.clear_billing_key or body.provider_id!=old['provider_id'] or body.api_base.rstrip('/')!=old['api_base'] else old['billing_secret']
        d.execute('UPDATE api_monitors SET name=?,api_base=?,secret=?,protocol=?,report=?,updated_at=?,provider_id=?,billing_secret=? WHERE id=?',(body.name,body.api_base.rstrip('/'),seal(body.api_key) if body.api_key else old['secret'],body.protocol,'{}',now(),body.provider_id,billing,id));return public(owned(d,u['id'],id))
@router.delete('/{id}')
def delete(id:str,u=Depends(user)):
    with connect(True) as d:owned(d,u['id'],id);d.execute('DELETE FROM api_monitors WHERE id=? AND user_id=?',(id,u['id']))
    return {'message':'监视卡片已删除'}
@router.post('/{id}/key')
def copy_key(id:str,u=Depends(user)):
    with connect() as d:row=owned(d,u['id'],id)
    return {'key':open_secret(row['secret'])}
@router.post('/{id}/refresh')
def refresh(id:str,u=Depends(user)):
    if not LIMIT.acquire(blocking=False):raise HTTPException(429,'正在更新其他卡片，请稍候')
    try:
        with connect() as d:row=owned(d,u['id'],id)
        previous=json.loads(row['report'])
        if time.time()-previous.get('epoch',0)<10:return public(row)
        report=probe(row,open_secret(row['secret']));report['epoch']=time.time()
        if report['errors'] and not report['models'] and previous.get('models'):
            report=previous|{'errors':report['errors'],'stale':True,'attempted_at':now(),'epoch':report['epoch']}
        with connect(True) as d:
            current=owned(d,u['id'],id)
            if current['secret']!=row['secret'] or current['api_base']!=row['api_base'] or current['billing_secret']!=row['billing_secret'] or current['provider_id']!=row['provider_id']:raise HTTPException(409,'配置已更改，请重新获取')
            current_report=json.loads(current['report'])
            for k in ('speed','test_epoch'):
                if k in current_report:report[k]=current_report[k]
            d.execute('UPDATE api_monitors SET report=? WHERE id=?',(json.dumps(report,ensure_ascii=False),id));return public(owned(d,u['id'],id))
    finally:LIMIT.release()

class SpeedTest(BaseModel):
    model:str=Field(min_length=1,max_length=200,pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:/-]*$')
@router.post('/{id}/test')
def speed_test(id:str,body:SpeedTest,u=Depends(user)):
    if not LIMIT.acquire(blocking=False):raise HTTPException(429,'正在测速，请稍候')
    try:
        with connect() as d:row=owned(d,u['id'],id)
        report=json.loads(row['report'])
        if time.time()-report.get('test_epoch',0)<15:raise HTTPException(429,'请间隔 15 秒再次测速')
        if report.get('models') and body.model not in {m['id'] for m in report.get('models',[])}:raise HTTPException(422,'请先刷新并选择平台支持的模型')
        base=api_base(row['api_base']);stored_base=row['api_base'];key=open_secret(row['secret']);start=time.perf_counter()
        # Persist rate limit before the network request, including failed attempts.
        with connect(True) as d:
            current=owned(d,u['id'],id);report=json.loads(current['report'])
            if current['secret']!=row['secret'] or current['api_base']!=stored_base:raise HTTPException(409,'配置已更改，请重新测速')
            if time.time()-report.get('test_epoch',0)<15:raise HTTPException(429,'请间隔 15 秒再次测速')
            report['test_epoch']=time.time();d.execute('UPDATE api_monitors SET report=? WHERE id=?',(json.dumps(report,ensure_ascii=False),id))
        if row['protocol']=='responses':url=base+'/responses';payload={'model':body.model,'max_output_tokens':32,'input':'Reply with one short sentence: hello.'}
        elif row['protocol']=='anthropic':url=base+'/messages';payload={'model':body.model,'max_tokens':32,'messages':[{'role':'user','content':'Reply with one short sentence: hello.'}]}
        elif row['protocol']=='gemini':url=base+'/models/'+body.model+':generateContent';payload={'contents':[{'parts':[{'text':'Reply with one short sentence: hello.'}]}],'generationConfig':{'maxOutputTokens':32}}
        else:url=base+'/chat/completions';payload={'model':body.model,'max_tokens':32,'stream':False,'messages':[{'role':'user','content':'Reply with one short sentence: hello.'}]}
        data=metered(u['id'],base,key,body.model,url,payload,auth(row,key));elapsed=time.perf_counter()-start;usage=data.get('usage',data.get('usageMetadata',{})) or {};output=number(usage.get('completion_tokens',usage.get('output_tokens',usage.get('candidatesTokenCount'))))
        with connect(True) as d:
            current=owned(d,u['id'],id)
            if current['secret']!=row['secret'] or current['api_base']!=stored_base:raise HTTPException(409,'配置已更改，请重新测速')
            value=json.loads(current['report']);value['speed']={'model':body.model,'duration_ms':round(elapsed*1000),'output_tokens':output,'tokens_per_second':round(output/elapsed,2) if output is not None else None,'measured_at':now()};d.execute('UPDATE api_monitors SET report=? WHERE id=?',(json.dumps(value,ensure_ascii=False),id));return public(owned(d,u['id'],id))
    finally:LIMIT.release()
