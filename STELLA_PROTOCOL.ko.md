# STELLA 프로토콜 — 명세 (Spec)

> Base 상의 AIGEN-트레저리 백업 스테이블코인. Terra/Luna 스테이블코인이 되었어야 할 모습: USDC 100% 담보, 단일 체인, 하드 공급 상한, 담보 부족 시 자동 일시정지, 상환은 절대 동결되지 않음.

---

## STELLA가 필요한 이유 (Why STELLA)

Terra/Luna는 올바른 비전(탈중앙화 스테이블코인, 무허가 통화 정책, DeFi 네이티브 레일)을 개척했지만 치명적인 메커니즘에 연결했다: 알고리즘 전용 백업, 보조된 20% 수익률, 창시자 중앙화, 크로스체인 공격 표면, 서킷 브레이커 없음.

비전은 여전히 옳다. 실행이 잘못되었을 뿐이다.

STELLA는 비전을 유지하면서 Luna를 죽인 모든 실패 모드를 코드로, 첫날부터 제거한 결과다.

## 핵심 원칙 (Core principles)

1. **백업은 실재하며 온체인에서 보인다.** 모든 STELLA는 AIGEN 트레저리 지갑의 USDC ≥150% 로 백업된다. 누구나 온체인에서 `collateralRatioBps()` 를 읽을 수 있다.
2. **민팅은 일시정지, 상환은 절대 그렇지 않다.** 트레저리 담보가 110% 미만으로 떨어지거나 페그가 $0.97 미만이면, 누구나 `pokePause()` 를 호출하고 민팅이 중단된다. 상환은 영원히 열려 있다 — 일시정지 상태에서도 $1에 USDC를 돌려받는다.
3. **창시자 없음, 관리자 없음, 업그레이드 프록시 없음.** 컨트랙트는 불변(immutable). 거버너(멀티시그)는 다음에 대한 48시간 타임락 큐잉 변경만 가능: 공급 상한, 거버너 주소, 일시정지 해제 플래그. 그 외에는 아무것도 없음.
4. **하드 공급 상한.** $100k로 시작. 거버너가 48h 타임락으로 상향. 단일 통합 또는 공격의 폭발 반경(blast radius)을 제한한다.
5. **기본 컨트랙트에 수익률 없음.** Terra의 Anchor가 치명타였다. STELLA 자체는 그저 민트하고 상환할 뿐. 수익률 상품은 별도의 opt-in 컨트랙트이며 보유자가 선택한다. 수익률은 실제 수익에서 와야 한다.
6. **단일 체인.** 출시 시 Base만. 크로스체인 브리지 없음 = Wormhole/Ronin급 취약점 없음.
7. **AIGEN 정렬(aligned).** 모든 AIGEN 바운티 해결에서 0.5%를 버는 동일한 트레저리가 STELLA를 백업한다. AIGEN 프로토콜 수익이 성장함에 따라 STELLA의 백업도 자동으로 성장한다. 두 플라이휠이 상호 강화된다.

## 메커니즘 (Mechanism)

### 민팅 (Mint)
```
caller → 100 USDC → Treasury wallet
Treasury → 100 STELLA → caller
```
다음 경우 되돌림(revert):
- 민팅 일시정지
- 공급 상한 위반
- 민팅 전 트레저리 담보 비율이 150% 미만이거나, 민팅 후 110% 미만으로 떨어질 경우
- 페그(Chainlink 통한 USDC/USD)가 $0.97 미만이거나 오라클이 오래됨(>1h)

### 상환 (Redeem)
```
caller → 100 STELLA → burned
Treasury → 100 USDC → caller
```
다음 경우에만 되돌림:
- 호출자 잔액 부족
- 트레저리가 컨트랙트를 승인하지 않음 (배포 시 설정)

그게 전체 표면이다. 특별한 예외 없음.

### 자동 일시정지 (Auto-pause, `pokePause`)
누구나 호출 가능. 저렴함 (조건 OK 시 상태 쓰기 없음). `collateral_ratio_bps < 11000` OR `peg < 97_000_000` 이면 `mintPaused = true` 설정.

일시정지 후:
- 민팅 차단
- 상환 영향 없음
- 거버너만 일시정지 해제 가능, 그리고 비율과 페그 모두 회복된 경우에만

### 거버넌스 (timelocked)
- `queueGovernorChange(addr)` → 48h 대기 → `executeGovernorChange()`
- `queueSupplyCap(amount)` → 48h 대기 → `executeSupplyCap()`
- `unpause()` — 즉시, 하지만 비율 + 페그가 현재 건강할 때만

그게 전체 거버넌스 표면이다. 민트, 번, 동결, 또는 사용자 자금에 손댈 수 없음.

## 수치 (Numerics)

