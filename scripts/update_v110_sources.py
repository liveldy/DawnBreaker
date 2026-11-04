from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'src/App.tsx';s=p.read_text(encoding='utf-8')
a=s.index('function CollectionPage(){');b=s.index('\ntype Track=',a)
s=s[:a]+'function CollectionPage(){return <Collection {...useApp()}/>;}\n'+s[b:]
if "import Collection from './Collection';" not in s:s=s.replace("import Admin from './Admin';","import Admin from './Admin';\nimport Collection from './Collection';\nimport { WordPronunciation } from './WordPronunciation';\nimport ClientUpdates from './ClientUpdates';")
if "if(plugin.id==='collection')" not in s:s=s.replace('function PluginPage({plugin}:{plugin:Plugin}){',"function PluginPage({plugin}:{plugin:Plugin}){\n if(plugin.id==='collection')return <CollectionPage/>;")
if '<WordPronunciation' not in s:s=s.replace("{mode==='choice'?<div className=\"answer-options\">", "{question.audio&&<WordPronunciation src={question.audio} phonetic={question.phonetic} notify={notify}/>}"+"{mode==='choice'?<div className=\"answer-options\">")
s=s.replace('测试每词每日首次正确可获得 {r.data?.reward ?? 1} 攀登点。','学习与测试进度都会保存到账号。')
s=s.replace("k==='stones'?'破晓石':'攀登点'","'破晓石'")
s=s.replace('支持 YouTube、哔哩哔哩、Vimeo、抖音。','支持 YouTube、哔哩哔哩、Vimeo、抖音的公开免登录视频。哔哩哔哩可能受平台风控限制。')
if '<ClientUpdates/>' not in s:
    s=s.replace('<div className="sidebar-bottom">','<div className="sidebar-bottom"><ClientUpdates/>')
    s=s.replace('<footer><span>破晓 / DawnBreaker</span>','<footer><ClientUpdates/><span>破晓 / DawnBreaker</span>')
p.write_text(s,encoding='utf-8')
p=root/'src/Admin.tsx';s=p.read_text(encoding='utf-8')
s=s.replace("{essence:'日光精华',stones:'破晓石',climb:'攀登点',collection:'收集点'}","{essence:'日光精华',stones:'破晓石'}")
s=s.replace('word_climb_reward:Number(f.get(\'word_climb_reward\')),','')
old='<label>每词每日首次测试正确 / 攀登点<input type="number" name="word_climb_reward" defaultValue={r.data.word_climb_reward} min={0} max={1000000} required/></label>'
s=s.replace(old,'').replace('每抽收集点','每抽日光精华')
p.write_text(s,encoding='utf-8')
p=root/'src/main.tsx';s=p.read_text(encoding='utf-8')
if "import './collection.css';" not in s:s+="\nimport './collection.css';\nimport './client-updates.css';\n"
p.write_text(s,encoding='utf-8')
for name in ['package.json','clients/desktop/package.json']:
    import json
    p=root/name;data=json.loads(p.read_text(encoding='utf-8'));data['version']='1.1.0';p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'android/app/build.gradle';s=p.read_text(encoding='utf-8');s=s.replace('versionCode 1','versionCode 2').replace('versionName "1.0"','versionName "1.1.0"');p.write_text(s,encoding='utf-8')
p=root/'server/main.py';s=p.read_text(encoding='utf-8').replace("version='1.0.0'","version='1.1.0'").replace("'version':'1.0.0'","'version':'1.1.0'")
if 'from .releases import' not in s:s=s.replace('app.include_router(admin_router)','app.include_router(admin_router)\nfrom .releases import router as releases_router\napp.include_router(releases_router)')
p.write_text(s,encoding='utf-8')
