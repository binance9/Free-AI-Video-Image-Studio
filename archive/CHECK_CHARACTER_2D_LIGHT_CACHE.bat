@echo off
setlocal
cd /d "%~dp0"
C:\Python314\python.exe -c "from pathlib import Path; import json; p=Path(r'data\models\image'); files=list(p.rglob('*dreamshaper*')); print(json.dumps({'cache_root': str(p.resolve()), 'dreamshaper_matches': len(files), 'sample': [str(x) for x in files[:10]]}, ensure_ascii=False, indent=2))"
pause
