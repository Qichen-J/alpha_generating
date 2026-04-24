from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrainCredentials:
    username: str
    password: str
    brain_api_url: str = "https://api.worldquantbrain.com"
    brain_url: str = "https://platform.worldquantbrain.com"


def _read_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def load_credentials(
    *,
    skill_dir: Path,
    config_filename: str = "configs/config.json",
    allow_env: bool = True,
    allow_home_secrets: bool = True,
) -> BrainCredentials:
    env_username = ""
    env_password = ""
    brain_api_url = os.environ.get("BRAIN_API_URL", "https://api.worldquantbrain.com")
    brain_url = os.environ.get("BRAIN_URL", "https://platform.worldquantbrain.com")

    if allow_env:
        env_username = os.environ.get("BRAIN_USERNAME", os.environ.get("BRAIN_EMAIL", ""))
        env_password = os.environ.get("BRAIN_PASSWORD", "")

    if env_username and env_password:
        return BrainCredentials(
            username=env_username,
            password=env_password,
            brain_api_url=brain_api_url,
            brain_url=brain_url,
        )

    cfg_path = skill_dir / config_filename
    cfg = _read_json_file(cfg_path)
    username = (cfg.get("username") or cfg.get("email") or "").strip()
    password = (cfg.get("password") or "").strip()
    brain_api_url = (cfg.get("BRAIN_API_URL") or brain_api_url).strip() or brain_api_url
    brain_url = (cfg.get("BRAIN_URL") or brain_url).strip() or brain_url

    if username and password:
        return BrainCredentials(
            username=username,
            password=password,
            brain_api_url=brain_api_url,
            brain_url=brain_url,
        )

    if allow_home_secrets:
        secret_path = Path.home() / "secrets" / "platform-brain.json"
        secret = _read_json_file(secret_path)
        username = (secret.get("email") or secret.get("username") or "").strip()
        password = (secret.get("password") or "").strip()
        if username and password:
            return BrainCredentials(
                username=username,
                password=password,
                brain_api_url=brain_api_url,
                brain_url=brain_url,
            )

    raise RuntimeError(
        "Missing BRAIN credentials. Provide either env vars, configs/config.json, "
        "or ~/secrets/platform-brain.json. See configs/config.example.json."
    )
