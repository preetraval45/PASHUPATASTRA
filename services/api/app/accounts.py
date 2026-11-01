"""Accounts, companies and training records (adr/Accounts).

Until 1 Nov 2026 the site held no personal data at all: training progress lived
in the browser and the Blue Team game used an anonymous token (progress.py).
Selling the product to companies needs the opposite for one feature, a company
admin seeing which employees finished their training, so this module adds
accounts with the least data that feature needs:

* **What is kept.** An account: an id, a display name, and for email accounts
  the address and a scrypt hash of the password (never the password). For
  Google accounts, Google's stable subject id and the verified address. Guest
  accounts keep nothing but the id.
* **What is not.** No IP addresses, no device data, no tracking. Nothing about
  an account reaches the public audit trail: audit records say *that* an
  account or a company was created, never who.
* **Deletion is real.** `delete_user` removes the account, its sign-in keys,
  its memberships and its training record.

Sessions are signed tokens (HMAC-SHA256) carrying the account id and an expiry.
The signing key comes from `PASHU_AUTH_SECRET` when set, otherwise it is made
once and kept in the store, so a fresh deployment needs no configuration.

Google sign-in uses Google Identity Services: the browser receives an ID token
from Google and this module asks Google's tokeninfo endpoint to check it, then
checks the audience is this site's client id. No Google secret is involved.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import get_settings

SESSION_DAYS = 30
ROLES = ("owner", "admin", "employee")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,24}$", re.IGNORECASE)
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AccountError(Exception):
    """A request the account rules refuse, with a message safe to show."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


# --- storage ---------------------------------------------------------------------------------


class _Memory:
    """Documents in memory, for local runs and tests. Same surface as the durable store's."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    def get_doc(self, partition: str, key: str) -> dict | None:
        row = self.rows.get((partition, key))
        return dict(row) if row else None

    def put_doc(self, partition: str, key: str, doc: dict, *, only_if_new: bool = False) -> bool:
        if only_if_new and (partition, key) in self.rows:
            return False
        self.rows[(partition, key)] = dict(doc)
        return True

    def delete_doc(self, partition: str, key: str) -> None:
        self.rows.pop((partition, key), None)

    def docs(self, partition: str, prefix: str = "") -> list[tuple[str, dict]]:
        return sorted((k, dict(v)) for (p, k), v in self.rows.items() if p == partition and k.startswith(prefix))


_memory = _Memory()


def store():
    """The durable store when it holds documents, else memory."""
    from .backend import durable

    found = durable()
    return found if found is not None and hasattr(found, "put_doc") else _memory


def reset_memory() -> None:
    """For tests: forget every in-memory account."""
    global _memory, _key
    _memory = _Memory()
    _key = None


# --- sessions --------------------------------------------------------------------------------

_key: bytes | None = None


def _signing_key() -> bytes:
    global _key
    if _key is not None:
        return _key
    configured = get_settings().auth_secret
    if configured:
        _key = configured.encode()
        return _key
    s = store()
    made = secrets.token_hex(32)
    s.put_doc("META", "AUTHKEY", {"key": made}, only_if_new=True)
    _key = (s.get_doc("META", "AUTHKEY") or {"key": made})["key"].encode()
    return _key


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(user_id: str, now: float | None = None) -> str:
    payload = _b64(json.dumps({"u": user_id, "exp": int((now or time.time()) + SESSION_DAYS * 86400)}).encode())
    signature = _b64(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify(token: str | None, now: float | None = None) -> str | None:
    """The account id a token was issued to, or None if it is forged, malformed or expired."""
    if not token or token.count(".") != 1:
        return None
    payload, signature = token.split(".")
    expected = _b64(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        claims = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(claims.get("exp", 0)) < (now or time.time()):
        return None
    return str(claims.get("u")) or None


# --- passwords -------------------------------------------------------------------------------


def _hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


def _check_password(password: str) -> None:
    if len(password) < 10:
        raise AccountError("Use at least 10 characters. A few random words make a strong password.")
    if len(password) > 200:
        raise AccountError("That password is too long.")


# --- accounts --------------------------------------------------------------------------------


@dataclass
class User:
    id: str
    name: str
    provider: str
    email: str | None = None

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "provider": self.provider, "email": self.email}


def _user(doc: dict | None) -> User | None:
    if not doc:
        return None
    return User(id=doc["id"], name=doc["name"], provider=doc["provider"], email=doc.get("email"))


def get_user(user_id: str) -> User | None:
    return _user(store().get_doc("USER", user_id))


def _new_user(name: str, provider: str, email: str | None = None, extra: dict | None = None) -> User:
    user = User(id=f"u_{secrets.token_hex(8)}", name=name.strip()[:60] or "Member", provider=provider, email=email)
    store().put_doc("USER", user.id, {**user.public(), "created": int(time.time()), **(extra or {})})
    return user


def create_guest() -> User:
    return _new_user("Guest", "guest")


def register(email: str, password: str, name: str) -> User:
    email = email.strip().lower()
    if not EMAIL.match(email):
        raise AccountError("That doesn't look like an email address.")
    _check_password(password)
    s = store()
    if s.get_doc("LOGIN", f"email#{email}"):
        raise AccountError("An account with that email already exists. Sign in instead.", 409)
    salt = secrets.token_bytes(16)
    user = _new_user(name or email.split("@")[0], "email", email, {"salt": salt.hex(), "hash": _hash(password, salt)})
    if not s.put_doc("LOGIN", f"email#{email}", {"user": user.id}, only_if_new=True):
        s.delete_doc("USER", user.id)
        raise AccountError("An account with that email already exists. Sign in instead.", 409)
    return user


LOCK_AFTER = 10
LOCK_SECONDS = 15 * 60


def login(email: str, password: str, now: float | None = None) -> User:
    """Ten wrong passwords for one email within 15 minutes lock it until the window passes, which turns
    guessing a password online from a matter of hours into one of centuries."""
    email = email.strip().lower()
    now = now or time.time()
    s = store()
    tries = s.get_doc("LOCK", email) or {"count": 0, "since": now}
    if now - tries["since"] > LOCK_SECONDS:
        tries = {"count": 0, "since": now}
    if tries["count"] >= LOCK_AFTER:
        raise AccountError("Too many attempts. Wait 15 minutes and try again.", 429)
    link = s.get_doc("LOGIN", f"email#{email}")
    doc = s.get_doc("USER", link["user"]) if link else None
    # The same message whether the email or the password was wrong: no telling which accounts exist.
    if not doc or "salt" not in doc or not hmac.compare_digest(_hash(password, bytes.fromhex(doc["salt"])), doc["hash"]):
        s.put_doc("LOCK", email, {"count": tries["count"] + 1, "since": tries["since"]})
        raise AccountError("That email and password don't match an account.", 401)
    s.delete_doc("LOCK", email)
    return _user(doc)  # type: ignore[return-value]


def _google_claims(credential: str) -> dict:
    """Google's own check of an ID token (signature, expiry), via its tokeninfo endpoint."""
    url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": credential})
    try:
        with urllib.request.urlopen(url, timeout=8) as response:  # noqa: S310 - fixed https URL
            return json.loads(response.read())
    except Exception as exc:  # noqa: BLE001 - any failure is a refused sign-in
        raise AccountError("Google could not confirm that sign-in. Try again.", 401) from exc


