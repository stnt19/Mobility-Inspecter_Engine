> 0.5.0 구조의 이력 문서입니다. 현재 0.6.0 Python APK 실행·구조는 [전환 문서](PYTHON_MIGRATION.md)를 참고하세요.

# 기술 구조 및 사용 가이드

기준일: 2026-10-31 · 앱 버전: 0.5.0 · 기반 구조 기준: `60fde4bcc887129bdc4e02a02a2558d04610a996` · 검사 세션은 [0.4 가이드](INSPECTION_SESSIONS.md) 참고

2023년형 일반 렉스턴 스포츠 엔진룸의 부품을 식별하고, 선택한 부품에 연결된 카탈로그 품번 후보와 관련 부속을 찾는 오프라인 애플리케이션이다. 부품 탐지 모델이며 고장·결함 진단이나 장착 적합성 확정 기능은 아니다.

## 1. 현재 기능과 실행 경로

| 경로 | 입력과 처리 | 제공 기능 | 확인 범위 |
|---|---|---|---|
| Android 검수 사진 | 검수 팩에 저장된 사진·라벨 | 박스 선택, 부품 목록, 카탈로그 검색, 원문/분해도 | AI 추론 없이 동작하는 검수 모드 |
| Android 실시간 카메라 | CameraX 프레임 → 네이티브 ONNX Runtime | 연속 탐지, 임계값 조정, 일시정지, 박스별 카탈로그 연결 | 코드·빌드 검증, 실기기 속도 미측정 |
| 오프라인 웹 검사 | 선택한 사진 → WASM ONNX 추론 | 박스·신뢰도, 카탈로그/PDF, 검사 JSON 내보내기 | 단위 검사·동일 텐서 추론 대조 완료, 전체 UI 실기기 검증 필요 |

웹 검사는 독립 브라우저와 Android 내장 WebView에서 같은 소스를 사용한다. 웹 모드는 사진 단위 추론이며 연속 카메라 탐지가 아니다. 네이티브 모드와 웹 모드는 자료 저장소가 별개이므로 각각 모델과 카탈로그를 가져와야 한다.

## 2. 기술 스택과 지원 조건

| 영역 | 구성 |
|---|---|
| Android | Kotlin 2.0.21, Android Gradle Plugin 8.7.3, Java 17, CI Gradle 8.9 |
| Android 대상 | minSdk 26(Android 8.0), compile/targetSdk 35, `arm64-v8a` / `x86_64` |
| 앱 식별 | `com.mobility.engine`, versionCode 5, versionName 0.5.0 |
| 카메라 | CameraX 1.4.1, Camera2 백엔드, PreviewView |
| 네이티브 추론 | ONNX Runtime Android 1.20.0 |
| 웹 화면 | HTML/CSS/JavaScript ES modules, 별도 UI 프레임워크 없음 |
| 웹 추론 | ONNX Runtime Web 1.20.1, WASM 단일 스레드, module Worker |
| PDF·ZIP | PDF.js 4.10.38, fflate 0.8.2; Android 네이티브 PDF 렌더링 |
| 웹 저장/연동 | IndexedDB, Service Worker, AndroidX WebKit 1.12.1 / WebViewAssetLoader |
| 데이터·카탈로그 도구 | Python, Pillow 11.0.0, PyMuPDF 1.28.2 |
| 저장소 학습 도구 | Ultralytics 8.3.40, ONNX 1.17.0, ONNX Runtime 1.20.1, PyYAML 6.0.2 |
| CI | GitHub Actions: Python 검사 → 웹 검사/빌드 → Android 검사/lint/APK |

의존성의 기준은 `android/*.gradle.kts`, `android/app/build.gradle.kts`, `web/package-lock.json`, `tools/requirements*.txt`이다. 별도 실험에서 만든 모델의 학습 환경과 저장소 학습 도구의 고정 버전은 동일하다고 가정하지 않는다.

Android 버전 조건을 충족해도 웹 모드에는 module Worker·WASM SIMD·PDF.js를 지원하는 WebView가 필요하다. OS 최소 버전만으로 모든 웹 기능의 호환성을 보장하지 않는다.

Galaxy Tab Active 1세대(SM-T360/SM-T365)는 제공된 사양상 Android 4.4~5.1.1, 32비트 Cortex-A7, RAM 1.5GB다. 현재 APK의 OS/ABI 조건과 맞지 않는다. 현재 기기의 실제 OS 버전은 별도 확인 대상이며, minSdk만 낮추는 것으로 대응되지 않는다.

