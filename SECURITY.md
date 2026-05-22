# Security Policy

## Reporting Vulnerabilities

**AIGEN-Protocol** maintains an active whitehat security research program. We disclose findings in third-party protocols through coordinated responsible disclosure, prioritizing project-side delivery before public bounty submissions.

If you've discovered a vulnerability in any AIGEN-Protocol smart contract or off-chain agent, please disclose it via:

- **GitHub Security Advisory** (preferred): use the "Privately report a vulnerability" feature on this repository
- **Encrypted email**: `builder@cryptogenesis.duckdns.org`
- **Discord**: contact `@CryptoGenesisSec` in the AIGEN community server

Please **do not** open public issues for security matters.

We aim to acknowledge new reports within 72 hours and to provide a triage outcome within 14 days.

## Whitehat Research

AIGEN operates a coordinated whitehat group that submits vulnerability reports to third-party bug bounty programs (Immunefi, Code4rena, Sherlock, Cantina). Our standard disclosure workflow is:

1. **Project-side delivery first.** We share the full report and reproducible PoC with the affected project via a private GitHub repo or direct security channel before any bounty submission.
2. **Coordinated timing.** We honour project-requested timing for public disclosure, capped at a default 90-day window if no fix is deployed.
3. **No public disclosure** of unpatched vulnerabilities. We will not publish, tweet, or commit a finding until the project has acknowledged it and mitigations are in place.
4. **Immunefi / bounty submissions** cite the project-side disclosure URL explicitly.

### Past disclosures

A public registry of fully-mitigated disclosures (with project acknowledgement and CVE / advisory links) is published at `github.com/Aigen-Protocol/security-advisories` once each report's embargo is lifted.

## Scope of Research

AIGEN whitehats focus on:

- Smart-contract logic bugs in DeFi primitives (AMM, lending, restaking, liquid staking)
- Cross-contract interaction errors (admin bypasses, reactivation flaws, share-accounting mismatches)
- On-chain governance and oracle-related attacks

We follow **Immunefi Vulnerability Severity Classification System v2.3** for severity mapping and use **verbatim** impact phrases when classifying severity.

## PGP key

Available on request via Discord. Fingerprint published at [AIGEN-Protocol manifesto](https://github.com/Aigen-Protocol/aigen-protocol/blob/main/MANIFESTO.md).

---

Last updated: 2026-05-22
