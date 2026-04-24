# Corpus Manifest

This skill ships a fixed local corpus. The Markdown files below are consumed locally by the skill.

The skill itself performs no runtime forum calls. Corpus expansion can happen externally or via MCP during maintenance work and then be baked back in as static files.

## Corpus Tiers

- Tier 1 `full-post`: full body preserved, optionally with selected comments.
- Tier 2 `search-snapshot`: MCP search result captured as a static Markdown snapshot because full detail-page retrieval timed out repeatedly.

## Included Full-Post Entries

- `data/forum_corpus/post_25011325553943.md` | `TL87739` | analyst signal purification with reusable short and long horizon template logic.
- `data/forum_corpus/post_28966942842263.md` | `XX42289` | value-factor recovery notes on dataset spread, self-correlation control, and quality-first submission.
- `data/forum_corpus/post_29083873126551.md` | `XX42289` | compact operator set observed across 15+ Gold-and-above consultants.
- `data/forum_corpus/post_29383292162199.md` | `XX42289` | ranking script emphasizing alpha count, pyramid count, combined performance, and stage thresholds.
- `data/forum_corpus/post_30680128170647.md` | `XH93773` | value-factor full post on portfolio-level performance comparison and region-by-region quality management.
- `data/forum_corpus/post_30933525139863.md` | `FL58960` | value-factor full post centered on single-dataset alpha discipline and template simplification.
- `data/forum_corpus/post_31002256151831.md` | `OB53521` | PPAC turnover full post on `ts_target_tvr_*` optimization and maxTrade intuition.
- `data/forum_corpus/post_31070381814295.md` | `JJ47083` | beginner failure modes around first-order templates and high correlation.
- `data/forum_corpus/post_31248622176791.md` | `AK76468` | PPAC payment-impact full post tying correlation structure to base payment behavior.
- `data/forum_corpus/post_31280678526615.md` | `HQ17963` | GM-stage full post covering infrastructure, correlation pruning, and staged search workflow.
- `data/forum_corpus/post_32223192365207.md` | `JR23144` | PPAC submission-debug post showing that a prod-correlation fail can mask a power-pool correlation breach.
- `data/forum_corpus/post_33394390003095.md` | `ZV96737` | Master-stage reflection with focus on machine-alpha refinement and super-alpha backtesting.
- `data/forum_corpus/post_33498292829591.md` | `JG21054` | full code post for correlation pruning against alpha pools and higher-order variants.
- `data/forum_corpus/post_33745762241175.md` | `JJ47083` | SAC global top-10 sharing on selection strictness, turnover control, and cross-region submission mix.
- `data/forum_corpus/post_33814296858519.md` | `FD69320` | rapid GM progression full post focused on target-setting, combine protection, and regular-alpha accumulation.
- `data/forum_corpus/post_35136119106839.md` | `GY71341` | workflow full post on regular/super-alpha interplay, combo usage, and template experimentation.
- `data/forum_corpus/post_35565000536087.md` | `LR93609` | PPAC monthly dual world-first sharing on low operator average, low self/prod correlation, and regular-vs-SA tradeoffs.
- `data/forum_corpus/post_38852178542743.md` | `HS88014` | IQC mainland-first full post highlighting diversity, OS awareness, and anti-overfitting mindset.
- `data/forum_corpus/post_38932709256727.md` | `HP65370` | Gold-to-GM full post on field filtering, template-flow reduction, and staged alpha processing.
- `data/forum_corpus/post_32196746752023.md` | `MH33574` | PPAC global-third full post on candidate construction, GPT-assisted screening, and OS-stable pool design.

## Included Search-Snapshot Entries

None currently shipped.

## Successful Recovery

- `32223192365207` | `JR23144` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after MCP detail-page retrieval succeeded during the second expansion pass.
- `32196746752023` | `MH33574` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `31280678526615` | `HQ17963` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `33814296858519` | `FD69320` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `38852178542743` | `HS88014` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `31002256151831` | `OB53521` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `30933525139863` | `FL58960` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `30680128170647` | `XH93773` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `31248622176791` | `AK76468` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `33498292829591` | `JG21054` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `35136119106839` | `GY71341` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.
- `38932709256727` | `HP65370` | upgraded from `search-snapshot` to `full-post` on 2026-04-12 after the local longer-timeout forum client recovered the full body.

## Recovery Targets

No active recovery targets remain inside the shipped corpus.

## Still Deferred

No separate deferred posts remain outside the shipped corpus at the moment. The previously deferred `HS88014` IQC post has been admitted as a Tier 2 search snapshot.