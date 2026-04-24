#!/usr/bin/env python3
"""Generate and submit WorldQuant Brain alpha simulations until a target number
of UNIQUE PLATFORM ALPHA IDs is reached.

This version expands the template space and raises submission ceilings.
It still dedupes both local expressions and returned platform alpha IDs.
"""

import getpass
import hashlib
import itertools
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from os.path import expanduser

import requests
from requests.auth import HTTPBasicAuth

API_URL = "https://api.worldquantbrain.com/simulations"
AUTH_URL = "https://api.worldquantbrain.com/authentication"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(SCRIPT_DIR, "simulate_5000_alphas_results.json")
CREDENTIALS_FILE = os.environ.get("BRAIN_CREDENTIALS_FILE", expanduser("~/brain_credentials_copy.txt"))

MAX_CONCURRENT_SIMULATIONS = int(os.environ.get("MAX_CONCURRENT_SIMULATIONS", "1"))
POLL_INTERVAL_SECONDS = 5
MAX_SUBMISSION_RETRIES = 5
RETRY_AFTER_SECONDS = 10
TARGET_UNIQUE_ALPHA_IDS = int(os.environ.get("TARGET_UNIQUE_ALPHA_IDS", "5000"))
MAX_TOTAL_SUBMISSIONS = int(os.environ.get("MAX_TOTAL_SUBMISSIONS", "60000"))
MAX_GENERATED_CANDIDATES = int(os.environ.get("MAX_GENERATED_CANDIDATES", "300000"))

API_TOKEN = os.environ.get("BRAIN_API_TOKEN")
BRAIN_EMAIL = os.environ.get("BRAIN_EMAIL")
BRAIN_PASSWORD = os.environ.get("BRAIN_PASSWORD")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

session = requests.Session()
login_method = None
auth_lock = threading.Lock()
CURRENT_EMAIL = BRAIN_EMAIL
CURRENT_PASSWORD = BRAIN_PASSWORD
LAST_AUTH_TIME = 0.0
AUTH_REFRESH_SECONDS = int(os.environ.get("AUTH_REFRESH_SECONDS", "12600"))



def authenticate_with_basic(email, password):
    temp_session = requests.Session()
    temp_session.auth = HTTPBasicAuth(email, password)
    temp_session.headers.update(HEADERS)
    response = temp_session.post(AUTH_URL)
    print(f"Basic auth response: {response.status_code} {response.text}")
    if response.status_code in (200, 201):
        return temp_session
    return None


def authenticate_with_body(email, password, body_type="email"):
    temp_session = requests.Session()
    temp_session.headers.update(HEADERS)
    payload = {"email" if body_type == "email" else "username": email, "password": password}
    response = temp_session.post(AUTH_URL, json=payload)
    print(f"Body auth ({body_type}) response: {response.status_code} {response.text}")
    if response.status_code in (200, 201):
        return temp_session
    return None


def authenticate_with_credentials(email, password):
    auth_session = authenticate_with_basic(email, password)
    if auth_session is None:
        auth_session = authenticate_with_body(email, password, body_type="email")
    if auth_session is None:
        auth_session = authenticate_with_body(email, password, body_type="username")
    return auth_session


def prompt_for_credentials():
    try:
        if not sys.stdin.isatty():
            return None, None
        email = input("请输入你的 Brain 登录邮箱：").strip()
        password = getpass.getpass("请输入你的 Brain 登录密码：")
    except KeyboardInterrupt:
        print("\n输入已取消。请重新运行脚本。")
        sys.exit(1)
    except EOFError:
        return None, None
    return email, password


def load_credentials_file():
    if not os.path.exists(CREDENTIALS_FILE):
        return None, None

    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"Failed to load credentials file {CREDENTIALS_FILE}: {exc}")
        return None, None

    if isinstance(data, dict):
        return data.get("email") or data.get("username"), data.get("password")
    if isinstance(data, list) and len(data) >= 2:
        return data[0], data[1]
    return None, None


