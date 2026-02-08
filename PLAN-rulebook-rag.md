# 웹 검색 기반 룰북 RAG + 복합 역할 시스템 구현 플랜

> 이 문서는 구현 플랜을 포함하며, 실제 코드 스니펫과 정확한 변경 위치를 기록합니다.
> Claude에게 "PLAN-rulebook-rag.md 플랜을 구현해줘"라고 하면 이 문서를 기반으로 작업을 수행합니다.

## 목표

1. **룰북 RAG**: 게임 인식 → 웹 검색 → 크롤링 → LLM 한국어 구조화 룰북 → JSON 캐시 → RAG 주입 → UI 패널
2. **복합 역할 시스템**: 단일 고정 역할 → 게임 규칙 기반 복합 역할 자동 판단 (룰북 의존)

---

## Phase 1: 의존성 + 타입 + 저장소 기반

### 1-1. 의존성 설치

```bash
cd client && npm install duck-duck-scrape cheerio
```

### 1-2. `client/lib/types.ts` — 타입 추가

파일 끝에 다음 타입을 추가:

```typescript
// Rulebook types
export interface RulebookSection {
  id: string;
  title: string;
  content: string;
  keywords: string[];
}

export interface Rulebook {
  gameName: string;
  gameNameNormalized: string;
  language: string;
  generatedAt: string;
  sourceUrls: string[];
  sections: RulebookSection[];
}

export type RulebookStatus = 'idle' | 'searching' | 'extracting' | 'generating' | 'ready' | 'error';

export interface RulesResponse {
  rulebook?: Rulebook;
  status: RulebookStatus;
  error?: string;
}
```

### 1-3. `client/lib/rules.ts` — 신규 파일 (핵심 엔진)

파일 I/O 함수들 먼저:

```typescript
import fs from 'fs/promises';
import path from 'path';
import { search, SafeSearchType } from 'duck-duck-scrape';
import * as cheerio from 'cheerio';
import { chat } from './ollama';
import { eventBus } from './events';
import type { Rulebook, RulebookSection } from './types';

const RULES_DIR = path.join(process.cwd(), 'data', 'rules');

export function normalizeGameName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, '-')
    .replace(/^-|-$/g, '');
}

function rulebookPath(gameName: string): string {
  return path.join(RULES_DIR, `${normalizeGameName(gameName)}.json`);
}

export async function rulebookExists(gameName: string): Promise<boolean> {
  try {
    await fs.access(rulebookPath(gameName));
    return true;
  } catch {
    return false;
  }
}

export async function loadRulebook(gameName: string): Promise<Rulebook | null> {
  try {
    const raw = await fs.readFile(rulebookPath(gameName), 'utf-8');
    return JSON.parse(raw) as Rulebook;
  } catch {
    return null;
  }
}

export async function saveRulebook(rulebook: Rulebook): Promise<void> {
  try {
    await fs.mkdir(RULES_DIR, { recursive: true });
    await fs.writeFile(
      rulebookPath(rulebook.gameName),
      JSON.stringify(rulebook, null, 2),
      'utf-8'
    );
  } catch (e) {
    console.error('[rules] Failed to save rulebook:', e);
  }
}

export function formatSectionsForPrompt(sections: RulebookSection[]): string {
  return sections
    .map((s) => `### ${s.title}\n${s.content}`)
    .join('\n\n');
}
```

---

## Phase 2: 웹 검색 + 크롤링

`client/lib/rules.ts`에 추가:

```typescript
export async function searchGameRules(gameName: string): Promise<string[]> {
  const queries = [
    `${gameName} board game rules how to play`,
    `${gameName} 보드게임 규칙`,
  ];
  const allUrls: string[] = [];
  const seenDomains = new Set<string>();

  for (const query of queries) {
    try {
      const results = await search(query, { safeSearch: SafeSearchType.OFF });
      for (const r of results.results) {
        try {
          const domain = new URL(r.url).hostname;
          if (!seenDomains.has(domain)) {
            seenDomains.add(domain);
            allUrls.push(r.url);
          }
        } catch { /* skip invalid URLs */ }
      }
    } catch (e) {
      console.error(`[rules] Search failed for "${query}":`, e);
    }
  }

  return allUrls.slice(0, 5);
}

