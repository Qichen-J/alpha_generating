from __future__ import annotations

import asyncio
import base64
import io
import sys
import time
from typing import Optional
from urllib.parse import urljoin

import requests

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    elif hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)


def log(message: str, level: str = "INFO") -> None:
    print(f"[{level}] {message}", file=sys.stderr)


def create_base_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def create_authenticated_session(
    *,
    username: str,
    password: str,
    brain_api_url: str = "https://api.worldquantbrain.com",
    interactive_biometric: bool = False,
    headless: bool = False,
    biometric_timeout_seconds: int = 300,
) -> requests.Session:
    session = create_base_session()

    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    response = session.post(
        f"{brain_api_url.rstrip('/')}/authentication",
        headers={"Authorization": f"Basic {encoded}"},
    )

    if response.status_code == 201:
        return session

    if response.status_code == 401:
        auth_mode = response.headers.get("WWW-Authenticate", "")
        location = response.headers.get("Location", "")
        if auth_mode == "persona" and location:
            if not interactive_biometric:
                raise RuntimeError(
                    "Biometric authentication is required. Re-run with interactive biometric support enabled."
                )
            biometric_url = urljoin(response.url, location)
            asyncio.run(
                _complete_biometric_auth(
                    session=session,
                    biometric_url=biometric_url,
                    headless=headless,
                    timeout_seconds=biometric_timeout_seconds,
                )
            )
            return session

    raise RuntimeError(f"Authentication failed with status code {response.status_code}: {response.text}")


async def _complete_biometric_auth(
    *,
    session: requests.Session,
    biometric_url: str,
    headless: bool,
    timeout_seconds: int,
) -> None:
    from playwright.async_api import async_playwright

    log("Opening browser for biometric authentication", "INFO")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=headless,
            args=["--no-sandbox"],
        )
        page = await browser.new_page(user_agent=USER_AGENT)
        await page.goto(biometric_url)

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            await asyncio.sleep(5)
            result = session.post(biometric_url)
            if result.status_code == 201:
                await browser.close()
                log("Biometric authentication completed", "SUCCESS")
                return

        await browser.close()
        raise RuntimeError("Biometric authentication timed out before completion.")


async def add_session_cookies_to_context(session: requests.Session, context) -> None:
    cookies = []
    for cookie in session.cookies:
        cookie_data = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.secure,
            "httpOnly": "HttpOnly" in cookie._rest,
            "sameSite": "Lax",
        }
        if cookie.expires:
            cookie_data["expires"] = cookie.expires
        cookies.append(cookie_data)

    if cookies:
        await context.add_cookies(cookies)
