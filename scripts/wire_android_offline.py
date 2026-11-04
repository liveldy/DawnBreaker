import json
from pathlib import Path
R=Path(__file__).resolve().parents[1];java=R/'android/app/src/main/java/app/dawnbreaker/mobile'
p=R/'capacitor.config.json';v=json.loads(p.read_text(encoding='utf-8'));v['server']={'hostname':'localhost','androidScheme':'https'};v['plugins']={'CapacitorHttp':{'enabled':True},'CapacitorCookies':{'enabled':True}};p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
p=java/'DawnClientPlugin.java';s=p.read_text(encoding='utf-8').replace('bridge.getServerUrl().replaceAll("/+$", "")','RemoteOrigin.base(bridge)');p.write_text(s,encoding='utf-8')
p=java/'DawnMediaPlugin.java';s=p.read_text(encoding='utf-8').replace('bridge.getServerUrl().replaceAll("/+$","")','RemoteOrigin.base(bridge)');s=s.replace('MediaStore.refreshQuote(getContext());call.resolve();','MediaStore.refreshQuote(getContext());new PlaybackLedger(getContext()).sync();call.resolve();');p.write_text(s,encoding='utf-8')
p=java/'MainActivity.java';s=p.read_text(encoding='utf-8').replace('registerPlugin(DawnMediaPlugin.class);','registerPlugin(DawnMediaPlugin.class);\n        registerPlugin(DawnOfflinePlugin.class);');s=s.replace('        super.load();','        super.load();\n        if(bridge!=null)bridge.getWebView().setWebViewClient(new OfflineWebViewClient(bridge));');s=s.replace('Uri source = Uri.parse(url);\n            Uri base = Uri.parse(bridge.getServerUrl());','Uri base = Uri.parse(RemoteOrigin.base(bridge));\n            Uri incoming=Uri.parse(url);\n            if("localhost".equals(incoming.getHost())&&incoming.getPath().startsWith("/api/"))url=RemoteOrigin.base(bridge)+incoming.getEncodedPath()+(incoming.getEncodedQuery()!=null?"?"+incoming.getEncodedQuery():"");\n            Uri source = Uri.parse(url);');p.write_text(s,encoding='utf-8')
p=java/'DawnMusicService.java';s=p.read_text(encoding='utf-8');s=s.replace('private boolean wasPlaying=false;','private boolean wasPlaying=false;private double unreported=0;private PlaybackLedger ledger;private double lastPosition=0;')
s=s.replace('instance=this;audio=', 'instance=this;ledger=new PlaybackLedger(this);audio=')
s=s.replace('if(!headers', 'if(!headers')
s=s.replace('   player.setDataSource(this,Uri.parse(', '   File cached=MusicCache.file(this,track().optString("id"));if(cached!=null&&cached.isFile()){player.setDataSource(cached.getAbsolutePath());cached.setLastModified(System.currentTimeMillis());}else{if(!OfflineProxy.connected(this))throw new java.io.IOException("not cached");player.setDataSource(this,Uri.parse(')
old='headers);\n   player.setOnPreparedListener'
assert old in s
s=s.replace(old,'headers);MusicCache.download(this,track().optString("id"));}\n   player.setOnPreparedListener',1)
s=s.replace('import java.util.*;','import java.util.*;\nimport java.io.File;')
start=s.index(' private final Runnable tick=');end=s.index(' @Override public void onDestroy()',start)
s=s[:start]+''' private final Runnable tick=new Runnable(){public void run(){long now=SystemClock.elapsedRealtime();boolean playing=isPlaying();double position=0;try{position=prepared&&player!=null?player.getCurrentPosition()/1000.0:0;}catch(Exception ignored){}if(playing&&wasPlaying&&position>lastPosition){double seconds=Math.min(Math.min((now-lastTick)/1000.0,2),position-lastPosition+.1);played+=seconds;unreported+=seconds;}wasPlaying=playing;lastPosition=position;lastTick=now;if(now-lastReport>=10000){lastReport=now;report();}handler.postDelayed(this,1000);}};
 private void report(){if(ledger==null)return;if(unreported>.1){double value=unreported;unreported=0;ledger.add(track().optString("id"),value,System.currentTimeMillis()/1000.0);}ledger.sync();}
''' + s[end:]
s=s.replace('void pause(){wantsPlaying=false;', 'void pause(){report();wantsPlaying=false;').replace('private void releasePlayer(){prepared=false;', 'private void releasePlayer(){report();lastPosition=0;prepared=false;')
p.write_text(s,encoding='utf-8')
p=R/'android/app/src/main/AndroidManifest.xml';s=p.read_text(encoding='utf-8').replace('    <!-- Permissions -->','    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>\n    <!-- Permissions -->');p.write_text(s,encoding='utf-8')
p=java/'DawnOfflinePlugin.java';s=p.read_text(encoding='utf-8').replace('result.put("music_count",MusicCache.count(getContext()));','result.put("music_count",MusicCache.count(getContext()));result.put("cached_ids",MusicCache.ids(getContext()));result.put("sync_error",OfflineProxy.prefs(getContext()).getString("sync_error",""));');p.write_text(s,encoding='utf-8')
print('Wired bundled Android shell, native GET proxy/cache and durable playback ledger')