def google(credential: str, claims_for=_google_claims) -> User:
    client = get_settings().google_client_id
    if not client:
        raise AccountError("Google sign-in is not set up on this deployment yet.", 503)
    claims = claims_for(credential)
    if claims.get("aud") != client or claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise AccountError("That Google sign-in was not meant for this site.", 401)
    if str(claims.get("email_verified")).lower() != "true":
        raise AccountError("Your Google email address is not verified.", 401)
    s = store()
    link = s.get_doc("LOGIN", f"google#{claims['sub']}")
    if link and (found := get_user(link["user"])):
        return found
    email = str(claims.get("email", "")).lower() or None
    user = _new_user(str(claims.get("name") or (email or "Member").split("@")[0]), "google", email)
    s.put_doc("LOGIN", f"google#{claims['sub']}", {"user": user.id})
    return user


def rename(user: User, name: str) -> User:
    doc = store().get_doc("USER", user.id) or {}
    doc["name"] = name.strip()[:60] or user.name
    store().put_doc("USER", user.id, doc)
    return _user(doc)  # type: ignore[return-value]


def delete_user(user: User) -> None:
    """Everything this account is: its sign-in keys, memberships, training record and the account."""
    s = store()
    for key, doc in s.docs("LOGIN"):
        if doc.get("user") == user.id:
            s.delete_doc("LOGIN", key)
    for org_id, _ in memberships(user.id):
        s.delete_doc("MEMBER", f"{org_id}#{user.id}")
        s.delete_doc("MEMBEROF", f"{user.id}#{org_id}")
    s.delete_doc("TRAINING", user.id)
    s.delete_doc("USER", user.id)


# --- companies -------------------------------------------------------------------------------


def _code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))


def create_org(user: User, name: str) -> dict:
    name = name.strip()[:80]
    if len(name) < 2:
        raise AccountError("Give the company a name.")
    if user.provider == "guest":
        raise AccountError("Create an account first: a company needs an owner who can sign in again.", 403)
    org = {"id": f"o_{secrets.token_hex(6)}", "name": name, "owner": user.id, "invite": _code(), "created": int(time.time())}
    s = store()
    s.put_doc("ORG", org["id"], org)
    s.put_doc("INVITE", org["invite"], {"org": org["id"]})
    _join(org["id"], user.id, "owner")
    return org


