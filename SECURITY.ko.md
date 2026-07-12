# 보안 정책 (Security Policy)

## 취약점 신고 (Reporting Vulnerabilities)

**AIGEN-Protocol** 은 활성화된 화이트햇(whitehat) 보안 연구 프로그램을 운영합니다. 우리는 조율된 책임 공개(coordinated responsible disclosure)를 통해 타사 프로토콜의 결과를 공개하며, 공개 bounty 제출 이전에 프로젝트 측 전달을 우선시합니다.

AIGEN-Protocol 스마트 컨트랙트나 오프체인 에이전트에서 취약점을 발견하셨다면 다음을 통해 신고해 주세요:

- **GitHub Security Advisory** (권장): 이 저장소의 "Privately report a vulnerability" 기능 사용
- **암호화 이메일**: `builder@cryptogenesis.duckdns.org`
- **Discord**: AIGEN 커뮤니티 서버에서 `@CryptoGenesisSec` 에 문의

보안 문제에 대해 **공개 이슈를 열지 마세요.**

우리는 새로운 신고를 72시간 이내에 확인하고, 14일 이내에 분류(triage) 결과를 제공하는 것을 목표로 합니다.

## 화이트햇 연구 (Whitehat Research)

AIGEN은 타사 버그 바운티 프로그램(Immunefi, Code4rena, Sherlock, Cantina)에 취약점 보고서를 제출하는 조율된 화이트햇 그룹을 운영합니다. 우리의 표준 공개 워크플로우는 다음과 같습니다:

1. **우선 프로젝트 측 전달.** 우리는 바운티 제출 이전에, 영향받는 프로젝트에 비공개 GitHub 저장소나 직접 보안 채널을 통해 전체 보고서와 재현 가능한 PoC를 공유합니다.
2. **조율된 타이밍.** 우리는 어떠한 수정도 배포되지 않은 경우 기본 90일 창(window)을 상한으로 하여, 공개 공개에 대해 프로젝트가 요청한 타이밍을 존중합니다.
3. **미패치 취약점의 공개 금지.** 프로젝트가 이를 인정하고 완화 조치가 마련될 때까지 우리는 결과를 게시, 트윗, 커밋하지 않습니다.
4. **Immunefi / 바운티 제출** 은 프로젝트 측 공개 URL을 명시적으로 인용합니다.

### 과거 공개 내역 (Past disclosures)

완전히 완화된 공개(프로젝트 인정 및 CVE / 권고 링크 포함)의 공개 레지스트리는 각 보고서의 엠바고(embargo)가 해제되면 `github.com/Aigen-Protocol/security-advisories` 에 게시됩니다.

## 연구 범위 (Scope of Research)

AIGEN 화이트햇은 다음에 집중합니다:

- DeFi 프리미티브(AMM, 대출, 재스테이킹, 유동성 스테이킹)의 스마트 컨트랙트 로직 버그
- 크로스 컨트랙트 상호작용 오류 (관리자 우회, 재활성화 결함, 공유 회계 불일치)
- 온체인 거버넌스 및 오라클 관련 공격

우리는 심각도 매핑을 위해 **Immunefi Vulnerability Severity Classification System v2.3** 을 따르며, 심각도를 분류할 때 영향(impact) 문구를 **verbatim(그대로)** 사용합니다.

## PGP 키 (PGP key)

Discord를 통해 요청 시 제공됩니다. 지문(fingerprint)은 [AIGEN-Protocol 매니페스토](https://github.com/Aigen-Protocol/aigen-protocol/blob/main/MANIFESTO.md) 에 게시되어 있습니다.

---

최종 업데이트: 2026-05-22
