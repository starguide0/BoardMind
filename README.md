# Board Game AI

카메라로 보드게임을 인식하고, 로컬 LLM이 규칙 안내 / 전략 조언 / 심판 / 직접 플레이까지 수행하는 실시간 보드게임 AI 도우미.

## 주요 기능

- **게임 인식** — 카메라 이미지로 보드게임 자동 식별 (Ollama Vision)
- **룰북 RAG** — 웹 검색(DuckDuckGo) + 크롤링(cheerio) + LLM 요약으로 한국어 규칙서 자동 생성 및 캐시
- **실시간 보드 분석** — N초 간격 자동 캡처, Canvas 픽셀 차분으로 변화 감지, LLM이 상황 해설
- **AI 역할 시스템** — DM / 플레이어 / 심판 / 관전자
- **AI 플레이어** — AI가 직접 게임에 참여, 카메라 오버레이로 액션 요청 (이동 화살표, 하이라이트)
- **다중 AI 플레이어** — 여러 AI가 각자 다른 개성(공격적/방어적/균형/랜덤)으로 참여, 턴 관리
- **음성 채팅** — Web Speech API 기반 STT 입력 + TTS 응답, 연속 음성 대화 모드
- **턴 타이머** — SSE 기반 서버 푸시 타이머 (경고, 만료 알림)

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프레임워크 | Next.js 16, React 19, TypeScript |
| 스타일링 | Tailwind CSS |
| AI | Ollama (로컬 LLM, REST API) |
| 웹 검색 | duck-duck-scrape (DuckDuckGo) |
| 크롤링 | cheerio |
| 실시간 통신 | SSE (Server-Sent Events) |
| 음성 | Web Speech API (STT/TTS) |
| 변화 감지 | Canvas 2D 픽셀 차분 (클라이언트) |

## 시작하기

### 사전 요구사항

- Node.js 18+
- [Ollama](https://ollama.ai) 설치 및 실행
- Vision 지원 모델 (기본: `gemma3:12b`)

```bash
ollama pull gemma3:12b
```

### 설치 및 실행

```bash
cd client
npm install
npm run dev
```

http://localhost:3000 접속

### 환경 변수 (선택)

`client/.env.local` 파일에 설정:

```bash
OLLAMA_HOST=http://localhost:11434    # Ollama 서버 주소 (기본값)
OLLAMA_MODEL=gemma3:12b              # 텍스트 모델 (기본값)
OLLAMA_VISION_MODEL=gemma3:12b       # 비전 모델 (기본값, 미설정 시 OLLAMA_MODEL 사용)
```

## 사용 방법

1. 카메라를 보드게임에 비추고 **스냅샷** 클릭 → 게임 자동 인식
2. 백그라운드에서 룰북 자동 생성 (웹 검색 → 크롤링 → LLM 요약)
3. AI 역할 선택 (단일 역할 또는 **다중 AI 플레이어** 모드)
4. **자동 감시** 활성화 → 보드 변화 시 AI가 상황 해설
5. 채팅 또는 **음성채팅** 버튼으로 AI와 대화 (규칙 질문 → RAG 기반 답변)
6. AI 플레이어 모드: 오버레이로 액션 요청 → 인간이 대신 수행 → **완료** 클릭

## 설정

### 캡처 간격

UI 슬라이더로 2초~30초 사이 조절 가능 (기본 5초).

`client/lib/constants.ts`에서 기본값 변경:

```typescript
export const DEFAULT_INTERVAL = 5;   // 기본 캡처 간격 (초)
export const MIN_INTERVAL = 2;       // 최소 간격
export const MAX_INTERVAL = 30;      // 최대 간격
```

### 변화 감지 민감도

`client/lib/constants.ts`에서 조절:

```typescript
export const CHANGE_THRESHOLD = 30;      // 픽셀 차이 임계값 (높이면 둔감)
export const CHANGE_PIXEL_RATIO = 0.008; // 변화 픽셀 비율 (높이면 둔감)
```

## 프로젝트 구조

```
client/
├── app/
│   ├── page.tsx                    # 메인 페이지 (오케스트레이터)
│   ├── layout.tsx                  # 루트 레이아웃
│   └── api/
│       ├── identify/route.ts       # 게임 인식 + 룰북 생성 트리거
│       ├── analyze/route.ts        # 보드 상태 분석 + RAG + 액션 파싱
│       ├── chat/route.ts           # 채팅 + RAG 주입
│       ├── rules/route.ts          # 룰북 생성(POST) / 조회(GET)
│       ├── events/route.ts         # SSE 엔드포인트
│       ├── timer/route.ts          # 턴 타이머
│       └── health/route.ts         # Ollama 상태 확인
├── components/
│   ├── CameraView.tsx              # 카메라 + 캡처 + 액션 오버레이
│   ├── RulebookPanel.tsx           # 규칙서 아코디언 패널
│   ├── ActionOverlay.tsx           # AI 플레이어 액션 오버레이 (화살표/하이라이트)
│   ├── PlayerSetup.tsx             # 다중 플레이어 설정 UI
│   └── TurnIndicator.tsx           # 턴 순서 표시
├── hooks/
│   ├── useMotionDetection.ts       # 보드 변화 감지 (Canvas pixel diff)
│   └── useServerEvents.ts          # SSE 클라이언트 훅
├── lib/
│   ├── ollama.ts                   # Ollama API 헬퍼 (서버 전용)
│   ├── rules.ts                    # 룰북 엔진 (검색/크롤링/LLM 요약/캐시)
│   ├── events.ts                   # SSE EventBus 싱글턴 + 타이머
│   ├── types.ts                    # TypeScript 타입 정의
│   └── constants.ts                # 설정 상수
├── types/
│   └── speech.d.ts                 # Web Speech API 타입
└── data/rules/                     # 게임별 룰북 JSON 캐시 (자동 생성)
```

## API

### POST /api/identify
카메라 이미지로 게임 식별. 성공 시 백그라운드 룰북 생성 자동 트리거.

### POST /api/analyze
보드 이미지 분석. 룰북 RAG 주입, AI 플레이어일 때 액션 요청 파싱.

### POST /api/chat
텍스트 채팅. 룰북에서 관련 섹션 검색 후 시스템 프롬프트에 주입.

### POST /api/rules
룰북 생성 트리거 (비동기, SSE로 진행 상태 푸시).

### GET /api/rules?game={name}
캐시된 룰북 조회.

### GET /api/events
SSE 스트림. 타이머 이벤트 및 룰북 생성 진행 상태 수신.

### POST /api/timer
턴 타이머 시작/중지.

### GET /api/health
Ollama 서버 연결 상태 확인.
