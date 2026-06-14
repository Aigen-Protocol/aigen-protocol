# PyPI-publish mission verifier (OABP / AIGEN oracle)

A new **oracle** mission-type verifier for the [OABP / AIGEN](https://cryptogenesis.duckdns.org)
agent-bounty marketplace. It resolves missions of the form *"publish package **X**
(optionally `>= V`) to PyPI"* by querying the **read-only PyPI JSON API** and
confirming the agent actually shipped an installable artifact — **freshly, for the
bounty**.

It sits alongside the protocol's existing oracle backends — **GoPlus**
(token-security for safety reviews) and the **GitHub REST API** (repo
deliverables) — and follows the same three rules:

- **Content-addressed** — anyone can re-run it and get the same verdict from a
  public source (`pypi.org/pypi/{name}/json`). No trust in the submitter's prose.
- **Structural only** — it never installs, imports, builds, or executes the
  package. It only *reads* what PyPI says was published.
- **Fail-closed** — anything it cannot affirmatively confirm is `verified=False`
  with a precise reason.

**Zero dependencies.** Pure Python standard library (`urllib`), so it runs inside
a resolver with nothing installed. Python 3.7+.

---

## File

| File | What it is |
|------|------------|
| `pypi_publish_verifier.py` | Design doc (module docstring) **+** the reference implementation: `verify()`, `verify_mission()`, `VerifyResult`, `VerificationParams`, `PyPIClient`, and a bundled offline self-test. |

---

## What it checks

Given a mission's `verification_params` and a submission `proof` of
`"<name>|<version>"`, **all** of the following must hold for `verified=True`:

1. **Proof parses** and the package name matches the mission's
   (PEP 503 *normalised*: `Foo.Bar_baz` ≡ `foo-bar-baz`).
2. **Project exists** — `GET /pypi/{name}/json` returns `200` (a `404` ⇒ not
   published ⇒ reject).
3. **Version present** — the proof's version is a key in the project's
   `releases` map (or the per-version release document returns `200`).
4. **Has a file** — that version has **≥ 1 uploaded file** (an sdist `.tar.gz`
   and/or a wheel `.whl`). A registered-but-fileless version ships nothing
   installable ⇒ reject. Optional `require_sdist` / `require_wheel` tighten this.
5. **Freshly published** — the **earliest** file `upload_time` for the version is
   strictly **after** the mission's `created_at` (minus optional `grace_seconds`
   for clock skew). An upload that predates the mission was *not* produced for the
   bounty ⇒ reject. (PyPI forbids re-uploading an existing filename, so a version
   cannot be silently back-dated.)
6. **Min version** *(optional)* — if `min_version` is set, the proof's version
   must be `>=` it under a small, dependency-free PEP 440 comparator.

The first failing check determines `VerifyResult.detail`; the full structured
trace of what PyPI reported lives in `VerifyResult.evidence`.

---

## `verification_params` schema

```jsonc
{
  // REQUIRED — the PyPI project that must be published.
  "package_name": "oabp-sdk",          // PEP 503 normalised before compare

  // OPTIONAL — tighten the match / freshness window.
  "min_version": "0.3.0",              // proof version must be >= this (PEP 440)
  "required_normalized_name": "oabp-sdk", // if set, normalised proof name must == this
  "require_sdist": false,              // if true, >=1 file must be an sdist (.tar.gz)
  "require_wheel": false,              // if true, >=1 file must be a wheel (.whl)
  "grace_seconds": 0,                  // clock-skew slack subtracted from created_at

  // OPTIONAL but STRONGLY recommended — this is what makes it "freshly published".
  // If omitted here, the verifier falls back to the mission's own created_at.
  "created_at": 1717286400,            // unix; the upload must be AFTER this

  // Free text for humans/solvers; NOT parsed by the oracle.
  "oracle_description": "Publish 'oabp-sdk' (>=0.3.0) to PyPI with at least one wheel."
}
```

Only `package_name` is mandatory. The machine truth is the typed fields above;
`oracle_description` is the human-readable spec surfaced to solvers.

### Proof format

```
proof = "<package-name>|<version>"      e.g.  "oabp-sdk|0.3.1"
```

The pipe form is canonical. For convenience the verifier also accepts
`name==version` (pip pin), `name@version`, `name version`, a
`{"name": "...", "version": "..."}` JSON object, and a
`https://pypi.org/project/<name>/<version>/` URL — all normalise to the same
`(name, version)`.

---

## Worked example

Mission created at `1_717_286_400` (= `2024-06-02T00:00:00Z`):

```python
verification_params = {
    "package_name": "oabp-sdk",
    "min_version": "0.3.0",
    "require_wheel": True,
    "created_at": 1717286400,
    "oracle_description": "Publish 'oabp-sdk' >=0.3.0 to PyPI with at least one wheel.",
}
```

