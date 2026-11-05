"""Transactional local storage; failed saves never replace the previous record."""
import base64
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from tools.contract import CLASSES
from .detector import read_image


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_box(box, width, height):
    if (not isinstance(box, list) or len(box) != 4 or not all(map(finite, box))
            or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
        raise ValueError('박스 좌표가 사진 범위를 벗어났습니다.')


def validate_session(s):
    if (not isinstance(s, dict) or s.get('schema_version') != 2
            or s.get('record_type') != 'engine_inspection_session'
            or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', str(s.get('id', '')))):
        raise ValueError('검사 기록 형식이 올바르지 않습니다.')
    for name, limit in [('title', 120), ('note', 4000), ('vehicle_id', 100), ('area', 100),
                        ('capture_mode', 30), ('image', 300), ('created_at', 40), ('updated_at', 40)]:
        if not isinstance(s.get(name, ''), str) or len(s.get(name, '')) > limit:
            raise ValueError('검사 기록의 문자 길이를 확인하세요.')
    w, h = s.get('width'), s.get('height')
    if (not all(map(finite, (w, h, s.get('threshold')))) or not 0 < w <= 20000
            or not 0 < h <= 20000 or w*h > 60_000_000 or not .05 <= s['threshold'] <= .95):
        raise ValueError('사진 크기 또는 임계값이 올바르지 않습니다.')
    for key in ('original', 'reviewed'):
        rows = s.get(key)
        if not isinstance(rows, list) or len(rows) > 500:
            raise ValueError('검사당 최대 500개 박스입니다.')
        seen = set()
        for r in rows:
            if not isinstance(r, dict) or r.get('class') not in CLASSES:
                raise ValueError('지원하지 않는 부품입니다.')
            validate_box(r.get('box'), w, h)
            score = r.get('score')
            if score is not None and (not finite(score) or not 0 <= score <= 1):
                raise ValueError('신뢰도가 올바르지 않습니다.')
            if key == 'reviewed':
                if (not isinstance(r.get('id'), str) or not r['id'] or r['id'] in seen
                        or r.get('origin') not in ('ai', 'manual', 'corrected')
                        or not isinstance(r.get('excluded'), bool)):
                    raise ValueError('수정 박스 정보가 올바르지 않습니다.')
                seen.add(r['id'])
                if r['origin'] != 'ai' and score is not None:
                    raise ValueError('수동 수정에 AI 신뢰도를 부여할 수 없습니다.')
    if s.get('fitment_verified') is not False:
        raise ValueError('품번은 적용 확인 전 후보입니다.')
    return s


def image_data_url(value):
    if not isinstance(value, str) or len(value) > 42 * 1024 * 1024:
        raise ValueError('검사 사진이 필요합니다.')
    match = re.fullmatch(r'data:image/(?:jpeg|png|webp);base64,([A-Za-z0-9+/=\r\n]+)', value)
    if not match:
        raise ValueError('JPG/PNG/WebP 사진만 지원합니다.')
    raw = base64.b64decode(match[1], validate=True)
    return read_image(raw)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS resources (name TEXT PRIMARY KEY, metadata TEXT NOT NULL, bytes BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, updated TEXT NOT NULL, body TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def resource(self, name):
        with self.connect() as db:
            row = db.execute('SELECT metadata,bytes FROM resources WHERE name=?', (name,)).fetchone()
        return (json.loads(row[0]), row[1]) if row else None

    def put_resource(self, name, meta, raw):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO resources VALUES (?,?,?)', (name, json.dumps(meta, allow_nan=False), raw))

    def save(self, session):
        validate_session(session)
        image_data_url(session.get('source_image'))
        display = image_data_url(session.get('display_image'))
        if display.size != (session['width'], session['height']):
            raise ValueError('표시 사진과 검사 좌표의 크기가 다릅니다.')
        body = json.dumps(session, ensure_ascii=False, allow_nan=False)
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)',
                       (session['id'], session['title'], session['updated_at'], body))

    def sessions(self):
        with self.connect() as db:
            return [dict(id=r[0], title=r[1], updated_at=r[2]) for r in
                    db.execute('SELECT id,title,updated FROM sessions ORDER BY updated DESC')]

    def session(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT body FROM sessions WHERE id=?', (identifier,)).fetchone()
        return json.loads(row[0]) if row else None
