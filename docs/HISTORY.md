# 워크스루: 오프라인 보드게임 AI (Walkthrough)

## 완료된 기능 (Completed Features)

### 1. 프로젝트 초기 설정
- **프론트엔드**: Next.js 14 + Tailwind CSS 초기화 완료.
- **백엔드**: FastAPI (Python) 서버 생성 완료.
- **환경**: `fastapi`, `uvicorn`, `opencv-python`, `ollama` 가상환경 설정 완료.

### 2. 비전 모듈 (눈, The "Eyes")
- **프론트엔드**: `CameraView` 컴포넌트 생성.
    - [x] 기기 카메라 접근.
    - [x] **자동 모니터링 (Auto-Monitoring)**: 연속 스냅샷 모드 토글 (1초 간격).
    - [x] 실시간 상태 표시 (`IDLE`, `MOVING`, `STABLE`).
- **백엔드**: `/api/analyze` 엔드포인트.
    - [x] 이미지 업로드 수신.
    - [x] **안정화 체크 (Stability Check)**: OpenCV를 사용하여 보드가 정지 상태인지 움직이는 중인지 감지.

### 3. 로컬 AI 연동 (두뇌 - 1단계)
- **서비스 계층**: Ollama API를 감싸는 `LLMService` 구현.
- **로직**:
    - [x] `VisionService`가 `stable_trigger` 신호를 보낼 때만 무거운 LLM 분석 수행.
    - [x] 텍스트용 `llama3`, 비전용 `llava` 지원.

## 현재 및 다음 단계 (Current & Next Steps)
- [ ] **게임 상태 매니저**: 현재 플레이 중인 "게임" 정의.
- [ ] **턴 관리**: 누구의 차례인지 추적.
- [ ] **음성 인터랙션**: STT (듣기) 및 TTS (말하기) 추가.
