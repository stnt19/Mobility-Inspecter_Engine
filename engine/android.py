"""Android bootstrap and ONNX JNI adapter. Application logic stays in Python."""
import json
import secrets
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import numpy as np
from .detector import Detector
from .server import Runtime, handler

_server = None


class AndroidSession:
    def __init__(self, raw):
        from java import jclass
        self.bridge = jclass('com.mobility.engine.OrtBridge')(raw)
        meta = json.loads(str(self.bridge.metadata()))
        self.inputs = [SimpleNamespace(**m) for m in meta['inputs']]
        self.outputs = [SimpleNamespace(**m) for m in meta['outputs']]

    def get_inputs(self):
        return self.inputs

    def get_outputs(self):
        return self.outputs

    def run(self, names, feeds):
        array = feeds[self.inputs[0].name]
        raw = bytes(self.bridge.run(array.astype('<f4').tobytes()))
        return [np.frombuffer(raw, dtype='<f4').reshape(self.outputs[0].shape)]

    def close(self):
        self.bridge.close()


def start(data_dir, web_dir):
    global _server
    if _server is None:
        runtime = Runtime(data_dir, lambda meta, raw: Detector(meta, raw, AndroidSession))
        token = secrets.token_urlsafe(32)
        _server = ThreadingHTTPServer(('127.0.0.1', 0), handler(runtime, web_dir, token))
        _server.token = token
        threading.Thread(target=_server.serve_forever, daemon=True, name='inspection-python').start()
    return f'http://127.0.0.1:{_server.server_port}/?token={_server.token}'
