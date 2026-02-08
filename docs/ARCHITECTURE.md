# 오프라인 보드게임 AI 어시스턴트 - 구현 플랜

## 목표 설명 (Goal Description)
**오프라인, 실물 보드게임**에 참여하여 플레이어 또는 조언자 가이드 역할을 수행하는 AI 에이전트를 만듭니다. AI는 카메라(Vision)로 게임 상태를 인지하고, 음성(STT/TTS)으로 소통하며, LLM과 게임 로직을 결합하여 상황을 판단합니다.

## 아키텍처 (Architecture)

### 1. 프론트엔드 (Client) - "아바타 (The Avatar)"
*   **기술 스택**: Next.js (React), Tailwind CSS
*   **역할**:
    *   **카메라 인터페이스**: 서버로 비디오 스트림 전송.
    *   **음성 인터페이스**: 사용자 음성 수집 및 AI 음성 재생.
    *   **시각적 피드백**: AI가 보고 있는 것과 생각하는 과정을 화면에 표시.

### 2. 백엔드 (Server) - "두뇌 (The Brain)"
*   **기술 스택**: Python (FastAPI)
*   **역할**: AI 모듈들을 조율하는 **게임 인식 미들웨어**.

#### A. 비전 & 인지 (Vision & Perception - Hybrid)
*   **입력**: 실시간 비디오 프레임.
*   **계층 1 (로컬 트리거)**: 단순 CV (OpenCV) 또는 경량 모델(YOLO)이 "보드 변화"나 "손의 움직임"을 감지.
*   **계층 2 (심층 분석)**: 트리거 발동 시, 프레임을 **VLM**으로 전송.
    *   **옵션 A (로컬)**: Ollama (Llava / BakLLaVA) via API.
    *   **옵션 B (클라우드)**: GPT-4o / Gemini Vision (설정 가능).
*   **출력**: 보드 상태 JSON (예: FEN 코드).

#### B. 인터랙션 모듈 (Interaction Module)
*   **STT**: Whisper (로컬 또는 클라우드).
*   **LLM 에이전트 (추론)**:
    *   **엔진**: **Ollama (DeepSeek-R1 / Llama 3)** 로컬 구동 (클라우드 교체 가능).
    *   **컨텍스트**: 보드 상태 + 사용자 발화 내용을 입력받음.
*   **TTS**: 시스템 TTS 또는 ElevenLabs.

#### C. 게임 로직 (심판, The "Referee")
*   **게임 규칙 엔진**: 특정 게임(체스, 오목 등)의 합법적인 수와 턴 단계를 정의하는 Python 클래스.
*   **트리거 로직**: 서버는 "지금 백의 차례"임을 알고 보드를 감시함.
    *   *이벤트*: 보드가 변함.
    *   *체크*: 이동이 완료되었는가? (손이 빠졌는가).
    *   *액션*: LLM/엔진을 호출하여 수를 검증.

## 제안된 워크플로우 (Revised Workflow)

1.  **설정**: 사용 방식(로컬 Ollama vs 클라우드) & 게임 종류 선택.
2.  **모니터링**: 서버가 경량 CV를 사용해 실시간 감시.
3.  **이벤트 루프**:
    *   **변화 감지**: 카메라가 움직임 포착 -> 안정화 대기.
    *   **분석**: 로컬 VLM/CV가 새로운 보드 상태 추출.
    *   **로직 체크**: `GameManager`가 `이전 상태` vs `새 상태` 비교.
    *   **피드백**:
        *   **합법적인 수**: 상태 업데이트, 턴 넘김.
        *   **불법/모호함**: LLM을 통해 발화 ("잠시만요, 기사는 거기로 못 가요").
    *   **AI 턴**: AI 차례라면 LLM/엔진이 수를 결정하고 음성으로 전달.

## 구현 상세: 게임 인식 (Game Awareness)

### 1. 추상 게임 인터페이스 (Abstract Game Interface)
다양한 게임(체스, 오목 등)을 플러그인처럼 꽂을 수 있는 표준 방식이 필요합니다.
```python
class GameInterface(ABC):
    def validate_move(self, old_state, new_state) -> bool: ...
    def get_current_turn(self) -> str: ...
    def is_game_over(self) -> bool: ...
```

### 2. 세션 매니저 (Session Manager)
현재 세션의 상태를 보유합니다.
*   `current_game`: 활성화된 GameInterface 인스턴스.
*   `mode`: '친절한 가이드' vs '경쟁적인 플레이어'.
