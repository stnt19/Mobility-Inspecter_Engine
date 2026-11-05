import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import numpy as np
from PIL import Image

from engine.detector import Detector, Letterbox, decode, nms, validate_manifest
from engine.store import Store, validate_session
from engine.server import Runtime, handler
from engine.review_bundle import import_bundle
from tools.contract import CLASSES
from tools.contract import TASK, CLASS_SCHEMA, candidates


def model_fixture(size=640):
    # Real executable ONNX fixture, not evidence of real-world recognition accuracy.
    import onnx
    from onnx import helper, TensorProto, numpy_helper
    rows = np.zeros((1, 6, candidates(size)), dtype=np.float32)
    rows[0, :, 0] = [size/2, size/2, size/2, size/2, .9, .1]
    rows[0, :, 1] = [size/2, size/2, size/2, size/2, .8, .1]
    rows[0, :, 2] = [size/2, size/2, size/2, size/2, .1, .85]
    node = helper.make_node('Constant', [], ['output'], value=numpy_helper.from_array(rows))
    graph = helper.make_graph([node], 'test-only',
        [helper.make_tensor_value_info('image', TensorProto.FLOAT, [1,3,size,size])],
        [helper.make_tensor_value_info('output', TensorProto.FLOAT, list(rows.shape))])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    model.ir_version = 8
    raw = model.SerializeToString()
    return dict(schema_version=1, architecture='yolo11', task=TASK, class_schema=CLASS_SCHEMA,
                input_size=size, classes=['battery','fuse_box'], sha256=hashlib.sha256(raw).hexdigest()), raw


def photo():
    buffer=io.BytesIO();Image.new('RGB',(100,80),(10,100,180)).save(buffer,format='PNG');return buffer.getvalue()


def session_fixture():
    image='data:image/png;base64,'+base64.b64encode(photo()).decode()
    return dict(schema_version=2, record_type='engine_inspection_session', id='test-session',
                title='점검', note='현장 메모', vehicle_id='TEST-01', area='엔진룸', capture_mode='부품 촬영',
                width=100,height=80,threshold=.35, original=[], reviewed=[],
                fitment_verified=False, source_image=image, display_image=image,
                created_at='2026-11-05T10:00:00Z',updated_at='2026-11-05T10:00:00Z')


