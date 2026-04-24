# Improvement Roadmap

This document tracks the next improvement phases for `brain-alpha-judge` after the static-corpus conversion.

## Current Baseline

- The skill is standalone.
- The shipped corpus is static.
- Platform baseline checks and local extra-review rules are already connected.
- The corpus architecture still supports two tiers when needed, but the current shipped corpus has been fully recovered to Tier 1 full-post entries.
- The corpus has reached 20 shipped full-post entries.
- The authoritative corpus index now also carries normalized `topic_tags` and `evidence_strength` metadata for all 20 entries.

## Goal

Move the skill from a useful review gate into a more reliable submission decision system with better evidence quality, stronger traceability, and a tighter feedback loop.

## Phase 1: Corpus Quality Upgrade

- Upgrade Tier 2 `search-snapshot` entries into Tier 1 `full-post` entries whenever body retrieval becomes stable.
- Keep a small allowlist of high-value authors and explicitly record why each author qualifies.
- Add topic tags to every corpus file, such as `template`, `self-correlation`, `prod-correlation`, `turnover`, `value-factor`, `GM`, `PPAC`, and `selection`.
- Record evidence strength per entry so future rubric updates can distinguish between full-body evidence and snippet-only evidence.

## Phase 2: Rubric Precision Upgrade

- Split `REVIEW` into lighter and heavier review states if needed.
- Add weighted scoring for evidence quality instead of only rule-pass aggregation.
- Separate rules that are safe to infer from full-post entries from rules that require stronger confirmation.
- Let the rubric distinguish between `no evidence`, `weak evidence`, and `contradictory evidence`.

## Phase 3: Expression Analysis Upgrade

- Add nesting-depth estimation.
- Add operator-family distribution checks instead of only operator count.
- Add repeated-window-pattern detection.
- Add checks for suspicious parameter churn, such as too many nearby windows without a rationale.

## Phase 4: Portfolio-Fit Upgrade

- Compare a candidate against the user's existing submission pool rather than only evaluating the candidate in isolation.
- Show whether the alpha helps diversification by dataset, region, delay, and operator family.
- Treat high-correlation cases differently when the alpha adds distinct portfolio coverage.

## Phase 5: Reporting Upgrade

- Add a short Chinese executive summary at the top of every Markdown report.
- Explicitly list missing evidence fields for each rule.
- Add an action section with three outcomes:
- `Do not submit now`
- `Need more evidence`
- `Reasonable to submit if confirmed`
- Show which conclusions came from platform checks, which came from full-post corpus evidence, and which came from search snapshots.

## Phase 6: Engineering Upgrade

- Add JSON schema validation for `data/extra_submission_rubric.json` and candidate input files.
- Add snapshot tests for report rendering.
- Add at least one offline regression test that covers a `READY`, `REVIEW`, and `BLOCK` candidate.
- Improve CLI error messages so broken config, missing credentials, and malformed input are easier to diagnose.

## Phase 7: Feedback Loop

- Store judge outcomes alongside later real submission outcomes.
- Compare `judge verdict` versus actual platform and payout outcomes.
- Tune thresholds only after enough real observations accumulate.
- Gradually convert this skill into a personalized submission playbook rather than a static one-size-fits-all checklist.

## Immediate Next Actions

- Start using the new corpus tags and evidence-strength metadata inside the judge report and rule explanations.
- Introduce a Chinese summary block and explicit evidence-gap section in the report.
- Add schema validation and one offline regression test suite.
- Keep future corpus expansions on the same rule: snapshot first only if needed, then recover to full-post before considering rubric upgrades.