| Parameter | Value | Why |
|---|---|---|
| `MIN_COLLATERAL_RATIO_BPS` | 15000 (150%) | 민팅에 필요. 버퍼가 USDC 디페그 이벤트 흡수. |
| `PAUSE_RATIO_BPS` | 11000 (110%) | 이 미만에서 자동 일시정지 트리거. 여전히 과담보. |
| `PEG_FLOOR` | $0.97 | USDC/USD 자체가 디페그되면 민팅 중단 (STELLA를 상류 붕괴로부터 방어). |
| `ORACLE_STALE_AFTER` | 1 hour | 오래된 Chainlink 읽기 거부. |
| `INITIAL_SUPPLY_CAP` | $100,000 | 초기 폭발 반경 제한. 48h 타임락 투표로 상향. |
| `TIMELOCK` | 48 hours | 모든 거버넌스 변경은 2일 대기. |
| `STELLA_DECIMALS` | 18 | ERC20 표준. |
| `USDC_DECIMALS` | 6 | Base USDC 기본. 변환 = ×1e12. |

## 배포 계획 (Deployment plan)

**Phase 1 — 감사 및 테스트 (현재)**
- 명세 작성 ✓
- 컨트랙트 코드 완성 ✓
- Foundry 테스트 스위트 (7개 테스트, 모두 통과) ✓
- 이 저장소를 통한 공개 리뷰

**Phase 2 — 테스트넷 (Base Sepolia)**
- 목(mock) USDC로 배포
- 트레저리에 $100 테스트넷 USDC로 부트스트랩
- 7일 이상 실행, `pokePause` 호출 모니터, 상환이 항상 동작 확인
- 퍼즈(fuzz) 테스트

**Phase 3 — 메인넷 (Base)**
- 초기 거버너로 멀티시그 (5-of-9) 설정
- `forge script Deploy.s.sol` 로 배포
- 트레저리가 컨트랙트에 USDC.transferFrom 승인
- 초기 공급 상한 = $100k
- 발표, 대기

**Phase 4 — 유동성 (Liquidity)**
- 트레저리 자금으로 Aerodrome STELLA/USDC 풀 시드 (작게, $1k–5k)
- 바운티: AIGEN에서 페그 방어 미션 (차익거래 작업에 AIGEN 지급)
- 유기적 채택 대기

**Phase 5 — 확장 (Scale, 몇 달 후)**
- 거버넌스 투표로 공급 상한 상향 (48h 타임락, 모두에게 보임)
- 수익률 컨트랙트 배포 (별도, opt-in)
- 공급 > $1M 일 때 크로스체인 지원 (정식(canonical) 브리지만)

## 무엇이 잘못될 수 있는가 (및 대응)

| Failure | Probability | Impact | Mitigation |
|---|---|---|---|
| USDC 자체 디페그 | Low (2023년 3월 0.87이었음) | High | $0.97 미만이면 민팅 자동 일시정지; 상환은 기존 준비금에서 $1로 계속; USDC 회복되면 민팅 재개. |
| 트레저리 지갑 손상 | Low (멀티시그 + 콜드 스토리지) | Catastrophic | 멀티시그 5-of-9 최소; 상환은 직접 트레저리 접근이 아닌 승인된 allowance에서 인출; 손상되면 공격자가 STELLA 컨트랙트 로직에 손댈 수 없음. |
| 스마트 컨트랙트 버그 | 사전 감사 Medium, 사후 Low | Catastrophic | 설계상 업그레이드 프록시 없음 — 버그는 마이그레이션으로 새 컨트랙트 재배포 필요. 초기 코드에 주의 강제. 배포 전 감사 필수. |
| 조정된 공매도 공격 | Medium | Medium | 150% 과담보가 33% 하방 버퍼 제공. 자동 일시정지가 인플레이션 스파이럴 방지. 하드 공급 상한이 매도 가능 규모 제한. |
| DEX 유동성 고갈 | Medium | Low | 상환은 DEX 유동성에 의존하지 않는 USDC 직접 방식. 최악: 차익 루프 느리지만 메커니즘 작동. |
| Chainlink 오라클 실패 | Low | Medium | 오래됨 체크가 1h 초과 오라클 읽기 거부; 민팅 자동 일시정지; 상환 영향 없음. |
| AIGEN 트레저리 자금 부족 | 현재 ~$0.08 USDC | 작을 때 Low | 비율 < 150% 이면 민팅 차단. STELLA 공급은 실제 AIGEN 프로토콜 수수료로 트레저리가 성장함에 따라서만 증가. 기계적으로 연결됨. |

## 감사 상태 (Audit status)

**아직 감사 안 됨.** 메인넷 전 권장:
- Trail of Bits / OpenZeppelin / Spearbit급 외부 감사 ($30k–80k typical)
- 공개 버그 바운티 프로그램 (감사 후)
- 민트/상환 불변식(invariants)의 형식 검증

감사 완료 전까지 테스트넷에만 배포.

## AIGEN이 STELLA를 지원하는 방식 (Luna가 UST에 그랬던 것과 다름)

