"""Generate test-only ONNX/image fixtures. Never use as a real parts model."""
import json
import sys
import zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'tests')]
from test_python_runtime import model_fixture, photo
folder=root/'.validation/fixtures';folder.mkdir(parents=True,exist_ok=True)
meta,raw=model_fixture()
with zipfile.ZipFile(folder/'model.zip','w') as z:
    z.writestr('manifest.json',json.dumps(meta));z.writestr('model.onnx',raw)
(folder/'photo.png').write_bytes(photo())
(folder/'model.onnx').write_bytes(raw)
(folder/'manifest.json').write_text(json.dumps(meta))
print('Generated test-only fixtures')
