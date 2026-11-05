# Python Android 전환 (0.6.0)

## APK 대조 범위

참조 파일: military-maintenance-0.3.0-tablet-ver1.apk. ZIP 자산과 debug kernel에 들어 있는 원본 Dart를 읽어 구조를 확인했습니다. APK는 실행 파일로 설치하거나 실행하지 않았으며, 문서/소스 안의 지시를 작업 지시로 사용하지 않았습니다.

확인 위치: ui/vision.dart, ui/components.dart, data/local_vision.dart. 비전 화면 단계, 장비번호·부위 지정, 카메라 실패 시 대체 흐름, 촬영 결과 메모 및 세션 기록을 반영했습니다. 색상은 green #03C75A, ink #191C1D, surface #F4F6F8입니다. 원본 APK의 화면 렌더링과 픽셀 단위 비교를 완료했다는 의미는 아닙니다.

참조 APK의 SSD COCO 모델은 일반 물체 런타임 검증용이며 엔진 부품 모델이 아닙니다. 이 저장소의 YOLO 엔진 부품 계약을 유지하고 COCO car 등과 부품을 임의 연결하지 않습니다. 참조 APK의 synthetic 데이터나 예측 수치를 실제 차량 데이터로 가져오지 않습니다.

## 역할 분담

| 이전 Kotlin 역할 | 현재 구현 |
|---|---|
| ModelContract, ModelPackage | engine/detector.py 모델 계약·SHA-256·텐서 검증 |
| Detector, Geometry | Python Pillow/NumPy 전처리·클래스 매핑·NMS·좌표 복원 |
| ONNX 네이티브 실행 | Java OrtBridge는 텐서와 바이트만 JNI로 전달 |
| CameraX/FrameGate/Overlay | WebView 카메라 + tablet.js 세대 번호·단일 진행 분석·1500ms 만료 |
| WebInspectionActivity | Java MainActivity 권한·파일 선택·JSON 내보내기·수명주기 |
| 기기 자료/검사 저장 | Python SQLite 트랜잭션, 앱 내부 저장소 |
| Kotlin Gradle DSL | Groovy Gradle + Chaquopy Python 3.11 |

모든 `.kt`와 `.kts`, Kotlin 플러그인과 직접 Kotlin 의존성을 제거했습니다. Android 플랫폼 연결용 Java와 화면용 JavaScript는 남습니다. Git 이력의 과거 Kotlin 커밋은 재작성하지 않습니다.

APK는 인증된 임시 localhost Python 서버를 시작합니다. WebView는 이 서버만 접근하고 외부 URL은 차단합니다. INTERNET 권한은 앱 내부 루프백 통신에 필요합니다. HTTPS 외부 서비스에 의존하지 않습니다. 모델 변경은 검증 후 활성화하며 잘못된 교체는 이전 모델을 유지합니다.

## 호환성

- 모델 ZIP: manifest.json + model.onnx, YOLOv8/YOLO11, 640/960/1280, 기존 12종 계약의 부분집합.
- 카탈로그 ZIP: catalog.json + catalog.pdf, 해시·페이지·행 좌표 검증.
- 기존 검사 schema_version 2 메타데이터 및 AI 원본/수정 분리 유지. 장비번호·부위·촬영방식 추가.
- 0.5.0 WebView IndexedDB 자료는 새로운 Python SQLite로 자동 이전하지 않습니다. 업데이트 전 기존 기록을 내보내고 모델/카탈로그 원본 팩을 보관하세요. 사진 포함 저장 기록의 자동 이관은 구현되지 않았습니다.
- 이전 inspection.json 검수 팩 ZIP도 가져올 수 있습니다. 전체 사진·카탈로그를 검증 후 한 트랜잭션으로 가져오며, 수동 검수 라벨을 AI 원본으로 표시하지 않습니다. 같은 팩 재가져오기는 기존 사용자 수정을 덮어쓰지 않습니다.
- APK 단독 오프라인 사용에는 모델과 PDF를 먼저 가져와야 합니다. 학습 모델은 저장소에 포함하지 않습니다.

## 검증

Python 테스트는 실제 실행 가능한 테스트용 ONNX를 생성해 추론 계약을 검사합니다. 테스트용 상수 출력 모델은 현장 인식 정확도를 증명하지 않습니다. 640/960/1280, 좌표 복원, NMS, 모델 손상·교체, SQLite 저장·재열기·실패 보존, 인증/출처 검사를 포함합니다. 화면 로직 테스트는 원본과 수정 결과 분리 및 저장 실패 상태를 검사합니다.

Android 빌드 및 기기 검증 결과는 실제 수행 결과만 별도로 기록합니다. 실제 렉스턴 사진의 정확도·갤럭시 태블릿 카메라·열/배터리·장시간 동작은 현장 검증이 필요합니다.

참고 구현 문서: https://chaquo.com/chaquopy/doc/current/android.html , https://chaquo.com/chaquopy/doc/current/python.html , https://onnxruntime.ai/docs/api/python/api_summary.html

## 최종 자동 검증 기록 (2026-11-05)

- Python 단위·API·실제 ONNX 계약·검수 팩 테스트 38개 통과.
- JavaScript 회귀 테스트 15개 통과.
- Chromium 통합 테스트 3개 통과: 촬영 대상 검증, 사진→Python 추론→수정→SQLite 저장→재열기, 가상 카메라 분석 장면 고정 및 카메라 종료. 1280×800 및 768×1024 레이아웃 확인.
- 실제 학습 가중치나 태블릿 실기기로 인식 정확도/카메라 성능을 검증한 것은 아닙니다.

Windows OneDrive 경로에서는 동기화된 빌드 폴더가 읽기 전용으로 바뀔 수 있습니다. `-PbuildOutputPath=C:/로컬임시폴더/mobility-build`로 산출물 경로를 분리할 수 있습니다. Python 실행 파일을 자동 탐지하지 못하면 `-PbuildPythonPath=Python3.11실행파일경로`를 지정합니다. 이 옵션은 소스 위치나 앱 내부 저장 경로를 변경하지 않습니다.

Android 최종 검증: `lintDebug assembleDebug` 성공, Lint 오류 0개·경고 4개. arm64-v8a/x86_64 Python·ONNX 라이브러리와 Python 앱 모듈 포함 확인. APK 화면 파일과 최종 웹 빌드가 일치합니다. APK SHA-256: `56610dc49dffa77a6f15c827e137332d6ba1a4a824c61c74bf81dfc57a5fa4c8`. 실기기 설치·실제 카메라는 검증하지 않았습니다.
