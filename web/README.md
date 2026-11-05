# 태블릿 화면

현재 화면은 APK 내부 Python API를 사용합니다. WASM 추론은 제거되었습니다. `npm ci --ignore-scripts && npm run build` 후 저장소 루트에서 `python -m engine.server`로 미리볼 수 있습니다. 정적 파일만 배포하면 추론·저장이 작동하지 않습니다. Android 빌드는 루트 README를 참고하세요.

자료 포함 실행 팩을 사용한다면 압축 해제한 폴더에서 `pip install -r requirements.txt` 후 `python serve.py`를 실행합니다. 모델·카탈로그 ZIP을 APK에 직접 가져오는 방법도 유지됩니다.
