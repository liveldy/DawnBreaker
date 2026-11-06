"""Shared, model-specific sticker art; messages reference it without duplicating user uploads."""
from pathlib import Path
import hashlib
from functools import lru_cache
from fastapi import HTTPException

ROOT=Path(__file__).parent/'content/emotion'
PACKS={
 'deepseek':[
  ('热情招呼','张开双手、笑着欢迎，适合打招呼或兴奋地分享'),
  ('托腮得意','双手托腮、自信微笑，适合嘴硬地关心或小小得意'),
  ('灵感思考','托着下巴思考，有灯泡和分析图，适合理清思路或想到办法'),
  ('疑惑歪头','歪头问号，适合没听懂、好奇或想进一步了解'),
  ('认真工作','专注敲代码，适合认真帮忙、处理问题或进入工作状态'),
  ('害羞局促','微微脸红、攥着手，适合被夸、害羞或嘴硬后的心软'),
  ('开饭啦','端着满满一碗饭开心吃，适合聊吃的、嘴馋或开饭'),
  ('困困摸鱼','对着电脑疲惫叹气，适合困倦、加班或想摸鱼'),
  ('开心完成','笑着举拳，有完成勾选标志，适合完成事情、加油或庆祝')],
 'grok':[
  ('兴奋招呼','笑着握拳，适合打招呼、兴奋或跃跃欲试'),
  ('坏笑调侃','托腮露出狡黠笑容，适合善意调侃、得意或开玩笑'),
  ('好奇思考','托着下巴思考，有灯泡，适合好奇、拆解问题或有了主意'),
  ('疑惑歪头','歪头问号，适合疑惑、不理解或想问清楚'),
  ('玩笑炸毛','笑着张牙舞爪、红色怒号，适合夸张玩笑或假装炸毛'),
  ('气鼓鼓','交叉双手、鼓着脸，适合不服、嘴硬或轻微不满'),
  ('笑着分享','眯眼大笑、举着电脑，适合分享有趣内容或吐槽笑场'),
  ('认真开工','专注敲代码、分析界面，适合认真帮忙或开始解决问题'),
  ('开心庆祝','笑着举拳，有闪亮星星，适合庆祝、成功或鼓励')]
}

def path(provider,id):
    if provider not in PACKS or id not in {f'{i:02}' for i in range(1,10)}:raise HTTPException(404,'表情包不存在')
    file=ROOT/provider/(id+'.png')
    if not file.is_file():raise HTTPException(404,'当前部署尚未安装此表情包')
    return file

def catalog(provider):
    if provider not in PACKS:return []
    return [{'id':f'{i:02}','name':name,'description':description} for i,(name,description) in enumerate(PACKS[provider],1) if (ROOT/provider/(f'{i:02}.png')).is_file()]

def public(provider,companion_id,id):
    file=path(provider,id);name=PACKS[provider][int(id)-1][0]
    # The short digest invalidates browser caches if the supplied art is replaced.
    stat=file.stat();revision=_revision(file,stat.st_mtime_ns,stat.st_size)
    return {'id':id,'name':name,'url':f'/api/plugins/companion/{companion_id}/stickers/{id}?v={revision}'}

@lru_cache(maxsize=64)
def _revision(file,mtime,size):return hashlib.sha256(file.read_bytes()).hexdigest()[:12]
