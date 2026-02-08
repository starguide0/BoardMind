# 작업 목록 (Tasks)

- [x] **프로젝트 초기 설정 (Project Setup)**
    - [x] Git 저장소 초기화
    - [x] Next.js 프론트엔드 설정 `client/`
    - [x] Python FastAPI 백엔드 설정 `server/`
    - [x] 기본 통신 설정 (API/WebSocket)

- [/] **비전 모듈 & 로컬 AI 설정 (Vision & Local AI)**
    - [x] 프론트엔드 카메라 캡처 구현
    - [x] 백엔드 이미지 처리 엔드포인트 생성
    - [x] **[NEW]** 백엔드에 Ollama 연동 (로컬 VLM/LLM) 
    - [x] **[NEW]** "변화 감지(Change Detection)" 로직 구현 (OpenCV)
    - [x] 상태 추출을 위한 VLM 통합

- [ ] **게임 상황 인식 & 인터랙션 (Game Awareness & Interaction)**
    - [ ] 추상 게임 클래스 정의 (상태/규칙)
    - [ ] "턴 매니저(Turn Manager)" 구현 (누구 차례인가?)
    - [ ] 연결: 비전 트리거 -> 게임 엔진 -> LLM 응답
    - [ ] STT(음성인식)/TTS(음성합성) 파이프라인 구현


- [ ] **고도화 & 테스트 (Refinement & Testing)**
    - [ ] 엔드 투 엔드(End-to-End) 게임 루프 테스트
    - [ ] 지연 시간(Latency) 최적화
    - [ ] UI/UX 폴리싱
