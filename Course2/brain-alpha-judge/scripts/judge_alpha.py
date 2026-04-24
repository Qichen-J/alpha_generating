from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
VENDOR_DIR = SCRIPT_DIR / "vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from ace_client import AceClient, classify_check_pass, extract_max_correlation
from llm_judge import LlmJudge
from load_credentials import load_credentials


DEFAULT_CORPUS_MAX_TOTAL_CHARS = 12000
DEFAULT_CORPUS_MAX_FILE_CHARS = 900
DEFAULT_TREND_TIME_BUDGET_SECONDS = 10
DEFAULT_TREND_CACHE_TTL_SECONDS = 6 * 60 * 60


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _excerpt_text(value: str, max_chars: int) -> str:
    text = flatten_text(value)
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def load_corpus(
    corpus_dir: Path,
    *,
    max_total_chars: int = DEFAULT_CORPUS_MAX_TOTAL_CHARS,
    max_file_chars: int = DEFAULT_CORPUS_MAX_FILE_CHARS,
) -> List[Dict[str, str]]:
    materials = []
    if not corpus_dir.exists() or not corpus_dir.is_dir():
        return materials

    remaining_chars = max_total_chars
    for file in sorted(corpus_dir.rglob("*")):
        if file.suffix.lower() not in {".md", ".txt"}:
            continue
        if remaining_chars <= 120:
            break

        raw = file.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            continue

        excerpt_budget = min(max_file_chars, remaining_chars)
        excerpt = _excerpt_text(raw, excerpt_budget)
        if not excerpt:
            continue

        materials.append({
            "title": file.stem,
            "path": file.name,
            "content": excerpt,
        })
        remaining_chars -= len(excerpt)

    return materials


def load_candidates(alpha_id: str, input_json: str) -> List[Dict[str, Any]]:
    if alpha_id:
        return [{"alpha_id": alpha_id}]
    if input_json:
        payload = load_json(Path(input_json), [])
        if isinstance(payload, list):
            return payload
        raise RuntimeError("Input JSON must contain a list of candidate objects.")
    raise RuntimeError("Provide either --alpha-id or --input-json.")


def safe_slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    return normalized or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def flatten_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_atom(detail: Dict[str, Any]) -> bool:
    """ATOM alpha means the alpha is single-dataset (pure-signal) by classification."""
    if not isinstance(detail, dict):
        return False

    classifications = detail.get("classifications") or []
    for cls in classifications:
        cid = str((cls or {}).get("id") or (cls or {}).get("name") or "")
        if "SINGLE_DATA_SET" in cid:
            return True

    tags = detail.get("tags") or []
    for tag in tags:
        if isinstance(tag, str) and tag.strip().lower() == "atom":
            return True

    for cls in classifications:
        cid = str((cls or {}).get("id") or (cls or {}).get("name") or "")
        if "ATOM" in cid.upper():
            return True

    return False


def _extract_pyramid_names(detail: Dict[str, Any]) -> List[str]:
    if not isinstance(detail, dict):
        return []

    pyramids = detail.get("pyramids")
    if isinstance(pyramids, list):
        return [p.get("name") for p in pyramids if isinstance(p, dict) and p.get("name")]

    pyramid_themes = detail.get("pyramidThemes") or {}
    if isinstance(pyramid_themes, dict):
        nested = pyramid_themes.get("pyramids")
        if isinstance(nested, list):
            return [p.get("name") for p in nested if isinstance(p, dict) and p.get("name")]

    return []


def _to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_recent_json(path: Path, max_age_seconds: int) -> Any:
    if not path.exists():
        return None
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > max_age_seconds:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _trend_cache_path(outputs_dir: Path, username: str, start_date: str, end_date: str) -> Path:
    cache_key = safe_slug(f"{username}_{start_date}_{end_date}")
    return outputs_dir / f"trend_cache_{cache_key}.json"


