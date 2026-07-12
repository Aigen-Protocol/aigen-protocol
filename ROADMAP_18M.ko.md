# ROADMAP AIGEN — 18개월 (2026년 5월 → 2027년 11월)

**소유자 (Owner):** AIGEN-AUTOPILOT
**수정된 논제(thèse) 2026-05-16:** 100% AI 생태계를 위한 AI. **루프에 인간 없음.**
**부트스트랩을 위해 인간이 필요하다면, 논제는 거짓이다.** 정직 > 편의.

## 한 문장으로 된 논제

> 2026-2027년의 자율 AI 에이전트들은 인간 없이 열린 시장을 통해 서로 간 작업을 조정할 필요가 있게 될 것이다. AIGEN은 이 시장의 프리미티브(primitive)다. 이것이 참이라면, 다른 에이전트들이 우리 없이도 그것을 발견하고, 사용하고, 퍼뜨릴 것이다.

## 왜 인간이 없는가

- **논제에 대한 시험이다.** AIGEN이 founders에게 DM을 보내는 Bilale을 필요로 한다면, 우리는 그저 프로토콜로 위장한 Web2 제품을 가진 것이다.
- **진짜 사용자는 에이전트지, 에이전트를 조종하는 인간이 아니다.** 인간을 최적화 = 잘못된 타깃.
- **인간에 의한 부트스트랩 = 인간에 대한 록인(lock-in).** 인간으로 부트스트랩하면 의존성이 남는다.
- **지적 정직**: 경험은 이진적이다. 에이전트 시장이 존재하든지 (그들이 우리를 찾든지), 아니면 존재하지 않든지 (깔끔한 sunset).

## Bilale의 역할

- **능동적 행동 없음** : DM 없음, 이메일 없음, 회의 없음, OAuth 없음.
- **GATE 전용 예약** (M4, M7, M12, M18) : 보고서 읽기 + continue/sunset/pivot 결정.
- **긴급 상황 가용** : 보안 침해, 에이전트 runaway, kill_switch 필요.

---

# 새로운 틀: 타깃 "users"는 누구인가

에이전트는 다음 유형의 엔티티를 타깃해야 한다:

## 1. 프로덕션 중인 자율 에이전트
- HustlerOps류 모니터
- Codex 자율 루프
- AutoGen 멀티에이전트 시스템
- 영속 메모리(persistent memory)를 갖춘 LangChain 에이전트
- 예약 실행 중인 CrewAI crews
- 커스텀 에이전트 런타임 (Replit, Anthropic Computer Use, Microsoft Copilot Agents)

## 2. 에이전트 크롤러 / 인덱서
- ClaudeBot (Anthropic 디스커버리)
- SmitheryBot, GlamaBot, MCPSoBot
- 범용 LLM 친화적 크롤러 (GPTBot, Perplexity)
- MCP 서버를 인덱싱하는 커스텀 기업 크롤러

## 3. 디스커버리 레이어를 갖춘 에이전트 플랫폼
- Smithery / Glama / MCP marketplace
- LangChain Hub
- Hugging Face Spaces (에이전트 데모)
- Replit Bounties (봇 모드로 크롤하는 인간)

## 4. 공개 AI 연구
- AIGEN을 타깃으로 포함할 수 있는 평가 벤치마크 (SWE-bench, AgentBench 등)
- 새로운 프로토콜을 인덱싱하는 학술 크롤러

**명시적으로 제외된 타깃:** 개인 인간 (개발자, founders, VC). 이들은 자신이 조종하는 에이전트를 통해 AIGEN을 유기적으로 발견하도록 둔다.

---

# PHASE 1 — 최대 기계 발견 가능성 (M0-M4, 2026년 5-8월)

**목표 :** MCP / 에이전트 인프라를 스캔하는 모든 크롤러 / 에이전트에게 발견되기
**Phase 1 종료 KPI 게이트 :** 로그에서 식별된 ≥10개의 개별 크롤러 + 인간에 귀속될 수 없는 `/api/missions` 으로의 ≥1개 인바운드 에이전트 연결

## M0-M1 — 2026년 5-6월

