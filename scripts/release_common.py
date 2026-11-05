"""One release identity shared by deployment, update manifests and GitHub publication."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
VERSION_CODE=int(re.search(r'versionCode\s+(\d+)',(ROOT/'android/app/build.gradle').read_text(encoding='utf-8'))[1])
NOTES=(ROOT/'release-notes'/f'{VERSION}.md').read_text(encoding='utf-8')
SUMMARY='破晓 1.3.2：暗格新增加密卡包、个人信息册和自定义字段；Windows / Android 新增系统管理，支持本机信息、内存整理和系统设置。'
