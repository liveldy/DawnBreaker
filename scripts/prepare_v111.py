"""Apply the release identity to native shells and remove fixed-version publishing paths."""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
p=root/'clients/desktop/package.json';data=json.loads(p.read_text(encoding='utf-8'));data['version']=version;p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'android/app/build.gradle';s=p.read_text(encoding='utf-8');s=re.sub(r'versionCode \d+','versionCode 3',s);s=re.sub(r'versionName "[^"]+"','versionName "'+version+'"',s);p.write_text(s,encoding='utf-8')
p=root/'server/main.py';s=p.read_text(encoding='utf-8').replace("'1.1.0'","'"+version+"'");p.write_text(s,encoding='utf-8')
p=root/'scripts/github_publish.py';s=p.read_text(encoding='utf-8')
if 'from release_common import' not in s:
    s=s.replace('import httpx','import httpx\nfrom release_common import VERSION,NOTES')
    s=s.replace("'1.1.0'",'VERSION')
    start=s.index("    body='''");end=s.index('    if response.status_code==404:',start)
    s=s[:start]+'    body=NOTES\n'+s[end:]
p.write_text(s,encoding='utf-8')
p=root/'scripts/publish_clients.py';s=p.read_text(encoding='utf-8')
if 'from release_common import' not in s:
    s=s.replace('import base64,hashlib,json','import base64,hashlib,json\nfrom release_common import VERSION_CODE,SUMMARY')
    s=s.replace("'version_code':2","'version_code':VERSION_CODE")
    s=re.sub(r"'notes':'[^']*'","'notes':SUMMARY",s)
p.write_text(s,encoding='utf-8')
p=root/'website/index.html';s=p.read_text(encoding='utf-8').replace('1.1.0',version);s=s.replace('安装 '+version+' 后，可在客户端内检查后续更新。','旧版 Android 请手动覆盖安装 '+version+'，启用内置更新。');p.write_text(s,encoding='utf-8')
print('Release identity updated to '+version)