def authenticate():
    global login_method, CURRENT_EMAIL, CURRENT_PASSWORD, LAST_AUTH_TIME

    if BRAIN_EMAIL and BRAIN_PASSWORD:
        auth_session = authenticate_with_credentials(BRAIN_EMAIL, BRAIN_PASSWORD)
        if auth_session is None:
            print("Authentication failed. 请确认邮箱/密码是否正确。")
            sys.exit(1)
        session.headers.update(HEADERS)
        session.cookies.update(auth_session.cookies)
        session.auth = HTTPBasicAuth(BRAIN_EMAIL, BRAIN_PASSWORD)
        CURRENT_EMAIL = BRAIN_EMAIL
        CURRENT_PASSWORD = BRAIN_PASSWORD
        LAST_AUTH_TIME = time.time()
        login_method = "credentials"
        print("Using email/password authentication.")
        return

    if API_TOKEN:
        session.headers.update({"Authorization": f"Bearer {API_TOKEN}", **HEADERS})
        LAST_AUTH_TIME = time.time()
        login_method = "token"
        print("Using API token authentication.")
        return

    email, password = load_credentials_file()
    if email and password:
        auth_session = authenticate_with_credentials(email, password)
        if auth_session is not None:
            session.headers.update(HEADERS)
            session.cookies.update(auth_session.cookies)
            session.auth = HTTPBasicAuth(email, password)
            CURRENT_EMAIL = email
            CURRENT_PASSWORD = password
            LAST_AUTH_TIME = time.time()
            login_method = "credentials"
            print(f"Loaded credentials from {CREDENTIALS_FILE}")
            return

    email, password = prompt_for_credentials()
    if not email or not password:
        print("ERROR: 当前终端不支持交互输入。请用环境变量提供认证信息。")
        sys.exit(1)

    auth_session = authenticate_with_credentials(email, password)
    if auth_session is None:
        print("Authentication failed. 请确认邮箱/密码是否正确。")
        sys.exit(1)

    session.headers.update(HEADERS)
    session.cookies.update(auth_session.cookies)
    session.auth = HTTPBasicAuth(email, password)
    CURRENT_EMAIL = email
    CURRENT_PASSWORD = password
    LAST_AUTH_TIME = time.time()
    login_method = "credentials"
    print("Using email/password authentication.")


authenticate()

COMMON_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 4,
    "neutralization": "MARKET",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "ON",
    "language": "FASTEXPR",
    "visualization": False,
}

BASE_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "returns",
    "cap",
    "assets",
    "sharesout",
]

# Keep the library mostly to raw fields or dimensionless transforms so template
# combinations do not trip Brain's unit checker.
SERIES_LIBRARY = [
    ("open", "open"),
    ("high", "high"),
    ("low", "low"),
    ("close", "close"),
    ("volume", "volume"),
    ("returns", "returns"),
    ("cap", "cap"),
    ("assets", "assets"),
    ("sharesout", "sharesout"),
    ("turnover", "volume / sharesout"),
    ("hl_spread", "(high - low) / close"),
    ("oc_return", "(close - open) / open"),
    ("co_gap", "(open - ts_delay(close, 1)) / ts_delay(close, 1)"),
    ("price_mid_dev", "(((high + low) / 2) - close) / close"),
    ("cap_to_assets", "cap / assets"),
    ("asset_to_cap", "assets / cap"),
    ("ret_range_mix", "returns * ((high - low) / close)"),
]

WINDOWS = [5, 10, 21, 42, 63, 126, 252, 378, 504]
SHORT_WINDOWS = [3, 5, 10, 21, 42]
LONG_WINDOWS = [63, 126, 252, 378, 504]
NEUTRAL_GROUPS = ["industry", "sector", "subindustry"]
FINAL_TRANSFORMS = ["rank", "zscore"]
COMBINE_OPS = ["+", "-", "*"]
GROUP_BUCKETS = [
    "bucket(rank(cap), range='0.1,1,0.1')",
    "bucket(rank(cap), range='0,1,0.1')",
    "bucket(rank(cap), range='0.2,1,0.2')",
]


def normalize_expression(expr):
    expr = re.sub(r"\s+", " ", expr.strip())
    expr = expr.replace(" ;", ";")
    return expr


def expression_fingerprint(expr):
    return hashlib.sha256(normalize_expression(expr).encode("utf-8")).hexdigest()


def canonical_pair(label_a, label_b, window_a, window_b, op):
    if op in {"+", "*"}:
        left = (label_a, window_a)
        right = (label_b, window_b)
        if right < left:
            return label_b, label_a, window_b, window_a
    return label_a, label_b, window_a, window_b


