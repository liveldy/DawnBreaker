"""One release identity shared by deployment, update manifests and GitHub publication."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
VERSION_CODE=int(re.search(r'versionCode\s+(\d+)',(ROOT/'android/app/build.gradle').read_text(encoding='utf-8'))[1])
NOTES=(ROOT/'release-notes'/f'{VERSION}.md').read_text(encoding='utf-8')
SUMMARY='破晓 1.2.0：开源全部程序；天眼运营商监视与斩杀图、词汇批次与练习历史、播放模式、LinkSwift 网盘下载、Mihomo 折跃门及浮光掠影壁纸。'