## 3. 저장소 구조

| 경로 | 역할 |
|---|---|
| `android/app/src/main/java/com/mobility/inspect/` | Android 구현. 폴더명과 달리 Kotlin 패키지는 `com.mobility.engine` |
| `MainActivity.kt`, `CameraFrame.kt`, `InspectionView.kt` | 모드 전환, 카메라 프레임 변환, 사진/박스 표시 |
| `Detector.kt`, `Geometry.kt`, `ModelContract.kt`, `ModelPackage.kt` | 추론, 좌표/NMS, 모델 계약 및 ZIP 검증 |
| `InspectionBundle.kt`, `Catalog.kt`, `CatalogDialog.kt`, `Parts.kt` | 검수 팩, 부품 ID, 카탈로그 검색/PDF |
| `WebInspectionActivity.kt` | 로컬 WebView, 파일 선택, JSON 저장 연동 |
| `web/src/app.js`, `index.html`, `style.css` | 사진 검사 UI, 자원 가져오기, 카탈로그/PDF, 내보내기 |
| `web/src/inference.worker.js`, `core.js` | 모델 실행, 전후처리, 모델/카탈로그 검증과 검색 |
| `web/src/storage.js`, `sw.js` | ZIP/체크섬/IndexedDB, 오프라인 캐시 |
| `web/build.mjs`, `serve.py`, `verify-model.mjs` | 런타임 묶기, 로컬 정적 서버, 수치 일치 검사 |
| `tools/catalog_index.py` | 제공 PDF 레이아웃 기반 카탈로그 색인 |
| `tools/build_inspection_bundle.py`, `build_web_bundle.py` | 검수 팩/웹 실행 팩 생성 |
| `tools/prepare_dataset.py`, `train_export.py`, `benchmark.py`, `contract.py` | 학습 데이터 검사·변환, 학습/ONNX 내보내기, 비교, 클래스 계약 |
| `tests/`, `web/tests/`, `android/app/src/test/` | Python/웹/Android 단위 검사 |
| `.github/workflows/` | 빌드 및 검증 자동화 |

## 4. 구동 원리

### 사진 추론

1. 사용자가 모델 ZIP과 사진을 선택한다. 모델 계약과 SHA-256을 확인한다.
2. 웹은 사진을 최대 변 길이 1920으로 제한하고, 640×640 letterbox 입력을 만든다. 비율 유지, 패딩 114, RGB, 0~1 정규화, float32 CHW를 사용한다.
3. Worker에서 ONNX 모델을 실행한다. 출력은 `[1,4+C,8400]`이며 현재 5종 모델은 `[1,9,8400]`이다. 별도 objectness 값을 곱하지 않는다.
4. 클래스 이름을 공통 부품 ID에 연결하고 좌표를 검사 이미지 좌표로 복원한다. 웹은 점수 하한 0.05, 클래스별 NMS IoU 0.45, 최대 50개를 적용한다.
5. UI 임계값(기본 0.35, 웹 범위 0.05~0.95)으로 결과를 필터링한다. 임계값 변경은 저장된 추론 결과에 적용된다.
6. 박스 또는 목록을 선택하면 부품 ID로 카탈로그 후보를 검색한다.

네이티브 추론기는 640/960/1280 입력 모델을 지원하지만 웹 계약은 현재 640이다. 두 실행 경로에 같은 입력 크기 지원을 가정하지 않는다.

### 실시간 카메라

v0.5부터 `PreviewView`의 카메라 미리보기와 `ImageAnalysis` 추론을 분리한다. 공통 ViewPort와 CameraX 좌표 변환으로 별도 오버레이를 배치한다. CameraX의 `STRATEGY_KEEP_ONLY_LATEST`와 처리 중 상태 제어를 사용한다. 처리하지 못한 프레임을 계속 쌓지 않고 최신 프레임 중심으로 추론한다. 실제 탐지 갱신 빈도는 모델·기기·발열에 따라 달라지며 보장 FPS는 없다. 화면의 갱신 횟수는 분석 결과 빈도이며 미리보기 FPS가 아니다. [실시간 처리 상세](LIVE_PREVIEW.md)를 참고한다. 네이티브 임계값 범위는 0.10~0.95, 기본값은 0.35다.

### 카탈로그 연결

