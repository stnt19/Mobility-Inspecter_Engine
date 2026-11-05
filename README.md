# Mobility Inspecter · Python Android

2023년형 렉스턴 스포츠 엔진룸 부품을 탐지하고 사진·수정 박스·품번 후보·카탈로그 원문을 함께 기록하는 **Android 설치형 앱**입니다.

0.6.0은 Kotlin 소스와 Kotlin Gradle 설정을 제거하고 Python으로 실행 로직을 옮깁니다. Python은 APK 내부에서 실행됩니다. PC나 외부 서버 없이 사용할 수 있습니다. Android 권한·파일 선택·내보내기는 Java, 화면은 로컬 HTML/CSS/JavaScript, ONNX 계산은 Android JNI를 사용합니다.

## 앱 흐름

첨부된 `military-maintenance-0.3.0-tablet-ver1.apk`의 비전 점검 화면을 기준으로 **촬영 방식 → 대상 지정 → 실시간 촬영 → 결과 확인 → 세션 기록** 흐름과 밝은 패널·초록 강조색을 적용했습니다. 첨부 앱 전체의 차량 관리·정비 계획 기능을 이 저장소에 복제하는 작업은 아닙니다. 이 저장소의 엔진룸 탐지 기능을 해당 비전 점검 흐름에 맞춘 것입니다.

1. 모델·카탈로그에서 기존 YOLO 모델 ZIP과 카탈로그 ZIP을 가져옵니다.
2. 부품 촬영 또는 차량 촬영을 선택하고 장비번호와 부위를 입력합니다.
3. 실시간 카메라, 사진 선택 또는 수동 박스 지정을 이용합니다. 카메라 권한이 없어도 사진 선택이 가능합니다.
4. 사진과 박스를 대조하고 수정·오탐 제외·품번 후보 선택·메모를 기록합니다.
5. 검사 저장 후 세션 기록에서 다시 열거나 JSON을 내보냅니다.

자동 탐지는 가져온 모델의 부품 클래스에만 적용됩니다. 차량 외관 고장이나 손상 판정은 하지 않습니다. 품번은 적용 조건을 별도로 확인해야 하는 후보입니다. 실제 학습 가중치·사진·PDF는 Git에 포함하지 않습니다.

## Android APK 빌드

JDK 17, Gradle 8.9, Android SDK 35, Python 3.11, Node 22가 필요합니다.

```sh
cd web
npm ci --ignore-scripts
npm run build
cd ..
python tools/stage_android.py
gradle -p android lintDebug assembleDebug
```

결과: `android/app/build/outputs/apk/debug/app-debug.apk`.
[GitHub Actions](https://github.com/stnt19/Mobility-Inspecter_Engine/actions)도 같은 빌드를 수행하며 `mobility-inspecter-python-debug` 아티팩트를 제공합니다.
Android 8.0 이상, arm64-v8a·x86_64 대상입니다. 디버그 APK는 개발 검증용이며 기존 설치본과 서명이 다르면 덮어쓸 수 없습니다. 기존 앱 데이터를 보존한 상태에서 서명을 맞춰 배포해야 합니다.

## PC에서 동일 Python 엔진 검증

```sh
python -m venv .venv
# 가상 환경 활성화 후
pip install -r requirements.txt
python -m engine.server
```

웹 번들을 먼저 빌드한 뒤 `http://127.0.0.1:8765`로 접속합니다. PC 미리보기는 서버를 실행하는 동안 사용합니다. APK는 서버를 자체 시작합니다.

```sh
pip install onnx PyYAML
python -m unittest discover -s tests -v
npm test --prefix web
```

- [전환 구조·호환성·검증 범위](docs/PYTHON_MIGRATION.md)
- [데이터 계약](docs/DATASET.md) · [카탈로그 계약](docs/CATALOG.md)
- `docs/TECHNICAL_GUIDE.md`, `LIVE_PREVIEW.md`, `WEB_VALIDATION.md` 등의 0.5.0 문서는 이전 Kotlin/WASM 구조의 이력입니다. 현재 실행 방법은 이 README와 전환 문서를 따릅니다.
