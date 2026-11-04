"""One release identity shared by deployment, update manifests and GitHub publication."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
VERSION_CODE=int(re.search(r'versionCode\s+(\d+)',(ROOT/'android/app/build.gradle').read_text(encoding='utf-8'))[1])
NOTES=(ROOT/'release-notes'/f'{VERSION}.md').read_text(encoding='utf-8')
SUMMARY='破晓 1.3.1：笔耕不辍改为文档前台停留时长并重置成就；新增三国杀·珍藏阁，封面采用乐蔡文姬·姝丽风华；天眼模型名称就近排布，密集处自动隐藏。'