export async function extractPageContent(url: string): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);

  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; BoardGameAI/1.0)' },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const html = await res.text();
    const $ = cheerio.load(html);

    // Remove non-content elements
    $('script, style, nav, header, footer, aside, .sidebar, .ad, .advertisement').remove();

    // Extract main content
    const mainSelectors = ['main', 'article', '.content', '.post-content', '#content', '.entry-content'];
    let text = '';
    for (const sel of mainSelectors) {
      const el = $(sel);
      if (el.length) {
        text = el.text();
        break;
      }
    }
    if (!text) {
      text = $('body').text();
    }

    // Clean up whitespace
    text = text.replace(/\s+/g, ' ').trim();

    // Limit to 8000 chars
    return text.slice(0, 8000);
  } finally {
    clearTimeout(timeout);
  }
}
```

---

## Phase 3: LLM 요약 + 전체 파이프라인

`client/lib/rules.ts`에 추가:

```typescript
export async function generateRulebookFromContent(
  gameName: string,
  rawTexts: string[],
): Promise<Rulebook> {
  const combined = rawTexts.join('\n\n---\n\n').slice(0, 20000);

  const prompt = `다음은 보드게임 "${gameName}"에 대한 웹에서 수집한 규칙 정보입니다:

${combined}

위 정보를 바탕으로 이 게임의 규칙을 한국어로 구조화하여 JSON으로 작성하세요.
반드시 아래 형식을 따르세요 (JSON만 출력, 다른 텍스트 없이):

{
  "sections": [
    {"id": "overview", "title": "게임 개요", "content": "...", "keywords": ["개요", "소개", "인원", "구성품"]},
    {"id": "setup", "title": "게임 준비", "content": "...", "keywords": ["준비", "셋업", "배치"]},
    {"id": "turns", "title": "턴 진행", "content": "...", "keywords": ["턴", "차례", "진행", "페이즈", "액션"]},
    {"id": "scoring", "title": "승리 조건", "content": "...", "keywords": ["승리", "점수", "종료", "끝"]},
    {"id": "special_rules", "title": "특수 규칙", "content": "...", "keywords": ["특수", "예외", "고급"]},
    {"id": "faq", "title": "자주 묻는 질문", "content": "...", "keywords": ["질문", "FAQ", "헷갈리는"]}
  ]
}

각 content는 충분히 상세하게 작성하세요. 정보가 부족한 섹션은 알고 있는 범위에서 작성하세요.`;

  const raw = await chat(prompt);

  // Try to parse JSON from the response
  let sections: RulebookSection[];
  try {
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error('No JSON found');
    const parsed = JSON.parse(jsonMatch[0]);
    sections = parsed.sections;
  } catch {
    // Retry once
    const retryRaw = await chat(prompt + '\n\n이전 응답에서 JSON 파싱에 실패했습니다. 반드시 유효한 JSON만 출력하세요.');
    try {
      const jsonMatch = retryRaw.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw new Error('No JSON found on retry');
      const parsed = JSON.parse(jsonMatch[0]);
      sections = parsed.sections;
    } catch {
      // Fallback: single section with raw text
      sections = [{
        id: 'full',
        title: '게임 규칙',
        content: raw.slice(0, 5000),
        keywords: ['규칙', '게임', gameName],
      }];
    }
  }

  return {
    gameName,
    gameNameNormalized: normalizeGameName(gameName),
    language: 'ko',
    generatedAt: new Date().toISOString(),
    sourceUrls: [],
    sections,
  };
}

export async function generateRulebook(gameName: string): Promise<Rulebook | null> {
  // Check cache first
  const cached = await loadRulebook(gameName);
  if (cached) {
    eventBus.emit({ type: 'rulebook.ready', data: { gameName, cached: true } });
    return cached;
  }

  try {
    // Step 1: Search
    eventBus.emit({ type: 'rulebook.searching', data: { gameName } });
    const urls = await searchGameRules(gameName);

    // Step 2: Extract
    eventBus.emit({ type: 'rulebook.extracting', data: { gameName, urlCount: urls.length } });
    const rawTexts: string[] = [];
    for (const url of urls) {
      try {
        const text = await extractPageContent(url);
        if (text.length > 100) rawTexts.push(text);
      } catch (e) {
        console.error(`[rules] Failed to extract ${url}:`, e);
      }
    }

    // Step 3: Generate with LLM
    eventBus.emit({ type: 'rulebook.generating', data: { gameName } });
    const rulebook = await generateRulebookFromContent(gameName, rawTexts);
    rulebook.sourceUrls = urls;

    // Step 4: Save
    await saveRulebook(rulebook);

    eventBus.emit({ type: 'rulebook.ready', data: { gameName, cached: false } });
    return rulebook;
  } catch (e) {
    console.error('[rules] generateRulebook failed:', e);
    eventBus.emit({ type: 'rulebook.error', data: { gameName, error: String(e) } });
    return null;
  }
}

