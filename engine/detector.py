"""Model contract, letterboxing and class-aware NMS ported from Android.

All inference happens in Python. The browser only sends an image and renders
pixel-coordinate results. No downloaded model is treated as a diagnosis.
"""
import hashlib
import io
import math
import re
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps
from tools.contract import CLASSES, SIZES, TASK, CLASS_SCHEMA, candidates


def validate_manifest(m):
    if not isinstance(m, dict):
        raise ValueError('모델 manifest가 필요합니다.')
    names = m.get('classes')
    if (m.get('schema_version') != 1 or m.get('task') != TASK
            or m.get('architecture') not in ('yolov8', 'yolo11')
            or m.get('input_size') not in SIZES
            or m.get('class_schema') != CLASS_SCHEMA
            or not isinstance(names, list) or not names
            or any(not isinstance(c, str) or c not in CLASSES for c in names)
            or len(set(names)) != len(names)
            or not re.fullmatch('[a-fA-F0-9]{64}', str(m.get('sha256', '')))):
        raise ValueError('지원하지 않는 엔진룸 모델 manifest입니다.')
    return m


@dataclass(frozen=True)
class Letterbox:
    width: int
    height: int
    size: int

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or self.size not in SIZES:
            raise ValueError('이미지/입력 크기가 올바르지 않습니다.')

    @property
    def resized(self):
        scale = min(self.size / self.width, self.size / self.height)
        return (max(1, math.floor(self.width * scale + .5)),
                max(1, math.floor(self.height * scale + .5)))

    @property
    def padding(self):
        w, h = self.resized
        return (self.size - w) // 2, (self.size - h) // 2

    def restore(self, cx, cy, w, h):
        rw, rh = self.resized
        left, top = self.padding
        return [max(0, min(self.width, (cx - w/2 - left) * self.width/rw)),
                max(0, min(self.height, (cy - h/2 - top) * self.height/rh)),
                max(0, min(self.width, (cx + w/2 - left) * self.width/rw)),
                max(0, min(self.height, (cy + h/2 - top) * self.height/rh))]


def iou(a, b):
    overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    return overlap / union if union > 0 else 0


def nms(rows, threshold=.45, limit=50):
    result = []
    for row in sorted(rows, key=lambda r: r['score'], reverse=True)[:3000]:
        if not any(r['class'] == row['class'] and iou(r['box'], row['box']) > threshold for r in result):
            result.append(row)
            if len(result) == limit:
                break
    return result


def decode(output, classes, geometry, threshold=.05):
    if not math.isfinite(threshold) or not .05 <= threshold <= .95:
        raise ValueError('임계값은 0.05~0.95이어야 합니다.')
    if output.shape != (1, 4+len(classes), candidates(geometry.size)):
        raise ValueError('모델 출력 형식이 계약과 다릅니다.')
    rows = output[0]
    scores = rows[4:].max(axis=0)
    indices = rows[4:].argmax(axis=0)
    valid = np.flatnonzero(np.isfinite(scores) & (scores >= threshold) & (scores <= 1))
    found = []
    for i in valid:
        cx, cy, w, h = map(float, rows[:4, i])
        if not all(map(math.isfinite, (cx, cy, w, h))) or w <= 0 or h <= 0:
            continue
        box = geometry.restore(cx, cy, w, h)
        if box[2] > box[0] and box[3] > box[1]:
            found.append({'class': classes[int(indices[i])], 'score': float(scores[i]), 'box': box})
    return nms(found)


def read_image(raw):
    if len(raw) > 30 * 1024 * 1024:
        raise ValueError('사진은 30MB 이하이어야 합니다.')
    image = Image.open(io.BytesIO(raw))
    if image.width * image.height > 60_000_000:
        raise ValueError('사진은 6천만 화소 이하이어야 합니다.')
    return ImageOps.exif_transpose(image).convert('RGB')


class Detector:
    def __init__(self, manifest, raw, session_factory=None):
        self.manifest = validate_manifest(manifest)
        if hashlib.sha256(raw).hexdigest() != manifest['sha256'].lower():
            raise ValueError('모델 SHA-256 불일치')
        if session_factory is None:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            session_factory = lambda b: ort.InferenceSession(b, sess_options=options, providers=['CPUExecutionProvider'])
        self.session = session_factory(raw)
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        size = manifest['input_size']
        if (len(inputs) != 1 or len(outputs) != 1 or inputs[0].type != 'tensor(float)'
                or outputs[0].type != 'tensor(float)' or inputs[0].shape != [1, 3, size, size]
                or outputs[0].shape != [1, 4+len(manifest['classes']), candidates(size)]):
            self.close()
            raise ValueError('모델 입력/출력 텐서 형식 불일치')
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name

    def close(self):
        if hasattr(self.session, 'close'):
            self.session.close()

    def detect(self, raw, threshold=.05):
        started = time.perf_counter()
        image = read_image(raw)
        geometry = Letterbox(image.width, image.height, self.manifest['input_size'])
        padded = Image.new('RGB', (geometry.size, geometry.size), (114, 114, 114))
        padded.paste(image.resize(geometry.resized, Image.Resampling.BILINEAR), geometry.padding)
        tensor = np.asarray(padded, dtype=np.float32).transpose(2, 0, 1)[None] / 255
        output = self.session.run([self.output_name], {self.input_name: tensor})[0]
        return {'detections': decode(output, self.manifest['classes'], geometry, threshold),
                'width': image.width, 'height': image.height,
                'model_sha256': self.manifest['sha256'], 'elapsed_ms': (time.perf_counter()-started)*1000}