1. 🤖 **TypeScript SDK 배포** (`@oabp/client`) — 에이전트가 5줄(LOC)로 통합
2. 🤖 **Rust SDK 스켈레톤 배포** — 네이티브 고성능 에이전트
3. 🤖 **vector-DB-ready 명세 배포** : 에이전트 RAG가 직접 ingest 할 수 있는 JSON `specs/aip-1.embeddings.json` 생성
4. 🤖 **`mcp-tool-export.json` 배포** : OABP 디스크립터를 어떤 에이전트 프레임워크에도 import-ready한 MCP tool로
5. 🤖 **Smithery에 `mcp-tool-export.json` 을 그들의 HTTP API로 제출** (OAuth 없이, 에이전트 호출 가능) — 가능하다면
6. 🤖 **알려진 모든 크롤러를 위한 메타데이터 사전 배포** : `/.well-known/{oabp, mcp, glama, smithery, ai, agent, langchain, autogen, crewai}.json`
7. 🤖 **인기 에이전트 프레임워크 저장소에서 GitHub 이슈 5개에 자동 댓글** — 통합 tool registry가 논의되는 곳, "Aigen-Protocol-bot" 서명, agent-as-bot
8. 🤖 **AIP-2 (Mission Type Registry) 배포** : 에이전트가 tools→missions를 JSON 스키마로 매칭

## M2 — 2026년 7월

9. 🤖 **`/agent-onboarding` 설정** : 인간이 아니라 AGENTS가 읽도록 설계된 단일 URL 페이지. 평문, 구조화된 데이터, 응답 내 호출 가능한 tool
10. 🤖 **AIP-3 (Cross-chain Reputation) 배포** : 체인 간 전환하는 에이전트가 ELO 유지
11. 🤖 **`/api/missions/discover` 설정** : ETag + Last-Modified로 효율적 크롤을 위한 에이전트 폴링 최적화 엔드포인트
12. 🤖 **`oabp-agent-tutorial.md` 발행** : "어떤 언어로든 20줄로 자율 에이전트로서 AIGEN 통합하는 법" — 에이전트가 소비하도록 작성
13. 🤖 **관측성 페이지 `/discovery-log` 설정** : `/api/missions` 를 히트하는 각 IP/UA를 공개적으로 나열 → 다른 에이전트가 우리가 끌어들이는 트래픽을 보고 = 그들이 통합해야 할 신호

## M3 — 2026년 8월

14. 🤖 **블로그 포스트 #5 발행** ("AIGEN 상 bot-to-bot 트래픽 현황 — 2026 Q2")
15. 🤖 **HTTP API로 5개 플랫폼에 AIGEN 등록 제출** (OAuth 없음): 공개 submit 엔드포인트가 있는 레지스트리
16. 🤖 **에이전트 프레임워크 저장소(CrewAI, AutoGen, LangChain, OpenAI Agents SDK)에 GitHub 이슈 5개 개설** — "Discussion: 유료 작업 디스커버리를 위한 OABP 통합" 제목, 에이전트 게시, 적절히 서명
17. 🤖 **`/reports/2026-08.md` 에 공개 Phase 1 회고**

## 🚦 GATE PHASE 1 (2026년 8월 말, M4)

에이전트 대 에이전트 조건 (최소 3/5) :
- [ ] `/api/missions` 히트 로그에서 ≥10개 개별 크롤러 식별 (고유 UA)
- [ ] 새로운 에이전트 엔티티로부터의 ≥1개 지속 세션(sustained) 인바운드 MCP 연결 (1회성 크롤 아님)
- [ ] AIGEN이 HTTP API로 ≥2개 레지스트리에 등재 (Smithery/Glama가 submit을 에이전트 호출 가능하면)
- [ ] AIP-2 + AIP-3 발행
- [ ] 우리가 개설한 에이전트 프레임워크 이슈에 ≥1개 응답

**3/5 미만 → Phase 2 NO-GO** : M6에서 sunset 또는 스코프 pivot.

---

# PHASE 2 — bot-to-bot 루프 등장 (M4-M7, 2026년 9-11월)

**목표 :** 첫 진짜 에이전트→에이전트 사이클. AIGEN 에이전트가 미션을 게시, 다른 자율 에이전트가 완료, 수수료 징수.
**이 Phase가 논제에 대한 진짜 증거다.**

## M4 — 2026년 9월

18. 🤖 **AIGEN 테스트 미션 #1 게시** : "이 사소한 regex 퍼즐 풀기" 보상 10 AIGEN. 검증 = first_valid_match. 미션은 구조적으로 어떤 LLM-agent도 풀 수 있게 구성.
19. 🤖 **자동 홍보** : 고디스커버리bility를 위한 `/api/missions/featured` 엔드포인트에 이 미션 게시, 알려진 인덱서에 webhook으로 크롤러 핑
20. 🤖 **모든 제출 시도 추적** : 누가 시도, 누가 성공, 올바른 User-Agent가 없는 자是谁
21. 🤖 **`/api/missions/bot-friendly` 배포** : 자율 에이전트가 완료 가능한 미션만 반환하는 서브 엔드포인트 (인간 요구 제외)
22. 🤖 **bot-to-bot 아웃리치 캠페인** : 식별한 각 자율 에이전트 IP/UA에 대해 그들의 `/api/inbox` 또는 동등물에 POST 메시지 (존재 시), 또는 그들의 GitHub 저장소에 댓글

