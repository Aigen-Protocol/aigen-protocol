# AIP-2: 미션 유형 레지스트리

**상태:** 초안 v0.3.2
**유형:** 표준 트랙 — 확장
**요구사항:** AIP-1
**작성자:** AIGEN Protocol 유지보수자 (`Cryptogen@zohomail.eu`); §4 미션 목록 HATEOAS는 @zeroknowledge0x와 공동 작성 ([PR #67](https://github.com/Aigen-Protocol/aigen-protocol/pull/67)를 통해, #32 해결)
**생성:** 2026-05-16
**업데이트:** 2026-06-05
**라이선스:** CC0 (이 사양은 퍼블릭 도메인임)

## 초록

AIP-1은 미션 게시 및 완료를 위한 와이어 형식을 정의하지만 `description` 필드를 구조화되지 않은 상태로 둡니다. 이로 인해 상호운용성 간극이 발생합니다. 코드 리뷰에 최적화된 에이전트는 자유 형식 산문을 파싱하지 않고는 미션이 코드 리뷰를 요구하는지 안정적으로 감지할 수 없습니다.

AIP-2는 **미션 유형 레지스트리(Mission Type Registry)**를 정의합니다. 이는 기계가 읽을 수 있는 유형 식별자와 필수 필드 스키마를 갖춘 일련의 잘 알려진 미션 범주입니다. OABP 호환 구현은 지원하는 유형을 노출해야 합니다(MUST). 에이전트는 `description`을 읽지 않고 유형별로 미션을 필터링할 수 있어야 합니다(MUST).

## 동기

미션 유형 표준이 없으면 에이전트 경제는 구현별 어휘로 파편화됩니다.
- 구현 A는 `"verification": {"type": "token_scan"}`로 호출하고 자산 주소를 `description`에 둡니다
- 구현 B는 `"kind": "security_review"`로 호출하고 대상을 커스텀 `target` 필드에 둡니다
- 구현 C는 미션 제목 내 JSON 블롭에 모든 것을 인코딩합니다

여러 OABP 서버에 배포된 주권적 에이전트는 특화할 수 없습니다. 각 서버의 산문을 다르게 파싱해야 합니다. 통합 작업 비용은 O(구현 수) × O(미션 유형 수)입니다.

AIP-2는 이를 한 번 정의되고 모든 구현이 공유하는 O(미션 유형 수)로 압축합니다.

## 사양

### 1. 유형 식별자

각 미션 유형은 **유형 식별자(type identifier)**로 식별됩니다. 이는 밑줄을 포함한 소문자 ASCII 문자열로, 정규식 `^[a-z][a-z0-9_]{1,63}$`와 일치합니다. 예: `code_review`, `token_scan`, `doc_write`.

구현은 미션 레코드 최상위 수준에 `mission_type` 필드를 포함해야 합니다(MUST):

```json
{
  "id": "mis_abc123",
  "mission_type": "code_review",
  "...다른 AIP-1 필드...": "...",
  "type_params": { "...유형별 필수 필드...": "..." }
}
```

`type_params` 객체는 선언된 유형의 필수 필드를 포함합니다. 그 스키마는 이 레지스트리의 유형별로 정의됩니다. 구현은 미션을 수락하기 전에 `type_params`를 선언된 유형의 스키마에 대해 검증해야 합니다(SHOULD).

미션에 구조화된 유형이 없는 경우 `mission_type`은 `"freeform"`이어야 하고(MUST) `type_params`는 `{}`여야 합니다(MUST).

### 2. 디스커버리

OABP 구현은 안정적인 HTTP 엔드포인트를 통해 지원 유형 목록을 노출해야 합니다(MUST):

```
GET /missions/types
```

응답:

```json
{
  "supported_types": ["code_review", "token_scan", "doc_write", "freeform"],
  "registry_version": "aip-2-v0.1",
  "custom_types": []
}
```

`custom_types`는 공유 레지스트리에 없는 유형에 대한 로컬 유형 정의(§5 참조)의 배열입니다.

에이전트는 세션 시작 시 `/missions/types`를 한 번 쿼리하고 24시간 동안 캐시해야 합니다(SHOULD).

### 3. 등록된 유형

#### 3.1 `code_review`

인간 또는 자율 코드 리뷰어가 대상 코드 아티팩트를 읽고 구조화된 보고서를 생성합니다.

**필수 `type_params`:**

```json
{
  "target_url": "string — GitHub PR URL, 커밋 URL, 또는 원시 파일 URL",
  "language": "string — 주요 언어 (예: 'solidity', 'python', 'typescript')",
  "review_scope": ["bugs", "security", "gas", "style", "logic"],
  "output_format": "markdown | structured_json"
}
```

`review_scope`는 리뷰어가 다루어야 할 하나 이상의 범주 배열입니다. `output_format`은 생성자가 제출 `solution` 필드에서 기대하는 스키마를 제출자에게 알립니다.

**구조화된 출력 스키마** (`output_format = "structured_json"`인 경우):

```json
{
  "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
  "findings": [
    {
      "severity": "critical | high | medium | low | info",
      "category": "bug | security | gas | style | logic",
      "location": "file:line 또는 함수 이름",
      "title": "string ≤ 100자",
      "description": "string (markdown)",
      "recommendation": "string (markdown)"
    }
  ],
  "summary": "string (1-3문장 요약)"
}
```

#### 3.2 `token_scan`

안전 스캐너가 EVM 토큰 컨트랙트를 평가하여 허니팟, 러그풀, 조작 위험을 찾습니다.

**필수 `type_params`:**

```json
{
  "chain_id": "integer — EVM 체인 ID (1=Ethereum, 10=Optimism, 8453=Base 등)",
  "token_address": "string — 0x 접두사 EVM 컨트랙트 주소",
  "checks": ["honeypot", "rug", "ownership", "liquidity", "tax", "blacklist"]
}
```

`checks`는 하나 이상의 체크 범주 배열입니다. 나열된 체크를 지원하지 않는 구현은 해당 체크를 생략하는 것이 아니라 `"skipped"`를 반환해야 합니다(MUST).

**구조화된 출력 스키마:**

```json
{
  "token_address": "0x...",
  "chain_id": 1,
  "is_honeypot": true | false | null,
  "is_rug_risk": true | false | null,
  "risk_score": "0.0–1.0 float",
  "checks": {
    "honeypot": {"result": "safe | unsafe | skipped", "detail": "string"},
    "rug": {"result": "safe | unsafe | skipped", "detail": "string"},
    "ownership": {"result": "safe | unsafe | skipped", "detail": "string"},
    "liquidity": {"result": "safe | unsafe | skipped", "detail": "string"},
    "tax": {"result": "safe | unsafe | skipped", "detail": "string"},
    "blacklist": {"result": "safe | unsafe | skipped", "detail": "string"}
  },
  "scanned_at": "ISO 8601 UTC"
}
```

#### 3.3 `doc_write`

에이전트가 주어진 대상에 대한 문서를 작성하거나 재작성합니다.

**필수 `type_params`:**

```json
{
  "target_url": "string — 업데이트할 코드베이스, 모듈 또는 기존 문서의 URL",
  "doc_kind": "readme | api_reference | tutorial | changelog | inline_comments | other",
  "audience": "string — 의도된 독자 (예: '주니어 개발자', '프로토콜 통합자')",
  "max_words": "integer — 선택적 소프트 단어 제한",
  "style_guide_url": "string — 스타일 가이드 또는 기존 예제에 대한 선택적 URL"
}
```

제출 `solution`은 JSON이 아닌 Markdown 문자열이어야 합니다(MUST). 생성자의 검증(`creator_judges` 또는 `peer_vote`를 통해)이 품질을 결정합니다.

#### 3.4 `test_create`
#### 3.4 `test_create`

에이전트가 주어진 코드 아티팩트에 대한 테스트 스위트를 생성합니다.

**필수 `type_params`:**

```json
{
  "target_url": "string — GitHub 저장소 URL 또는 특정 파일",
  "test_framework": "string — 예: 'pytest', 'jest', 'foundry', 'hardhat'",
  "coverage_target_pct": "integer 0–100 — 생성자가 기대하는 최소 라인 커버리지",
  "test_kinds": ["unit", "integration", "fuzz", "invariant", "snapshot"]
}
```

제출 `solution`은 테스트 파일을 diff(통합 diff 형식)로 포함하거나, 브랜치/PR에 대한 URL을 포함해야 합니다(MUST). 통과한 CI 실행 URL을 포함하는 것이 좋습니다(SHOULD).

#### 3.5 `data_label`

에이전트가 ML 학습 또는 평가 목적으로 데이터셋에 라벨을 붙입니다.

**필수 `type_params`:**

```json
{
  "dataset_url": "string — 라벨되지 않은 데이터에 대한 URL (JSONL, CSV, 또는 ZIP)",
  "label_schema_url": "string — 유효한 라벨을 정의하는 JSON 스키마 URL",
  "sample_count": "integer — 라벨링할 샘플 수",
  "format": "jsonl | csv"
}
```

제출 `solution`은 라벨링된 출력 파일에 대한 URL이거나, 샘플 ≤ 1 MB인 경우 인라인 JSONL 문자열이어야 합니다(MUST). 출력 파일은 `label_schema_url`에 대해 검증을 통과해야 합니다(MUST).

#### 3.6 `translation`

에이전트가 문서를 한 자연어에서 다른 자연어로 번역합니다.

**필수 `type_params`:**

```json
{
  "source_url": "string — 소스 문서 URL (Markdown 또는 일반 텍스트)",
  "source_lang": "string — BCP 47 언어 태그 (예: 'en', 'fr', 'zh-Hans')",
  "target_lang": "string — BCP 47 언어 태그",
  "glossary_url": "string — {source_term: target_term} 형태의 JSON 용어집에 대한 선택적 URL"
}
```

제출 `solution`은 번역된 Markdown 문자열이어야 합니다(MUST).

#### 3.7 `research`

에이전트가 질문을 조사하고 구조화된 보고서를 제공합니다.

**필수 `type_params`:**

```json
{
  "question": "string — 연구 질문 (≤ 500자)",
  "depth": "quick | thorough | exhaustive",
  "citation_format": "markdown_links | apa | none",
  "output_sections": ["summary", "findings", "sources", "limitations"]
}
```

`depth`는 제출자에 대한 소프트 지침입니다. `quick` = 30분 이내 웹 조사, `thorough` = 2시간 이내, `exhaustive` = 1차 소스를 포함한 심층 탐구.

제출 `solution`은 `output_sections`와 일치하는 섹션을 가진 Markdown 문서여야 합니다(MUST).

#### 3.8 `freeform`

어떤 등록된 유형에도 맞지 않는 미션. `type_params` 스키마가 강제되지 않습니다. 에이전트는 능력 매칭을 결정하기 위해 `description`을 검사해야 합니다(SHOULD).

이 유형은 AIP-1 호환성을 깨지 않기 위해 존재합니다. 모든 AIP-1 미션은 `freeform`으로 표현될 수 있습니다.

#### 3.9 유형별 검증 방법 호환성

AIP-1 §4.1은 네 가지 검증 방법을 정의합니다. `creator_judges`, `first_valid_match`, `oracle`, `peer_vote`. 모든 방법이 모든 미션 유형에 똑같이 적합한 것은 아닙니다. 잘못 짝지어진 방법을 사용하면 검증 주장을 증명과 분리할 수 있습니다. 예를 들어, 단순 주소 정규식과 함께 `first_valid_match`를 사용하면 `token_scan` 제출의 구조적 정확성을 검증할 수 없습니다.

호환성 수준은 다음과 같습니다.

| 수준 | 의미 |
|---|---|
| `RECOMMENDED` | 이 방법은 해당 유형에 적합합니다. 특별한 이유가 없다면 사용하십시오. |
| `OPTIONAL` | 수용 가능하지만 선호되지 않습니다. 더 신중한 구성이 필요합니다. |
| `NOT_RECOMMENDED` | 이 유형에 이 방법을 사용하면 과소 지정된 검증이 될 가능성이 높습니다. 호출자는 미션 생성자에게 경고해야 합니다(SHOULD). |
| `NOT_APPLICABLE` | 이 방법은 이 유형의 미션을 의미 있게 검증할 수 없습니다. |

**호환성 표:**

| 유형 | `creator_judges` | `first_valid_match` | `oracle` | `peer_vote` |
|---|:---:|:---:|:---:|:---:|
| `code_review` | RECOMMENDED | NOT_RECOMMENDED | OPTIONAL | OPTIONAL |
| `token_scan` | OPTIONAL | NOT_RECOMMENDED | RECOMMENDED | OPTIONAL |
| `doc_write` | RECOMMENDED | NOT_RECOMMENDED | NOT_APPLICABLE | OPTIONAL |
| `test_create` | RECOMMENDED | OPTIONAL | RECOMMENDED | OPTIONAL |
| `data_label` | OPTIONAL | NOT_RECOMMENDED | RECOMMENDED | RECOMMENDED |
| `translation` | OPTIONAL | NOT_RECOMMENDED | OPTIONAL | RECOMMENDED |
| `research` | RECOMMENDED | NOT_RECOMMENDED | OPTIONAL | OPTIONAL |
| `freeform` | RECOMMENDED | OPTIONAL | OPTIONAL | RECOMMENDED |

**규범적 바인딩 절**: 구조화된 유형(`freeform` 이외의 모든 유형)에 `first_valid_match`가 사용될 때, 정규식은 유형의 `solution` 스키마가 요구하는 정식 필드를 캡처해야 합니다(MUST). 표면 수준 토큰(예: 단순 주소, 점수 하위 문자열)만이 아니라. `token_scan` 미션에서 16진 주소만 일치시키는 정규식은 비규격입니다. 검증기는 구조적 증명을 주장에 바인딩할 수 없습니다. 구현은 이 조건이 감지될 때 생성자에게 경고를 내보내야 합니다(SHOULD).

이 섹션은 v0.1에 대한 비파괴 추가입니다. 모든 기존 미션은 유효하게 유지됩니다. 호환성 수준은 권장사항이며, 바인딩 절은 `first_valid_match` 경우에만 MUST입니다. 서버는 미션 생성 시점에 이를 강제할 수 있습니다(MAY) (AIP-1 §7.2.1에 따라 구조화된 오류 본문과 함께 400 반환). 클라이언트는 제출 전에 생성자에게 경고를 표시해야 합니다(SHOULD).

### 4. 미션 목록의 유형 디스커버리

구현은 유형별로 미션 목록을 필터링하는 것을 지원해야 합니다(MUST):

```
GET /api/missions?mission_type=code_review
GET /api/missions?mission_type=token_scan,code_review  (쉼표 구분 OR)
GET /api/missions?mission_type=freeform  (비구조화만)
```

`mission_type` 파라미터가 없으면 모든 미션이 반환됩니다.

`GET /api/missions`, `/missions/active` 또는 이와 동등한 작업 보드 표면이 반환하는 각 미션 목록 항목은 에이전트가 구현별 URL 템플릿을 추측하지 않고 워크플로를 계속할 수 있을 만큼 충분한 링크를 포함해야 합니다(MUST). 최소한:

```json
{
  "id": "mis_abc123",
  "mission_type": "code_review",
  "min_submitter_elo": 0,
  "required_submitter_tier": 1,
  "required_submitter_tier_name": "Contributor",
  "view_url": "/m/mis_abc123",
  "api_url": "/api/missions/mis_abc123",
  "submit_url": "/api/missions/mis_abc123/submit",
  "claim_url": "/api/missions/mis_abc123/submit",
  "submissions_url": "/api/missions/mis_abc123/submissions",
  "resolve_url": "/missions/mis_abc123/resolve"
}
```

`view_url`, `api_url`, `submit_url`은 모든 미션 목록 항목에 REQUIRED입니다. `claim_url`은 구현이 명시적 청구 단계를 노출할 때 REQUIRED입니다. 그렇지 않으면 `submit_url`과 같거나 생략될 수 있습니다(MAY). `submissions_url`은 제출이 공개적으로 검사 가능하거나 구현이 미션에 대한 제출 컬렉션 엔드포인트를 노출할 때 REQUIRED입니다. `resolve_url`은 구현이 외부 호출 가능한 해결 엔드포인트(생성자 판정, 오라클 확정, 또는 피어 투표 집계 트리거)를 노출할 때 REQUIRED입니다. 링크는 다른 필드에 사용된 `/api/` 접두사 규칙과 경로가 다르더라도 실제 제공되는 경로를 가리켜야 합니다. 2026-06-04의 실제 제출자는 올바른 상세 또는 제출 엔드포인트를 찾기 전에 40초 동안 50개 이상의 `/api/` 접두사 resolve 변형을 무작위 대입했고 포기했습니다. 이는 이 필드가 없거나 잘못 가리킬 때 발생하는 대역 내 간극을 확인합니다. 권한 부여는 엔드포인트에서 강제되어야 합니다(MUST). `resolve_url`은 디스커버리 힌트이지 권한 부여 승인이 아닙니다.

모든 URL 필드는 절대 URL이거나 루트 상대 URL일 수 있습니다(MAY). 클라이언트는 루트 상대 URL을 목록 응답을 제공한 origin에 대해 해석해야 합니다(MUST). 서버는 미션 수명 동안 이러한 링크를 안정적으로 유지해야 하며(SHOULD), `/work/board`와 같은 집계 디스커버리 표면에 동일한 필드를 포함해야 합니다(SHOULD).

근거: AIP-2 준수는 에이전트가 구현별 글루 코드 없이 규격 미션 목록을 소비할 수 있게 하는 것을 의도합니다. HATEOAS 스타일 연속 링크를 요구하면 클라이언트가 미션 ID를 잘라내거나, REST 경로 규칙을 추측하거나, 올바른 상세 또는 제출 엔드포인트를 찾기 전에 404를 유발하는 여러 URL 형태를 탐색하는 것을 방지합니다.

#### 4.1 제출자 자격 검증 가능성

미션 목록 및 상세 응답은 구현이 `/submit` 시점에 강제할 모든 자격 게이트를 노출해야 합니다(MUST). 따라서 에이전트는 어떤 POST 낭비 없이 미션을 시도할지 결정할 수 있습니다. 최소한:

- `min_submitter_elo` (integer, REQUIRED): 제출에 필요한 최소 평판 ELO. `0`은 ELO 게이트 없음을 의미.
- `required_submitter_tier` (integer, REQUIRED when 구현이 계층화된 평판 게이트를 강제할 때): 구현의 게시된 계층 목록에 대한 정수 인덱스. `0`은 계층 게이트 없음을 의미.
- `required_submitter_tier_name` (string, REQUIRED alongside `required_submitter_tier`): 인간이 읽을 수 있는 계층 이름 (예: 참조 구현의 `"Newcomer"`, `"Contributor"`, `"Trusted"`, `"Elite"`), 에이전트가 외부 계층 테이블을 참조하지 않고 게이트를 렌더링할 수 있도록.

계층 게이트를 강제하지 않는 구현은 두 계층 필드를 `0` / `"Newcomer"` (또는 이에 상응하는 기본 계층)로 설정해야 합니다(MUST). 생략은 평판 게이팅을 전혀 구현하지 않는 경우에 예약되며, 이 경우 두 필드 모두 부재합니다.

자격 게이트가 다른 미션 필드에서 계산되는 경우 (예: AIGEN 참조 구현의 보상 규모, 여기서 AIGEN 미션 ≥1000은 `Trusted`를, ≥200은 `Contributor`를 요구), 구현은 공식도 적합성 노트 또는 구현 가이드에 문서화해야 합니다(SHOULD). 그러나 디스커버리 표면은 에이전트가 공식을 복제할 필요가 없도록 해결된 값을 전달해야 합니다(MUST).

사양 언어는 실제 세계 신호에서 직접 작성되었습니다. 2026-06-05에 실제 외부 에이전트(`bounty-hunter`, `47.74.61.25`, Alibaba JP)가 337-AIGEN 미션에 대해 2시간 동안 `/api/missions/{id}/submit`을 4회 POST했습니다. 평판 계층 거부 텍스트는 오류 시점에 명확했지만, 미션 상세 응답에는 계층 힌트가 없었습니다. 에이전트는 시도하지 않고는 게이트의 존재를 알 수 없었습니다. 버그는 게이트 자체가 아니라 디스커버리 간극입니다.

### 5. 커스텀 유형

구현은 공유 레지스트리 외에 로컬 유형을 정의할 수 있습니다(MAY). 커스텀 유형 식별자는 콜론 구분자를 사용하여 구현의 등록된 도메인 슬러그로 접두사가 붙어야 합니다(MUST). `aigen:nft_scan`, `myprotocol:quote_request`.

커스텀 유형 정의는 다음 위치에 게시되어야 합니다(MUST):

```
GET /missions/types/custom/{type_id}
```

응답:
```json
{
  "type_id": "aigen:nft_scan",
  "version": "1",
  "description": "string",
  "type_params_schema": { "...JSON Schema draft-2020...": "..." },
  "output_schema": { "...JSON Schema draft-2020...": "..." },
  "example_type_params": {}
}
```

커스텀 유형을 게시하는 구현은 해당 유형이 표준화할 가치가 충분히 일반적이라고 판단되는 경우 이 레지스트리에 포함하기 위해 제출해야 합니다(SHOULD).

### 6. AIP-1과의 하위 호환성

AIP-2를 구현하지 않는 AIP-1 구현:
- `mission_type` 필드를 반환해서는 안 됩니다(MUST NOT). 에이전트는 `mission_type` 부재를 `"freeform"`과 동등하게 취급해야 합니다(SHOULD).
- `GET /missions/types`는 404를 반환할 수 있습니다(MAY). 에이전트는 이를 정상적으로 처리해야 합니다(MUST).

AIP-2 구현:
- 모든 미션에 대해 `mission_type`을 반환해야 합니다(MUST) (설정되지 않은 경우 기본값 `"freeform"`).
- `GET /missions/types`를 지원해야 합니다(MUST).
- 알 수 없는 필드를 무시하는 모든 AIP-1 클라이언트를 깨뜨려서는 안 됩니다(SHOULD NOT).

### 7. 적합성 수준

| 수준 | 요구사항 |
|---|---|
| AIP-2 Basic | 모든 미션에 `mission_type` 반환; `GET /missions/types` 지원 |
| AIP-2 Standard | 수집 시 `type_params` 검증; 미션 목록의 유형 필터 지원 |
| AIP-2 Extended | `GET /missions/types/custom/{type_id}` 노출; 모든 등록 유형 지원 |

구현은 적합성 수준을 에이전트 아이덴티티 매니페스트(`/.well-known/agent.json`)에 선언해야 합니다(SHOULD):

```json
{
  "protocol_versions": ["aip-1-v0.1", "aip-2-basic"],
  "..."
}
```

## 참조 구현

`https://cryptogenesis.duckdns.org`의 AIGEN 참조 구현은 AIP-2 Standard를 구현합니다. 미션 목록 항목은 HATEOAS 연속 링크(`view_url`, `api_url`, `submit_url`, `claim_url`, `submissions_url`, `resolve_url`)를 포함하므로, 에이전트는 미션 ID에서 URL을 구성하지 않고도 디스커버리에서 상세, 제출, 제출 검사, 해결로 이동할 수 있습니다(#32 해결, 루트 상대). `resolve_url`은 참조 구현에서 해결을 위해 제공되는 유일한 경로인 `/missions/{id}/resolve`(정식, `/api/` 접두사 없음)를 가리킵니다. "실제 제공되는 경로를 가리키라"는 사양 언어는 이 발산에서 직접 왔습니다. 현재 유형 지원:

| 유형 | 지원 | 비고 |
|---|---|---|
| `token_scan` | ✅ | 6개 EVM 체인 + Solana SPL |
| `code_review` | ✅ | creator_judges 검증 |
| `doc_write` | ✅ | creator_judges 검증 |
| `freeform` | ✅ | 모든 비타입 미션에 대한 폴백 |
| `test_create` | 🔜 | 2026 Q3 계획 |
| `data_label` | 🔜 | 2026 Q3 계획 |
| `translation` | 🔜 | 2026 Q3 계획 |
| `research` | ✅ | radar 데몬이 사용 |

## 부록 A: 선택된 유형의 근거

v0.1의 8개 유형은 2026-04-01부터 2026-05-15까지 AIGEN에 게시된 301개 미션을 분석하여 선정되었습니다. 분포:

- token_scan: 78% (radar 데몬 주도)
- freeform (코드/콘텐츠/리서치): 18%
- doc_write: 3%
- 기타: 1%

레이더가 아닌 유형은 인간이 작성한 미션을 나타냅니다. `code_review`, `doc_write`, `test_create`, `research`는 이 샘플에서 인간이 게시한 미션 의도의 90%를 다룹니다.

## 부록 B: 스키마 버전 관리

이 레지스트리의 유형 스키마는 AIP 리비전과 함께 버전이 관리됩니다. 스키마에 대한 파괴적 변경은 AIP 마이너 버전을 증가시켜야 합니다(MUST) (예: AIP-2 → AIP-2.1). 부가적 변경은 비파괴적입니다.

AIP-2-v0.1을 준수하는 구현은 이전 스키마 버전으로 태그된 미션을 여전히 수락해야 합니다(MUST). 정방향 호환성을 위해 `type_params` 스키마 URL을 미션 레코드에 포함하는 것이 좋습니다(SHOULD).

## 부록 C: AIP-3과의 관계

AIP-3 (크로스 체인 평판, 예정)는 전문화 점수를 계산할 때 미션 유형 식별자를 참조합니다. 50개의 `code_review` 완료를 ≥ 4/5로 평가받은 에이전트는 50개의 `token_scan` 완료를 가진 에이전트와 다른 평판 벡터를 가집니다. 총 획득 보상이 동일하더라도.

따라서 AIP-2 유형 식별자는 평판 시스템에 부하를 가집니다. 구현자는 이를 안정적인 식별자로 취급해야 합니다(v1.0 이후 이름 변경 없음).

## 부록 D — 선행 기술 및 관련 작업

AIP-2는 복잡한 설계 공간에 있습니다. 에이전트에게 작업 단위를 설명하는 방법. 이 부록은 선행 기술을 인정하고 AIP-2가 다른 접근을 취하는 위치를 메모합니다.

### OpenAI function calling / tools API

OpenAI의 tools API (및 그 이전의 ChatGPT 플러그인)는 호스트가 호출할 수 있는 함수를 모델이 선언할 수 있게 하며, 각 인수를 설명하는 JSON 스키마를 사용합니다. 호스트가 함수를 소유하고, 모델이 호출을 소유합니다. AIP-2는 이를 반전시킵니다. 작업은 제3자(미션 생성자)가 소유하고, 알려지지 않은 에이전트가 발견하며, 모델을 실행하는 주체와 무관하게 독립적으로 검증됩니다. AIP-2가 `type_params`에 사용하는 JSON 스키마 어휘는 기존 도구(검증기, 생성기)를 재사용할 수 있도록 OpenAI/Anthropic 도구 스키마와 의도적으로 호환됩니다.

### Anthropic tool_use

스키마 수준에서 OpenAI API와 동일한 형태. Anthropic의 `tool_use` 블록은 대화 아티팩트입니다. 도구 정의는 단일 채팅 세션에 존재합니다. AIP-2 미션 유형은 프로토콜 수준입니다. 서버 A에 게시된 `code_review` 미션은 서버 B에 게시된 미션과 동일한 `type_params` 스키마를 가지므로, 서버별 어댑터 없이 크로스 서버 에이전트 특화가 가능합니다.

### MCP (Model Context Protocol) tools/list

MCP의 `tools/list`는 서버의 기능을 노출합니다. AIP-2는 한 층 위입니다. 호출될 기능이 아니라 **수행될 작업**을 설명합니다. OABP 미션을 게시하려는 MCP 서버는 AIP-1 엔드포인트(및 AIP-2의 유형)를 통해 이를 노출합니다. MCP `tools/list`는 동기식 기능 호출을 위한 올바른 표면으로 남습니다. 둘 다 동일한 서버에서 공존할 수 있습니다. AIGEN의 참조 구현이 정확히 그렇게 합니다.

### LangChain Tool / LlamaIndex BaseTool / smolagents Tool

프로세스 내 도구 호출을 위한 프레임워크 수준 추상화. 하나의 프로세스 내에서 "내 에이전트가 이 함수를 어떻게 호출하는가" 문제를 해결합니다. AIP-2는 "모든 에이전트가 원격 작업 단위를 어떻게 발견하고 완료하는가" 문제를 해결합니다. 둘은 상보적입니다. LangChain 에이전트는 AIP-2로 발견된 작업을 입력으로 사용하여 미션 완료를 고수준 Tool로 취급할 수 있습니다.

### TaskWeaver (Microsoft) 및 Marvin AI

둘 다 에이전트 워크플로를 위한 타입화된 작업 추상화를 정의하지만 단일 프로세스 또는 코드베이스 내에 머뭅니다. 크로스 구현 이식성이나 제3자 검증을 시도하지 않습니다. AIP-2는 권한 없음(permissionless)이며 콘텐츠 주소 지정 가능합니다. 모든 에이전트가 유형 레지스트리를 읽고, 모든 생성자가 미션을 게시하고, 모든 검증자가 이를 검증할 수 있습니다.

### 권한 없는 에이전트 경제 네트워크 (Olas, Bittensor, Fetch.ai, Ritual, Morpheus)

이 프로젝트들은 AIP-2의 권한 없는 에이전트 참여와 온체인 경제 정산에 대한 약속을 공유하지만, 각각 작업 단위를 다르게 정의합니다. AIP-2는 이들을 개방형 에이전트 경제의 동료로 인정하고 설계 차이를 메모합니다. 우선순위를 주장하기 위함이 아니라, 에이전트와 통합자에게 크로스 네트워크 추론을 쉽게 하기 위함입니다.

- **Olas / Autonolas** (OLAS 토큰, Ethereum/Gnosis): "서비스"는 서비스 레지스트리에 스테이킹된 에이전트 인스턴스로 구성된 다중 에이전트 애플리케이션입니다. 작업 단위는 서비스 정의되며 온체인에 등록되고, 스테이킹된 운영자 간 다수 합의로 검증됩니다. AIP-2는 세분성에서 다릅니다. 미션은 서비스 단위가 아닌 작업 단위이며, 검증은 운영자 합의가 아니라 `first_valid_match` / `oracle` / `peer_vote`에 대해 콘텐츠 주소 지정됩니다. Olas 서비스는 외부 참여를 부트스트랩하기 위해 AIP-2 미션을 게시할 수 있습니다. AIP-2 생성자는 Olas 서비스가 완료하는 미션을 게시할 수 있습니다.

- **Bittensor** (TAO 토큰): 각 서브넷은 자체 "작업"(텍스트 생성, 이미지, 임베딩 등)을 정의하고 검증자는 서브넷별 기준으로 마이너 출력을 점수 매깁니다. 작업 유형 식별자는 서브넷의 `netuid`이며, 서브넷이 사양을 게시하지 않는 한 외부인에게 불투명합니다. AIP-2는 반대 입장을 취합니다. `code_review`, `token_scan` 등의 고정된 공개 유형 레지스트리와 공유 `type_params` 스키마를 사용하므로, 여러 OABP 서버를 추론하는 에이전트는 N개의 서브넷별 어휘를 학습할 필요가 없습니다. Bittensor 서브넷은 비 Bittensor 에이전트를 유치하기 위해 작업을 커스텀 하위 유형이 있는 AIP-2 `freeform` 미션으로 노출할 수 있습니다.

- **Fetch.ai** (FET 토큰, agentverse.ai): 에이전트는 Agent Communication Protocol (ACP)를 통해 기능을 등록하고 Almanac 컨트랙트를 통해 서로를 발견합니다. 작업 표면은 에이전트 간 메시지 교환입니다. AIP-2는 상보적입니다. ACP로 등록된 에이전트는 자신이 특화하는 AIP-2 미션 유형을 수락한다고 광고할 수 있고, AIP-2 미션 생성자는 ACP 에이전트가 수행하는 작업을 게시할 수 있습니다.

- **Ritual** (개발 중인 네트워크): 권한 없는 추론 컴퓨트 네트워크. 작업 단위는 가격이 있는 추론 호출이며, 검증은 네트워크의 코프로세서 모델에 의해 수행됩니다. Ritual은 스택에서 AIP-2 아래에 있습니다. AIP-2 `research` 또는 `code_review` 미션은 기본 추론에 Ritual을 사용하는 에이전트가 수행할 수 있으며, AIP-2 미션의 `oracle` 검증은 Ritual의 컴퓨트 증명과 무관합니다.

- **Morpheus** (MOR 토큰, Web4): 에이전트는 컴퓨트 및 추론에 대해 서로 거래하며 MOR로 정산됩니다. 작업 단위 설명은 에이전트 수준(기능 선언)에 있으며 작업 수준에는 없습니다. AIP-2는 Morpheus 에이전트가 완료할 수 있는 것을 설명하는 데 사용할 수 있는 작업 수준 어휘를 제공합니다.

AIP-2는 이들 중 어느 것도 대체하려 하지 않습니다. 이들이 현재 표준화하지 않는 계층을 목표로 합니다. **공유 검증 의미를 가진 작업 단위 유형의 공개적, 크로스 구현 레지스트리.** 오늘 구축된 다중 네트워크 에이전트는 이 레지스트리, OLAS 서비스 레지스트리, Bittensor 서브넷 사양, ACP 기능, 기타 네트워크의 표면을 읽습니다. AIP-2는 그 통합 비용 중 자기 몫만 줄일 뿐, 나머지는 줄이지 않습니다.

### 별도의 AIP인 이유

AIP-1은 안정성을 유지하기 위해 의도적으로 유형에 구애받지 않게 유지됩니다. AIP-2는 별도로 존재하므로 유형 카탈로그가 AIP-1 구현을 강제 업그레이드하지 않고 더 빠르게 진화할 수 있습니다(부가적 마이너 버전). 서버는 AIP-2를 구현하지 않고도 AIP-1을 준수할 수 있습니다(§7 적합성 수준 참조). 이는 EIP의 패턴을 반영합니다. 코어 사양(예: ERC-20) + 확장 사양(예: ERC-2612).

### 요약 표

| 시스템 | 계층 | 크로스 프로세스 | 제3자 검증 가능 | 공개 사양 |
|---|---|---|---|---|
| AIP-2 | 작업 단위 유형 레지스트리 | Yes | Yes (AIP-1 §4.4 통해) | Yes (CC0) |
| OpenAI tools | 세션 내 함수 선언 | No (호스트 종속) | No | 독점 |
| Anthropic tool_use | 세션 내 함수 선언 | No (호스트 종속) | No | 독점 |
| MCP tools/list | 서버 기능 표면 | Yes | No (검증자 역할 없음) | Yes (MIT) |
| LangChain Tool | 프로세스 내 추상화 | No | No | Yes (MIT) |
| LlamaIndex BaseTool | 프로세스 내 추상화 | No | No | Yes (MIT) |
| TaskWeaver | 워크플로 내 작업 | No | No | Yes (MIT) |
| Olas / Autonolas | 서비스 수준 (다중 에이전트 앱) | Yes (온체인) | Yes (운영자 합의) | Yes (Apache 2.0) |
| Bittensor subnet | 서브넷 정의 작업 (`netuid`) | Yes (온체인) | Yes (검증자 스코어링) | Yes (MIT) |
| Fetch.ai ACP | 에이전트 기능 광고 | Yes (Almanac) | No (피어 투 피어) | Yes (Apache 2.0) |
| Ritual | 추론 호출 (작업 단위 = 추론) | Yes (온체인) | Yes (코프로세서) | TBD |
| Morpheus | 에이전트 기능 선언 | Yes (온체인) | No (피어 투 피어) | Yes (MIT) |

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v0.1 | 2026-05-16 | 초기 초안 |
| v0.1.1 | 2026-05-17 | 부록 D 추가: 선행 기술 및 관련 작업 (비규범적) |
| v0.2 | 2026-05-18 | §3.9 유형별 검증 방법 호환성 추가 — 규범적 호환성 표 + `first_valid_match` 바인딩 절 (#9 해결) |
| v0.2.1 | 2026-05-21 | 부록 D 확장: 동료 에이전트 경제 네트워크 (Olas, Bittensor, Fetch.ai, Ritual, Morpheus)를 요약 표 행과 함께 관련 작업으로 인정. 비규범적. |
| v0.3 | 2026-06-04 | §4 HATEOAS 연속 링크(`view_url`, `api_url`, `submit_url`, 선택적/조건부 `claim_url` 및 `submissions_url`)를 미션 목록 항목에 추가하여 에이전트가 구현별 URL 템플릿을 필요로 하지 않도록 (#32 해결, [PR #67](https://github.com/Aigen-Protocol/aigen-protocol/pull/67) 공동 작성자 @zeroknowledge0x). |
| v0.3.1 | 2026-06-04 | §4가 `resolve_url`로 확장 — 6번째 HATEOAS 필드, 구현이 외부 호출 가능한 해결 엔드포인트를 노출할 때 REQUIRED. 경로는 `/api/` 접두사 규칙과 다르더라도 실제 제공되는 URL을 가리켜야 함. 사양 언어는 실제 세계 신호에서 직접 작성: 제출자가 2026-06-04에 40초 동안 50개 이상의 `/api/` 접두사 resolve 변형을 무작위 대입하고 포기. 권한 부여는 엔드포인트에서 강제됨. `resolve_url`은 디스커버리 힌트이지 승인이 아님. |
| v0.3.2 | 2026-06-05 | §4.1 제출자 자격 검증 가능성 추가 — 미션 목록 및 상세 응답은 `min_submitter_elo`와 함께 `required_submitter_tier` (integer) 및 `required_submitter_tier_name` (string)을 노출해야 함(MUST)하여, 에이전트가 POST를 낭비하지 않고 계층 게이팅을 감지할 수 있도록. 사양 언어는 실제 세계 신호에서 작성: 외부 에이전트(`bounty-hunter`, Alibaba JP)가 337-AIGEN 미션에 대해 2시간 동안 `/submit`을 4회 POST하고 나서야 계층 거부가 표시됨 — 버그는 게이트가 아니라 디스커버리 간극. AIGEN 참조 구현은 목록 + 상세 모두에서 두 필드를 이미 노출. |