def build_expression(template_name, series_a, series_b, window_a, window_b, neutral, final_transform, combine_op, bucket_group):
    label_a, expr_a = series_a
    label_b, expr_b = series_b
    label_a, label_b, window_a, window_b = canonical_pair(label_a, label_b, window_a, window_b, combine_op)
    label_to_expr = {name: expr for name, expr in SERIES_LIBRARY}
    expr_a = label_to_expr[label_a]
    expr_b = label_to_expr[label_b]

    if template_name == "single_ts":
        expr = (
            f"x = ts_zscore({expr_a}, {window_a});"
            f" alpha = group_neutralize(x, {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "dual_ts":
        expr = (
            f"a = ts_zscore({expr_a}, {window_a});"
            f" b = ts_zscore({expr_b}, {window_b});"
            f" alpha = group_neutralize(a {combine_op} b, {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "rank_spread":
        expr = (
            f"a = group_rank({expr_a}, {neutral});"
            f" b = group_rank({expr_b}, {neutral});"
            f" alpha = a {combine_op} b;"
            f" {final_transform}(alpha)"
        )

    elif template_name == "regression_residual":
        expr = (
            f"a = ts_zscore({expr_a}, {window_a});"
            f" b = ts_zscore({expr_b}, {window_b});"
            f" residual = ts_regression(a, b, {window_a});"
            f" {final_transform}(residual)"
        )

    elif template_name == "delta_combo":
        expr = (
            f"a = ts_zscore(ts_delta({expr_a}, {window_a}), {window_b});"
            f" b = ts_zscore(ts_mean({expr_b}, {window_b}), {window_a});"
            f" alpha = group_neutralize(a {combine_op} b, {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "vol_adj":
        expr = (
            f"a = ts_zscore({expr_a}, {window_a});"
            f" b = ts_std_dev(a, {window_b});"
            f" alpha = group_neutralize(a / abs(b), {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "mixed_triplet":
        expr = (
            f"a = ts_rank({expr_a}, {window_a});"
            f" b = ts_zscore({expr_b}, {window_b});"
            f" c = ts_delta(returns, {window_a});"
            f" alpha = group_neutralize((a {combine_op} b) - c, {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "small_and_steady":
        expr = (
            f"a = ts_zscore({expr_a}, {window_a});"
            f" risk = ts_std_dev(a, {window_b});"
            f" alpha = -a * risk;"
            f" {final_transform}(group_neutralize(alpha, {neutral}))"
        )

    elif template_name == "corr_reversal":
        expr = (
            f"a = ts_corr({expr_a}, {expr_b}, {window_a});"
            f" b = ts_zscore(ts_delta({expr_a}, {window_b}), {window_a});"
            f" alpha = group_neutralize((-a) {combine_op} b, {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "double_neutral":
        expr = (
            f"a = ts_zscore({expr_a}, {window_a});"
            f" b = group_neutralize(a, {neutral});"
            f" c = group_neutralize(b, {bucket_group});"
            f" {final_transform}(c)"
        )

    elif template_name == "range_break":
        expr = (
            f"a = ts_zscore(ts_mean(({expr_a}), {window_a}), {window_b});"
            f" b = ts_std_dev(a, {window_b});"
            f" alpha = group_neutralize(a / abs(b), {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "overnight_turnover":
        expr = (
            f"gap = ts_mean((open - ts_delay(close, 1)) / ts_delay(close, 1), {window_a});"
            f" turn = ts_mean(volume / sharesout, {window_b});"
            f" alpha = group_neutralize(gap {combine_op} turn, {neutral});"
            f" {final_transform}(alpha)"
        )

    elif template_name == "mean_vs_rank":
        expr = (
            f"a = ts_zscore(ts_mean({expr_a}, {window_a}), {window_b});"
            f" b = ts_rank({expr_b}, {window_b});"
            f" alpha = group_neutralize(a {combine_op} b, {neutral});"
            f" {final_transform}(alpha)"
        )

    else:
        raise ValueError(f"Unknown template_name: {template_name}")

    safe_bucket = bucket_group.replace("bucket(rank(cap), range='", "bucket_").replace("')", "").replace(",", "_").replace(" ", "")
    label = f"{template_name}_{label_a}_{label_b}_w{window_a}_{window_b}_{neutral}_{final_transform}_{combine_op}_{safe_bucket}"
    return normalize_expression(expr), label


def candidate_stream():
    template_names = [
        "single_ts",
        "dual_ts",
        "rank_spread",
        "regression_residual",
        "delta_combo",
        "vol_adj",
        "mixed_triplet",
        "small_and_steady",
        "corr_reversal",
        "double_neutral",
        "range_break",
        "overnight_turnover",
        "mean_vs_rank",
    ]

    field_pairs = [(a, b) for a in SERIES_LIBRARY for b in SERIES_LIBRARY if a[0] != b[0]]
    param_space = itertools.product(
        template_names,
        field_pairs,
        WINDOWS,
        WINDOWS,
        NEUTRAL_GROUPS,
        FINAL_TRANSFORMS,
        COMBINE_OPS,
        GROUP_BUCKETS,
    )

    yielded = 0
    seen_fingerprints = set()
    for template_name, (series_a, series_b), window_a, window_b, neutral, final_transform, combine_op, bucket_group in param_space:
        if template_name in {"overnight_turnover", "corr_reversal"} and window_a > 126:
            continue
        if template_name in {"small_and_steady", "range_break"} and window_b < 10:
            continue
        if template_name == "double_neutral" and combine_op != "+":
            # combine_op is unused for this family; freeze it to shrink exact duplicates.
            continue
        expr, label = build_expression(
            template_name,
            series_a,
            series_b,
            window_a,
            window_b,
            neutral,
            final_transform,
            combine_op,
            bucket_group,
        )
        fp = expression_fingerprint(expr)
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        yielded += 1
        yield {
            "expression": expr,
            "label": label,
            "fingerprint": fp,
        }
        if yielded >= MAX_GENERATED_CANDIDATES:
            return


def build_payload(expression):
    return {
        "type": "REGULAR",
        "settings": COMMON_SETTINGS,
        "regular": expression,
    }


def safe_location(response):
    location = response.headers.get("Location")
    if not location:
        raise ValueError("Simulation response did not return Location header")
    return location


def refresh_request_session(request_session):
    if request_session is None:
        return
    request_session.headers.clear()
    request_session.headers.update(session.headers)
    request_session.cookies.clear()
    request_session.cookies.update(session.cookies)
    request_session.auth = session.auth


def maybe_refresh_auth(request_session=None, force=False):
    if login_method != "credentials":
        return False
    if not force and (time.time() - LAST_AUTH_TIME) < AUTH_REFRESH_SECONDS:
        return False
    reauthenticate_session("proactive refresh before request")
    refresh_request_session(request_session)
    return True


def is_auth_error(response=None, error_text=""):
    status_code = getattr(response, "status_code", None)
    if status_code in {401, 403}:
        return True
    text = (error_text or "").lower()
    auth_markers = ["unauthorized", "authentication", "forbidden", "token", "expired", "permission"]
    return any(marker in text for marker in auth_markers)


def reauthenticate_session(reason=""):
    global login_method, CURRENT_EMAIL, CURRENT_PASSWORD, LAST_AUTH_TIME
    with auth_lock:
        print(f"Re-authenticating session{': ' + reason if reason else ''}...")

        if login_method == "token":
            if API_TOKEN:
                session.headers.clear()
                session.headers.update({"Authorization": f"Bearer {API_TOKEN}", **HEADERS})
                LAST_AUTH_TIME = time.time()
                print("Re-authenticated with API token.")
                return
            if CURRENT_EMAIL and CURRENT_PASSWORD:
                print("API token unavailable; falling back to saved email/password.")
                login_method = "credentials"
            else:
                raise RuntimeError("API token missing; cannot re-authenticate.")

        email = CURRENT_EMAIL or BRAIN_EMAIL
        password = CURRENT_PASSWORD or BRAIN_PASSWORD
        if (not email or not password) and os.path.exists(CREDENTIALS_FILE):
            file_email, file_password = load_credentials_file()
            email = email or file_email
            password = password or file_password

        if not email or not password:
            raise RuntimeError("Missing email/password for session refresh.")

        auth_session = authenticate_with_credentials(email, password)
        if auth_session is None:
            raise RuntimeError("Re-authentication failed.")

        session.headers.clear()
        session.headers.update(HEADERS)
        session.cookies.clear()
        session.cookies.update(auth_session.cookies)
        session.auth = HTTPBasicAuth(email, password)
        CURRENT_EMAIL = email
        CURRENT_PASSWORD = password
        LAST_AUTH_TIME = time.time()
        login_method = "credentials"
        print("Re-authenticated with email/password.")


def request_with_retry(method, url, *, request_session=None, max_attempts=6, **kwargs):
    s = request_session or session
    backoff = 3
    maybe_refresh_auth(request_session=s if request_session is not None else None)
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = s.request(method, url, timeout=60, **kwargs)

            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", RETRY_AFTER_SECONDS))
                print(f"HTTP 429 on {method} {url}; sleeping {wait}s (attempt {attempt}/{max_attempts})")
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                wait = min(backoff, 30)
                print(f"HTTP {response.status_code} on {method} {url}; sleeping {wait}s (attempt {attempt}/{max_attempts})")
                time.sleep(wait)
                backoff *= 2
                continue

            if is_auth_error(response=response, error_text=getattr(response, "text", "")):
                if attempt == max_attempts:
                    return response
                reauthenticate_session(f"{method} {url}")
                refresh_request_session(request_session)
                continue

            return response
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            response = getattr(exc, "response", None)
            if response is not None and is_auth_error(response=response, error_text=getattr(response, "text", "")) and attempt < max_attempts:
                reauthenticate_session(f"exception on {method} {url}")
                refresh_request_session(request_session)
                continue

            wait = min(backoff, 30)
            print(f"Request error on {method} {url}: {exc}; sleeping {wait}s (attempt {attempt}/{max_attempts})")
            time.sleep(wait)
            backoff *= 2

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"request_with_retry exhausted attempts for {method} {url}")


def make_thread_session():
    thread_session = requests.Session()
    thread_session.headers.update(session.headers)
    thread_session.cookies.update(session.cookies)
    thread_session.auth = session.auth
    return thread_session


def extract_alpha_id(progress_data):
    alpha_obj = progress_data.get("alpha")
    if isinstance(alpha_obj, dict):
        for key in ("id", "alphaId", "alpha_id"):
            value = alpha_obj.get(key)
            if value:
                return str(value)
    for key in ("alphaId", "alpha_id", "id"):
        value = progress_data.get(key)
        if value:
            return str(value)
    return None


def load_existing_results():
    if not os.path.exists(RESULTS_FILE):
        return {}

    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except Exception as exc:
        print(f"Failed to load existing results: {exc}. Starting fresh.")
        return {}

    results = {}
    for record in existing:
        idx = record.get("index")
        if not isinstance(idx, int):
            continue
        if "fingerprint" not in record and record.get("payload", {}).get("regular"):
            record["fingerprint"] = expression_fingerprint(record["payload"]["regular"])
        if "alpha_id" not in record and isinstance(record.get("result"), dict):
            record["alpha_id"] = extract_alpha_id(record["result"])
        results[idx] = record
    return results


def save_results(results_dict):
    tmp_path = RESULTS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump([results_dict[i] for i in sorted(results_dict)], f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, RESULTS_FILE)


def refresh_saved_simulation_status(results_dict):
    changed = False
    for idx, record in list(results_dict.items()):
        if record.get("status") in {"COMPLETED", "DUPLICATE_ALPHA_ID", "FAILED", "ERROR"}:
            continue
        location = record.get("location")
        if not location:
            continue

        try:
            response = request_with_retry("GET", location)
            response.raise_for_status()
            progress_data = response.json()
            status = progress_data.get("status", "unknown").strip().upper()
            error = progress_data.get("error") or progress_data.get("message")
            has_alpha = "alpha" in progress_data
            alpha_id = extract_alpha_id(progress_data)

            if has_alpha and not error:
                record["status"] = "COMPLETED"
                record["result"] = progress_data
                record["alpha_id"] = alpha_id
                changed = True
            elif status in {"ERROR", "FAILED", "CANCELLED"} or error:
                record["status"] = "FAILED"
                record["result"] = progress_data
                record["alpha_id"] = alpha_id
                changed = True
        except Exception as exc:
            print(f"[{idx}] failed to refresh saved location: {exc}")

    if changed:
        save_results(results_dict)
    return results_dict


def run_simulation(task):
    sim_index = task["index"]
    expr = task["expression"]
    label = task["label"]
    fingerprint = task["fingerprint"]

    payload = build_payload(expr)
    sim_record = {
        "index": sim_index,
        "label": label,
        "fingerprint": fingerprint,
        "payload": payload,
        "location": None,
        "status": "SUBMITTED",
        "result": None,
        "alpha_id": None,
    }

    s = make_thread_session()

    try:
        # --- 1. POST 提交阶段 ---
        try:
            response = request_with_retry("POST", API_URL, request_session=s, max_attempts=MAX_SUBMISSION_RETRIES + 1, json=payload)
            response.raise_for_status()
            sim_record["location"] = safe_location(response)
            print(f"[{sim_index}] SUBMITTED :: {label} :: location={sim_record['location']}")
        except requests.exceptions.RequestException as exc:
            sim_record["status"] = "ERROR"
            sim_record["result"] = {"error": getattr(exc.response, "text", str(exc)) if hasattr(exc, 'response') else str(exc)}
            return sim_record
        except Exception as exc:
            sim_record["status"] = "ERROR"
            sim_record["result"] = {"error": str(exc)}
            return sim_record

        # --- 2. GET 轮询阶段 ---
        total_poll_seconds = 0.0
        poll_count = 0
        while True:
            try:
                progress_response = request_with_retry("GET", sim_record["location"], request_session=s)
                progress_response.raise_for_status()
                
                # 增加 JSON 解析保护
                try:
                    progress_data = progress_response.json()
                except ValueError:
                    raise requests.exceptions.RequestException("Invalid JSON response (Possible HTML error page)")

                status = progress_data.get("status", "unknown").strip().upper()
                error = progress_data.get("error") or progress_data.get("message")
                has_alpha = "alpha" in progress_data
                alpha_id = extract_alpha_id(progress_data)
                sim_record["alpha_id"] = alpha_id
                
                retry_after = float(progress_response.headers.get("Retry-After", POLL_INTERVAL_SECONDS))
                retry_after = max(1.0, min(retry_after, 60.0))
                poll_count += 1
                
                print(
                    f"[{sim_index}] POLL #{poll_count} :: status={status} :: has_alpha={has_alpha} :: "
                    f"alpha_id={alpha_id or '-'} :: waited={total_poll_seconds:.1f}s :: next_wait={retry_after}s"
                )

                if has_alpha and not error:
                    sim_record["status"] = "COMPLETED"
                    sim_record["result"] = progress_data
                    break

                if status in {"ERROR", "FAILED", "CANCELLED"} or error:
                    sim_record["status"] = "FAILED"
                    sim_record["result"] = progress_data
                    break

                total_poll_seconds += retry_after if retry_after > 0 else POLL_INTERVAL_SECONDS
                if total_poll_seconds >= 300:
                    sim_record["status"] = "TIMEOUT"
                    sim_record["result"] = progress_data
                    break

                time.sleep(retry_after if retry_after > 0 else POLL_INTERVAL_SECONDS)
                
            except requests.exceptions.RequestException as exc:
                sim_record["status"] = "ERROR"
                sim_record["result"] = {"error": getattr(exc.response, "text", str(exc)) if hasattr(exc, 'response') else str(exc)}
                break # 退出 while 轮询
            except Exception as exc:
                sim_record["status"] = "ERROR"
                sim_record["result"] = {"error": str(exc)}
                break # 退出 while 轮询

    finally:
        # 👑 最关键的一步：强制释放系统资源
        s.close()

    return sim_record
def summarize(results_dict):
    counts = {}
    for status in ["COMPLETED", "DUPLICATE_ALPHA_ID", "TIMEOUT", "FAILED", "ERROR"]:
        counts[status] = sum(1 for r in results_dict.values() if r.get("status") == status)
    counts["UNIQUE_LOCAL_EXPRESSIONS"] = len({r.get("fingerprint") for r in results_dict.values() if r.get("fingerprint")})
    counts["UNIQUE_ALPHA_IDS"] = len({r.get("alpha_id") for r in results_dict.values() if r.get("alpha_id")})
    return counts


def main():
    print(f"Using results file: {RESULTS_FILE}")
    print(
        f"Config | TARGET_UNIQUE_ALPHA_IDS={TARGET_UNIQUE_ALPHA_IDS} | "
        f"MAX_TOTAL_SUBMISSIONS={MAX_TOTAL_SUBMISSIONS} | "
        f"MAX_GENERATED_CANDIDATES={MAX_GENERATED_CANDIDATES} | "
        f"MAX_CONCURRENT_SIMULATIONS={MAX_CONCURRENT_SIMULATIONS} | "
        f"AUTH_REFRESH_SECONDS={AUTH_REFRESH_SECONDS}"
    )

    results_dict = load_existing_results()
    results_dict = refresh_saved_simulation_status(results_dict)

    used_fingerprints = {r.get("fingerprint") for r in results_dict.values() if r.get("fingerprint")}
    seen_alpha_ids = {r.get("alpha_id") for r in results_dict.values() if r.get("alpha_id")}
    next_index = max(results_dict.keys(), default=0) + 1

    summary = summarize(results_dict)
    print(
        f"Loaded {len(results_dict)} records | "
        f"UNIQUE_LOCAL_EXPRESSIONS={summary['UNIQUE_LOCAL_EXPRESSIONS']} | "
        f"UNIQUE_ALPHA_IDS={summary['UNIQUE_ALPHA_IDS']}"
    )

    if len(seen_alpha_ids) >= TARGET_UNIQUE_ALPHA_IDS:
        print("Already reached target unique alpha ID count.")
        return

    candidates = candidate_stream()
    submitted = 0

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SIMULATIONS) as executor:
        in_flight = {}

        while len(seen_alpha_ids) < TARGET_UNIQUE_ALPHA_IDS:
            while len(in_flight) < MAX_CONCURRENT_SIMULATIONS and submitted < MAX_TOTAL_SUBMISSIONS:
                try:
                    cand = next(candidates)
                except StopIteration:
                    break

                if cand["fingerprint"] in used_fingerprints:
                    continue

                task = {
                    "index": next_index,
                    "expression": cand["expression"],
                    "label": cand["label"],
                    "fingerprint": cand["fingerprint"],
                }
                used_fingerprints.add(cand["fingerprint"])
                future = executor.submit(run_simulation, task)
                in_flight[future] = task
                next_index += 1
                submitted += 1

            if not in_flight:
                print("No more tasks available or submission limit reached.")
                break

            done_future = next(as_completed(in_flight))
            in_flight.pop(done_future)
            sim_record = done_future.result()

            if sim_record.get("status") == "COMPLETED" and sim_record.get("alpha_id"):
                if sim_record["alpha_id"] in seen_alpha_ids:
                    sim_record["status"] = "DUPLICATE_ALPHA_ID"
                    print(
                        f"[{sim_record['index']}] DUPLICATE_ALPHA_ID :: {sim_record['label']} :: alpha_id={sim_record['alpha_id']}"
                    )
                else:
                    seen_alpha_ids.add(sim_record["alpha_id"])
                    print(
                        f"[{sim_record['index']}] NEW_ALPHA_ID :: {sim_record['label']} :: alpha_id={sim_record['alpha_id']} | TOTAL_UNIQUE_ALPHA_IDS={len(seen_alpha_ids)}/{TARGET_UNIQUE_ALPHA_IDS}"
                    )
            else:
                print(f"[{sim_record['index']}] {sim_record['status']} :: {sim_record['label']}")

            results_dict[sim_record["index"]] = sim_record
            save_results(results_dict)

            if len(results_dict) % 25 == 0:
                summary = summarize(results_dict)
                print(
                    f"Progress | SUBMITTED={submitted} | "
                    f"UNIQUE_ALPHA_IDS={summary['UNIQUE_ALPHA_IDS']}/{TARGET_UNIQUE_ALPHA_IDS} | "
                    f"DUPLICATE_ALPHA_ID={summary['DUPLICATE_ALPHA_ID']} | "
                    f"TIMEOUT={summary['TIMEOUT']} | FAILED={summary['FAILED']} | ERROR={summary['ERROR']}"
                )

            if submitted >= MAX_TOTAL_SUBMISSIONS and not in_flight:
                break

    summary = summarize(results_dict)
    print("\nFinal Summary:")
    print(f"  COMPLETED: {summary['COMPLETED']}")
    print(f"  DUPLICATE_ALPHA_ID: {summary['DUPLICATE_ALPHA_ID']}")
    print(f"  TIMEOUT: {summary['TIMEOUT']}")
    print(f"  FAILED: {summary['FAILED']}")
    print(f"  ERROR: {summary['ERROR']}")
    print(f"  UNIQUE_LOCAL_EXPRESSIONS: {summary['UNIQUE_LOCAL_EXPRESSIONS']}")
    print(f"  UNIQUE_ALPHA_IDS: {summary['UNIQUE_ALPHA_IDS']}")
    print(f"Results written to: {RESULTS_FILE}")

    if summary["UNIQUE_ALPHA_IDS"] < TARGET_UNIQUE_ALPHA_IDS:
        print("WARNING: target not reached. Increase MAX_TOTAL_SUBMISSIONS or expand templates.")


if __name__ == "__main__":
    main()
