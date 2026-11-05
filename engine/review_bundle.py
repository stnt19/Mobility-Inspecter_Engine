"""Import legacy reviewed-photo ZIPs without confusing labels with AI output."""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import re
import zipfile
from tools.contract import CLASSES, CLASS_SCHEMA
from .catalog import validate_catalog
from .detector import read_image
from .store import validate_session, validate_box


def import_bundle(store, raw, vehicle_id):
    if not isinstance(vehicle_id, str) or not vehicle_id.strip() or len(vehicle_id) > 100:
        raise ValueError('검수 사진을 연결할 장비번호를 먼저 입력하세요.')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=z.infolist()
        names=[e.filename for e in entries]
        if (len(names) != len(set(names)) or len(names) > 6003
                or sum(e.file_size for e in entries) > 128*1024*1024
                or any(e.is_dir() or (e.filename not in ('inspection.json','catalog.json','catalog.pdf')
                    and not re.fullmatch(r'images/[A-Za-z0-9_-]+\.jpg', e.filename)) for e in entries)):
            raise ValueError('검수 팩 ZIP 경로 또는 크기가 올바르지 않습니다.')
        doc=json.loads(z.read('inspection.json'));catalog=json.loads(z.read('catalog.json'));pdf=z.read('catalog.pdf')
        validate_catalog(catalog,pdf)
        rows=doc.get('images')
        if (doc.get('schema_version') != 1 or doc.get('class_schema') != CLASS_SCHEMA
                or doc.get('classes') != CLASSES or doc.get('annotation_kind') != 'reviewed_boxes'
                or doc.get('catalog_sha256') != catalog['source_sha256']
                or not isinstance(rows,list) or not 1 <= len(rows) <= 5000):
            raise ValueError('검수 팩의 클래스/출처 계약이 올바르지 않습니다.')
        expected={'inspection.json','catalog.json','catalog.pdf'}
        sessions=[];seen=set();digest=hashlib.sha256(raw).hexdigest();now=datetime.now(timezone.utc).isoformat()
        for row in rows:
            name=row['file_name']
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.jpg',name) or name.casefold() in seen:
                raise ValueError('검수 사진 이름이 올바르지 않습니다.')
            seen.add(name.casefold());path='images/'+name;expected.add(path);image=z.read(path)
            if hashlib.sha256(image).hexdigest() != row.get('file_sha256'):
                raise ValueError('검수 사진 체크섬 불일치')
            decoded=read_image(image);w,h=decoded.size
            if [w,h] != [row.get('width'),row.get('height')] or max(w,h)>1280:
                raise ValueError('검수 사진 크기 불일치')
            reviewed=[]
            for i,obj in enumerate(row['objects']):
                validate_box(obj['bbox'],w,h)
                reviewed.append({'id':f'review-{i}','class':obj['class'],'box':obj['bbox'],
                                 'score':None,'origin':'manual','excluded':False,'candidate':None})
            data='data:image/jpeg;base64,'+base64.b64encode(image).decode()
            identifier=hashlib.sha256((digest+'|'+vehicle_id+'|'+name).encode()).hexdigest()
            session=dict(schema_version=2,record_type='engine_inspection_session',id='review-'+identifier,
                title=name,note='검수 팩에 등록된 수동 라벨입니다. AI 탐지 결과가 아닙니다.',
                created_at=now,updated_at=now,app_version='0.6.0',mode='reviewed_photo_bundle',
                vehicle_id=vehicle_id.strip(),area='엔진룸',capture_mode='부품 촬영',image=name,width=w,height=h,
                threshold=.35,nms_iou=.45,model=None,catalog_sha256=catalog['source_sha256'],
                original=[],reviewed=reviewed,fitment_verified=False,source_image=data,display_image=data,
                review_source={'bundle_sha256':digest,'file_sha256':row['file_sha256']})
            validate_session(session);sessions.append(session)
        if set(names) != expected:
            raise ValueError('검수 사진 목록과 ZIP 내용이 다릅니다.')
    # Commit all photos and catalog together only after every entry passes validation.
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO resources VALUES (?,?,?)',('catalog',json.dumps(catalog),pdf))
        for s in sessions:
            # Reimporting the same pack must not erase the user's edits.
            db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?,?,?)',
                       (s['id'],s['title'],s['updated_at'],json.dumps(s,ensure_ascii=False,allow_nan=False)))
    return {'count':len(sessions),'ids':[s['id'] for s in sessions]}
