"""Copy the built tablet assets into the APK without copying private data."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
source=root/'web/dist'
if not (source/'index.html').is_file():
    raise SystemExit('Run npm run build in web first')
shutil.copytree(source,root/'android/app/src/main/assets/web',dirs_exist_ok=True)
print('Staged tablet assets')
