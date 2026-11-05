"""One release identity shared by deployment, update manifests and GitHub publication."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
VERSION_CODE=int(re.search(r'versionCode\s+(\d+)',(ROOT/'android/app/build.gradle').read_text(encoding='utf-8'))[1])
NOTES=(ROOT/'release-notes'/f'{VERSION}.md').read_text(encoding='utf-8')
SUMMARY='破晓 1.4.1：拾光者改为自然分句与对话内多模态工具，新增多引擎搜索、网页精读、情感查看、语音气泡及折叠文本、图片下载。'