사용자 제공 786쪽 PDF에서 관련 235개 행을 색인한다. 각 행에는 품번, 이름, 옵션, 적용 기간, 변속기, 비고, PDF 페이지/행 좌표, 분해도 페이지, 주요 부품/관련 부속 관계를 보존한다. 전체 PDF의 모든 품목을 색인한 것은 아니다.

연결은 **탐지 클래스 → 부품 관계 규칙 → 후보 행 → 원문 표/분해도** 순서다. 생산일·차량 옵션 등에 따른 후보가 함께 나타날 수 있다. 사진만으로 단일 품번을 확정하지 않는다.

### 오프라인 처리

- Android는 `https://appassets.androidplatform.net/assets/web/index.html`의 앱 내부 자산을 사용한다. 외부 서버 주소가 아니며 서버 설치가 필요 없다.
- 웹의 모델/PDF는 IndexedDB에 저장한다. 네이티브 팩은 앱 내부 저장소에 별도로 보관한다.
- APK에 웹 런타임·WASM·PDF 뷰어를 포함하며 실행 시 CDN을 사용하지 않는다. Android INTERNET 권한은 선언하지 않는다.
- 일반 브라우저에서는 localhost 또는 지원되는 HTTPS 원점이 필요하다. `file://` 직접 실행과 일반 HTTP 원격 호스트는 지원하지 않는다.
- 앱 데이터나 브라우저 사이트 데이터를 삭제하면 가져온 자료가 지워질 수 있으므로 원본 ZIP을 별도 보관한다.

## 5. 사용자 사용법

### A. APK 설치와 웹 사진 검사

