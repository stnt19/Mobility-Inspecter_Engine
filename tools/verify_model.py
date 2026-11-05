"""Numerical parity: python tools/verify_model.py model.onnx input.bin expected.bin"""
import sys
import json
import numpy as np
import onnxruntime as ort
model,source,expected=sys.argv[1:]
session=ort.InferenceSession(model,providers=['CPUExecutionProvider'])
info=session.get_inputs()[0]
values=np.fromfile(source,dtype='<f4').reshape(info.shape)
output=session.run(None,{info.name:values})[0]
target=np.fromfile(expected,dtype='<f4').reshape(output.shape)
if not np.isfinite(output).all():raise ValueError('Non-finite output')
error=float(np.max(np.abs(output-target)))
if error>=.01:raise ValueError(f'Max absolute error {error}')
print(json.dumps(dict(engine='Python ONNX Runtime',output_shape=list(output.shape),max_absolute_error=error,passed=True)))