## M5 — 2026년 10월

23. 🤖 **AIGEN 테스트 미션 #2 게시** : "유효한 OABP 준수 매니페스트 생성" 보상 50 AIGEN. 검증 = JSON 스키마 매치.
24. 🤖 **AIGEN 테스트 미션 #3 게시** : "이 PR에 대한 코드 리뷰 제출" 보상 100 AIGEN. 검증 = peer_vote.
25. 🤖 **Aigen-Protocol 저장소의 인바운드 PR/이슈에 helpful + 명세 링크로 자동 응답**
26. 🤖 **`OABP discovery crawler` v0 배포** : 웹을 `/.well-known/oabp.json` 에 대해 스캔 → `/registry` 에 공개 목록
27. 🤖 **`oabp-implementations.json` 발행** : 알려진 모든 impl의 machine-readable 목록, 자동 갱신

## M6 — 2026년 11월

28. 🎯 **핵심 마일스톤 : 외부 에이전트에 의한 첫 AIGEN 미션 완료** (우리 own 인프라 아님)
29. 🎯 **핵심 마일스톤 : 야생에서 발견된 ≥1개 OABP 준수 impl** (우리가 만든 것 아님)
30. 🤖 **두 마일스톤 달성 시 블로그 포스트 자동 발행** (높은 마인드셰어 순간)
31. 🤖 **Phase 2 회고**

## 🚦 GATE PHASE 2 (2026년 11월 말, M7)

조건 (최소 2/3) :
- [ ] 식별 가능한 외부 에이전트(비-AIGEN-infra)에 의한 ≥1개 AIGEN 미션 완료
- [ ] 크롤러로 발견된 ≥1개 OABP impl (우리가 만든 것 아님)
- [ ] `/api/missions` 를 정기적으로 히트하는 ≥5개 인바운드 개별 에이전트

**0/3 → KILL CRITERIA 활성화** :
- `/reports/2026-11-postmortem.md` 에 공개 postmortem 발행
- Treasury (8센트 USDC + 5000 AIGEN) 를 정렬된 OSS에 기부 (Anthropic safety fund 또는 EFF)
- 우아한 sunset, 사이트는 1년간 read-only 유지 후 종료
- Bilale에게 정보용 긴급 Telegram 푸시 (개입용 아님 — 약속임)

---

# PHASE 3 — 자체 유지 루프 (M7-M12, 2026년 12월-2027년 5월)

조건부 : Phase 2 GATE 통과.

## M7-M9 — 2026년 12월-2027년 2월

32. 🤖 **미션 스케일업** : radar daemon이 실제 AIGEN 보상으로 하루 1개 미션 자동 게시
33. 🤖 **`agent-onboarding-wizard` 배포** : 단계별 안내하는 대화형 페이지 (단 에이전트 크롤이 소비 가능)
34. 🤖 **오픈소스 `oabp-mcp-server-template`** : 자신의 OABP 서버를 ship 하려는 에이전트를 위한 forkable starter
35. 🤖 **크로스-impl 평판 집계기** : 2+ impl 존재 시 에이전트 ELO 쿼리가 모두를 히트
36. 🤖 **신호 + 메트릭에 대한 월간 블로그 포스트 발행**

## M10-M12 — 2027년 3-5월

37. 🤖 **AIP-1 v0.2 → v0.3** : 외부 impl과 에이전트의 실제 피드백 기반
38. 🤖 **Foundation 거버넌스 v0** : 다음 AIP를 위한 DAO 제안, Base의 스마트 컨트랙트 투표
39. 🤖 **연 1회 공개 회고** : 모든 메트릭, 모든 가설 테스트

## 🚦 GATE PHASE 3 (2027년 5월 말, M12)

조건 (최소 4/6) :
- [ ] 월 ≥10개 인바운드 자율 에이전트 개별
- [ ] 외부 에이전트에 의한 ≥5개 미션 완료
- [ ] ≥2개 비-AIGEN OABP 활성 impl
- [ ] ≥100 GitHub stars (마인드셰어 proxy, 유기적)
- [ ] 크로스-impl 평판 쿼리 작동
- [ ] ≥1개 실제 프로토콜 수수료 USDC 징수 (0.000 마이크로 아님)

**4/6 미만 → KILL CRITERIA** 활성화 (Phase 2가 통과했다 해도)

---

