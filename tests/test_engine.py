import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from contract import CLASSES, candidates
from prepare_dataset import convert
from benchmark import decision

class EngineTests(unittest.TestCase):
    def fixture(self, root, change=None):
        rows=[]; images={}
        for i,split in enumerate(('train','val','test')):
            name=f'{split}.jpg'; stream=io.BytesIO()
            Image.new('RGB',(100,80),(i*70,80,120)).save(stream,format='JPEG')
            images[name]=stream.getvalue()
            rows.append(dict(file_name=name,width=100,height=80,split=split,group_id=f'vehicle-{i}',
                             vehicle='rexton_sports',model_year=2023,variant='standard',reviewed=True,
                             objects=[{'class':c,'bbox':[10,8,50,40]} for c in CLASSES]))
        doc={'classes':CLASSES,'images':rows}
        if change: change(doc,images)
        archive=root/'input.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('dataset/annotations.json',json.dumps(doc))
            for name,raw in images.items(): z.writestr('dataset/images/'+name,raw)
        return archive

    def test_conversion(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); report=convert(self.fixture(root),root/'out')
            self.assertEqual(len(report['images']),3)
            line=(root/'out/labels/train/train.txt').read_text().splitlines()[0]
            self.assertEqual(line,'0 0.30000000 0.30000000 0.40000000 0.40000000')

    def rejected(self,change):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with self.assertRaises(ValueError): convert(self.fixture(root,change),root/'out')
            self.assertFalse((root/'out').exists())

    def test_vehicle_leakage(self):
        self.rejected(lambda d,i:d['images'][1].update(group_id='vehicle-0'))
    def test_wrong_variant(self):
        self.rejected(lambda d,i:d['images'][0].update(variant='khan'))
    def test_unreviewed(self):
        self.rejected(lambda d,i:d['images'][0].update(reviewed=False))
    def test_duplicates(self):
        self.rejected(lambda d,i:i.update({'val.jpg':i['train.jpg']}))
    def test_invalid_box(self):
        self.rejected(lambda d,i:d['images'][0]['objects'][0].update(bbox=[0,0,101,80]))
    def test_nan_box(self):
        self.rejected(lambda d,i:d['images'][0]['objects'][0].update(bbox=[0,0,float('nan'),80]))
    def test_missing_class(self):
        self.rejected(lambda d,i:d['images'][0].update(objects=[]))
    def test_traversal(self):
        self.rejected(lambda d,i:d['images'][0].update(file_name='../train.jpg'))
    def test_shapes(self):
        self.assertEqual([candidates(s) for s in (640,960,1280)],[8400,18900,33600])
        with self.assertRaises(ValueError): candidates(641)
    def test_gate(self):
        b={'map50_95':.5,'recall':[.7]*len(CLASSES)}
        c={'map50_95':.55,'recall':[.71]*len(CLASSES)}
        self.assertTrue(decision(b,c,.03)['accuracy_gate_passed'])
        c['recall'][0]=.6
        self.assertFalse(decision(b,c,.03)['accuracy_gate_passed'])
        c['map50_95']=float('nan')
        with self.assertRaises(ValueError): decision(b,c,.03)
    def test_python_and_browser_contract(self):
        path=Path(__file__).resolve().parents[1]/'web/src/core.js'
        import re
        ids=re.findall(r"'([^']+)'",path.read_text(encoding='utf-8').split('export const CLASSES=[')[1].split(']')[0])
        self.assertEqual(ids,CLASSES)
        self.assertFalse(list((Path(__file__).resolve().parents[1]/'android').rglob('*.kt')))
        self.assertFalse(list((Path(__file__).resolve().parents[1]/'android').rglob('*.kts')))

if __name__=='__main__': unittest.main()

