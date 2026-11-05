> 0.5.0 구조의 이력 문서입니다. 현재 0.6.0 Python APK 실행·구조는 [전환 문서](PYTHON_MIGRATION.md)를 참고하세요.

# Offline web implementation verification

## Implemented
- Actual ONNX Runtime Web WASM inference in a module Worker. User photos are not sent to a server.
- RGB/CHW normalization, 640 letterbox, class-name mapping, class-aware NMS, threshold filtering.
- Existing source-grounded catalog extractor and relation rules reused; validated supplied index has 235 rows and 786 PDF pages, with 32 battery candidate rows.
- PDF.js loads bundled/imported PDF, shows source row highlight and diagram pages with options and applicability fields.
- Android local asset origin, ZIP document picker, IndexedDB resource persistence and native JSON export.
- Generated offline pack includes Android-ready model/catalog import ZIPs. Public Git contains no source photos, PDFs or trained weights.

## Checks performed
- 7 JavaScript unit tests: letterbox/inverse transform, class mapping, NMS, model shape and catalog validation/search.
- 20 existing Python tests passed.
- Real model `640543356080be5719b3134cff28ec195b25f09def543bc7d3dc90340abc287a` run with ONNX Runtime Web 1.20.1 WASM on a CPU-preprocessed test image; output `[1,9,8400]`, maximum absolute output difference versus Python ONNX Runtime: `0.000244140625` (< 0.01).
- The actual shipped Worker module was exercised with a Node worker adapter: model SHA check, warmup, inference and decoded detections all completed. This checks module/runtime wiring; it is not an Android/browser end-to-end test.
- GitHub Actions builds web dependencies and runs Android unit tests, lint and APK assembly. Consult the latest commit's run for its final status.

## Remaining verification
- The available browser preview uses an HTTP host that is not a secure context. The app correctly refuses initialization there because Web Crypto and offline service-worker features require a secure context. No browser security settings were changed to work around this limitation.
- End-to-end photo upload, inference, PDF navigation and offline restart on a supported localhost/HTTPS browser or Android tablet remain to be checked.
- Browser Canvas resampling can differ from the Python/OpenCV pipeline; previously reported 9-image model metrics are not claimed to be browser-runtime benchmark results.
- Physical Android camera integration, latency, thermal behavior, memory/storage pressure and long-running use remain unverified. Web mode is photo inference; native CameraX real-time mode remains available separately.

## Reproduce numerical runtime parity

From `web/`, after `npm ci --ignore-scripts`:

```sh
node verify-model.mjs /path/model.onnx /path/input-f32.bin /path/expected-output-f32.bin
```

Input: little-endian contiguous float32 `[1,3,640,640]`; expected: raw float32 output from the same ONNX model and exact input. This intentionally compares identical tensors and does not hide preprocessing differences.

References: [ONNX Runtime Web deployment](https://onnxruntime.ai/docs/tutorials/web/deploy.html), [Android local WebView assets](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content).
