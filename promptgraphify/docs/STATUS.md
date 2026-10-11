# Status

Resume from this file if context is lost. Last updated: end of M0.

## Stage

| Stage | State |
|-------|-------|
| M0 Inspect | **done** — environment checked, reference read, `REFERENCE_NOTES.md` and `DECISIONS.md` written |
| M1 IR and fixtures | not started |
| M2 Vertical slice | not started |
| M3 Full parsers and analysis | not started |
| M4 Interfaces | not started |
| M5 Semantic layer and hardening | not started |
| M6 Handover | not started |

## Next action (M1)

1. Python package skeleton (`uv`, venv inside `promptgraphify/.venv`, lockfile).
2. Freeze IR: Pydantic v2 models (node, edge, span, diagnostic, graph), relation endpoint table,
   ID recipe (D-004), span rules (D-003).
3. Write ≥ 20 fixtures with hand-written expected outputs **before** any parser code
   (expectations as `{type, quoted text}`, tests resolve quotes to spans).
4. Invariant tests (span, relation table, EXTRACTED-needs-explicit-reference, ID stability).

## Known blockers / NOT VERIFIED so far

- Docker daemon unreachable → Docker build NOT VERIFIED (see D-008).
- Nothing implemented yet; no tests exist; no acceptance criterion is verified.
