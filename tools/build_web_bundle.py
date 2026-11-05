"""Add user-owned resources to a built offline web app; never commits source data."""
import argparse
import hashlib
import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from catalog_index import build_index


def build(dist, model_zip, catalog, output, samples=(), android_assets=None):
    dist, output = Path(dist).resolve(), Path(output).resolve()
    if not (dist / 'app.js').is_file():
        raise ValueError('Run npm ci and npm run build in web/ first')
    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    if dist == output or dist in output.parents:
        raise ValueError('Output ZIP must be outside web/dist')
    with zipfile.ZipFile(model_zip) as z:
        if len(z.infolist()) != 2 or set(z.namelist()) != {'model.onnx', 'manifest.json'}:
            raise ValueError('Model ZIP needs exactly model.onnx and manifest.json')
        if sum(i.file_size for i in z.infolist()) > 100 * 1024**2:
            raise ValueError('Model package exceeds 100 MiB')
        model, manifest_bytes = z.read('model.onnx'), z.read('manifest.json')
    manifest = json.loads(manifest_bytes)
    if hashlib.sha256(model).hexdigest() != manifest['sha256']:
        raise ValueError('Model SHA-256 mismatch')
    if manifest['input_size'] not in (640,960,1280) or manifest['class_schema'] != 'engine-seed-v2':
        raise ValueError('Unsupported model contract')
    index = build_index(catalog)
    assets_dir = dist / 'local-assets'
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir()
    (assets_dir / 'model.onnx').write_bytes(model)
    (assets_dir / 'manifest.json').write_bytes(manifest_bytes)
    (assets_dir / 'catalog.json').write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
    shutil.copyfile(catalog, assets_dir / 'catalog.pdf')
    assets = {'model': {'metadata': 'local-assets/manifest.json', 'file': 'local-assets/model.onnx'},
              'catalog': {'metadata': 'local-assets/catalog.json', 'file': 'local-assets/catalog.pdf'}, 'samples': []}
    for i, source in enumerate(samples):
        from PIL import Image
        target = assets_dir / f'sample-{i+1}.jpg'
        with Image.open(source) as im:
            im.convert('RGB').save(target, quality=95)
        assets['samples'].append({'name': Path(source).name, 'url': f'local-assets/{target.name}'})
    (dist / 'assets.json').write_text(json.dumps(assets, ensure_ascii=False), encoding='utf-8')
    files = sorted(p for p in dist.rglob('*') if p.is_file() and p.name not in {'cache-files.json', 'sw.js'})
    digest = hashlib.sha256()
    for p in files:
        digest.update(p.relative_to(dist).as_posix().encode()); digest.update(p.read_bytes())
    sw = dist / 'sw.js'
    sw.write_text(re.sub(r"const CACHE='[^']+'", f"const CACHE='mobility-engine-web-{digest.hexdigest()[:16]}'", sw.read_text()), encoding='utf-8')
    (dist / 'cache-files.json').write_text(json.dumps([p.relative_to(dist).as_posix() for p in files] + ['sw.js']), encoding='utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as z:
        for p in dist.rglob('*'):
            if p.is_file(): z.write(p, 'web/' + p.relative_to(dist).as_posix())
        z.write(Path(__file__).parent.parent / 'web' / 'serve.py', 'serve.py')
        root=Path(__file__).resolve().parents[1]
        for module in (root/'engine').glob('*.py'):
            z.write(module,'engine/'+module.name)
        for name in ('__init__.py','contract.py'):
            z.write(root/'tools'/name,'tools/'+name)
        z.write(root/'requirements.txt','requirements.txt')
        z.write(Path(__file__).parent.parent / 'web' / 'README.md', 'README.md')
        z.write(model_zip, 'android-imports/model.zip')
        catalog_zip = io.BytesIO()
        with zipfile.ZipFile(catalog_zip, 'w', zipfile.ZIP_DEFLATED) as pack:
            pack.write(assets_dir / 'catalog.json', 'catalog.json')
            pack.write(assets_dir / 'catalog.pdf', 'catalog.pdf')
        z.writestr('android-imports/catalog.zip', catalog_zip.getvalue())
    if android_assets:
        target = Path(android_assets).resolve()
        if target.name != 'web' or target.parent.name != 'assets':
            raise ValueError('Android target must end with assets/web')
        if target.exists(): shutil.rmtree(target)
        shutil.copytree(dist, target)
    return {'catalog_rows': len(index['rows']), 'catalog_pages': index['page_count'],
            'model_sha256': manifest['sha256'], 'zip': str(output), 'bytes': output.stat().st_size}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dist', default='web/dist'); p.add_argument('--model-zip', required=True)
    p.add_argument('--catalog', required=True); p.add_argument('--output', required=True)
    p.add_argument('--sample', action='append', default=[]); p.add_argument('--android-assets')
    a = p.parse_args()
    print(json.dumps(build(a.dist, a.model_zip, a.catalog, a.output, a.sample, a.android_assets), ensure_ascii=False, indent=2))
