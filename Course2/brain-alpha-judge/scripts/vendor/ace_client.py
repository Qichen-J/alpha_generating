from __future__ import annotations

import time
from typing import Any, Dict, List

from auth_utils import create_authenticated_session


class AceClient:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        brain_api_url: str = "https://api.worldquantbrain.com",
        interactive_biometric: bool = False,
    ) -> None:
        self.base_url = brain_api_url.rstrip("/")
        self.session = create_authenticated_session(
            username=username,
            password=password,
            brain_api_url=self.base_url,
            interactive_biometric=interactive_biometric,
        )

    def _request_json(self, method: str, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        while True:
            response = self.session.request(method, url)
            retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
            if retry_after:
                time.sleep(float(retry_after))
                continue
            response.raise_for_status()
            text = (response.text or "").strip()
            return response.json() if text else {}

    def get_alpha_details(self, alpha_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"/alphas/{alpha_id}")

    def get_submission_checks(self, alpha_id: str) -> List[Dict[str, Any]]:
        payload = self._request_json("GET", f"/alphas/{alpha_id}/check")
        return payload.get("is", {}).get("checks", [])

    def get_self_correlations(self, alpha_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"/alphas/{alpha_id}/correlations/self")

    def get_prod_correlations(self, alpha_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"/alphas/{alpha_id}/correlations/prod")

    def get_yearly_stats(self, alpha_id: str) -> Dict[str, Any]:
        return self._request_json("GET", f"/alphas/{alpha_id}/recordsets/yearly-stats")

    def get_user_alphas(
        self,
        *,
        stage: str = "OS",
        limit: int = 500,
        offset: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
        submission_start_date: str | None = None,
        submission_end_date: str | None = None,
        order: str | None = None,
        hidden: bool | None = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "stage": stage,
            "limit": limit,
            "offset": offset,
        }
        if start_date:
            params["dateCreated>"] = start_date
        if end_date:
            params["dateCreated<"] = end_date
        if submission_start_date:
            params["dateSubmitted>"] = submission_start_date
        if submission_end_date:
            params["dateSubmitted<"] = submission_end_date
        if order:
            params["order"] = order
        if hidden is not None:
            params["hidden"] = str(hidden).lower()

        url = f"{self.base_url}/users/self/alphas"
        while True:
            response = self.session.get(url, params=params)
            retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
            if retry_after:
                time.sleep(float(retry_after))
                continue
            response.raise_for_status()
            text = (response.text or "").strip()
            return response.json() if text else {}

    def get_pyramid_multipliers(self) -> Dict[str, Any]:
        return self._request_json("GET", "/users/self/activities/pyramid-multipliers")

    def submit_alpha(self, alpha_id: str) -> bool:
        response = self.session.post(f"{self.base_url}/alphas/{alpha_id}/submit")
        while True:
            retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
            if not retry_after:
                break
            time.sleep(float(retry_after))
            response = self.session.get(f"{self.base_url}/alphas/{alpha_id}/submit")
        return response.status_code == 200


def classify_check_pass(check: Dict[str, Any]) -> bool:
    for key in ("result", "status", "checkResult"):
        value = check.get(key)
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"pass", "passed", "ok", "true", "success"}:
            return True
        if normalized in {"fail", "failed", "false", "error"}:
            return False
    return False


def extract_max_correlation(payload: Any) -> float | None:
    values: List[float] = []

    def _walk(node: Any, parent_key: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                _walk(value, key)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item, parent_key)
            return
        if isinstance(node, (int, float)) and "corr" in parent_key.lower():
            values.append(float(node))

    _walk(payload)
    return max(values) if values else None