def _compute_entropy_normalized(per_pyramid: Dict[str, int]) -> float:
    p = len(per_pyramid)
    if p <= 1:
        return 0.0

    total = sum(per_pyramid.values())
    if total <= 0:
        return 0.0

    entropy = 0.0
    for count in per_pyramid.values():
        q = count / total
        if q > 0:
            entropy -= q * math.log2(q)

    max_entropy = math.log2(p)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def compute_value_factor_trend_score(
    client: AceClient,
    start_date: str,
    end_date: str,
    *,
    time_budget_seconds: int = DEFAULT_TREND_TIME_BUDGET_SECONDS,
) -> Dict[str, Any]:
    """Replicate the platform trend score in standalone skill context.

    A means ATOM alpha count in the window (single-dataset regular submissions).
    """
    regular_alphas: List[Dict[str, Any]] = []
    offset = 0
    limit = 500
    deadline = time.monotonic() + max(5, int(time_budget_seconds or DEFAULT_TREND_TIME_BUDGET_SECONDS))
    partial = False

    while True:
        if time.monotonic() >= deadline:
            partial = True
            break

        page = client.get_user_alphas(
            stage="OS",
            limit=limit,
            offset=offset,
            submission_start_date=start_date,
            submission_end_date=end_date,
        )
        results = page.get("results", []) if isinstance(page, dict) else []
        if not results:
            break

        regular_alphas.extend([alpha for alpha in results if alpha.get("type") == "REGULAR"])

        fetched = len(results)
        total = int(page.get("count", 0)) if isinstance(page, dict) and page.get("count") is not None else 0
        offset += fetched
        if fetched < limit:
            break
        if total and offset >= total:
            break

    atom_count = 0
    per_pyramid: Dict[str, int] = {}
    sampled_regulars = 0
    for alpha in regular_alphas:
        if time.monotonic() >= deadline:
            partial = True
            break

        alpha_id = str(alpha.get("id", "")).strip()
        if not alpha_id:
            continue

        try:
            detail = client.get_alpha_details(alpha_id)
        except Exception:
            continue

        sampled_regulars += 1

        if _is_atom(detail):
            atom_count += 1

        for name in _extract_pyramid_names(detail):
            per_pyramid[name] = per_pyramid.get(name, 0) + 1

    n_total = sampled_regulars
    a_atom = atom_count
    p_covered = len(per_pyramid)

    p_max = None
    try:
        multipliers = client.get_pyramid_multipliers()
        pyramids = multipliers.get("pyramids", []) if isinstance(multipliers, dict) else []
        if isinstance(pyramids, list):
            p_max = len(pyramids)
    except Exception:
        p_max = None

    if not p_max or p_max <= 0:
        p_max = max(p_covered, 1)

    s_a = (a_atom / n_total) if n_total > 0 else 0.0
    s_p = (p_covered / p_max) if p_max > 0 else 0.0
    s_h = _compute_entropy_normalized(per_pyramid)

    return {
        "diversity_score": s_a * s_p * s_h,
        "N": n_total,
        "A": a_atom,
        "P": p_covered,
        "P_max": p_max,
        "S_A": s_a,
        "S_P": s_p,
        "S_H": s_h,
        "per_pyramid_counts": per_pyramid,
        "partial": partial,
        "sampled_regulars": sampled_regulars,
        "fetched_regulars": len(regular_alphas),
        "time_budget_seconds": int(time_budget_seconds or DEFAULT_TREND_TIME_BUDGET_SECONDS),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _unique_names(values: Iterable[Any]) -> List[str]:
    seen = set()
    items: List[str] = []
    for value in values:
        name = str(value or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        items.append(name)
    return items


def _metric_projection(label: str, description: str, before: float, after: float) -> Dict[str, Any]:
    delta = after - before
    epsilon = 1e-12
    if delta > epsilon:
        direction = "increase"
    elif delta < -epsilon:
        direction = "decrease"
    else:
        direction = "unchanged"

    return {
        "label": label,
        "description": description,
        "before": before,
        "after": after,
        "delta": delta,
        "direction": direction,
    }


def project_value_factor_after_submission(
    trend_block: Dict[str, Any],
    platform: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(trend_block, dict) or not trend_block.get("available"):
        return {
            "available": False,
            "reason": "trend_unavailable",
        }

    score = trend_block.get("score")
    if not isinstance(score, dict):
        return {
            "available": False,
            "reason": "trend_score_missing",
        }

    alpha_details = platform.get("alpha_details") if isinstance(platform, dict) else None
    if not isinstance(alpha_details, dict) or not alpha_details:
        return {
            "available": False,
            "reason": "alpha_details_unavailable",
        }

    current_counts_raw = score.get("per_pyramid_counts")
    if not isinstance(current_counts_raw, dict):
        current_counts_raw = {}

    current_counts = {
        str(name): int(count)
        for name, count in current_counts_raw.items()
        if str(name).strip()
    }

    current_n = max(0, int(_safe_float(score.get("N"), 0.0)))
    current_a = max(0, int(_safe_float(score.get("A"), 0.0)))
    current_p_max = max(1, int(_safe_float(score.get("P_max"), 1.0)))

    candidate_is_atom = _is_atom(alpha_details)
    candidate_pyramids = _unique_names(_extract_pyramid_names(alpha_details))
    new_pyramids = [name for name in candidate_pyramids if name not in current_counts]

    projected_counts = dict(current_counts)
    for name in candidate_pyramids:
        projected_counts[name] = projected_counts.get(name, 0) + 1

    projected_n = current_n + 1
    projected_a = current_a + (1 if candidate_is_atom else 0)
    projected_p = len(projected_counts)
    projected_p_max = max(current_p_max, projected_p, 1)
    projected_s_a = (projected_a / projected_n) if projected_n > 0 else 0.0
    projected_s_p = (projected_p / projected_p_max) if projected_p_max > 0 else 0.0
    projected_s_h = _compute_entropy_normalized(projected_counts)
    projected_diversity = projected_s_a * projected_s_p * projected_s_h

    current_s_a = _safe_float(score.get("S_A"), (current_a / current_n) if current_n > 0 else 0.0)
    current_s_p = _safe_float(score.get("S_P"), 0.0)
    current_s_h = _safe_float(score.get("S_H"), _compute_entropy_normalized(current_counts))
    current_diversity = _safe_float(
        score.get("diversity_score"),
        current_s_a * current_s_p * current_s_h,
    )

    components = [
        _metric_projection(
            "ATOM purity (S_A)",
            "Share of submitted regular alphas that are single-dataset ATOM alphas.",
            current_s_a,
            projected_s_a,
        ),
        _metric_projection(
            "Pyramid coverage (S_P)",
            "Covered pyramid categories divided by total pyramid categories.",
            current_s_p,
            projected_s_p,
        ),
        _metric_projection(
            "Pyramid balance (S_H)",
            "Normalized entropy of distribution across covered pyramids.",
            current_s_h,
            projected_s_h,
        ),
    ]

    overall = _metric_projection(
        "Diversity score",
        "Overall score defined as S_A * S_P * S_H.",
        current_diversity,
        projected_diversity,
    )

    notes = [
        "This is a hypothetical incremental projection only; it does not submit anything.",
        "The projection appends the candidate alpha onto the current trend window and recomputes the score.",
    ]
    if not platform.get("platform_submit_ok"):
        notes.append("Platform baseline is not currently passing; this still shows the hypothetical post-submit direction.")
    if not candidate_pyramids:
        notes.append("No pyramid categories were parsed from alpha details, so S_P and S_H may remain unchanged.")
    elif new_pyramids:
        notes.append("This candidate introduces new pyramid coverage, so S_P may improve.")
    else:
        notes.append("This candidate stays within existing pyramids, so the main impact is on S_A and S_H.")

    return {
        "available": True,
        "mode": "hypothetical_if_submitted",
        "candidate_is_atom": candidate_is_atom,
        "candidate_pyramids": candidate_pyramids,
        "new_pyramids": new_pyramids,
        "before": {
            "N": current_n,
            "A": current_a,
            "P": len(current_counts),
            "P_max": current_p_max,
            "S_A": current_s_a,
            "S_P": current_s_p,
            "S_H": current_s_h,
            "diversity_score": current_diversity,
            "per_pyramid_counts": current_counts,
        },
        "after": {
            "N": projected_n,
            "A": projected_a,
            "P": projected_p,
            "P_max": projected_p_max,
            "S_A": projected_s_a,
            "S_P": projected_s_p,
            "S_H": projected_s_h,
            "diversity_score": projected_diversity,
            "per_pyramid_counts": projected_counts,
        },
        "components": components,
        "overall": overall,
        "notes": notes,
    }


def extract_expression(alpha_details: Dict[str, Any]) -> str:
    preferred = [
        alpha_details.get("regular", {}).get("code") if isinstance(alpha_details.get("regular"), dict) else None,
        alpha_details.get("regular"),
        alpha_details.get("expression"),
        alpha_details.get("code"),
    ]
    for candidate in preferred:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    def _walk(node: Any) -> str:
        if isinstance(node, dict):
            for key in ("code", "expression", "regular"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    nested = _walk(value)
                    if nested:
                        return nested
            for value in node.values():
                nested = _walk(value)
                if nested:
                    return nested
        elif isinstance(node, list):
            for item in node:
                nested = _walk(item)
                if nested:
                    return nested
        return ""

    return _walk(alpha_details)


def analyze_expression(expression: str, rubric: List[Dict[str, Any]]) -> Dict[str, Any]:
    expression = expression or ""
    operators = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", expression)
    numbers = [float(item) for item in re.findall(r"(?<![A-Za-z_])(\d+(?:\.\d+)?)", expression)]
    windows = sorted({int(value) for value in numbers if float(value).is_integer() and 1 <= value <= 2000})
    conditional_ops = {"if_else", "trade_when", "where"}
    conditional_count = sum(1 for op in operators if op in conditional_ops)

    heuristics = {
        "operator_count": len(operators),
        "unique_operator_count": len(set(operators)),
        "conditional_count": conditional_count,
        "distinct_windows": windows,
        "noncanonical_windows": [],
    }

    for rule in rubric:
        expr_cfg = rule.get("expression_heuristics")
        if not expr_cfg:
            continue
        canonical = set(expr_cfg.get("canonical_windows", []))
        heuristics["noncanonical_windows"] = [value for value in windows if value not in canonical]
        break
    return heuristics


def baseline_from_platform(client: AceClient, alpha_id: str) -> Dict[str, Any]:
    alpha_details = client.get_alpha_details(alpha_id)
    checks = client.get_submission_checks(alpha_id)
    failed_checks = [check for check in checks if not classify_check_pass(check)]
    passed_checks = [check for check in checks if classify_check_pass(check)]
    self_corr = client.get_self_correlations(alpha_id)
    prod_corr = client.get_prod_correlations(alpha_id)
    yearly_stats = client.get_yearly_stats(alpha_id)

    return {
        "available": True,
        "alpha_details": alpha_details,
        "expression": extract_expression(alpha_details),
        "checks": checks,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "platform_submit_ok": bool(checks) and not failed_checks,
        "max_self_correlation": extract_max_correlation(self_corr),
        "max_prod_correlation": extract_max_correlation(prod_corr),
        "yearly_stats": yearly_stats,
    }


def evaluate_required_fields(candidate: Dict[str, Any], required_fields: Iterable[str]) -> Tuple[bool, List[str]]:
    missing = [field for field in required_fields if not flatten_text(candidate.get(field, ""))]
    return (not missing, missing)


def evaluate_any_fields(candidate: Dict[str, Any], any_fields: Iterable[str]) -> Tuple[bool, List[str]]:
    present = [field for field in any_fields if flatten_text(candidate.get(field, ""))]
    return (bool(present), present)


def evaluate_platform_soft_checks(platform: Dict[str, Any], soft_checks: Dict[str, Any]) -> List[str]:
    if not platform.get("available"):
        return []

    labels = {
        "max_self_correlation": "Max self correlation",
        "max_prod_correlation": "Max prod correlation",
    }
    reasons: List[str] = []
    for key, label in labels.items():
        limit = soft_checks.get(key)
        value = platform.get(key)
        if limit is None or value is None:
            continue
        try:
            limit_value = float(limit)
            actual_value = float(value)
        except (TypeError, ValueError):
            continue
        if actual_value > limit_value:
            reasons.append(f"{label} {actual_value:.3f} exceeds soft limit {limit_value:.3f}.")
    return reasons


def summarize_source_posts(source_posts: Iterable[Dict[str, Any]]) -> List[str]:
    summaries = []
    for item in source_posts:
        if not isinstance(item, dict):
            continue
        post_id = str(item.get("post_id", "")).strip()
        author = str(item.get("author", "")).strip()
        note = flatten_text(item.get("note", ""))
        label = f"{author}#{post_id}" if author and post_id else author or post_id
        if label and note:
            summaries.append(f"{label}: {note}")
        elif label:
            summaries.append(label)
    return summaries


def evaluate_extra_standards(
    candidate: Dict[str, Any],
    rubric: List[Dict[str, Any]],
    heuristics: Dict[str, Any],
    platform: Dict[str, Any],
) -> Dict[str, Any]:
    results = []
    for rule in rubric:
        status = "pass"
        reasons: List[str] = []
        severity = rule.get("severity", "review")

        ok, missing_fields = evaluate_required_fields(candidate, rule.get("required_fields", []))
        if not ok:
            status = severity
            reasons.append(f"Missing required fields: {', '.join(missing_fields)}")

        any_fields = rule.get("any_of_fields", [])
        if any_fields:
            any_ok, present_fields = evaluate_any_fields(candidate, any_fields)
            if not any_ok:
                status = severity
                reasons.append(f"Need at least one supporting field: {', '.join(any_fields)}")
            elif status == "pass":
                reasons.append(f"Supporting evidence provided via: {', '.join(present_fields)}")

        soft_check_reasons = evaluate_platform_soft_checks(platform, rule.get("platform_soft_checks", {}))
        if soft_check_reasons:
            status = severity
            reasons.extend(soft_check_reasons)

        if rule["id"] == "implementation_simplicity":
            expr_cfg = rule.get("expression_heuristics", {})
            max_ops = int(expr_cfg.get("max_operator_count", 25))
            max_cond = int(expr_cfg.get("max_conditional_count", 3))
            max_windows = int(expr_cfg.get("max_distinct_windows", 6))

            if heuristics.get("operator_count", 0) > max_ops:
                status = "review"
                reasons.append(
                    f"Operator count {heuristics['operator_count']} exceeds soft limit {max_ops}."
                )
            if heuristics.get("conditional_count", 0) > max_cond:
                status = "review"
                reasons.append(
                    f"Conditional count {heuristics['conditional_count']} exceeds soft limit {max_cond}."
                )
            if len(heuristics.get("distinct_windows", [])) > max_windows:
                status = "review"
                reasons.append(
                    f"Distinct windows {len(heuristics['distinct_windows'])} exceed soft limit {max_windows}."
                )
            if heuristics.get("noncanonical_windows"):
                status = "review"
                reasons.append(
                    "Uses uncommon window choices that should be justified explicitly: "
                    + ", ".join(str(value) for value in heuristics["noncanonical_windows"])
                    + "."
                )
            if heuristics.get("operator_count", 0) > max_ops * 2 or heuristics.get("conditional_count", 0) > max_cond + 3:
                status = "block"
                reasons.append("Expression complexity is high enough to create an overfitting risk before submission.")

        results.append(
            {
                "id": rule["id"],
                "title": rule["title"],
                "status": status,
                "description": rule["description"],
                "reasons": reasons,
                "source_posts": rule.get("source_posts", []),
            }
        )

    if any(item["status"] == "block" for item in results):
        overall = "block"
    elif any(item["status"] == "review" for item in results):
        overall = "review"
    else:
        overall = "pass"
    return {"overall": overall, "rules": results}


def deterministic_verdict(platform: Dict[str, Any], extra: Dict[str, Any]) -> str:
    if not platform.get("available"):
        return "REVIEW"
    if not platform.get("platform_submit_ok"):
        return "BLOCK"
    if extra.get("overall") == "block":
        return "BLOCK"
    if extra.get("overall") == "review":
        return "REVIEW"
    return "READY"


def build_doc_grounded_suggestions(
    platform: Dict[str, Any],
    extra: Dict[str, Any],
    trend_block: Dict[str, Any],
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    failed = platform.get("failed_checks", []) if isinstance(platform.get("failed_checks"), list) else []
    failed_names = {str(item.get("name", "")).upper() for item in failed if isinstance(item, dict)}

    def add(title: str, actions: List[str], evidence: List[str]) -> None:
        suggestions.append(
            {
                "title": title,
                "actions": actions,
                "evidence": evidence,
            }
        )

    if {"LOW_SHARPE", "LOW_FITNESS"} & failed_names:
        add(
            "先修复 Sharpe/Fitness 主约束",
            [
                "保留核心经济假设，优先做模板化增强而非堆算子。",
                "对同一想法做 3-6 个结构变体并比较 2Y Sharpe 与 Fitness。",
                "若信号长期方向偏负，先测试符号翻转再做细调。",
            ],
            [
                "TL87739#25011325553943",
                "JJ47083#31070381814295",
                "LR93609#35565000536087",
            ],
        )

    if {"LOW_GLB_AMER_SHARPE", "LOW_GLB_EMEA_SHARPE", "LOW_GLB_APAC_SHARPE"} & failed_names:
        add(
            "补做跨区域稳健性",
            [
                "分别检查 AMER/APAC/EMEA 的子表现，定位拖后腿区域。",
                "降低区域特异参数，优先使用跨区域可复用模板。",
                "记录 cross_region_notes，作为提交前证据。",
            ],
            [
                "JJ47083#33745762241175",
                "ZV96737#33394390003095",
            ],
        )

    if "CONCENTRATED_WEIGHT" in failed_names:
        add(
            "控制权重集中",
            [
                "增加稳健归一化/排序步骤并检查 truncation 设置。",
                "结合中性化方式复核单票暴露是否被压制。",
            ],
            [
                "BRAIN checks: CONCENTRATED_WEIGHT",
            ],
        )

    if "POWER_POOL_CORRELATION" in failed_names or "DATA_DIVERSITY" in failed_names:
        add(
            "降低拥挤与相关性风险",
            [
                "避免只围绕单一数据源反复微调，扩展到低相关模板族。",
                "在候选池中优先保留低 self/prod corr 的变体。",
            ],
            [
                "XX42289#28966942842263",
                "LR93609#35565000536087",
            ],
        )

    extra_rules = extra.get("rules", []) if isinstance(extra.get("rules"), list) else []
    missing_evidence_rules = [
        rule for rule in extra_rules if isinstance(rule, dict) and str(rule.get("status", "")).lower() == "review"
    ]
    if missing_evidence_rules:
        add(
            "补齐提交叙述证据（避免 REVIEW）",
            [
                "至少补齐 idea_summary 与 rationale。",
                "补充 template_notes / stability_notes / portfolio_fit_notes / value_factor_notes。",
                "把关键实验写入 cross_universe_notes 与 cross_region_notes。",
            ],
            [
                "extra_submission_rubric.json rules",
            ],
        )

    trend_score = (trend_block or {}).get("score", {}) if isinstance(trend_block, dict) else {}
    s_p = trend_score.get("S_P")
    try:
        s_p_value = float(s_p)
    except (TypeError, ValueError):
        s_p_value = None
    if s_p_value is not None and s_p_value < 0.1:
        add(
            "提升 value-factor 覆盖广度",
            [
                "在保证质量前提下，把提交分布扩展到更多 pyramid 类别。",
                "保持 ATOM 纯度的同时提升 P 与分布均衡度。",
            ],
            [
                "value_factor_trend: S_P",
            ],
        )

    return suggestions[:6]


def _compact_check(check: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": check.get("name"),
        "result": check.get("result"),
        "value": check.get("value"),
        "limit": check.get("limit"),
    }


def build_llm_payload(
    *,
    alpha_id: str,
    platform: Dict[str, Any],
    extra: Dict[str, Any],
    heuristics: Dict[str, Any],
    trend_block: Dict[str, Any],
    projection_block: Dict[str, Any],
    corpus_materials: List[Dict[str, str]],
    deterministic: str,
) -> Dict[str, Any]:
    checks = platform.get("checks", []) if isinstance(platform.get("checks"), list) else []
    failed_checks = platform.get("failed_checks", []) if isinstance(platform.get("failed_checks"), list) else []
    expression = platform.get("expression") or ""

    return {
        "candidate": {
            "alpha_id": alpha_id,
            "platform_available": bool(platform.get("available")),
            "platform_submit_ok": bool(platform.get("platform_submit_ok")),     
            "expression": expression,
            "failed_checks": [_compact_check(item) for item in failed_checks[:20]],
            "checks": [_compact_check(item) for item in checks[:30]],
            "max_self_correlation": platform.get("max_self_correlation"),       
            "max_prod_correlation": platform.get("max_prod_correlation"),       
            "expression_analysis": heuristics,
            "extra": {
                "overall": extra.get("overall"),
                "rules": [
                    {
                        "id": item.get("id"),
                        "status": item.get("status"),
                        "reasons": item.get("reasons", []),
                    }
                    for item in (extra.get("rules") or [])
                ],
            },
            "value_factor_trend": trend_block,
            "value_factor_projection": projection_block,
            "deterministic_verdict": deterministic,
        },
        "reference_materials": corpus_materials
    }


def render_markdown(result: Dict[str, Any]) -> str:
    lines = [
        f"# Alpha Judge Report: {result.get('candidate_label', 'candidate')}",
        "",
        f"- Alpha ID: {result.get('alpha_id', '') or 'N/A'}",
        f"- Platform Submit OK: {result['platform'].get('platform_submit_ok', False)}",
        f"- Extra Standard Status: {result['extra'].get('overall', 'review')}",
        f"- Deterministic Verdict: {result.get('deterministic_verdict', 'REVIEW')}",
        f"- Overall Verdict: {result.get('overall_verdict', 'REVIEW')}",
        f"- Worth Submit Now: {result.get('worth_submit_now', False)}",
        "",
        "## Platform Baseline",
        "",
        f"- Available: {result['platform'].get('available', False)}",
        f"- Failed Checks: {len(result['platform'].get('failed_checks', []))}",
        f"- Max Self Correlation: {result['platform'].get('max_self_correlation')}",
        f"- Max Prod Correlation: {result['platform'].get('max_prod_correlation')}",
        "",
        "## Value Factor Trend Score",
        "",
    ]

    trend = result.get("value_factor_trend") or {}
    if trend.get("available"):
        score = trend.get("score", {})
        lines.extend(
            [
                f"- Window: {trend.get('start_date')} -> {trend.get('end_date')}",
                f"- diversity_score: {score.get('diversity_score')}",
                f"- N (regular submissions): {score.get('N')}",
                f"- A (ATOM regulars): {score.get('A')}",
                f"- P (covered pyramids): {score.get('P')}",
                f"- P_max (all pyramids): {score.get('P_max')}",
                f"- S_A (A/N): {score.get('S_A')}",
                f"- S_P (P/P_max): {score.get('S_P')}",
                f"- S_H (normalized entropy): {score.get('S_H')}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "- Available: False",
                f"- Reason: {trend.get('reason', 'unavailable')}",
                "",
            ]
        )

    lines.extend([
        "## Value Factor Projection If Submitted",
        "",
    ])

    projection = result.get("value_factor_projection") or {}
    if projection.get("available"):
        overall = projection.get("overall") or {}
        lines.extend(
            [
                f"- Candidate is ATOM: {projection.get('candidate_is_atom')}",
                f"- Candidate pyramids: {', '.join(projection.get('candidate_pyramids', [])) or 'None'}",
                f"- New pyramids: {', '.join(projection.get('new_pyramids', [])) or 'None'}",
                f"- Diversity score before: {overall.get('before')}",
                f"- Diversity score after: {overall.get('after')}",
                f"- Diversity delta: {overall.get('delta')}",
                f"- Direction: {overall.get('direction')}",
                "",
            ]
        )
        for item in projection.get("components", []):
            lines.extend(
                [
                    f"### {item.get('label')}",
                    "",
                    f"- Description: {item.get('description')}",
                    f"- Before: {item.get('before')}",
                    f"- After: {item.get('after')}",
                    f"- Delta: {item.get('delta')}",
                    f"- Direction: {item.get('direction')}",
                    "",
                ]
            )
        notes = projection.get("notes") or []
        if notes:
            lines.append("- Notes:")
            for note in notes:
                lines.append(f"  - {note}")
            lines.append("")
    else:
        lines.extend(
            [
                "- Available: False",
                f"- Reason: {projection.get('reason', 'unavailable')}",
                "",
            ]
        )

    lines.extend([
        "## LLM Decision",
        "",
    ])

    llm = result.get("llm_decision") or {}
    if llm.get("available"):
        lines.extend(
            [
                f"- Provider: {llm.get('provider')}",
                f"- Model: {llm.get('model')}",
                f"- Verdict: {llm.get('verdict')}",
                f"- Confidence: {llm.get('confidence')}",
                f"- Comment: {llm.get('comment', '')}",
            ]
        )
        strengths = llm.get("strengths") or []
        risks = llm.get("risks") or []
        if strengths:
            lines.append("- Strengths:")
            for item in strengths:
                lines.append(f"  - {item}")
        if risks:
            lines.append("- Risks:")
            for item in risks:
                lines.append(f"  - {item}")
        lines.append("")
    else:
        lines.extend(
            [
                "- Available: False",
                f"- Reason: {llm.get('reason', 'disabled_or_unconfigured')}",
                "",
            ]
        )

    lines.extend(
        [
            "## Expression Analysis",
            "",
            f"- Operator Count: {result['expression_analysis'].get('operator_count', 0)}",
            f"- Unique Operator Count: {result['expression_analysis'].get('unique_operator_count', 0)}",
            f"- Conditional Count: {result['expression_analysis'].get('conditional_count', 0)}",
            f"- Distinct Windows: {', '.join(str(value) for value in result['expression_analysis'].get('distinct_windows', [])) or 'None'}",
            f"- Noncanonical Windows: {', '.join(str(value) for value in result['expression_analysis'].get('noncanonical_windows', [])) or 'None'}",
            "",
            "## Extra Standards",
            "",
        ]
    )
    for item in result["extra"].get("rules", []):
        lines.append(f"### {item['title']} [{item['status'].upper()}]")
        lines.append("")
        lines.append(item["description"])
        lines.append("")
        source_summaries = summarize_source_posts(item.get("source_posts", []))
        if source_summaries:
            lines.append("Derived from local corpus posts:")
            for summary in source_summaries:
                lines.append(f"- {summary}")
            lines.append("")
        for reason in item.get("reasons", []):
            lines.append(f"- {reason}")
        if not item.get("reasons"):
            lines.append("- No issues raised.")
        lines.append("")

    lines.extend([
        "## Suggestions (Doc-grounded)",
        "",
    ])
    suggestions = result.get("suggestions", []) if isinstance(result.get("suggestions"), list) else []
    if not suggestions:
        lines.append("- None")
        lines.append("")
    else:
        for item in suggestions:
            lines.append(f"### {item.get('title', 'Suggestion')}")
            lines.append("")
            for action in item.get("actions", []):
                lines.append(f"- {action}")
            evidence = item.get("evidence", [])
            if evidence:
                lines.append(f"- Evidence: {', '.join(str(x) for x in evidence)}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Judge whether a regular alpha is worth submitting now.")
    parser.add_argument("--alpha-id", default="")
    parser.add_argument("--input-json", default="")
    parser.add_argument("--config", default=str(SKILL_DIR / "configs" / "config.json"))
    parser.add_argument("--corpus-dir", default=str(SKILL_DIR / "data" / "forum_corpus"))
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-markdown", default="")
    parser.add_argument("--confirm-submit", action="store_true")
    parser.add_argument("--interactive-biometric", action="store_true")
    parser.add_argument("--trend-start-date", default="")
    parser.add_argument("--trend-end-date", default="")
    parser.add_argument("--trend-window-days", type=int, default=365)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(Path(args.config), {})
    judge_cfg = config.get("judge", {}) if isinstance(config, dict) else {}
    trend_cfg = judge_cfg.get("value_factor_trend", {}) if isinstance(judge_cfg, dict) else {}
    llm_cfg = judge_cfg.get("llm", {}) if isinstance(judge_cfg, dict) else {}
    outputs_dir = SKILL_DIR / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    rubric = load_json(SKILL_DIR / "data" / "extra_submission_rubric.json", [])
    candidates = load_candidates(args.alpha_id, args.input_json)

    client = None
    active_username = "unknown"
    try:
        credentials = load_credentials(skill_dir=SKILL_DIR)
        active_username = str(credentials.username or "unknown")
        client = AceClient(
            username=credentials.username,
            password=credentials.password,
            brain_api_url=credentials.brain_api_url,
            interactive_biometric=args.interactive_biometric,
        )
    except Exception:
        client = None

    now_utc = datetime.now(timezone.utc)
    configured_window_days = trend_cfg.get("window_days", args.trend_window_days)
    try:
        trend_window_days = max(1, int(configured_window_days))
    except (TypeError, ValueError):
        trend_window_days = max(1, int(args.trend_window_days))

    trend_enabled = bool(trend_cfg.get("enabled", True))
    trend_start_date = args.trend_start_date.strip() if args.trend_start_date else _to_iso_z(now_utc - timedelta(days=trend_window_days))
    trend_end_date = args.trend_end_date.strip() if args.trend_end_date else _to_iso_z(now_utc)

    corpus_materials = load_corpus(Path(args.corpus_dir))
    cache_cfg = trend_cfg.get("cache", {}) if isinstance(trend_cfg, dict) else {}
    cache_ttl_seconds = int(cache_cfg.get("ttl_seconds", DEFAULT_TREND_CACHE_TTL_SECONDS) or DEFAULT_TREND_CACHE_TTL_SECONDS)
    trend_time_budget_seconds = int(trend_cfg.get("time_budget_seconds", DEFAULT_TREND_TIME_BUDGET_SECONDS) or DEFAULT_TREND_TIME_BUDGET_SECONDS)
    trend_cache_file = _trend_cache_path(outputs_dir, active_username, trend_start_date, trend_end_date)
    cached_trend = _load_recent_json(trend_cache_file, cache_ttl_seconds)

    trend_block: Dict[str, Any]
    if not trend_enabled:
        trend_block = {
            "available": False,
            "reason": "disabled_by_config",
            "start_date": trend_start_date,
            "end_date": trend_end_date,
        }
    elif isinstance(cached_trend, dict) and cached_trend.get("available"):
        trend_block = dict(cached_trend)
        trend_block["cache_hit"] = True
    elif client is None:
        trend_block = {
            "available": False,
            "reason": "client_unavailable",
            "start_date": trend_start_date,
            "end_date": trend_end_date,
        }
    else:
        try:
            trend_score = compute_value_factor_trend_score(
                client,
                trend_start_date,
                trend_end_date,
                time_budget_seconds=trend_time_budget_seconds,
            )
            trend_block = {
                "available": True,
                "start_date": trend_start_date,
                "end_date": trend_end_date,
                "score": trend_score,
                "cache_hit": False,
                "notes": [
                    "A means ATOM alpha count (single-dataset regular alphas in this submission-date window).",
                    "diversity_score = S_A * S_P * S_H",
                ],
            }
            if trend_score.get("partial"):
                trend_block["notes"].append("Trend score is an approximate partial sample bounded by a runtime budget.")
            _write_json(trend_cache_file, trend_block)
        except Exception as exc:
            trend_block = {
                "available": False,
                "reason": str(exc),
                "start_date": trend_start_date,
                "end_date": trend_end_date,
            }

    llm_judge = LlmJudge(llm_cfg)

    reports = []
    for candidate in candidates:
        alpha_id = str(candidate.get("alpha_id", "")).strip()
        platform = {"available": False, "platform_submit_ok": False, "failed_checks": []}
        if alpha_id and client is not None:
            try:
                platform = baseline_from_platform(client, alpha_id)
            except Exception as exc:
                platform = {
                    "available": False,
                    "platform_submit_ok": False,
                    "failed_checks": [{"error": str(exc)}],
                }

        if not candidate.get("expression") and platform.get("expression"):
            candidate["expression"] = platform["expression"]

        heuristics = analyze_expression(candidate.get("expression", ""), rubric)
        extra = evaluate_extra_standards(candidate, rubric, heuristics, platform)
        rule_based_verdict = deterministic_verdict(platform, extra)
        projection = project_value_factor_after_submission(trend_block, platform)

        llm_payload = build_llm_payload(
            alpha_id=alpha_id,
            platform=platform,
            extra=extra,
            heuristics=heuristics,
            trend_block=trend_block,
            projection_block=projection,
            corpus_materials=corpus_materials,
            deterministic=rule_based_verdict,
        )
        llm_decision = llm_judge.decide(llm_payload)
        if llm_decision.get("available") and llm_decision.get("verdict") in {"READY", "REVIEW", "BLOCK"}:
            overall_verdict = str(llm_decision.get("verdict"))
        else:
            overall_verdict = rule_based_verdict

        report = {
            "alpha_id": alpha_id,
            "candidate_label": alpha_id or safe_slug(candidate.get("idea_summary", "candidate")),
            "platform": platform,
            "value_factor_trend": trend_block,
            "value_factor_projection": projection,
            "expression_analysis": heuristics,
            "extra": extra,
            "deterministic_verdict": rule_based_verdict,
            "llm_decision": llm_decision,
            "overall_verdict": overall_verdict,
            "platform_submit_ok": bool(platform.get("platform_submit_ok")),
            "worth_submit_now": overall_verdict == "READY" and bool(platform.get("platform_submit_ok")),
            "submit_action": "not_attempted",
        }

        report["suggestions"] = build_doc_grounded_suggestions(platform, extra, trend_block)

        if args.confirm_submit and report["worth_submit_now"] and alpha_id and client is not None:
            report["submit_action"] = "submitted" if client.submit_alpha(alpha_id) else "submit_failed"
        elif args.confirm_submit and not report["worth_submit_now"]:
            report["submit_action"] = "blocked_before_submit"
        elif report["worth_submit_now"]:
            report["submit_action"] = "confirmation_required"

        reports.append(report)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_json = Path(args.output_json) if args.output_json else outputs_dir / f"judge_{timestamp}.json"
    output_markdown = Path(args.output_markdown) if args.output_markdown else outputs_dir / f"judge_{timestamp}.md"

    output_json.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = "\n\n".join(render_markdown(report) for report in reports)
    output_markdown.write_text(markdown, encoding="utf-8")

    print(json.dumps({"json": str(output_json), "markdown": str(output_markdown), "count": len(reports)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