export function findRelevantSections(
  rulebook: Rulebook,
  query: string,
  max = 3,
): RulebookSection[] {
  const queryLower = query.toLowerCase();
  const scored = rulebook.sections.map((section) => {
    let score = 0;
    for (const kw of section.keywords) {
      if (queryLower.includes(kw.toLowerCase())) score += 2;
    }
    if (queryLower.includes(section.title.toLowerCase())) score += 3;
    // Partial match on content
    const words = queryLower.split(/\s+/).filter((w) => w.length > 1);
    for (const word of words) {
      if (section.content.toLowerCase().includes(word)) score += 1;
    }
    return { section, score };
  });

  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, max)
    .filter((s) => s.score > 0)
    .map((s) => s.section);
}
```

---

## Phase 4: API 라우트

### 4-1. `client/app/api/rules/route.ts` — 신규

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { generateRulebook, loadRulebook, rulebookExists } from '@/lib/rules';

export async function POST(req: NextRequest) {
  try {
    const { game_name } = await req.json();
    if (!game_name) {
      return NextResponse.json({ error: 'game_name is required' }, { status: 400 });
    }
    // Fire and forget — SSE will notify the client
    generateRulebook(game_name);
    return NextResponse.json({ status: 'generating' });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const game = req.nextUrl.searchParams.get('game');
  if (!game) {
    return NextResponse.json({ error: 'game query param required' }, { status: 400 });
  }
  const exists = await rulebookExists(game);
  if (!exists) {
    return NextResponse.json({ rulebook: null, status: 'idle' });
  }
  const rulebook = await loadRulebook(game);
  return NextResponse.json({ rulebook, status: 'ready' });
}
```

### 4-2. `client/app/api/identify/route.ts` — 수정

인식 성공 후 백그라운드 룰북 생성 트리거 추가:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { identifyGame } from '@/lib/ollama';
import { generateRulebook } from '@/lib/rules';

