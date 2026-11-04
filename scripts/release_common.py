"""One release identity shared by deployment, update manifests and GitHub publication."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
VERSION_CODE=int(re.search(r'versionCode\s+(\d+)',(ROOT/'android/app/build.gradle').read_text(encoding='utf-8'))[1])
NOTES=(ROOT/'release-notes'/f'{VERSION}.md').read_text(encoding='utf-8')
SUMMARY='破晓 1.3.0：修复折跃门首次连接、交互式多屏网页壁纸与网盘直链下载；星丛可见操作与文档/记忆保存；新增语录历史、每日记录、节假日及流萤集空间与图片管理。'