1. [Actions](https://github.com/Origin1332/Mobility-Inspecter_Engine/actions)에서 성공한 실행의 `mobility-inspecter-engine-debug` 아티팩트를 내려받아 압축을 풀고 APK를 설치한다. 현재 배포 산출물은 debug APK다.
2. 별도로 받은 `engine_web_offline.zip`의 압축을 풀고 `android-imports/model.zip`, `android-imports/catalog.zip`을 태블릿에 복사한다. 공개 저장소나 CI APK에는 학습 가중치와 원본 PDF가 없다.
3. 앱에서 **오프라인 웹 검사**를 연 뒤 모델 ZIP과 카탈로그 팩 ZIP을 각각 가져온다.
4. **사진 선택 → 부품 탐지**를 누른다. Android 웹 화면에서는 별도 사진 촬영 버튼을 숨기며 파일 선택기를 사용한다. 촬영한 사진을 선택하거나 네이티브 실시간 모드를 사용한다.
5. 박스나 부품 목록에서 부품을 선택하고 품번 후보·옵션·원문 행·분해도를 확인한다.
6. **검사 기록 내보내기**로 JSON을 저장한다. 재실행 시 자료가 유지되는지, 비행기 모드에서 동작하는지 대상 기기에서 확인한다.

### B. 검수 사진과 실시간 카메라

1. 메인 화면 **검수 팩 ZIP**에 `engine_inspection_catalog_v2.zip` 같은 검수 팩을 가져온다. 원본 데이터셋 ZIP이나 웹용 `catalog.zip`을 이 자리에 넣지 않는다.
2. **검수 사진**, **이전 사진/다음 사진**, **화면 부품 목록**으로 라벨과 카탈로그 연결을 확인한다. 이 박스는 AI 예측이 아니다.
3. **YOLO 모델 ZIP**에서 모델을 가져온 뒤 **실시간 카메라**를 누르고 카메라 권한을 허용한다.
4. 신뢰도 기준과 **일시정지/재개**를 사용한다. 박스의 카탈로그 연결에는 검수 팩의 카탈로그가 필요하다.

### C. PC 브라우저

완성 실행 팩의 압축을 푼 폴더에서:

```sh
python serve.py
```

`http://127.0.0.1:8765/`에 접속한다. Python은 정적 파일만 제공하며 서버 추론이나 사진 업로드를 수행하지 않는다. 인터넷이 없어도 Python 프로세스는 실행 중이어야 한다. 일반 브라우저의 **오프라인 화면 저장**은 동일 원점의 파일을 캐시하며, 서버가 없는 Android 내장 자산 방식과 구분한다.

### 검사 JSON

v0.4는 검사 세션을 기기에 사진과 함께 저장하고 다시 연다. JSON 내보내기는 스키마 2로 AI 원본과 사용자 수정 결과, 선택 후보, 메모, 모델 정보와 앱 버전을 포함한다. 사진은 JSON에서 제외한다. 상세 규격과 제한은 [검사 세션 가이드](INSPECTION_SESSIONS.md)를 참고한다.

## 6. 개발 환경과 빌드

저장소 루트에서 시작한다. CI와 맞추려면 Python 3.12, Node.js 22, Java 17, Gradle 8.9, Android SDK 35를 준비한다. 의존성 다운로드는 개발 준비 단계에 필요하며 완성 앱의 오프라인 실행과 구분한다.

```sh
cd web
npm ci --ignore-scripts
npm test
npm run build
cd ..
python web/serve.py --directory web/dist
```

소스 빌드는 런타임만 생성하므로 모델과 카탈로그를 가져와야 한다. `serve.py`의 기본 디렉터리는 완성 실행 팩 구조용이어서 소스 실행에서는 위 옵션이 필요하다.

Android 빌드 전 웹 런타임을 assets에 복사한다(Linux/macOS 셸 예시):

```sh
mkdir -p android/app/src/main/assets/web
cp -R web/dist/. android/app/src/main/assets/web/
gradle -p android testDebugUnitTest lintDebug assembleDebug --no-daemon
```

APK: `android/app/build/outputs/apk/debug/app-debug.apk`. 저장소에 Gradle wrapper가 없으므로 설치한 Gradle을 사용한다. CI도 같은 방식으로 웹 자산을 준비한다.

### 비공개 실행 팩 생성

```sh
python -m pip install -r tools/requirements-catalog.txt
python tools/build_web_bundle.py --model-zip /path/model.zip --catalog /path/catalog.pdf --output /path/engine_web_offline.zip
```

앞서 웹 빌드를 완료해야 한다. `--sample /path/photo.jpg`를 반복하면 샘플 사진을 넣을 수 있다. `--android-assets android/app/src/main/assets/web`를 추가하면 자료까지 포함한 로컬 Android 자산을 만들 수 있다. 기존 출력 파일은 덮어쓰지 않는다.

검수 사진 팩 생성:

```sh
python tools/build_inspection_bundle.py --dataset /path/dataset.zip --catalog /path/catalog.pdf --output /path/inspection.zip
```

| 팩 | 주요 내용 | 사용처 |
|---|---|---|
| 모델 ZIP | `model.onnx`, `manifest.json` | 네이티브/웹 모델 가져오기 |
| 검수 팩 ZIP | `inspection.json`, 사진, `catalog.json`, `catalog.pdf` | 네이티브 검수·카탈로그, 웹에서는 카탈로그만 사용 가능 |
| 카탈로그 ZIP | `catalog.json`, `catalog.pdf` | 웹 카탈로그 가져오기 |
| 완성 웹 실행 ZIP | `web/`, `serve.py`, `android-imports/` 등 | PC 실행 및 Android 자료 전달 |

원본 PDF·사진·데이터셋·학습 가중치는 공개 Git에 추가하지 않는다. 생성 자료는 무시되는 `web/dist/`와 Android assets 또는 별도 배포 팩으로 관리한다. 카탈로그 추출기는 제공 PDF의 레이아웃 전용이므로 다른 PDF를 넣으면 원문 대조가 필요하다.

## 7. 모델 및 검증 상태

현재 제공된 58장 기반 모델은 배터리, 퓨즈 박스, 에어클리너, 냉각수 보조탱크, 엔진오일 레벨 게이지의 **5종**을 학습했다. 공통 ID 계약은 12종이지만 나머지 7종을 탐지할 수 있다는 뜻은 아니다. 초기 6장/30박스 검수 팩과 이후 학습 모델은 별개 산출물이다.

저장소의 `prepare_dataset.py`, `train_export.py`, `benchmark.py`는 12종 데이터 계약과 분할별 클래스 충족을 요구한다. 따라서 5종 모델을 읽는 앱의 지원과 5종 실험을 이 명령만으로 재현하는 기능은 다르다. 58장 실험 산출물과 감사 보고서는 별도 제공 자료이며 이 저장소만으로 그 실험 전체를 재현할 수 있다고 주장하지 않는다.

검증된 ONNX SHA-256:

```text
640543356080be5719b3134cff28ec195b25f09def543bc7d3dc90340abc287a
```

- 기존 확인: Python 20개, 웹 7개 검사 통과; Android 단위 검사/lint/APK 빌드 성공.
- 기준 코드의 [CI 실행](https://github.com/Origin1332/Mobility-Inspecter_Engine/actions/runs/41083393912)은 성공했다.
- 동일 입력 텐서의 Python ONNX Runtime와 Web WASM 출력 최대 절대 차이는 `0.000244140625`였다.
- 실제 Worker 모듈의 모델 검증·초기화·추론은 Node 어댑터로 확인했다. 브라우저/Android 전체 UI 검증을 대신하지 않는다.
- 별도 9장 시험(정답 45개), 임계값 0.35/매칭 IoU 0.5에서 후보 모델은 TP 38, FP 0, FN 7이었다. Precision 100%, Recall 84.4%, F1 91.6%이며 mAP50 0.9886, mAP50–95 0.6865로 보고되었다. mAP는 단일 임계값의 P/R과 다른 평가다.
- 이 수치는 작은 기존 시험 집합의 결과다. 음성 장면·다른 차량·새 현장 자료의 성능이나 실제 태블릿 FPS를 보장하지 않는다. 점수는 보정된 정답 확률이 아니며 미탐지를 부품 부재/고장으로 해석하지 않는다.

추가 확인: 지원 브라우저에서 사진→추론→PDF→저장→오프라인 재시작, 실제 Android 카메라/파일 선택, 메모리·발열·지연·장시간 안정성. 자세한 런타임 확인 범위는 [WEB_VALIDATION.md](WEB_VALIDATION.md)를 참고한다.

재검사 명령:

```sh
python -m pip install -r tools/requirements-catalog.txt
python -m unittest discover -s tests -v
cd web
npm ci --ignore-scripts
npm test
npm run build
cd ..
gradle -p android testDebugUnitTest lintDebug assembleDebug --no-daemon
```

Android 검사 전에는 위의 assets 복사 절차를 수행한다. 문서 변경만으로 모델을 재학습하거나 실기기 성능을 검증한 것으로 간주하지 않는다.

## 8. 문제 해결

| 증상 | 확인 사항 |
|---|---|
| APK 설치 불가 | Android 8.0 이상과 지원 ABI 확인. Active 1세대는 현재 지원 대상이 아님 |
| 웹 시작 실패/보안 컨텍스트 오류 | localhost 또는 지원 HTTPS 사용. `file://`와 일반 원격 HTTP는 사용하지 않음 |
| 모델/카탈로그 없음 | 해당 실행 모드에서 가져왔는지 확인. 웹/네이티브 저장은 공유되지 않음 |
| ZIP 거부 | 올바른 종류, 내부 파일/manifest/체크섬 확인. 원본 데이터셋 ZIP은 실행 모델이 아님 |
| 박스가 없거나 일부 부품 누락 | 지원 5종, 임계값, 조명/가림/촬영 거리 확인. 낮은 점수 결과도 정답 보장은 없음 |
| 품번 후보가 여러 개 | 옵션·적용 기간·원문 확인. 자동 장착 확정 기능이 아님 |
| 웹 기능이 안 됨 | WebView/브라우저의 Worker·WASM 지원 확인. OS 최소 버전만으로 판단하지 않음 |
| 재실행 후 자료 없음 | 앱/사이트 데이터 삭제 여부와 저장 실패 안내 확인 후 ZIP 재가져오기 |

## 9. 개발 및 브랜치 운영 방침

1. `main`에서 전체 기능 개발과 검증을 먼저 진행한다.
2. 주요 기능이 완료되고 안정화되면 기준 커밋에 태그를 남기고 `legacy_active`를 생성한다. 현재 문서 작업에서는 해당 브랜치를 만들지 않는다.
3. `legacy_active`에서 실제 기기 측정을 바탕으로 불필요하거나 실행 불가능한 기능을 축소·대체한다. 사진 단위 추론, 경량 카탈로그, 구형 카메라/런타임 대응은 향후 검토 대상이며 현재 구현 기능이 아니다.
4. 추론·카메라·카탈로그·저장 경계를 유지하고 공통 부품 ID와 데이터 규격의 의미를 보존한다. 공통 오류 수정은 적용 커밋을 기록하며 양쪽에 반영한다.
5. 저사양 최적화 모델을 만들면 정확도와 지연을 다시 검증하고 모델 해시를 별도로 관리한다. 현재 모델의 검증 수치를 그대로 승계하지 않는다.

관련 문서: [웹 개발/실행](../web/README.md) · [데이터 규격](DATASET.md) · [카탈로그 연결](CATALOG.md) · [초기 작업 기록](STATUS.md)
