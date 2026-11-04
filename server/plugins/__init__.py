"""Trusted server plugins. Each module exposes MANIFEST and router.

Plugins are registered on the server; installation is per-account entitlement,
never downloading executable code onto the client.
"""
from . import checkin, quotes, vocabulary, collection, music, journal, downloader,library,constellation,vault,atlas,warp,wallpaper
MODULES = [journal, checkin, quotes, collection, music, vocabulary, downloader,library,constellation,vault,atlas,warp,wallpaper]
CONTENT = [
    {'id':'sgs','name':'三国杀·珍藏阁','type':'content','parent':'collection','description':'武将经典、界限突破与同名皮肤卡册。收录姓名、故事与完整原画。','category':'收藏内容','version':'1.0.0','icon':'Layers','note':'资料与图像来源：哔哩哔哩游戏三国杀 BWIKI。美术版权归原权利方。'},
    {'id':'lol-quotes','name':'英雄联盟·流光笺','type':'content','parent':'quotes','description':'59 句英雄语录，配有原声朗读。','category':'金句内容','version':'1.0.0','icon':'Quote','note':'用户提供的英雄联盟语音内容。'},
    {'id':'lol','name':'英雄联盟·珍藏阁','type':'content','parent':'collection','description':'英雄与皮肤主题卡池，配有完整集卡册。','category':'收藏内容','version':'1.0.0','icon':'Layers','note':'使用用户提供的英雄图像资源。英雄与图像版权归 Riot Games。'},
    {'id':'ancient','name':'古风歌曲·弦音余韵','type':'content','parent':'music','description':'22 首古风歌曲与同步歌词，给日常配一段旋律。','category':'音乐内容','version':'1.0.0','icon':'Music2','note':'使用用户提供的 MP3 与 LRC 资源，音频保存在服务端。'},
    {'id':'kaoyan','name':'考研词汇·飞跃','type':'content','parent':'vocabulary','description':'考研英语大纲词汇，附音标与中文释义。','category':'学习内容','version':'1.0.0','icon':'BookOpen','note':'从用户提供的 XLS 原表转换，保留词汇、音标、释义与原表行号。'}
]
CATALOG = [m.MANIFEST | {'type':'standard','version':'1.0.0'} for m in MODULES] + CONTENT
BY_ID = {p['id']:p for p in CATALOG}

def catalog(db, uid):
    installed = {r[0] for r in db.execute('SELECT plugin_id FROM installed WHERE user_id=?',(uid,))}
    return [p | {'installed':p['id'] in installed, 'requires':[p['parent']] if p.get('parent') else []} for p in CATALOG]

