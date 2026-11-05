"""Local Python API + tablet assets. Run: python -m engine.server"""
import argparse
import base64
import hashlib
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs
from http.cookies import SimpleCookie
import secrets

from .detector import Detector
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 128 * 1024 * 1024


class Runtime:
    def __init__(self, directory, detector_factory=Detector):
        self.store = Store(Path(directory) / 'inspection.sqlite3')
        self.detector_factory = detector_factory
        self.detector = None
        self.lock = threading.Lock()

    def model(self, manifest, raw):
        # Candidate validation precedes BOTH persistence and active-session swap.
        with self.lock:
            candidate = self.detector_factory(manifest, raw)
            try:
                self.store.put_resource('model', manifest, raw)
            except Exception:
                candidate.close()
                raise
            previous = self.detector
            self.detector = candidate
            if previous:
                previous.close()
        return manifest

    def infer(self, raw, expected):
        with self.lock:
            if self.detector is None:
                saved = self.store.resource('model')
                if saved is None:
                    raise ValueError('모델 ZIP을 먼저 가져오세요.')
                self.detector = self.detector_factory(*saved)
            if expected != self.detector.manifest['sha256']:
                raise ValueError('다른 창에서 모델이 변경되었습니다. 모델을 다시 불러오세요.')
            return self.detector.detect(raw)


def handler(runtime, static, token=None):
    static = Path(static).resolve()

    class Handler(BaseHTTPRequestHandler):
        def authorized(self):
            if token is None:
                return True
            cookie = SimpleCookie()
            cookie.load(self.headers.get('Cookie', ''))
            value = cookie.get('inspection_session')
            return value is not None and secrets.compare_digest(value.value, token)

        def log_message(self, format, *args):
            # Bootstrap URL contains an ephemeral capability. Never log it.
            if 'token=' not in self.path:
                super().log_message(format, *args)

        def send(self, status, data, mime='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if token and urlsplit(self.path).path == '/':
                supplied = parse_qs(urlsplit(self.path).query).get('token', [''])[0]
                if secrets.compare_digest(supplied, token):
                    self.send_response(303)
                    self.send_header('Set-Cookie', f'inspection_session={token}; HttpOnly; SameSite=Strict; Path=/')
                    self.send_header('Location', '/')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
            if not self.authorized():
                return self.send(403, {'error': '앱 세션 인증이 필요합니다.'})
            path = unquote(urlsplit(self.path).path)
            if path == '/api/health':
                return self.send(200, {'runtime': 'python', 'version': '0.6.0'})
            if path == '/api/sessions':
                return self.send(200, runtime.store.sessions())
            if path.startswith('/api/sessions/'):
                value = runtime.store.session(path.removeprefix('/api/sessions/'))
                return self.send(200 if value else 404, value or {'error': '검사 기록이 없습니다.'})
            if path.startswith('/api/resources/'):
                parts = path.split('/')
                if len(parts) != 5 or parts[3] not in ('model', 'catalog') or parts[4] not in ('metadata', 'bytes'):
                    return self.send(404, {'error': '자료가 없습니다.'})
                value = runtime.store.resource(parts[3])
                if not value:
                    return self.send(404, {'error': '자료가 없습니다.'})
                return self.send(200, value[0]) if parts[4] == 'metadata' else self.send(200, value[1], 'application/octet-stream')
            target = (static / (path.lstrip('/') or 'index.html')).resolve()
            if not target.is_relative_to(static) or not target.is_file():
                return self.send(404, {'error': '파일이 없습니다. npm run build를 실행했는지 확인하세요.'})
            mime = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.wasm': 'application/wasm'}.get(target.suffix)
            return self.send(200, target.read_bytes(), mime or mimetypes.guess_type(str(target))[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.authorized():
                return self.send(403, {'error': '앱 세션 인증이 필요합니다.'})
            # Same-origin browser mutations only; not an internet-facing service.
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                return self.send(403, {'error': '다른 출처의 요청은 허용하지 않습니다.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_BODY:
                    return self.send(413, {'error': '요청 크기 제한을 초과했습니다.'})
                self.connection.settimeout(60)
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('요청 데이터가 불완전합니다.')
                path = urlsplit(self.path).path
                if path == '/api/model':
                    meta = json.loads(base64.b64decode(self.headers.get('X-Metadata', ''), validate=True))
                    return self.send(200, runtime.model(meta, raw))
                if path == '/api/infer':
                    return self.send(200, runtime.infer(raw, self.headers.get('X-Model-Sha256')))
                if path == '/api/review-bundle':
                    from .review_bundle import import_bundle
                    vehicle = base64.b64decode(self.headers.get('X-Vehicle', ''), validate=True).decode('utf-8')
                    return self.send(200, import_bundle(runtime.store, raw, vehicle))
                if path == '/api/catalog':
                    from .catalog import validate_catalog
                    meta = json.loads(raw)
                    pdf = base64.b64decode(meta['bytes'], validate=True)
                    validate_catalog(meta['index'], pdf)
                    runtime.store.put_resource('catalog', meta['index'], pdf)
                    return self.send(200, {'saved': True})
                if path == '/api/sessions':
                    runtime.store.save(json.loads(raw))
                    return self.send(200, {'saved': True})
                self.send(404, {'error': '지원하지 않는 작업입니다.'})
            except (ValueError, KeyError, TypeError, OSError) as error:
                self.send(400, {'error': str(error)})
            except Exception as error:
                self.log_error('Runtime error: %s', error)
                self.send(503, {'error': 'Python 처리에 실패했습니다. 서버 로그와 모델을 확인하세요.'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/runtime')
    parser.add_argument('--static', type=Path, default=ROOT / 'web/dist')
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), handler(Runtime(args.data), args.static))
    print(f'Python tablet UI: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
