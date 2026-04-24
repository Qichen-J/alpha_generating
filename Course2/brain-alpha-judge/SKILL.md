---
name: brain-alpha-judge
description: >-
  Judge whether a regular WorldQuant BRAIN alpha is worth submitting now by
  combining platform hard checks with a shipped local corpus of high-value
  Chinese forum Markdown posts. Use when the user wants to 在提交前做额外质量审查、
  基于静态论坛语料整理标准、评估 regular alpha 是否值得提交、或在明确确认后提交 regular
  alpha.
---

# Brain Alpha Judge

Use this skill as a two-gate workflow for regular alphas only.

## Scope

- Regular alpha only.
- Static local corpus only.
- No runtime forum access and no in-skill corpus rebuild step.
- Submit only after explicit user confirmation.

The shipped corpus lives in `data/forum_corpus/` and `data/forum_corpus/index.json`.
V1 currently includes 20 accepted Chinese corpus entries packaged into this skill:

- 20 full-post Markdown files preserved locally.
- 0 remaining shipped search-snapshot entries after the longer-timeout local recovery pass.

## Gate Order

1. Apply platform hard checks to confirm the alpha is submittable at baseline.
2. Compute value-factor trend score context from submitted regular alphas (OS window).
3. Apply the extra submission rubric derived from the local corpus to answer whether the alpha is worth submitting now.
4. Run an optional LLM decision layer using checks + expression + trend + rubric evidence.
5. Submit only after explicit user confirmation.

## LLM Decision Layer

The judge can call an LLM to produce final decision and comments after all structured evidence is collected.

Two execution modes:

- Agent mode (preferred in this AI chat): use the current AI session to produce LLM verdict and comments, no extra API key required.
- Script API mode (optional for standalone CLI): call an external OpenAI-compatible endpoint, requires API key.

- Input evidence includes: platform checks, failed checks, expression, expression analysis, extra rubric statuses/reasons, value-factor trend block, and the hypothetical post-submit value-factor projection block.
- Output includes: `verdict`, `confidence`, `comment`, `strengths`, `risks`.
- LLM text output (`comment`, `strengths`, `risks`) should be in Chinese (Simplified Chinese by default).
- Final `overall_verdict` uses LLM verdict when available, else falls back to deterministic rule verdict.
- Safety guard: if `platform_submit_ok=false`, LLM verdict cannot become `READY`.

Enabled by default. Configure under `configs/config.json` with `judge.llm`.

## Recommendation Requirement

When judging a candidate, always provide actionable suggestions grounded in local documents/rubric evidence.

- Suggestions must reference corpus/rubric evidence (post IDs or rule IDs).
- Suggestions should map directly to failed checks and missing evidence fields.
- Minimum target: 3 concrete actions when verdict is `REVIEW` or `BLOCK`.

## Value Factor Trend Score Meaning

The judge now computes a value-factor trend context block during each run.

- Uses submission dates only (`stage=OS`) in a configurable window.
- Uses regular alphas only.
- `A` means ATOM alpha count in the window.
- ATOM here means single-dataset purity (`SINGLE_DATA_SET` classification; with `atom` fallbacks).

Returned terms:

- `N`: number of regular submissions in the window
- `A`: number of ATOM regular submissions in the window
- `P`: number of covered pyramid categories
- `P_max`: total pyramid category count from platform multipliers
- `S_A = A / N`
- `S_P = P / P_max`
- `S_H`: normalized entropy of per-pyramid distribution
- `diversity_score = S_A * S_P * S_H`

Interpretation:

- Higher `S_A`: cleaner single-dataset submission mix
- Higher `S_P`: broader pyramid coverage
- Higher `S_H`: more balanced distribution across covered pyramids

This score is computed and reported as context for judging quality and value-factor direction.
The skill also reports a hypothetical projection for the current candidate, showing the before/after diversity score, delta, and direction if that alpha were submitted into the same window.
It does not auto-submit and does not bypass explicit confirmation.

## Inspect The Local Corpus

If you want to inspect the supporting Markdown corpus before judging a candidate:

```powershell
Set-Location "untracked/skills/brain-alpha-judge"
Get-ChildItem "data/forum_corpus"
Get-Content "data/forum_corpus/index.json"
```

For corpus policy and the current manifest, read:

- [references/source-selection.md](references/source-selection.md)
- [references/corpus-manifest.md](references/corpus-manifest.md)

## Judge A Candidate

Use the judge CLI after the corpus and rubric exist locally.

Single alpha by ID:

```powershell
Set-Location "untracked/skills/brain-alpha-judge"
python scripts/judge_alpha.py --alpha-id "<alpha_id>"
```

Batch candidates from JSON:

```powershell
Set-Location "untracked/skills/brain-alpha-judge"
python scripts/judge_alpha.py --input-json "data/candidates.example.json"
```

The judge writes both JSON and Markdown reports to `outputs/` by default.

Optional trend-score window controls:

```powershell
Set-Location "untracked/skills/brain-alpha-judge"
python scripts/judge_alpha.py --alpha-id "<alpha_id>" --trend-window-days 365
python scripts/judge_alpha.py --alpha-id "<alpha_id>" --trend-start-date "2025-01-01T00:00:00Z" --trend-end-date "2026-01-01T00:00:00Z"
```

LLM setup example:

```json
{
  "judge": {
    "llm": {
      "enabled": true,
      "provider": "openai-compatible",
      "model": "gpt-4o-mini",
      "api_url": "https://api.openai.com/v1/chat/completions",
      "api_key": ""
    }
  }
}
```

You can also provide key from env:

- `BRAIN_JUDGE_LLM_API_KEY`
- `OPENAI_API_KEY`

## Confirmation Rule

Never submit automatically in normal use.

Only run submit when all of the following are true:

- platform baseline passes
- final overall verdict is `READY` (LLM if enabled, otherwise deterministic)
- the user explicitly asks to submit

If explicit confirmation is given, run:

```powershell
Set-Location "untracked/skills/brain-alpha-judge"
python scripts/judge_alpha.py --alpha-id "<alpha_id>" --confirm-submit
```

## Standalone Rule

Treat this skill as self-contained.

- Import only from this skill folder.
- Keep vendored runtime helpers under `scripts/vendor/`.
- Do not rely on runtime imports from `untracked/` or `untracked/APP/`.

## References

- Extra rubric: [references/extra-standard-rubric.md](references/extra-standard-rubric.md)
- Source policy: [references/source-selection.md](references/source-selection.md)
- Corpus manifest: [references/corpus-manifest.md](references/corpus-manifest.md)
- Improvement roadmap: [references/improvement-roadmap.md](references/improvement-roadmap.md)
- Future improvement guide: [references/future-improvement-guide.md](references/future-improvement-guide.md)
- Machine-readable rubric: `data/extra_submission_rubric.json`