class DetectorTests(unittest.TestCase):
    def test_real_onnx_inference_class_mapping_and_nms(self):
        manifest, raw = model_fixture()
        result = Detector(manifest,raw).detect(photo())
        self.assertEqual([r['class'] for r in result['detections']], ['battery','fuse_box'])
        np.testing.assert_allclose(result['detections'][0]['box'], [25,15,75,65])
        self.assertEqual((result['width'],result['height']), (100,80))

    def test_supported_input_sizes(self):
        for size in (640,960,1280):
            meta, raw=model_fixture(size)
            self.assertEqual(len(Detector(meta,raw).detect(photo())['detections']),2)

    def test_hash_mismatch(self):
        meta, raw=model_fixture()
        with self.assertRaisesRegex(ValueError,'SHA-256'):Detector(meta,raw+b'x')

    def test_tensor_shape_mismatch(self):
        meta,raw=model_fixture();meta['classes']=['battery']
        with self.assertRaisesRegex(ValueError,'텐서'):Detector(meta,raw)

    def test_invalid_manifest(self):
        meta,_=model_fixture()
        for changes in ({'classes':['car']},{'classes':['battery','battery']},{'input_size':320},{'architecture':'ssd'}):
            with self.assertRaises(ValueError):validate_manifest(meta|changes)

    def test_portrait_and_rounded_geometry(self):
        g=Letterbox(333,1000,640)
        self.assertEqual(g.resized,(213,640))
        self.assertEqual(g.padding,(213,0))
        np.testing.assert_allclose(g.restore(319.5,320,213,640),[0,0,333,1000])

    def test_invalid_outputs(self):
        rows=np.zeros((1,5,8400),dtype=np.float32)
        rows[0,:,0]=[320,320,10,10,float('nan')]
        rows[0,:,1]=[320,320,-10,10,.9]
        rows[0,:,2]=[320,320,10,10,1.1]
        self.assertEqual(decode(rows,['battery'],Letterbox(640,640,640)),[])
        with self.assertRaises(ValueError):decode(rows,['battery'],Letterbox(640,640,640),float('nan'))

    def test_exif_rotation_and_rgb_preprocessing(self):
        from engine.detector import read_image
        im=Image.new('RGB',(100,80),(10,100,180));exif=im.getexif();exif[274]=6
        buffer=io.BytesIO();im.save(buffer,format='JPEG',exif=exif)
        self.assertEqual(read_image(buffer.getvalue()).size,(80,100))
        meta,raw=model_fixture();detector=Detector(meta,raw)
        actual=[];real=detector.session
        class Spy:
            def run(self,names,feeds):
                actual.append(feeds['image'].copy());return real.run(names,feeds)
        detector.session=Spy();detector.detect(photo())
        self.assertEqual(actual[0].shape,(1,3,640,640))
        np.testing.assert_allclose(actual[0][0,:,0,0],[114/255]*3,rtol=1e-6)
        np.testing.assert_allclose(actual[0][0,:,320,320],[10/255,100/255,180/255],rtol=1e-6)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'data.sqlite3')
        self.s=session_fixture();self.s['original']=[]

    def test_persistent_roundtrip(self):
        self.s['reviewed']=[{'id':'manual-1','class':'battery','box':[1,2,50,60],'origin':'manual','score':None,'excluded':False,'candidate':None}]
        self.store.save(self.s)
        second=Store(self.store.path)
        self.assertEqual(second.session(self.s['id']),self.s)
        self.assertEqual(second.sessions()[0]['title'],'점검')

    def test_invalid_save_preserves_existing(self):
        self.store.save(self.s)
        bad=copy.deepcopy(self.s);bad['note']='덮어쓰면 안 됨';bad['display_image']='data:image/png;base64,AAAA'
        with self.assertRaises((ValueError,OSError)):self.store.save(bad)
        self.assertEqual(self.store.session(self.s['id'])['note'],'현장 메모')

    def test_geometry_and_manual_confidence(self):
        row={'id':'x','class':'battery','box':[0,0,50,60],'origin':'manual','excluded':False,'score':.99}
        self.s['reviewed']=[row]
        with self.assertRaises(ValueError):validate_session(self.s)
        row['score']=None;row['box']=[0,0,101,60]
        with self.assertRaises(ValueError):validate_session(self.s)

    def test_original_and_corrected_separate(self):
        self.s['original']=[{'class':'battery','box':[0,0,50,60],'score':.9}]
        self.s['reviewed']=[{'id':'ai-0','class':'fuse_box','box':[1,1,55,65],'score':None,'origin':'corrected','excluded':False}]
        self.store.save(self.s)
        result=self.store.session(self.s['id'])
        self.assertEqual(result['original'][0]['class'],'battery')
        self.assertEqual(result['reviewed'][0]['class'],'fuse_box')


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.runtime=Runtime(self.temp.name)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),handler(self.runtime,self.temp.name,'test-token'))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.base=f'http://127.0.0.1:{self.http.server_port}'

    def stop(self):
        self.http.shutdown();self.http.server_close();self.thread.join()

    def request(self,path,data=None,headers=None):
        return urlopen(Request(self.base+path,data,headers={'Cookie':'inspection_session=test-token',**(headers or {})}),timeout=10)

    def test_unauthenticated_android_request_blocked(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.base+'/api/health')
        self.assertEqual(e.exception.code,403)

    def test_model_import_infer_and_invalid_replacement(self):
        meta,raw=model_fixture()
        headers={'X-Metadata':base64.b64encode(json.dumps(meta).encode()).decode()}
        self.assertEqual(self.request('/api/model',raw,headers).status,200)
        result=json.load(self.request('/api/infer',photo(),{'X-Model-Sha256':meta['sha256']}))
        self.assertEqual(len(result['detections']),2)
        with self.assertRaises(HTTPError):self.request('/api/model',b'broken',headers)
        self.assertEqual(self.runtime.store.resource('model')[1],raw)
        self.assertEqual(len(self.runtime.infer(photo(),meta['sha256'])['detections']),2)

    def test_stale_model_and_cross_origin_rejected(self):
        meta,raw=model_fixture();self.runtime.model(meta,raw)
        with self.assertRaises(HTTPError) as e:self.request('/api/infer',photo(),{'X-Model-Sha256':'bad'})
        self.assertEqual(e.exception.code,400)
        with self.assertRaises(HTTPError) as e:self.request('/api/sessions',b'{}',{'Origin':'https://unrelated.example'})
        self.assertEqual(e.exception.code,403)

    def test_save_reopen_and_traversal(self):
        s=session_fixture();s['original']=[]
        self.request('/api/sessions',json.dumps(s).encode())
        self.assertEqual(json.load(self.request('/api/sessions/test-session'))['vehicle_id'],'TEST-01')
        with self.assertRaises(HTTPError) as e:self.request('/../data.sqlite3')
        self.assertEqual(e.exception.code,404)