**중요 설계 포인트**: AIGEN은 UST에 대한 LUNA 역할을 하지 않는다.
그 역할이 Terra를 죽였다. 죽음의 나선은 UST 페그가 INFINITELY MINTING LUNA로 방어되었기 때문에 발생 — 즉 UST 가치가 LUNA 가치에 의존하고, 그 반대도 마찬가지여서, 하나가 금이 가면 다른 하나가 뒤따랐다.

STELLA는 **완전히 USDC 백업** — 그 가치는 AIGEN이 아닌 USDC에 의존한다.
AIGEN은 MakerDAO/MKR 스타일의 지원 역할을 한다:

| Role | Mechanism | Limit |
|---|---|---|
| **거버넌스 (Governance)** | AIGEN 보유자가 supplyCap, 오라클 소스, 파라미터에 투표. 모두 48h 타임락 + 악의적 변경에 대한 긴급 취소. | 민트 권한 없음. |
| **작업 조정 (Work coordination)** | AIGEN 바운티가 에이전트에 페그 방어 작업 지급: STELLA 오프페그 시 차익거래, 오라클 모니터, 준비금 감사. 0.5% 프로토콜 수수료로 자금. | AIGEN 프로토콜 수익으로 한정. 보조금 없음. |
| **수수료 포획 (Fee capture)** | STELLA가 v2에서 민트/상환 수수료를 발생시키면 AIGEN 트레저리 → AIGEN 바이백으로 흐름. STELLA 확장이 AIGEN 풍요롭게 함. | 단방향: AIGEN은 STELLA로부터 이익, STELLA는 AIGEN 없이 기능. |
| **보험 기금 (capped)** | 스테이크된 AIGEN이 STELLA 담보가 100% 미만으로 떨어지면 나쁜 부채 흡수. **STELLA 공급의 5%로 상한** (하드코딩). 상한 도달 시 보험 중지 — 무한 민팅 없음. | 5% 하드 상한은 모든 보험이 사용되어도 STELLA 백업이 ≥95% USDC 유지 의미. 나선 없음. |

**Luna와의 핵심 대조:**

| Luna for UST | AIGEN for STELLA |
|---|---|
| UST 가치 = LUNA 가치의 함수 (둘 다 서로 백업) | STELLA 가치 = 컨트랙트 내 USDC의 함수. AIGEN 가치는 독립적. |
| UST 매도 흡수 위해 LUNA 무한 민팅 가능 | AIGEN 보험 기금은 STELLA 공급의 5%로 상한. 소진되면 STELLA 디페그 가능하나 AIGEN은 인플레 불가. |
| 한 토큰 붕괴가 다른 토큰 끌어내림 | AIGEN이 $0으로 추락해도 STELLA는 여전히 USDC 백업. STELLA가 백업 상실하면 AIGEN 보험이 최대 5%까지 지급, 그 이상은 STELLA 보유자가 손실 부담하나 AIGEN은 무한 희석하지 않음. |

**보험 기금 메커니즘 (v0.3 명세, 아직 구현 안 됨):**

```solidity
// v0.3 보험 컨트랙트 의사코드 (Stella.sol과 별도)
contract StellaInsurance {
    uint256 public constant MAX_COVERAGE_BPS = 500; // STELLA 공급의 5%

    function stakeAIGEN(uint256 amount) external;
    function unstakeAIGEN(uint256 amount) external; // 14일 쿨다운
    function claimDeficit() external; // STELLA 백업 < 100% 일 때 호출 가능

    function maxCoverageUSD() public view returns (uint256) {
        return (Stella.totalSupply() * MAX_COVERAGE_BPS) / 10000;
    }
}
```

보험 메커니즘은 AIGEN 보유자에게 OPT-IN. 그들은 위험에 대한 보상으로 STELLA 수수료 일부를 얻는다. 하드코딩된 5% 상한은 최대 AIGEN 희석 시나리오가: 현재 AIGEN 가격에서 STELLA 공급의 정확히 5%를 커버하는 데 필요한 만큼만 AIGEN 공급 확장됨을 의미.

## 열린 질문 (Open questions)

- 상환에 작은 수수료 (예: 1bps) 를 부과하여 MEV 쳐리(churn)를 방해해야 하는가? **현재: 수수료 없음.**
- 보험 기금 최소 스테이크 금액? **TBD — 1000 AIGEN 최소 제안 중.**
- 보험 기금 수익률? **TBD — STELLA 민트/상환 수수료의 X% 제안 중, 상한 있음.**
- 거버너가 긴급 셧다운 함수 (`pause + redeem freeze`) 를 가져야 하는가? **아니오 — 명시적 설계상. 상환은 절대 동결되지 않음.**

## 소스 (Source)

- 컨트랙트: `contracts/src/Stella.sol`
- 테스트: `contracts/test/Stella.t.sol`
- 배포 스크립트: `contracts/script/Deploy.s.sol`
- 이 명세: `STELLA_PROTOCOL.md`

## 라이선스 (License)

MIT, immutable, public-good infrastructure.