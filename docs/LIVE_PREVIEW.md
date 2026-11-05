> 0.5.0 구조의 이력 문서입니다. 현재 0.6.0 Python APK 실행·구조는 [전환 문서](PYTHON_MIGRATION.md)를 참고하세요.

# 실시간 미리보기와 추론 분리 (v0.5.0)

## 변경된 동작

- CameraX `Preview` → `PreviewView`: 카메라 미리보기 전용 경로다. 추론 완료를 기다려 Bitmap 화면을 갱신하던 경로를 대체한다.
- CameraX `ImageAnalysis` → crop/RGBA 변환 → 회전 → ONNX → 투명 박스 오버레이: 분석 결과만 별도로 갱신한다.
- `PreviewView`는 `COMPATIBLE`/`FIT_CENTER`를 사용한다. Preview와 ImageAnalysis는 같은 `UseCaseGroup`의 ViewPort에 묶는다.
- 분석 프레임은 `ImageProxy.cropRect` 영역만 읽고 `rotationDegrees`를 적용한다. `ImageProxyTransformFactory`의 crop/rotation 옵션도 활성화하여 이 좌표계를 PreviewView로 변환한다. 준비되지 않은 좌표 변환은 임의로 추정하지 않고 박스 표시를 기다린다.
- 이미지 복사와 변환 정보를 확보한 뒤 ImageProxy를 닫고 추론한다. 분석은 단일 worker와 `KEEP_ONLY_LATEST`를 사용한다. `FrameGate`는 게시 대기까지 포함해 처리 중 결과를 하나로 제한한다.

## 결과 유효성

카메라 재연결·화면 크기/표시 회전 변경·배경 전환·일시정지 때 실행 세대를 무효화한다. 이전 실행의 추론이 늦게 끝나도 새 화면에 게시하지 않는다. 이미 실행 중인 ONNX 연산을 강제 중단하지는 않는다.

분석 시작부터 1.5초가 지난 박스는 실시간 미리보기에서 숨긴다. 이는 초기 UI 정책이며 정확도 보정이나 대상 추적이 아니다. 1.5초 이내에도 카메라/부품이 움직이면 시간차로 박스가 어긋날 수 있으므로 최종 확인에는 고정 사진을 사용한다. 오래된 박스의 터치/목록 선택도 함께 제거한다.

화면에는 분석 소요 ms와 분석 결과 갱신 횟수/초를 표시한다. 카메라 미리보기 FPS를 측정하거나 보장하는 값이 아니다. 실제 성능은 대상 장치에서 측정해야 한다.

## 고정·검사

**분석 장면 일시정지/재개** 또는 **분석 장면 고정·검사**는 마지막 분석 프레임을 고정한다. 빠르게 움직이는 현재 PreviewView 화면에 과거 박스를 붙여 저장하지 않는다.

Bitmap, 해당 프레임의 박스, 모델 manifest, 임계값, 분석 시작 시각을 한 묶음으로 UI에 전달한다. 고정 시 같은 묶음에서 사진과 메타데이터를 복사하며 프레임 경과 시간을 표시한다. 촬영 버튼을 누른 정확한 시각의 사진이라는 뜻은 아니다. 모델이 없으면 빈 박스의 사진을 웹에서 수동 검수할 수 있다.

일시정지 시 카메라 use case를 해제하고 고정 사진을 표시한다. 재개하면 카메라를 다시 연결한다. 검사 편집에서 돌아오면 고정 상태가 유지된다. 화면 회전으로 Activity가 재생성되면 아직 저장하지 않은 네이티브 고정 프레임은 복원하지 않으므로 검사 화면에서 저장한 기록을 사용한다.

## 코드

| 파일 | 책임 |
|---|---|
| `MainActivity.kt` | Preview/ImageAnalysis 바인딩, 실행 세대, 결과 게시, 프레임 고정/검사 연결 |
| `DetectionOverlay.kt` | PreviewView 좌표로 변환된 박스 표시/터치 |
| `CameraFrame.kt`, `CameraPixels.kt` | crop·행/픽셀 stride·RGBA 읽기 및 회전 |
| `FrameGate.kt` | 처리 중 결과 수 제한, 오래된 실행 차단, 표시 만료 기준 |
| `InspectionView.kt` | 기존 검수 사진 및 고정 분석 프레임 표시 |

CameraX view 의존성도 기존 카메라 모듈과 같은 1.4.1로 고정한다. 웹 세션 데이터 형식은 v0.4의 스키마 2를 유지한다. legacy_active 대응은 이 변경에 포함하지 않는다.

## 검증 범위

추가 단위 검사:

- 카메라 재연결 전후 처리 중 결과가 하나로 유지되는지
- 일시정지/배경 전환 이전 실행의 결과가 재개 후 거부되는지
- 박스 만료 경계와 시간 역전 입력
- crop offset, 버퍼 position, 행 패딩, pixel stride, RGB 순서 및 잘린 버퍼 거부

이 검사는 실제 카메라 센서·PreviewView 변환·Android 그래픽 회전을 대신하지 않는다. Android 단위 검사/lint/APK는 GitHub Actions에서 실행하며 커밋별 결과를 확인한다.

실기기에서 남은 확인:

1. 가로/세로/180도 회전, 화면 비율 변경 후 동일 부품에 박스가 맞는지.
2. 느린 추론 중 미리보기가 독립적으로 갱신되는지, 오래된 박스가 숨겨지는지.
3. 화면 고정과 검사 전달 시 사진·박스·모델이 같은 프레임에 속하는지.
4. 카메라↔검수 모드 반복, 홈/복귀, 모델 교체 중 늦은 결과가 섞이지 않는지.
5. 10분 이상 실행 시 메모리·발열·지연과 카메라 해제/재연결 안정성.

참고: [CameraX 좌표 변환](https://developer.android.com/media/camera/camerax/transform-output), [ImageProxyTransformFactory 소스](https://github.com/androidx/androidx/blob/androidx-main/camera/camera-view/src/main/java/androidx/camera/view/transform/ImageProxyTransformFactory.java), [CoordinateTransform 소스](https://github.com/androidx/androidx/blob/androidx-main/camera/camera-view/src/main/java/androidx/camera/view/transform/CoordinateTransform.java).
