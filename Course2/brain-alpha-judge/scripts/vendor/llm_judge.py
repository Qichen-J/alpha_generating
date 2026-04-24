from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import requests


class LlmJudge:
    def __init__(self, cfg: Dict[str, Any] | None = None) -> None:
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.provider = str(cfg.get("provider", "openai-compatible"))
        self.model = str(cfg.get("model", "gpt-4o-mini"))
        self.api_url = str(cfg.get("api_url", "https://api.openai.com/v1/chat/completions"))
        self.timeout_seconds = int(cfg.get("timeout_seconds", 60))
        self.language = str(cfg.get("language", "zh-CN"))

        configured_key = str(cfg.get("api_key", "")).strip()
        env_key = (
            os.environ.get("BRAIN_JUDGE_LLM_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        self.api_key = configured_key or env_key

    def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "available": False,
                "reason": "disabled_by_config",
            }

        if not self.api_key:
            return {
                "available": False,
                "reason": "missing_api_key",
            }

        system_prompt = (
            "You are a strict alpha submission judge and an expert quant researcher. "
            "Given quantitative checks, expression features, and provided reference materials (corpus), return a JSON object only. "
            "You must synthesize the quantitative baseline with the insights from the reference documentation completely. "
            "If a hypothetical post-submit diversity projection is provided, you must explicitly consider whether the candidate improves, weakens, or leaves unchanged the portfolio diversity profile. "
            "Use verdict in {READY, REVIEW, BLOCK}. "
            "Never output READY if platform_submit_ok is false. "
            "Provide insightful, professional, and doc-grounded suggestions. "
            "All explanatory text fields must be in Simplified Chinese."
        )

        user_prompt = {
            "task": "Decide submission readiness and provide actionable, doc-grounded comment/suggestions.",
            "required_output_schema": {
                "verdict": "READY|REVIEW|BLOCK",
                "confidence": "float between 0 and 1",
                "comment": "short explanation referring to reference_materials if applicable",
                "strengths": ["list of strengths"],
                "risks": ["list of risks"],
            },
            "language_requirement": self.language,
            "candidate_analysis": payload.get("candidate", payload),
            "reference_materials": payload.get("reference_materials", []),
        }

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
        }
        
        # Some reasoning models like kimi-k2.5 only allow temperature=1
        if "kimi" not in self.model.lower():
            body["temperature"] = 0.1

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            content = ""
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                content = str((choices[0].get("message") or {}).get("content") or "")

            parsed = self._parse_json_content(content)
            verdict = str(parsed.get("verdict", "REVIEW")).upper().strip()
            if verdict not in {"READY", "REVIEW", "BLOCK"}:
                verdict = "REVIEW"

            candidate = payload.get("candidate", payload)
            if not candidate.get("platform_submit_ok") and verdict == "READY":
                verdict = "BLOCK"

            confidence_raw = parsed.get("confidence", 0.5)
            try:
                confidence = max(0.0, min(1.0, float(confidence_raw)))
            except (TypeError, ValueError):
                confidence = 0.5

            strengths = parsed.get("strengths")
            risks = parsed.get("risks")
            if not isinstance(strengths, list):
                strengths = []
            if not isinstance(risks, list):
                risks = []

            return {
                "available": True,
                "provider": self.provider,
                "model": self.model,
                "verdict": verdict,
                "confidence": confidence,
                "comment": str(parsed.get("comment", "")).strip(),
                "strengths": [str(x) for x in strengths][:8],
                "risks": [str(x) for x in risks][:8],
            }
        except Exception as exc:
            return {
                "available": False,
                "reason": str(exc),
                "provider": self.provider,
                "model": self.model,
            }

    def _parse_json_content(self, content: str) -> Dict[str, Any]:
        content = (content or "").strip()
        if not content:
            return {}

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return {}

        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