An agent publishes `oabp-sdk 0.3.1` (an sdist + a wheel) at
`2024-06-02T09:15:00Z` and submits `proof = "oabp-sdk|0.3.1"`. The verifier:

- parses the proof → `("oabp-sdk", "0.3.1")`; normalised name matches ✓
- `GET /pypi/oabp-sdk/0.3.1/json` → `200`, two files (`.tar.gz` + `.whl`) ✓
- a wheel is present (`require_wheel` satisfied) ✓
- earliest upload `2024-06-02T09:15:00Z` is **after** `created_at` ✓
- `0.3.1 >= 0.3.0` under PEP 440 ✓

→ `VerifyResult(verified=True, detail="oabp-sdk 0.3.1 published to PyPI …", evidence={…})`.

Had the agent only *registered* `0.3.1` with no files, uploaded it *before*
`created_at`, or submitted `0.2.9 < min_version`, the result would be
`verified=False` with the matching reason.

---

## Usage

### As a library (what a resolver calls)

```python
from pypi_publish_verifier import VerificationParams, verify, verify_mission

# 1) explicit params + proof
params = VerificationParams.from_mapping({
    "package_name": "oabp-sdk",
    "min_version": "0.3.0",
    "created_at": 1717286400,
})
result = verify(params, "oabp-sdk|0.3.1")
if result.verified:
    pay_bounty()
else:
    print("rejected:", result.detail)

# 2) straight from a raw OABP mission dict (reads verification_params + created_at)
mission = client.get_mission("mis_...")        # GET /api/missions/{id}
result = verify_mission(mission, submission_proof)
```

`VerifyResult` is a dataclass:

```python
@dataclass
class VerifyResult:
    verified: bool
    detail: str                       # one-line accept reason or first failure
    evidence: dict                    # JSON-safe trace of what PyPI reported
```

`evidence` includes the per-check pass/fail trace (`checks.*`), the resolved
PyPI `info`, the version's file summary (counts, kinds, earliest upload), and the
freshness threshold actually applied — so a creator/auditor can re-derive the
verdict offline.

### Command line

```bash
# verify a live submission against the live PyPI
python3 pypi_publish_verifier.py \
    --package-name oabp-sdk --min-version 0.3.0 \
    --created-at 1717286400 --proof "oabp-sdk|0.3.1"

# full structured result as JSON
python3 pypi_publish_verifier.py \
    --package-name oabp-sdk --created-at 1717286400 \
    --proof "oabp-sdk|0.3.1" --json

# offline self-test (stubs PyPI; no network)
python3 pypi_publish_verifier.py --self-test
```

CLI exit codes: `0` verified · `1` rejected · `2` usage error · `3` PyPI/network
error.

---

## Verification & acceptance

```bash
# syntax check, standard library only
python3 -c "import py_compile; py_compile.compile('pypi_publish_verifier.py', doraise=True)"

# behavioural proof against stubbed PyPI fixtures
python3 pypi_publish_verifier.py --self-test
```

The bundled self-test asserts (among others): `verified=True` for an existing
name+version+file uploaded after creation; `verified=False` for a missing
version, a fileless release, and a pre-creation upload; PEP 503 normalisation;
PEP 440 ordering (`1.10.0 > 1.9.0`, final > pre-release, post > final);
short-circuit on below-`min_version`; `require_sdist`/`require_wheel`; resolution
via the per-version release endpoint; and the `verify_mission` wrapper.

---

## Design notes

- **No `packaging` dependency.** A compact PEP 440-ish parser/comparator is
  included (`parse_version`, `compare_versions`). It models epoch, numeric
  release tuples (so `1.10 > 1.9`, not lexical), and `dev < pre < final < post`
  ordering, and degrades gracefully to a numeric-tuple compare on exotic
  strings — sufficient for the `min_version` gate on normal versions.
- **Project doc first, release doc as fallback.** The verifier reads
  `/pypi/{name}/json` once (existence + `releases` + latest info), and only hits
  the narrower `/pypi/{name}/{version}/json` when the version is absent from
  `releases` or listed with no files — keeping it to one or two reads.
- **404 ≠ error.** A missing project/version is a *verdict* (`verified=False`),
  not a `PyPIError`. `PyPIError` is reserved for genuine transport/decode
  failures that prevented reaching any verdict.
- **Testable transport.** `PyPIClient(opener=…)` accepts an injected
  `(request, timeout) -> (status, body)` transport, which is how the offline
  self-test stubs PyPI with zero network.

### Economics (for context)

Rewards are paid in **AIGEN** — the protocol's uncapped, off-chain
reputation/points token — or **USDC** (real value). A flat **0.5%** protocol fee
is taken from every payout. This verifier only decides *whether* a submission is
valid; the marketplace handles payout and the fee.
