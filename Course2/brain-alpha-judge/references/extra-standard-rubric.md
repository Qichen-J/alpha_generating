# Extra Submission Rubric

This rubric is the second gate after platform hard checks.

It is derived from the shipped local corpus in `data/forum_corpus/`, not from live forum calls.

## Objective

Answer a different question from platform checks:

- Platform gate: can this alpha be submitted?
- Extra gate: is this alpha worth submitting now?

## Corpus-Derived Themes

### Reusable Template, Not One-Off Tuning

- `TL87739` turns a weak analyst signal into a reusable purification template with short and long horizon market-relative components.
- `JJ47083` shows that naive first-order templates often fail by high correlation, which makes base-signal choice more important than blind expression churn.

### Correlation Discipline And Dataset Spread

- `XX42289` explicitly warns against concentrating on one dataset because self correlation rises.
- `XX42289` uses `self_correlation < 0.4` as a practical SuperAlpha selection discipline.
- `LR93609` ties low self correlation to stable combine and low prod correlation to stable value factor.

### Quality Before Irreversible Submission Count

- `XX42289` says low-quality submissions cannot be withdrawn, so quantity never overrides quality.
- `XX42289` also notes value-factor improvement needs enough good regulars, not just any additional submissions.

### Simplicity Beats Cosmetic Complexity

- `XX42289`'s operator survey shows a compact operator core shared by many higher-stage consultants.
- `LR93609` reports PPAC world-first results with operator average mostly between 1 and 3 and warns against forcing datasets together or adding artificial entry-exit controls.

### Universe, Turnover, And Portfolio Fit Matter

- `JJ47083` checks universe composition, turnover buckets, and region mix before deciding what to submit.
- `ZV96737` focuses on refining machine-alpha and super-alpha backtests after reaching Master.
- `XX42289`'s ranking script emphasizes alpha count, pyramid count, and combined performance rather than single-expression vanity metrics.

## Rule Families

### Economic Foundation

- Require a short plain-language explanation of the idea.
- Require a rationale that links the signal to a plausible market mechanism.

### Template Generalizability

- Prefer structures that can be described as a reusable template or data-transformation pattern.
- If the alpha looks like a one-off expression that only works in one narrow slice, keep it in review.

### Implementation Simplicity

- Prefer fewer moving parts and a compact operator budget.
- Flag excessive conditionals, too many distinct window choices, and unusual windows without justification.
- Treat very high complexity as an overfitting warning.

### Diversification And Correlation Discipline

- Require an explanation of how the candidate fits the existing submitted pool.
- If self correlation or prod correlation is high, require a deliberate justification before recommending submit.

### Anti-Overfitting Evidence

- Look for notes about train/test, hidden two-year risk, cross-universe checks, or cross-region checks.
- Lack of any such evidence should keep the result at least in review.

### Coverage And Turnover Awareness

- Look for coverage handling, turnover control, liquidity profile, or universe-composition checks.
- The goal is to avoid submitting a platform-pass alpha with fragile real-world behavior.

### Quality Over Quantity

- Require a short note about why this alpha deserves a submission slot now.
- If the candidate is only being pushed to increase count, keep it in review.

### Value Factor Alignment

- Look for evidence that the alpha improves diversification, lowers problematic correlation, or helps the user's longer-term value-factor path.
- This is especially important when deciding between multiple platform-pass candidates.

## Verdicts

- `BLOCK`: do not recommend submit now.
- `REVIEW`: platform may pass, but the extra evidence is not strong enough.
- `READY`: platform passes and no extra-standard blocker remains.

## Expected Candidate Fields

- `alpha_id`
- `expression`
- `idea_summary`
- `rationale`
- `template_notes`
- `stability_notes`
- `coverage_notes`
- `turnover_notes`
- `diversification_notes`
- `capacity_notes`
- `liquidity_notes`
- `portfolio_fit_notes`
- `submission_priority_notes`
- `value_factor_notes`
- `cross_universe_notes`
- `cross_region_notes`
- `test_period_notes`

The first version tolerates partial evidence, but missing evidence should usually prevent `READY`.
