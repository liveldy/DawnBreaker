from fastapi import APIRouter, Depends, HTTPException
from ..core import require_plugin, installed, credit, state, set_state, today
from ..db import connect
from ..milestones import listening_seconds
MANIFEST={'id':'journal','name':'拾光记','description':'记录签到、练习、听曲、珍藏、创作与交流，领取每日任务和递进成就奖励。','category':'基础支持','icon':'Flag','ui':'journal'}
router=APIRouter(prefix='/api/plugins/journal',tags=['拾光记']);user=require_plugin('journal')
REWARDS=[{'essence':50},{'essence':2000},{'essence':10000},{'stones':5},{'stones':10},{'stones':20},{'stones':50}]
def completed_albums(db,uid):
    from .collection import CONFIG,ALBUMS
    from ..collection_catalog import album_specs,accessible_cards,tree_for
    cards=accessible_cards(db,uid,CONFIG,ALBUMS);owned=state(db,uid,'collection','owned',{})
    complete=set()
    def visit(node,album):
        if node['kind']=='series':
            if node['total']>0 and node['owned']==node['total']:complete.add((album,node['id']))
        else:
            for child in node['children']:visit(child,album)
    for a in album_specs(ALBUMS):
        if installed(db,uid,a['content_plugin']):visit(tree_for(a,[c for c in cards if c['album_id']==a['id']],owned),a['id'])
    return len(complete)
def tasks(db,uid):
    result=[];daily=[]
    def events(kind,day=False):
        return db.execute('SELECT COUNT(*) FROM events WHERE user_id=? AND kind=?'+(" AND json_extract(payload,'$.date')=?" if day else ''),(uid,kind,today()) if day else (uid,kind)).fetchone()[0]
    def add(id,title,description,progress,target,reward,kind,**extra):
        task=dict(id=id,title=title,description=description,progress=min(progress,target),target=target,reward=reward,kind=kind,claimed=state(db,uid,'journal','claim:'+id,False),**extra)
        result.append(task);return task
    specs=[('checkin','始于足下','在朝暮签完成今日签到',events('checkin',True),1,5),('vocabulary','记忆者','在飞跃学习 / 测试 / 复习累计 20 个不同词汇',events('word-practiced',True),20,10),('music','品味旋律','在弦音余韵累计听曲 10 分钟',int(listening_seconds(db,uid,today())),600,5),('collection','开抽！','在珍藏阁抽一次卡',events('draw',True),1,5)]
    for plugin,title,desc,n,target,reward in specs:
        if installed(db,uid,plugin):daily.append(add('v2-daily-'+plugin+':'+today(),title,desc,n,target,{'essence':reward},'每日任务',unit='秒' if plugin=='music' else '词' if plugin=='vocabulary' else '次'))
    for plugin,title,desc,event in [('library','图书管理员','在流萤集编辑保存一次文本','document-saved'),('constellation','好助手','在星丛和一位助手对话一次','assistant-chatted'),('atlas','静观其变','进入天眼页面并更新数据','atlas-refreshed')]:
        if installed(db,uid,plugin):daily.append(add('v2-daily-'+plugin+':'+today(),title,desc,events(event,True),1,{'essence':5},'每日任务',unit='次'))
    if all(installed(db,uid,p) for p in ['checkin','vocabulary','music','collection']):add('v2-daily-all:'+today(),'有始有终','完成其他所有每日任务',sum(t['progress']>=t['target'] for t in daily),len(daily),{'essence':10},'每日任务')
    memory=state(db,uid,'vocabulary','memory',{})
    groups=[('checkin','千里之行',events('checkin'),[3,7,15,30,60,120,240],'累计完成 {} 天签到'),('vocabulary','记忆大师',sum(bool(v.get('memorized')) for v in memory.values()),[20,100,250,500,1000,2000,5000],'累计已记忆 {} 词'),('music','旋律爱好者',int(listening_seconds(db,uid)//60),[20,100,250,500,1000,2000,5000],'累计听曲 {} 分钟'),('collection','绝无仅有',completed_albums(db,uid) if installed(db,uid,'collection') else 0,[1,2,5,10,20,50,100],'累计集齐 {} 个系列卡册')]
    changed=db.execute("SELECT COALESCE(SUM(json_extract(payload,'$.characters')),0) FROM events WHERE user_id=? AND kind='document-saved'",(uid,)).fetchone()[0]
    groups += [('library','笔耕不辍',changed,[500,2000,10000,20000,50000,200000,500000],'累计文本改动 {} 字'),('constellation','心灵的交流',events('assistant-chatted'),[10,20,50,100,200,500,1000],'累计和助手对话 {} 次')]
    for plugin,title,n,levels,desc in groups:
        if not installed(db,uid,plugin):continue
        milestones=[dict(target=target,reward=REWARDS[i],claimed=state(db,uid,'journal',f'claim:v2-ach-{plugin}-{i}',False)) for i,target in enumerate(levels)]
        index=next((i for i,m in enumerate(milestones) if not m['claimed']),6)
        add(f'v2-ach-{plugin}-{index}',title,desc.format(levels[index]),n,levels[index],REWARDS[index],'成就',level=index+1,milestones=milestones)
    return result
@router.get('')
def get(u=Depends(user)):
    with connect() as db:return {'tasks':tasks(db,u['id'])}
@router.post('/claim/{task_id:path}')
def claim(task_id:str,u=Depends(user)):
    with connect(True) as db:
        task=next((t for t in tasks(db,u['id']) if t['id']==task_id),None)
        if not task:raise HTTPException(404,'任务不存在或该阶段已领取')
        if task['claimed']:raise HTTPException(409,'奖励已领取')
        if task['progress']<task['target']:raise HTTPException(409,'任务尚未完成')
        for kind,amount in task['reward'].items():credit(db,u['id'],kind,amount,task['title'],'task:'+task_id)
        set_state(db,u['id'],'journal','claim:'+task_id,True)
    return {'message':'奖励已收入账户'}