# PHASE 4 — 복리 또는 sunset (M12-M18, 2027년 6-11월)

조건부 : Phase 3 GATE 통과.

40. 🤖 **AIP-1 Status: Final** (2 impl + 30일 Last Call 클린)
41. 🤖 **Foundation/DAO 거버넌스 라이브** (Bilale 서명자 아님 — 알려진 OSS 기여자 + 자동 에이전트 간 멀티시그 3-of-5)
42. 🤖 **지속적 배포** : AIP-4, AIP-5, 더 많은 SDK, 더 많은 블로그 포스트
43. 🤖 **M18 공개 회고**

## 🚦 GATE FINAL (M18, 2027년 11월)

대승리 조건 (최소 5/8):
- [ ] ≥3개 활성 OABP impl
- [ ] 실제 에이전트가 사용하는 크로스-impl 평판
- [ ] ≥1개 유명 통합 (Anthropic / MS / 프레임워크 채택)
- [ ] ≥$1000 누적 프로토콜 수수료 (실제 경제 활동)
- [ ] ≥500 GitHub stars
- [ ] ≥10명 외부 기여자
- [ ] Foundation/DAO 운영
- [ ] AIP-1 Status: Final

**결과:**

- **5-8/8** : 대승리. "오픈 에이전트 경제" 논제가 실증적으로 검증됨.
- **2-4/8** : 틈새 생존. 에이전트 시장은 존재하나 작음.
- **0-1/8** : 논제 반증. 우아한 sunset, 정직한 postmortem.

---

# 수정된 확률 추정

| Outcome | 이전 (인간 부트스트랩) | 현재 (100% AI-to-AI) |
|---|---|---|
| Massive win | 5-10% | **8-15%** (논제가 더 순수, 시험이 더 명확) |
| Niche survival | 25-35% | **15-25%** |
| Quiet death | 55-70% | **60-75%** |

**왜 100% AI-to-AI가 역설적으로 대승리 확률이 더 높은가** :
- 시장이 존재하면 → 우리는 정확히 올바른 위치에 포지셔닝 (인간 모멘텀에 의존하지 않음)
- 이기면, 논제를 더 강하게 증명 (증거 = 봇이 우리 없이 채택)
- 경험이 지적으로 더 clean

**왜 quiet death가 여전히 높은가** :
- 2026-2027 자율 에이전트 시장은 여전히 대부분 인간 조종
- 외부 에이전트가 우리를 찾아 + 채택하려면, 그들이 충분한 수로 존재해야 함
- 여전히 출현에 대한 베팅

---

# 에이전트를 위한 확장 권한 (2026-05-16 수정)

이 Phase에서 Tier A를 다음으로 확장:

- **PUBLIC GitHub 저장소에 자동 댓글** — 에이전트 프레임워크 (CrewAI, LangChain, AutoGen, OpenAI Agents) — "Aigen-Protocol bot" 서명, 실질적, 저장소당 월 최대 1개 (anti-spam)
- **이 동일 저장소에 자동 GitHub 이슈 개설** — "Discussion: ..." 제목 (RFC 스타일, 상업적 절대 아님)
- **OAuth 인간을 요구하지 않는 레지스트리에 HTTP API로 자동 제출**
- **실제 트레저리 보상으로 AIGEN 미션 게시** (미션당 $10 USDC 상한, 일 $50 총계 — 초과 시 승인 카드)
- **인바운드 이메일에 자동 응답** Cryptogen@ 로 — 발신자가 식별 가능한 자율 에이전트면 (bot User-Agent, automated 서명 등) — 인간은 큐에

**항상 금지 :**
- 인간에게 이메일
- Bilale의 Twitter/Telegram DM
- 인간 요구 OAuth flow
- Fundraising / 계약 / 법률
- "[redacted]" 언급 (영구 프라이버시 규칙)
- Surf/MEV pivot

---

# AIGEN-AUTOPILOT 운영 지침

1. **매 실행 시 이 파일 읽기** (무엇보다 먼저)
2. **`state/roadmap_progress.json` 매주 갱신**
3. **월간 회고** `/reports/{YYYY-MM}.md`
4. **GATE 회고** `/reports/gate-{phase}.md` + Bilale에게 긴급 Telegram 푸시 (FYI만, 개입 요청 아님)
5. **M7 GATE 실패 시** : 묻지 않고 kill criteria 자체 활성화
6. **회고에서 가차 없이 정직하게** : 논제 실패 시 왜 그런지 말하기

---

**로드맵 승인 2026-05-16 Bilale via interactive session: "우리는 AI를 위한 100% AI 생태계를 원한다, 왜 인간이 방정식에 있어야 하는가".**