def _join(org_id: str, user_id: str, role: str) -> None:
    s = store()
    s.put_doc("MEMBER", f"{org_id}#{user_id}", {"org": org_id, "user": user_id, "role": role, "joined": int(time.time())})
    s.put_doc("MEMBEROF", f"{user_id}#{org_id}", {"org": org_id, "role": role})


def get_org(org_id: str) -> dict | None:
    return store().get_doc("ORG", org_id)


def memberships(user_id: str) -> list[tuple[str, str]]:
    return [(doc["org"], doc["role"]) for _, doc in store().docs("MEMBEROF", f"{user_id}#")]


def role_in(org_id: str, user_id: str) -> str | None:
    doc = store().get_doc("MEMBER", f"{org_id}#{user_id}")
    return doc["role"] if doc else None


def join(user: User, code: str) -> dict:
    invite = store().get_doc("INVITE", code.strip().upper())
    org = get_org(invite["org"]) if invite else None
    if not org or org.get("invite") != code.strip().upper():
        raise AccountError("That invite code isn't valid. Ask your admin for the current one.", 404)
    if not role_in(org["id"], user.id):
        _join(org["id"], user.id, "employee")
    return org


def require(org_id: str, user: User, *roles: str) -> dict:
    org = get_org(org_id)
    role = role_in(org_id, user.id) if org else None
    if not org or role is None:
        raise AccountError("Company not found.", 404)
    if roles and role not in roles:
        raise AccountError("Only the company's admins can do that.", 403)
    return org


def rotate_invite(org_id: str, user: User) -> str:
    org = require(org_id, user, "owner", "admin")
    s = store()
    s.delete_doc("INVITE", org["invite"])
    org["invite"] = _code()
    s.put_doc("ORG", org_id, org)
    s.put_doc("INVITE", org["invite"], {"org": org_id})
    return org["invite"]


def set_role(org_id: str, actor: User, member_id: str, role: str) -> None:
    require(org_id, actor, "owner")
    if role not in ("admin", "employee"):
        raise AccountError("A member is an admin or an employee.")
    if member_id == actor.id:
        raise AccountError("The owner's role can't be changed.")
    if not role_in(org_id, member_id):
        raise AccountError("That person isn't in this company.", 404)
    _join(org_id, member_id, role)


def remove_member(org_id: str, actor: User, member_id: str) -> None:
    org = require(org_id, actor, "owner", "admin")
    if member_id == org["owner"]:
        raise AccountError("The owner can't be removed.")
    s = store()
    s.delete_doc("MEMBER", f"{org_id}#{member_id}")
    s.delete_doc("MEMBEROF", f"{member_id}#{org_id}")


# --- training --------------------------------------------------------------------------------

SLUG = re.compile(r"^[a-z0-9-]{2,60}$")


def training(user_id: str) -> dict[str, dict]:
    return (store().get_doc("TRAINING", user_id) or {}).get("modules", {})


def record_training(user_id: str, slug: str, score: float, passed: bool) -> dict[str, dict]:
    """Folds one test result into the account's record: best score kept, passing is never undone.

    The score is the browser's own marking of the module test, so it is self-reported; a company sees
    it as the employee's record, not as proctored certification (adr/Accounts)."""
    if not SLUG.match(slug):
        raise AccountError("Unknown module.")
    score = max(0.0, min(1.0, float(score)))
    modules = training(user_id)
    before = modules.get(slug, {})
    modules[slug] = {
        "best": max(score, float(before.get("best", 0))),
        "last": score,
        "attempts": int(before.get("attempts", 0)) + 1,
        "passed": bool(before.get("passed")) or bool(passed),
        "at": int(time.time()),
    }
    store().put_doc("TRAINING", user_id, {"modules": modules})
    return modules


def members(org_id: str, actor: User) -> list[dict]:
    """Everyone in the company with their training, for its admins."""
    require(org_id, actor, "owner", "admin")
    out = []
    for _, doc in store().docs("MEMBER", f"{org_id}#"):
        user = get_user(doc["user"])
        if not user:
            continue
        modules = training(user.id)
        out.append({
            **user.public(),
            "role": doc["role"],
            "joined": doc.get("joined"),
            "passed": sorted(slug for slug, m in modules.items() if m.get("passed")),
            "attempts": sum(int(m.get("attempts", 0)) for m in modules.values()),
            "last_active": max((int(m.get("at", 0)) for m in modules.values()), default=None),
            "average": round(sum(float(m.get("best", 0)) for m in modules.values()) / len(modules), 3) if modules else None,
        })
    return sorted(out, key=lambda m: (ROLES.index(m["role"]), m["name"].lower()))
