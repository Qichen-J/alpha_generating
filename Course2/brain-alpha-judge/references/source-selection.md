# Source Selection

This skill ships a fixed local corpus.

It does not fetch forum posts at runtime.

Corpus expansion can still happen outside the skill and then be baked back in as static files.

## Corpus Rules

- Limit v1 to Chinese forum content.
- Keep the skill self-contained by consuming only local Markdown files.
- Admit posts by author identity, not only by topic quality.
- Save each accepted post as one Markdown file with source metadata.
- Keep the full post body whenever full post retrieval succeeds.
- Keep only high-value comments, usually from allowlisted authors.
- Treat `data/forum_corpus/index.json` as the source of truth for shipped entries.

## Two Corpus Tiers

- Tier 1: `full-post`
- Use when the full forum post body and selected comments were successfully retrieved.
- These entries are the primary basis for extracting durable review standards.

- Tier 2: `search-snapshot`
- Use only when authenticated detail-page retrieval repeatedly times out but MCP forum search returns a strong title, snippet, author, date, and engagement signal.
- These entries are valid static corpus expansion artifacts, but they should be treated as secondary evidence until upgraded to full-post form.
- Do not let search-snapshot entries alone rewrite the rubric without additional confirmation.

## Current Shipped Corpus

- Full-post entries:
- `post_25011325553943.md` | `TL87739`
- `post_28966942842263.md` | `XX42289`
- `post_29083873126551.md` | `XX42289`
- `post_29383292162199.md` | `XX42289`
- `post_30680128170647.md` | `XH93773`
- `post_30933525139863.md` | `FL58960`
- `post_31002256151831.md` | `OB53521`
- `post_31070381814295.md` | `JJ47083`
- `post_31248622176791.md` | `AK76468`
- `post_31280678526615.md` | `HQ17963`
- `post_32223192365207.md` | `JR23144`
- `post_33498292829591.md` | `JG21054`
- `post_33394390003095.md` | `ZV96737`
- `post_33745762241175.md` | `JJ47083`
- `post_33814296858519.md` | `FD69320`
- `post_35136119106839.md` | `GY71341`
- `post_35565000536087.md` | `LR93609`
- `post_38932709256727.md` | `HP65370`
- `post_38852178542743.md` | `HS88014`
- `post_32196746752023.md` | `MH33574`

- Search-snapshot entries:

None currently shipped. Tier 2 remains a fallback acquisition mode for future corpus expansion work.

See `references/corpus-manifest.md` for the role of each file, the upgraded full-post entry, and the remaining recovery targets.

## Traceability Rules

- Record the original URL for every post.
- Record the post ID for every post.
- Record the search query or manual seed that led to the post.
- Record the author used for admission.
- Record the crawl timestamp.
- Record whether the entry is `full-post` or `search-snapshot`.
- Record normalized `topic_tags` for each entry in `data/forum_corpus/index.json`.
- Record `evidence_strength` for each entry in `data/forum_corpus/index.json`.
- Record a retrieval note when a search snapshot exists because detail-page reads timed out.

## Evidence Strength Mapping

- `strong`: full-post body retrieved locally and preserved in the shipped corpus.
- `moderate`: search-snapshot only; title, metadata, and snippet are reliable, but the full thread body is still missing.

## Practical Filtering

- Prefer an explicit allowlist of confirmed high-value authors.
- Use regex author patterns only as a supplement.
- Skip posts whose author identity cannot be confirmed for the current corpus policy.
- Keep corpus expansion outside this skill. If more posts are needed later, fetch them externally or with MCP, then add them back as static Markdown.