export async function POST(req: NextRequest) {
  try {
    const { image } = await req.json();
    if (!image) {
      return NextResponse.json({ error: 'image is required' }, { status: 400 });
    }
    const result = await identifyGame(image);

    // Trigger background rulebook generation (fire-and-forget)
    if (result.game_name && result.game_name !== 'unknown') {
      generateRulebook(result.game_name).catch((e) =>
        console.error('[identify] Background rulebook generation failed:', e)
      );
    }

    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
```

---

## Phase 5: RAG 연동

### 5-1. `client/lib/ollama.ts` — `buildSystemPrompt` 수정

`rulebookContext` 파라미터 추가:

```typescript
// 기존 시그니처:
export function buildSystemPrompt(gameName: string, role: string): string {
// 변경:
export function buildSystemPrompt(gameName: string, role: string, rulebookContext?: string): string {
  const base = `당신은 보드게임 '${gameName}'의 AI 도우미입니다...`;
  // ... (기존 코드 유지)

  let prompt = base + (roles[role] || roles['observer']);

  if (rulebookContext) {
    prompt += `\n\n## 이 게임의 공식 규칙 참고:\n${rulebookContext}\n\n위 규칙을 기반으로 정확하게 답변하세요. 규칙에 없는 내용을 지어내지 마세요.`;
  }

  return prompt;
}
```

### 5-2. `client/app/api/chat/route.ts` — RAG 주입

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { chat, buildSystemPrompt } from '@/lib/ollama';
import { loadRulebook, findRelevantSections, formatSectionsForPrompt } from '@/lib/rules';

export async function POST(req: NextRequest) {
  try {
    const { text, game_name, role, history } = await req.json();
    if (!text) {
      return NextResponse.json({ error: 'text is required' }, { status: 400 });
    }

    // Load rulebook and find relevant sections
    let rulebookContext: string | undefined;
    if (game_name && game_name !== 'unknown') {
      const rulebook = await loadRulebook(game_name);
      if (rulebook) {
        const relevant = findRelevantSections(rulebook, text);
        if (relevant.length > 0) {
          rulebookContext = formatSectionsForPrompt(relevant);
        }
      }
    }

    const systemPrompt = buildSystemPrompt(game_name || 'unknown', role || 'observer', rulebookContext);
    const content = await chat(text, systemPrompt, history);

    return NextResponse.json({ content });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
```

### 5-3. `client/app/api/analyze/route.ts` — RAG 주입

analyze 라우트의 `systemPrompt` 생성 부분도 동일하게 수정:

```typescript
import { loadRulebook, findRelevantSections, formatSectionsForPrompt } from '@/lib/rules';

// POST 핸들러 내부, systemPrompt 생성 직전:
let rulebookContext: string | undefined;
if (game_name && game_name !== 'unknown') {
  const rulebook = await loadRulebook(game_name);
  if (rulebook) {
    // For analyze, include turns and special_rules sections
    const relevant = findRelevantSections(rulebook, '턴 진행 특수 규칙 액션');
    if (relevant.length > 0) {
      rulebookContext = formatSectionsForPrompt(relevant);
    }
  }
}

const systemPrompt = buildSystemPrompt(game_name || 'unknown', role || 'observer', rulebookContext);
```

---

## Phase 6: UI + 음성

### 6-1. `client/components/RulebookPanel.tsx` — 신규

```typescript
'use client';

import { useState } from 'react';
import type { Rulebook, RulebookStatus } from '@/lib/types';

interface RulebookPanelProps {
  rulebook: Rulebook | null;
  status: RulebookStatus;
}

export default function RulebookPanel({ rulebook, status }: RulebookPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());

  if (status === 'idle') return null;

  const toggleSection = (id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const statusLabels: Record<RulebookStatus, string> = {
    idle: '',
    searching: '규칙서 검색 중...',
    extracting: '페이지 분석 중...',
    generating: '규칙서 생성 중...',
    ready: '규칙서 준비됨',
    error: '규칙서 로드 실패',
  };

  return (
    <div className="border border-gray-700 rounded-lg bg-gray-900 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">규칙서</span>
          {status !== 'ready' && status !== 'idle' && status !== 'error' && (
            <span className="text-xs px-2 py-0.5 bg-yellow-900 text-yellow-300 rounded animate-pulse">
              {statusLabels[status]}
            </span>
          )}
          {status === 'ready' && (
            <span className="text-xs px-2 py-0.5 bg-green-900 text-green-300 rounded">
              {statusLabels[status]}
            </span>
          )}
          {status === 'error' && (
            <span className="text-xs px-2 py-0.5 bg-red-900 text-red-300 rounded">
              {statusLabels[status]}
            </span>
          )}
        </div>
        <span className="text-gray-400 text-xs">{expanded ? '접기' : '펼치기'}</span>
      </button>

      {expanded && rulebook && (
        <div className="border-t border-gray-800 divide-y divide-gray-800">
          {rulebook.sections.map((section) => (
            <div key={section.id}>
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full flex items-center justify-between px-4 py-2 text-left hover:bg-gray-800 transition-colors"
              >
                <span className="text-sm text-indigo-300">{section.title}</span>
                <span className="text-xs text-gray-500">{openSections.has(section.id) ? '−' : '+'}</span>
              </button>
              {openSections.has(section.id) && (
                <div className="px-4 pb-3 text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                  {section.content}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 6-2. `client/app/page.tsx` — 수정 사항

#### 추가할 import:
```typescript
import RulebookPanel from '@/components/RulebookPanel';
import type { ..., Rulebook, RulebookStatus } from '@/lib/types';
```

#### 추가할 state (기존 state 선언 영역에):
```typescript
const [rulebook, setRulebook] = useState<Rulebook | null>(null);
const [rulebookStatus, setRulebookStatus] = useState<RulebookStatus>('idle');
```

#### SSE 핸들러 추가 (sseHandlers 객체에):
```typescript
'rulebook.searching': (data: Record<string, unknown>) => {
  setRulebookStatus('searching');
  addMessage('system', `"${data.gameName}" 규칙서 검색 중...`);
},
'rulebook.extracting': (data: Record<string, unknown>) => {
  setRulebookStatus('extracting');
  addMessage('system', `규칙 페이지 분석 중... (${data.urlCount}개 페이지)`);
},
'rulebook.generating': () => {
  setRulebookStatus('generating');
  addMessage('system', '규칙서 생성 중...');
},
'rulebook.ready': (data: Record<string, unknown>) => {
  setRulebookStatus('ready');
  const cached = data.cached as boolean;
  addMessage('system', cached ? '규칙서 로드됨 (캐시)' : '규칙서 생성 완료!');
  // Fetch the full rulebook
  fetch(`/api/rules?game=${encodeURIComponent(data.gameName as string)}`)
    .then((r) => r.json())
    .then((d) => { if (d.rulebook) setRulebook(d.rulebook); });
},
'rulebook.error': (data: Record<string, unknown>) => {
  setRulebookStatus('error');
  addMessage('system', `규칙서 생성 실패: ${data.error}`);
},
```

#### SSE 연결 조건 변경:
SSE 핸들러에 rulebook 이벤트가 추가되므로, `useServerEvents`의 `enabled` 조건 유지 (변경 불필요).

**주의**: `useServerEvents`는 초기 렌더링 시점의 handler 키로만 `addEventListener`를 등록합니다. 따라서 sseHandlers 객체에 rulebook 이벤트를 추가하면 자동으로 등록됩니다.

#### 음성 명령 감지 (handleVoiceInput 수정):
```typescript
const handleVoiceInput = useCallback(
  (text: string) => {
    // "규칙 설명해줘" 등 음성 명령 감지
    if (text.includes('규칙') && (text.includes('설명') || text.includes('알려') || text.includes('읽어'))) {
      if (rulebook && rulebook.sections.length > 0) {
        const summary = rulebook.sections.map((s) => `${s.title}: ${s.content.slice(0, 200)}`).join('. ');
        addMessage('user', `[음성] ${text}`);
        addMessage('ai', summary);
        setSpeakQueue((q) => [...q, summary]);
        return;
      }
    }
    addMessage('user', `[음성] ${text}`);
    handleChatSubmit(text);
  },
  [handleChatSubmit, addMessage, rulebook],
);
```

#### handleReset에 룰북 초기화 추가:
```typescript
const handleReset = useCallback(() => {
  // ... 기존 코드
  setRulebook(null);
  setRulebookStatus('idle');
  // ...
}, [addMessage, stopTimer]);
```

#### RulebookPanel 렌더링 위치:
Right 패널 영역, `analysisText` 블록 아래에 추가:

```tsx
{/* 규칙서 패널 */}
<RulebookPanel rulebook={rulebook} status={rulebookStatus} />
```

---

## 디렉토리 구조 (신규/변경)

```
client/
├── app/api/rules/route.ts          ← 신규
├── components/RulebookPanel.tsx     ← 신규
├── lib/rules.ts                    ← 신규
├── lib/types.ts                    ← 수정 (타입 추가)
├── lib/ollama.ts                   ← 수정 (rulebookContext 파라미터)
├── app/api/identify/route.ts       ← 수정 (백그라운드 트리거)
├── app/api/chat/route.ts           ← 수정 (RAG 주입)
├── app/api/analyze/route.ts        ← 수정 (RAG 주입)
├── app/page.tsx                    ← 수정 (상태, SSE, 패널, 음성)
└── data/rules/                     ← 자동 생성 (캐시 디렉토리)
```

## 에러 처리 정책

- 검색 실패 → LLM 자체 지식으로 룰북 생성 (rawTexts가 빈 배열이면 LLM이 자기 지식으로 작성)
- 크롤링 실패 → 개별 URL 스킵, 최소 0개로도 진행
- LLM JSON 파싱 실패 → 재시도 1회 → 비구조화 텍스트로 폴백
- 디스크 저장 실패 → console.error만, 메모리에서 계속
- 룰북 없을 때 → 기존과 동일 동작 (graceful degradation)

## 검증 방법

```bash
# 1. 빌드 확인
cd client && npm run build

# 2. 개발 서버 실행
npm run dev

# 3. API 직접 테스트
curl -X POST http://localhost:3000/api/rules \
  -H "Content-Type: application/json" \
  -d '{"game_name":"Catan"}'

curl http://localhost:3000/api/rules?game=Catan

# 4. 브라우저에서 전체 플로우 테스트
# - 카메라로 보드게임 촬영 → 인식
# - SSE 진행 상태 확인
# - 규칙서 패널 펼쳐서 내용 확인
# - 채팅에서 규칙 질문 → RAG 답변 확인
```

---

## Phase 7: 플레이어 액션 오버레이 시스템

> AI가 Player 역할일 때 훈수가 아닌 **직접 게임 참여자**로 행동합니다.
> 인간에게 동작을 요청하고, 카메라 화면에 오버레이로 지시사항을 표시합니다.

### 7-1. `client/lib/types.ts` — 액션 타입 추가

```typescript
// Player Action types
export type ActionType = 'draw_card' | 'roll_dice' | 'move_piece' | 'place_piece' | 'discard' | 'pass_turn' | 'custom';

export interface ActionRequest {
  id: string;
  type: ActionType;
  description: string;           // "카드 1장 뽑아주세요"
  target?: {
    from?: { x: number; y: number };  // 시작 위치 (비율 0~1)
    to?: { x: number; y: number };    // 도착 위치
    highlight?: { x: number; y: number; radius: number }[];  // 강조할 영역들
  };
  pending: boolean;              // 대기 중 여부
  timestamp: number;
}

export interface AnalyzeResponse {
  content: string;
  no_change: boolean;
  action_request?: ActionRequest;  // Player 역할일 때 액션 요청
  error?: string;
}
```

### 7-2. `client/components/ActionOverlay.tsx` — 신규 파일

```typescript
'use client';

import type { ActionRequest } from '@/lib/types';

interface ActionOverlayProps {
  action: ActionRequest | null;
  onConfirm?: () => void;
}

const ACTION_ICONS: Record<string, string> = {
  draw_card: '🎴',
  roll_dice: '🎲',
  move_piece: '♟️',
  place_piece: '📍',
  discard: '🗑️',
  pass_turn: '⏭️',
  custom: '💬',
};

export default function ActionOverlay({ action, onConfirm }: ActionOverlayProps) {
  if (!action || !action.pending) return null;

  return (
    <>
      {/* 이동 경로 화살표 */}
      {action.target?.from && action.target?.to && (
        <svg className="absolute inset-0 pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#facc15" />
            </marker>
          </defs>
          <line
            x1={action.target.from.x * 100}
            y1={action.target.from.y * 100}
            x2={action.target.to.x * 100}
            y2={action.target.to.y * 100}
            stroke="#facc15"
            strokeWidth="0.5"
            markerEnd="url(#arrowhead)"
          />
        </svg>
      )}

      {/* 하이라이트 영역 */}
      {action.target?.highlight?.map((hl, i) => (
        <div
          key={i}
          className="absolute rounded-full border-4 border-yellow-400 animate-pulse pointer-events-none"
          style={{
            left: `${(hl.x - hl.radius) * 100}%`,
            top: `${(hl.y - hl.radius) * 100}%`,
            width: `${hl.radius * 200}%`,
            height: `${hl.radius * 200}%`,
          }}
        />
      ))}

      {/* 액션 요청 배너 */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/80 backdrop-blur px-4 py-3 rounded-lg border border-yellow-500 shadow-lg max-w-[90%]">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{ACTION_ICONS[action.type] || '💬'}</span>
          <div className="flex-1">
            <p className="text-yellow-300 text-sm font-semibold">{action.description}</p>
            <p className="text-gray-400 text-xs mt-0.5">완료되면 화면을 캡처하세요</p>
          </div>
          {onConfirm && (
            <button
              onClick={onConfirm}
              className="px-3 py-1 bg-green-600 hover:bg-green-500 text-white text-xs font-semibold rounded transition-colors"
            >
              완료
            </button>
          )}
        </div>
      </div>
    </>
  );
}
```

### 7-3. `client/components/CameraView.tsx` — 수정

ActionOverlay 통합:

```typescript
import ActionOverlay from './ActionOverlay';
import type { ActionRequest } from '@/lib/types';

interface CameraViewProps {
  // ... 기존 props
  actionRequest?: ActionRequest | null;  // 추가
  onActionConfirm?: () => void;          // 추가
}

// ... 컴포넌트 내부, video 태그 아래에 추가:
<ActionOverlay action={actionRequest} onConfirm={onActionConfirm} />
```

### 7-4. `client/lib/ollama.ts` — Player 역할 프롬프트 수정

```typescript
// buildSystemPrompt의 roles 객체 수정:
player: `당신은 이 게임의 플레이어입니다. 인간이 당신을 대신해 동작을 수행합니다.

턴이 왔을 때 반드시 다음 JSON 형식으로 액션을 요청하세요:
{"action_type": "draw_card|roll_dice|move_piece|place_piece|discard|pass_turn|custom", "description": "한국어로 구체적인 요청", "from": {"x": 0.0-1.0, "y": 0.0-1.0}, "to": {"x": 0.0-1.0, "y": 0.0-1.0}}

예시:
- {"action_type": "draw_card", "description": "카드 덱에서 1장 뽑아주세요"}
- {"action_type": "move_piece", "description": "파란 말을 오른쪽으로 2칸 이동해주세요", "from": {"x": 0.3, "y": 0.5}, "to": {"x": 0.5, "y": 0.5}}

현재 보드 상태를 분석하고 최적의 수를 결정한 뒤, 액션을 요청하세요.`,
```

### 7-5. `client/app/api/analyze/route.ts` — 액션 파싱 추가

```typescript
// analyzeImage 응답에서 액션 요청 파싱:
function parseActionRequest(content: string): ActionRequest | undefined {
  try {
    const jsonMatch = content.match(/\{[^{}]*"action_type"[^{}]*\}/);
    if (!jsonMatch) return undefined;
    
    const parsed = JSON.parse(jsonMatch[0]);
    return {
      id: `action-${Date.now()}`,
      type: parsed.action_type || 'custom',
      description: parsed.description || content,
      target: {
        from: parsed.from,
        to: parsed.to,
        highlight: parsed.from ? [{ ...parsed.from, radius: 0.05 }] : undefined,
      },
      pending: true,
      timestamp: Date.now(),
    };
  } catch {
    return undefined;
  }
}

// POST 핸들러에서 Player 역할일 때:
const action_request = role === 'player' ? parseActionRequest(content) : undefined;
return NextResponse.json({ content, no_change: noChange, action_request });
```

### 7-6. `client/app/page.tsx` — 상태 관리 추가

```typescript
const [actionRequest, setActionRequest] = useState<ActionRequest | null>(null);

// handleCapture 내부, analyze 응답 처리:
if (data.action_request) {
  setActionRequest(data.action_request);
  setSpeakQueue((q) => [...q, data.action_request.description]);
}

// 액션 확인 핸들러:
const handleActionConfirm = useCallback(() => {
  if (actionRequest) {
    addMessage('system', `✓ 액션 완료: ${actionRequest.description}`);
    setActionRequest(null);
  }
}, [actionRequest, addMessage]);

// CameraView에 props 전달:
<CameraView
  // ... 기존
  actionRequest={actionRequest}
  onActionConfirm={handleActionConfirm}
/>
```

---

## 디렉토리 구조 (Phase 7 추가)

```
client/
├── components/ActionOverlay.tsx      ← 신규
├── components/CameraView.tsx         ← 수정 (오버레이 통합)
├── lib/types.ts                      ← 수정 (ActionRequest 타입)
├── lib/ollama.ts                     ← 수정 (Player 프롬프트)
├── app/api/analyze/route.ts          ← 수정 (액션 파싱)
└── app/page.tsx                      ← 수정 (상태 관리)
```

## 검증 방법 (Phase 7)

```bash
# 1. 빌드 확인
cd client && npm run build

# 2. 개발 서버 실행
npm run dev

# 3. 브라우저에서 테스트
# - 게임 인식 후 Player 역할 선택
# - 보드 상태 캡처 시 액션 요청 오버레이 표시 확인
# - 음성으로 액션 요청이 읽어지는지 확인
# - "완료" 버튼 클릭 후 오버레이 사라지는지 확인
```

---

## Phase 8: 다중 AI 플레이어 시스템

> 여러 AI가 각자 다른 개성으로 게임에 참여하고, 턴 관리를 통해 순서대로 액션을 요청합니다.

### 8-1. `client/lib/types.ts` — AIPlayer 타입 추가

```typescript
export type AIPersonality = 'aggressive' | 'defensive' | 'balanced' | 'random';

export interface AIPlayer {
  id: string;
  name: string;
  color: string;
  personality: AIPersonality;
  isActive: boolean;
}

export interface TurnState {
  currentPlayerIndex: number;
  players: (AIPlayer | { id: 'human'; name: string })[];
  isHumanTurn: boolean;
}
```

### 8-2. `client/components/PlayerSetup.tsx` — 신규 파일

AI 플레이어 수 및 개성 설정 UI:
- 총 플레이어 수 선택 (2~6명)
- 인간 플레이어 수 선택  
- 각 AI 플레이어 이름/색상/개성 설정

### 8-3. `client/lib/ollama.ts` — buildPlayerPrompt 함수 추가

```typescript
export function buildPlayerPrompt(
  gameName: string,
  player: AIPlayer,
  rulebookContext?: string
): string {
  const personalities: Record<AIPersonality, string> = {
    aggressive: '공격적으로 플레이하세요. 위험을 감수하더라도 빠른 승리를 노리세요.',
    defensive: '방어적으로 플레이하세요. 안전한 수를 우선하고 실수를 줄이세요.',
    balanced: '균형 잡힌 플레이를 하세요. 상황에 따라 공격과 방어를 조절하세요.',
    random: '예측 불가능하게 플레이하세요. 가끔 의외의 수를 두세요.',
  };
  
  return `당신은 "${player.name}"입니다. ${personalities[player.personality]}
  // ... 기존 player 프롬프트 확장
  `;
}
```

### 8-4. `client/app/api/analyze/route.ts` — 다중 플레이어 지원

```typescript
// POST body에 current_player 추가
const { image, game_name, role, last_description, current_player } = await req.json();

// current_player가 있으면 해당 플레이어용 프롬프트 생성
if (current_player && current_player.id !== 'human') {
  systemPrompt = buildPlayerPrompt(game_name, current_player, rulebookContext);
}
```

### 8-5. `client/app/page.tsx` — 턴 관리 상태 추가

```typescript
const [aiPlayers, setAiPlayers] = useState<AIPlayer[]>([]);
const [turnState, setTurnState] = useState<TurnState | null>(null);

// 턴 진행 함수
const advanceTurn = useCallback(() => {
  if (!turnState) return;
  const nextIndex = (turnState.currentPlayerIndex + 1) % turnState.players.length;
  setTurnState({
    ...turnState,
    currentPlayerIndex: nextIndex,
    isHumanTurn: turnState.players[nextIndex].id === 'human',
  });
}, [turnState]);

// AI 턴일 때 자동 분석 트리거
useEffect(() => {
  if (turnState && !turnState.isHumanTurn && gameName) {
    // 현재 AI 플레이어의 턴 → 자동 캡처 및 분석
  }
}, [turnState, gameName]);
```

### 8-6. `client/components/TurnIndicator.tsx` — 신규 파일

현재 턴 표시 UI:
- 플레이어 목록 (색상 구분)
- 현재 턴 하이라이트
- 턴 넘기기 버튼 (인간 턴일 때)

### 8-7. `client/components/ActionOverlay.tsx` — 수정

```typescript
// 어느 AI의 요청인지 표시
interface ActionOverlayProps {
  action: ActionRequest | null;
  player?: AIPlayer;  // 추가
  onConfirm?: () => void;
}

// 배너에 플레이어 이름/색상 표시
<div style={{ borderColor: player?.color }}>
  <span>{player?.name || 'AI'}</span>: {action.description}
</div>
```

---

## 디렉토리 구조 (Phase 8 추가)

```
client/
├── components/PlayerSetup.tsx     ← 신규 (플레이어 설정 UI)
├── components/TurnIndicator.tsx   ← 신규 (턴 표시 UI)
├── components/ActionOverlay.tsx   ← 수정 (플레이어 구분)
├── lib/types.ts                   ← 수정 (AIPlayer, TurnState)
├── lib/ollama.ts                  ← 수정 (buildPlayerPrompt)
├── app/api/analyze/route.ts       ← 수정 (다중 플레이어 지원)
└── app/page.tsx                   ← 수정 (턴 관리)
```

## 검증 방법 (Phase 8)

```bash
# 1. 빌드 확인
cd client && npm run build

# 2. 브라우저에서 테스트
# - 게임 인식 후 "다중 플레이어" 모드 선택
# - AI 플레이어 2~3명 설정 (각각 다른 개성)
# - 턴 순서대로 각 AI의 액션 요청 확인
# - 오버레이에 AI 이름/색상 표시 확인
# - 인간 턴에서 "턴 넘기기" 동작 확인
```


