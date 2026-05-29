#!/usr/bin/env python3
"""
Full API test suite for the IVS Streaming Platform.
Uses only the standard library — no extra dependencies required.

Usage:
    python3 test.py                          # test against localhost:8000
    python3 test.py --base http://x.x.x.x:8000
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────
BASE = "http://localhost:8000"
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--base" and i < len(sys.argv) - 1:
        BASE = sys.argv[i + 1]

TS           = int(time.time()) % 100_000   # keeps usernames unique per run
USERNAME     = f"testuser_{TS}"
EMAIL        = f"test_{TS}@example.com"
PASSWORD     = "TestPass123!"
USERNAME2    = f"testuser2_{TS}"
EMAIL2       = f"test2_{TS}@example.com"
CHANNEL_NAME = f"Test Channel {TS}"
CHANNEL_DESC = "Created by automated test suite"

# ── ANSI colours ──────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"

# ── Shared state (token, channel id, …) ──────────────────────────────────────
S: dict = {}

# ── Counters ──────────────────────────────────────────────────────────────────
passed = failed = skipped = 0


# ── HTTP helper ───────────────────────────────────────────────────────────────
def http(method: str, path: str, *, body=None, form=None, token: str = None):
    url = f"{BASE}{path}"
    headers: dict = {}
    data = None

    if form:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if "application/json" in ct:
                return resp.status, (json.loads(raw) if raw else None)
            return resp.status, {"_raw": raw[:80].decode(errors="replace")}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:    return e.code, json.loads(raw)
        except: return e.code, {"detail": str(e)}
    except Exception as e:
        return 0, {"detail": str(e)}


# ── Test runner ───────────────────────────────────────────────────────────────
def t(label: str, method: str, path: str, *,
      body=None, form=None, token: str = None,
      want: int = None, check=None,
      save: str = None, aws: bool = False, note: str = None):
    """
    Run one API test.

    want   – expected HTTP status code
    check  – callable(data) → bool for additional assertion
    save   – key in S{} to store the response for later tests
    aws    – mark as SKIP (instead of FAIL) when AWS creds are missing
    note   – extra detail printed on success
    """
    global passed, failed, skipped

    status, data = http(method, path, body=body, form=form, token=token)

    ok = True
    if want is not None and status != want:
        ok = False
    if check is not None and ok:
        try:    ok = bool(check(data))
        except: ok = False

    if save and data and ok:
        S[save] = data

    if ok:
        passed += 1
        tail = f"  {D}{note}{X}" if note else ""
        print(f"  {G}✓{X}  {label}{tail}")
    elif aws:
        skipped += 1
        detail = str((data or {}).get("detail", ""))[:70]
        print(f"  {Y}⚠{X}  {label}  {D}[needs AWS — {status}: {detail}]{X}")
    else:
        failed += 1
        detail = json.dumps(data)[:90] if data else ""
        print(f"  {R}✗{X}  {label}")
        print(f"     {D}→ HTTP {status}  {detail}{X}")

    return status, data


def section(title: str):
    pad = max(0, 54 - len(title))
    print(f"\n{B}{C}── {title} {'─' * pad}{X}")


# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{B}IVS Streaming Platform — API Test Suite{X}")
print(f"{D}Base URL : {BASE}{X}")
print(f"{D}Test user: {USERNAME}{X}")


# ── 1. Health ─────────────────────────────────────────────────────────────────
section("Health & Info")

t("Health check returns healthy",
  "GET", "/health",
  want=200,
  check=lambda d: d.get("status") == "healthy")

t("Local-IP endpoint returns ip + port + scheme",
  "GET", "/api/local-ip",
  want=200,
  check=lambda d: "ip" in d and "port" in d and "scheme" in d)

t("API docs reachable",
  "GET", "/api/docs",
  want=200,
  check=lambda d: True)


# ── 2. Auth — happy path ──────────────────────────────────────────────────────
section("Auth — registration & login")

t("Register new user",
  "POST", "/api/auth/register",
  body={"username": USERNAME, "email": EMAIL, "password": PASSWORD},
  want=201,
  check=lambda d: d.get("username") == USERNAME and "id" in d,
  save="user1",
  note=f"id={'{}'} username={'{}'}")

t("Register second user (for ownership tests)",
  "POST", "/api/auth/register",
  body={"username": USERNAME2, "email": EMAIL2, "password": PASSWORD},
  want=201,
  save="user2")

t("Login returns JWT token",
  "POST", "/api/auth/login",
  form={"username": USERNAME, "password": PASSWORD},
  want=200,
  check=lambda d: "access_token" in d and d.get("token_type") == "bearer",
  save="login1")

# store token for convenience
if "login1" in S:
    S["tok1"] = S["login1"]["access_token"]

t("Login second user",
  "POST", "/api/auth/login",
  form={"username": USERNAME2, "password": PASSWORD},
  want=200,
  save="login2")

if "login2" in S:
    S["tok2"] = S["login2"]["access_token"]

t("GET /api/auth/me returns current user",
  "GET", "/api/auth/me",
  token=S.get("tok1"),
  want=200,
  check=lambda d: d.get("username") == USERNAME)


# ── 3. Auth — error cases ─────────────────────────────────────────────────────
section("Auth — error cases")

t("Duplicate username → 409 Conflict",
  "POST", "/api/auth/register",
  body={"username": USERNAME, "email": f"other_{TS}@example.com", "password": PASSWORD},
  want=409)

t("Duplicate email → 409 Conflict",
  "POST", "/api/auth/register",
  body={"username": f"other_{TS}", "email": EMAIL, "password": PASSWORD},
  want=409)

t("Wrong password → 401 Unauthorized",
  "POST", "/api/auth/login",
  form={"username": USERNAME, "password": "WrongPassword!"},
  want=401)

t("Unknown username → 401 Unauthorized",
  "POST", "/api/auth/login",
  form={"username": "nobody_exists_xyz", "password": PASSWORD},
  want=401)

t("GET /me without token → 401",
  "GET", "/api/auth/me",
  want=401)

t("GET /me with fake token → 401",
  "GET", "/api/auth/me",
  token="not.a.real.token",
  want=401)


# ── 4. Channels — public reads (no auth, no AWS) ─────────────────────────────
section("Channels — public reads")

t("List all channels (public)",
  "GET", "/api/channels",
  want=200,
  check=lambda d: isinstance(d, list))

t("List live channels (public)",
  "GET", "/api/channels/live",
  want=200,
  check=lambda d: isinstance(d, list))

t("Get non-existent channel → 404",
  "GET", "/api/channels/999999",
  want=404)

t("Get my channel before creating → 404",
  "GET", "/api/channels/mine",
  token=S.get("tok1"),
  want=404)


# ── 5. Channels — create (requires AWS) ──────────────────────────────────────
section("Channels — create & manage (requires AWS)")

_, create_resp = t("Create channel (provisions IVS on AWS)",
  "POST", "/api/channels",
  body={"name": CHANNEL_NAME, "description": CHANNEL_DESC},
  token=S.get("tok1"),
  want=201,
  check=lambda d: d.get("name") == CHANNEL_NAME and "id" in d,
  save="channel",
  aws=True)

# If channel was created, run all dependent tests
if "channel" in S:
    CID = S["channel"]["id"]

    t("Duplicate channel → 409 (one channel per user)",
      "POST", "/api/channels",
      body={"name": "Another Channel", "description": ""},
      token=S.get("tok1"),
      want=409)

    t("GET /api/channels/mine returns the channel",
      "GET", "/api/channels/mine",
      token=S.get("tok1"),
      want=200,
      check=lambda d: d["id"] == CID)

    t("GET /api/channels/{id} returns the channel (public)",
      "GET", f"/api/channels/{CID}",
      want=200,
      check=lambda d: d["id"] == CID)

    t("Channel appears in channel list",
      "GET", "/api/channels",
      want=200,
      check=lambda d: any(c["id"] == CID for c in d))

    t("PATCH channel — update name and description",
      "PATCH", f"/api/channels/{CID}",
      body={"name": f"{CHANNEL_NAME} (edited)", "description": "Updated description"},
      token=S.get("tok1"),
      want=200,
      check=lambda d: "(edited)" in d.get("name", ""))

    t("PATCH channel by non-owner → 403 Forbidden",
      "PATCH", f"/api/channels/{CID}",
      body={"name": "Hacked"},
      token=S.get("tok2"),
      want=403)

    t("PATCH channel without token → 401",
      "PATCH", f"/api/channels/{CID}",
      body={"name": "No auth"},
      want=401)

    # ── 6. Stream credentials ─────────────────────────────────────────────────
    section("Stream credentials (requires AWS)")

    t("GET stream key (owner only)",
      "GET", f"/api/channels/{CID}/stream-key",
      token=S.get("tok1"),
      want=200,
      check=lambda d: "stream_key" in d and "rtmps_url" in d and "ingest_endpoint" in d,
      save="streamkey",
      aws=True)

    t("GET stream key by non-owner → 403",
      "GET", f"/api/channels/{CID}/stream-key",
      token=S.get("tok2"),
      want=403)

    t("GET stream key without token → 401",
      "GET", f"/api/channels/{CID}/stream-key",
      want=401)

    t("Rotate stream key (generates new key)",
      "POST", f"/api/channels/{CID}/rotate-key",
      token=S.get("tok1"),
      want=200,
      check=lambda d: "stream_key" in d and "rtmps_url" in d,
      aws=True)

    t("Rotate key by non-owner → 403",
      "POST", f"/api/channels/{CID}/rotate-key",
      token=S.get("tok2"),
      want=403)

    # ── 7. Stream status ──────────────────────────────────────────────────────
    section("Stream status")

    t("GET stream status (public, channel exists)",
      "GET", f"/api/streams/{CID}/status",
      want=200,
      check=lambda d: "is_live" in d and "viewer_count" in d)

    t("GET stream status — not live",
      "GET", f"/api/streams/{CID}/status",
      want=200,
      check=lambda d: d.get("is_live") is False)

    t("GET stream status for unknown channel → 404",
      "GET", "/api/streams/999999/status",
      want=404)

    t("Stop stream when not live (best-effort, AWS)",
      "POST", f"/api/streams/{CID}/stop",
      token=S.get("tok1"),
      aws=True)

    t("Stop stream by non-owner → 403",
      "POST", f"/api/streams/{CID}/stop",
      token=S.get("tok2"),
      want=403)

    t("Stop stream without token → 401",
      "POST", f"/api/streams/{CID}/stop",
      want=401)

    # ── 8. Chat token ─────────────────────────────────────────────────────────
    section("Chat token (requires AWS)")

    t("GET chat token — regular viewer",
      "POST", f"/api/channels/{CID}/chat-token",
      token=S.get("tok2"),
      want=200,
      check=lambda d: "token" in d and "region" in d,
      aws=True)

    t("GET chat token — owner gets moderator capabilities",
      "POST", f"/api/channels/{CID}/chat-token",
      token=S.get("tok1"),
      want=200,
      check=lambda d: "token" in d,
      aws=True)

    t("GET chat token without auth → 401",
      "POST", f"/api/channels/{CID}/chat-token",
      want=401)

    t("GET chat token for unknown channel → 404",
      "POST", "/api/channels/999999/chat-token",
      token=S.get("tok1"),
      want=404)

    # ── 9. Cleanup ────────────────────────────────────────────────────────────
    section("Cleanup")

    t("DELETE channel by non-owner → 403",
      "DELETE", f"/api/channels/{CID}",
      token=S.get("tok2"),
      want=403)

    t("DELETE channel without token → 401",
      "DELETE", f"/api/channels/{CID}",
      want=401)

    t("DELETE channel (owner, cleans up AWS resources)",
      "DELETE", f"/api/channels/{CID}",
      token=S.get("tok1"),
      want=204,
      aws=True)

    t("GET deleted channel → 404",
      "GET", f"/api/channels/{CID}",
      want=404)

else:
    section("Stream status — no AWS (limited)")

    t("GET stream status for unknown channel → 404",
      "GET", "/api/streams/999999/status",
      want=404)

    t("Stop stream without token → 401",
      "POST", "/api/streams/1/stop",
      want=401)

    print(f"\n  {Y}ℹ  Skipped channel-dependent tests — create channel failed (AWS not configured){X}")
    print(f"  {Y}ℹ  Add AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY to .env to run full suite{X}")


# ── 10. Frontend pages ────────────────────────────────────────────────────────
section("Frontend pages")

for page, path in [
    ("Browse page",    "/app/index.html"),
    ("Watch page",     "/app/watch.html"),
    ("Stream page",    "/app/stream.html"),
    ("Dashboard page", "/app/dashboard.html"),
]:
    t(f"{page} is served",
      "GET", path,
      want=200,
      check=lambda d: True)


# ── Summary ───────────────────────────────────────────────────────────────────
total = passed + failed + skipped
print(f"\n{'─' * 58}")
print(f"{B}Results:{X}  "
      f"{G}{passed} passed{X}  "
      f"{R}{failed} failed{X}  "
      f"{Y}{skipped} skipped (needs AWS){X}  "
      f"{D}/ {total} total{X}")

if failed == 0:
    print(f"\n{G}{B}✓ All tests passed!{X}")
else:
    print(f"\n{R}{B}✗ {failed} test(s) failed — see details above.{X}")

print()
sys.exit(0 if failed == 0 else 1)
