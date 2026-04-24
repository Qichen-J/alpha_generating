# Future Improvement Guide

This document explains how users and maintainers should extend `brain-alpha-judge` in the future without breaking the current design.

Use this guide when you want to add new corpus evidence, improve the judge rubric, strengthen the report, or make the skill more reliable.

## Keep These Invariants

- Keep the skill standalone inside `untracked/skills/brain-alpha-judge`.
- Keep runtime behavior static and local. Do not add live forum fetching back into the normal judge flow.
- Keep submission behind explicit user confirmation.
- Prefer stronger evidence before adding stronger rules.
- Keep `data/forum_corpus/index.json` as the source of truth for shipped corpus metadata.
- Do not make this skill depend on `untracked/APP/` or other monolith paths.

## Best Improvement Order

Improve this skill in the following order:

1. Improve corpus quality.
2. Improve rubric precision.
3. Improve judge analysis and report clarity.
4. Add offline validation and regression coverage.
5. Add longer-term feedback loops from real outcomes.

This order matters because weak evidence leads to weak rules, and weak rules lead to misleading verdicts.

## What To Add First

### 1. Corpus Expansion

Add more high-value full-post entries before changing the rubric aggressively.

Focus on gaps such as:

- self-correlation and prod-correlation
- turnover control and churn patterns
- GM and PPAC discussion
- value-factor and crowding discussion
- selection-specific advice
- delay, universe, and neutralization tradeoffs
- overfitting warnings and template misuse

Files to update:

- `data/forum_corpus/post_<id>.md`
- `data/forum_corpus/index.json`
- `references/corpus-manifest.md`
- `references/source-selection.md` only if corpus policy changes

Each new corpus entry should include:

- source URL
- post ID
- author
- crawl timestamp or recovery timestamp
- `entry_type`
- normalized `topic_tags`
- `evidence_strength`
- retrieval note if the entry is not full-post

Preferred rule:

- snapshot first only when necessary
- recover to full-post before using the new evidence to change rubric logic

### 2. Rubric Refinement

After corpus quality improves, refine the decision logic.

Useful upgrades include:

- split `REVIEW` into lighter and heavier review states if that helps actionability
- add weighted scoring based on evidence strength
- distinguish `no evidence`, `weak evidence`, `strong evidence`, and `contradictory evidence`
- attach rule explanations to corpus entry IDs or topic tags
- separate hard blockers from soft caution signals

Files to update:

- `data/extra_submission_rubric.json`
- `references/extra-standard-rubric.md`
- `scripts/judge_alpha.py`
- `data/candidates.example.json` if new input shape is needed

### 3. Report Improvement

The next high-value improvement is report quality.

Good additions include:

- a short Chinese executive summary at the top of each Markdown report
- an explicit evidence-gap section for missing proof
- clearer separation between platform checks and corpus-derived advice
- topic-tag summaries explaining which parts of the corpus influenced the verdict
- use of `topic_tags` and `evidence_strength` already stored in `index.json`

Files to update:

- `scripts/judge_alpha.py`
- `outputs/` sample artifacts if you maintain examples

### 4. Analysis Improvement

If you want better alpha-structure review, extend the local expression analysis.

Useful directions include:

- nesting-depth estimation
- operator-family distribution analysis
- repeated-window-pattern detection
- suspicious parameter churn detection
- better identification of template-like expressions with low originality

Main file to update:

- `scripts/judge_alpha.py`

### 5. Portfolio-Fit Improvement

The current skill mainly judges a candidate in isolation. A stronger future version should also evaluate whether the alpha improves the user's existing submission pool.

Possible upgrades:

- compare against existing submitted or candidate alphas
- show diversification by dataset, operator family, region, and delay
- treat some high-correlation cases differently when portfolio coverage improves

This should be added only after the standalone single-alpha review remains clear and stable.

## File Map For Common Changes

- Add or edit corpus entries: `data/forum_corpus/`
- Change corpus metadata: `data/forum_corpus/index.json`
- Change source policy: `references/source-selection.md`
- Update corpus registry and recovery history: `references/corpus-manifest.md`
- Change review standards: `references/extra-standard-rubric.md`
- Change machine-readable rules: `data/extra_submission_rubric.json`
- Change judge logic and report rendering: `scripts/judge_alpha.py`
- Change user-facing skill instructions: `SKILL.md`

## Safe Workflow For Future Changes

1. Decide whether the change is evidence, rubric, analysis, or reporting.
2. Update the smallest number of files needed.
3. Keep metadata synchronized in `index.json`.
4. Run the judge on a known sample candidate.
5. Confirm the JSON and Markdown reports still agree.
6. Update the reference documents if the change affects shipped behavior.

## Validation Checklist

Before calling an improvement complete, verify all of the following:

- the skill still works without runtime forum access
- the skill still stays inside its own folder boundaries
- `scripts/judge_alpha.py --help` still runs
- a sample judge run still produces both JSON and Markdown output
- rubric text and rubric JSON still describe the same logic
- corpus entries and `index.json` do not disagree
- any new verdict state is explained clearly in the report

## Avoid These Mistakes

- Do not change the rubric based on weak snippets alone when full-post recovery is still possible.
- Do not add runtime dependencies on external forum fetching.
- Do not let report language become more complex than the decision it explains.
- Do not update corpus Markdown files without also updating `index.json`.
- Do not mix portfolio-level judgment into the basic single-alpha verdict unless the output remains easy to interpret.

## Recommended Near-Term Upgrades

If you want the highest-value next steps, start here:

1. Use `topic_tags` and `evidence_strength` inside the judge report.
2. Add a Chinese summary block and evidence-gap section.
3. Add offline regression cases for `READY`, `REVIEW`, and `BLOCK`.
4. Expand the corpus only with high-value full-post evidence.

Use [references/improvement-roadmap.md](references/improvement-roadmap.md) for the internal phase view, and use this guide when deciding what to add next and where the change should go.