class ReviewBundleTests(unittest.TestCase):
    setUp = StorageTests.setUp

    def bundle(self, change=None):
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=100,height=100)
        output=io.BytesIO();writer.write(output);pdf=output.getvalue();digest=hashlib.sha256(pdf).hexdigest()
        index=dict(schema_version=1,page_count=1,source_sha256=digest,rows=[dict(id='r',part_number='P1',
            name_ko='배터리',pdf_page=1,page_width=100,page_height=100,row_rect=[0,0,50,50],
            diagram_pages=[1],relations={'battery':'primary'})])
        image=io.BytesIO();Image.new('RGB',(100,80)).save(image,format='JPEG');raw=image.getvalue()
        doc=dict(schema_version=1,class_schema=CLASS_SCHEMA,classes=CLASSES,annotation_kind='reviewed_boxes',
            catalog_sha256=digest,images=[dict(file_name='review.jpg',width=100,height=80,
                file_sha256=hashlib.sha256(raw).hexdigest(),objects=[{'class':'battery','bbox':[0,0,50,50]}])])
        if change:change(doc,index)
        result=io.BytesIO()
        with zipfile.ZipFile(result,'w') as z:
            z.writestr('inspection.json',json.dumps(doc));z.writestr('catalog.json',json.dumps(index))
            z.writestr('catalog.pdf',pdf);z.writestr('images/review.jpg',raw)
        return result.getvalue()

    def test_manual_review_import_and_reimport_preserves_edits(self):
        raw=self.bundle();result=import_bundle(self.store,raw,'TEST-01');identifier=result['ids'][0]
        saved=self.store.session(identifier)
        self.assertEqual(saved['original'],[]);self.assertIsNone(saved['reviewed'][0]['score'])
        saved['note']='사용자 수정';self.store.save(saved)
        import_bundle(self.store,raw,'TEST-01')
        self.assertEqual(self.store.session(identifier)['note'],'사용자 수정')

    def test_invalid_bundle_has_no_partial_import(self):
        for change in (lambda d,c:d['images'][0].update(file_sha256='0'*64),
                       lambda d,c:d['images'][0]['objects'][0].update(bbox=[0,0,101,50]),
                       lambda d,c:c['rows'][0].update(pdf_page=2)):
            with self.assertRaises(ValueError):import_bundle(self.store,self.bundle(change),'TEST-01')
            self.assertEqual(self.store.sessions(),[])
            self.assertIsNone(self.store.resource('catalog'))


if __name__=='__main__':unittest.main()
