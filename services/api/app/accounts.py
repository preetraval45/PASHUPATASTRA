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
from functools import lru_cache
from pathlib import Path
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


def _version(user_id: str) -> int:
    """The account's session version: raised by a password change or "sign out everywhere", which
    ends every token issued before it."""
    return int((store().get_doc("USER", user_id) or {}).get("v", 0))


def issue(user_id: str, now: float | None = None) -> str:
    claims = {"u": user_id, "exp": int((now or time.time()) + SESSION_DAYS * 86400), "v": _version(user_id)}
    payload = _b64(json.dumps(claims).encode())
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
    user_id = str(claims.get("u") or "")
    if not user_id or int(claims.get("v", 0)) != _version(user_id):
        return None
    return user_id


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
    #: The address is proven to be this person's: a link sent to it was opened (or Google vouched for it).
    verified: bool = False

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "provider": self.provider, "email": self.email,
                "verified": self.verified}


def _user(doc: dict | None) -> User | None:
    if not doc:
        return None
    # Google only signs in an address it has verified (google() refuses otherwise), so it counts as verified.
    verified = bool(doc.get("verified")) or doc["provider"] == "google"
    return User(id=doc["id"], name=doc["name"], provider=doc["provider"], email=doc.get("email"), verified=verified)


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
        with urllib.request.urlopen(url, timeout=8) as response:  # a fixed https URL
            return json.loads(response.read())
    except Exception as exc:  # any failure is a refused sign-in
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


def record_training(user_id: str, slug: str, score: float, passed: bool, verified: bool = False) -> dict[str, dict]:
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
        # Marked by the server from the answers given (mark_attempt), not reported by the browser.
        "verified_passed": bool(before.get("verified_passed")) or (verified and bool(passed)),
        "verified_best": max(float(before.get("verified_best", 0)), score if verified else 0.0),
        "at": int(time.time()),
    }
    store().put_doc("TRAINING", user_id, {"modules": modules})
    return modules


def members(org_id: str, actor: User) -> list[dict]:
    """Everyone in the company with their training, for its admins."""
    org = require(org_id, actor, "owner", "admin")
    required = settings(org)["required"]
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
            "verified": sorted(slug for slug, m in modules.items() if m.get("verified_passed")),
            "attempts": sum(int(m.get("attempts", 0)) for m in modules.values()),
            "last_active": max((int(m.get("at", 0)) for m in modules.values()), default=None),
            "average": round(sum(float(m.get("best", 0)) for m in modules.values()) / len(modules), 3) if modules else None,
            "policies_acknowledged": acknowledged(org_id, user.id),
            "required_passed": sum(1 for slug in required if modules.get(slug, {}).get("passed")),
        })
    return sorted(out, key=lambda m: (ROLES.index(m["role"]), m["name"].lower()))


# --- passwords and sessions, managed ----------------------------------------------------------

RESET_SECONDS = 60 * 60
VERIFY_SECONDS = 24 * 60 * 60
RESEND_SECONDS = 60


def _bump(user_id: str) -> None:
    doc = store().get_doc("USER", user_id) or {}
    doc["v"] = int(doc.get("v", 0)) + 1
    store().put_doc("USER", user_id, doc)


def sign_out_everywhere(user: User) -> None:
    """Ends every session this account has, on every device, this one included."""
    _bump(user.id)


def _set_password(user_id: str, password: str) -> None:
    _check_password(password)
    doc = store().get_doc("USER", user_id) or {}
    salt = secrets.token_bytes(16)
    doc.update({"salt": salt.hex(), "hash": _hash(password, salt), "v": int(doc.get("v", 0)) + 1})
    store().put_doc("USER", user_id, doc)
    if doc.get("email"):
        store().delete_doc("LOCK", doc["email"])


def change_password(user: User, current: str, new: str) -> None:
    """A new password, given the current one. Every other session ends."""
    doc = store().get_doc("USER", user.id) or {}
    if "salt" not in doc:
        raise AccountError("This account has no password to change.")
    if not hmac.compare_digest(_hash(current, bytes.fromhex(doc["salt"])), doc["hash"]):
        raise AccountError("Your current password isn't right.", 401)
    _set_password(user.id, new)


def _reset_token(user_id: str, now: float | None = None) -> str:
    """A one-time reset token. Only its SHA-256 is stored, so a copy of the table cannot reset anyone."""
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    store().put_doc("RESET", digest, {"user": user_id, "exp": int((now or time.time()) + RESET_SECONDS)})
    return token


def request_reset(email: str, now: float | None = None) -> str | None:
    """A reset token for an email account, or None when there is no such account. The route answers the
    same either way, so the form cannot be used to find out who has an account."""
    link = store().get_doc("LOGIN", f"email#{email.strip().lower()}")
    return _reset_token(link["user"], now) if link else None


def reset_password(token: str, password: str, now: float | None = None) -> User:
    digest = hashlib.sha256(token.encode()).hexdigest()
    found = store().get_doc("RESET", digest)
    if not found or int(found["exp"]) < (now or time.time()):
        raise AccountError("That reset link has expired or was already used. Ask for a new one.", 400)
    _set_password(found["user"], password)
    store().delete_doc("RESET", digest)
    user = get_user(found["user"])
    if user is None:
        raise AccountError("That account no longer exists.", 404)
    return user


def verification_token(user: User, now: float | None = None) -> str | None:
    """A one-time link token proving the account's address, for an email account not yet verified; None
    otherwise, or when one was issued less than a minute ago (resending is not a way to send mail at will).
    Like reset tokens, only its SHA-256 is stored, with the address it was sent to."""
    if user.provider != "email" or user.verified or not user.email:
        return None
    moment = now or time.time()
    doc = store().get_doc("USER", user.id) or {}
    if moment - float(doc.get("verify_sent", 0)) < RESEND_SECONDS:
        return None
    doc["verify_sent"] = int(moment)
    store().put_doc("USER", user.id, doc)
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    store().put_doc("VERIFY", digest, {"user": user.id, "email": user.email, "exp": int(moment + VERIFY_SECONDS)})
    return token


def confirm_email(token: str, now: float | None = None) -> User:
    """Marks the address verified from its link. Refused when the link is spent or expired, or when the
    account's address is no longer the one the link was sent to."""
    digest = hashlib.sha256(token.encode()).hexdigest()
    found = store().get_doc("VERIFY", digest)
    if not found or int(found["exp"]) < (now or time.time()):
        raise AccountError("That link has expired or was already used. Ask for a new one from your account.", 400)
    doc = store().get_doc("USER", found["user"])
    if not doc or doc.get("email") != found["email"]:
        store().delete_doc("VERIFY", digest)
        raise AccountError("That link was for a different address. Ask for a new one from your account.", 400)
    doc["verified"] = True
    store().put_doc("USER", found["user"], doc)
    store().delete_doc("VERIFY", digest)
    user = _user(doc)
    assert user is not None
    return user


def admin_reset(org_id: str, actor: User, member_id: str) -> str:
    """A one-time reset token an owner or admin hands to a member who cannot sign in. Works with no email
    service at all, which is the point: a company can manage its people before email is set up."""
    require(org_id, actor, "owner", "admin")
    if not role_in(org_id, member_id):
        raise AccountError("That person isn't in this company.", 404)
    member = get_user(member_id)
    if member is None or member.provider != "email":
        raise AccountError("Only email accounts have a password to reset.")
    return _reset_token(member_id)


# --- company policies ------------------------------------------------------------------------
#
# A company's own security policies (acceptable use, passwords, remote work …), published by its admins
# and acknowledged by each member. Text only, kept with the company and visible to its members only.

POLICY_TITLE, POLICY_BODY = 120, 20_000


def add_policy(org_id: str, actor: User, title: str, body: str) -> dict:
    require(org_id, actor, "owner", "admin")
    title, body = title.strip(), body.strip()
    if not title or not body:
        raise AccountError("A policy needs a title and its text.")
    if len(title) > POLICY_TITLE or len(body) > POLICY_BODY:
        raise AccountError(f"Keep the title under {POLICY_TITLE} characters and the text under {POLICY_BODY:,}.")
    policy = {"id": f"p_{secrets.token_hex(5)}", "title": title, "body": body, "created": int(time.time()), "by": actor.id}
    store().put_doc("POLICY", f"{org_id}#{policy['id']}", policy)
    return policy


def remove_policy(org_id: str, actor: User, policy_id: str) -> None:
    require(org_id, actor, "owner", "admin")
    s = store()
    s.delete_doc("POLICY", f"{org_id}#{policy_id}")
    for key, _ in s.docs("ACK", f"{org_id}#{policy_id}#"):
        s.delete_doc("ACK", key)


def policies(org_id: str, user: User) -> list[dict]:
    """The company's policies, newest first, each saying whether this member has acknowledged it and,
    for admins, how many members have."""
    require(org_id, user)
    admin = role_in(org_id, user.id) in ("owner", "admin")
    s = store()
    out = []
    for _, p in s.docs("POLICY", f"{org_id}#"):
        acks = s.docs("ACK", f"{org_id}#{p['id']}#")
        mine = next((a for k, a in acks if k.endswith(f"#{user.id}")), None)
        out.append({**p, "acknowledged": mine["at"] if mine else None, **({"acks": len(acks)} if admin else {})})
    return sorted(out, key=lambda p: -p["created"])


def acknowledge(org_id: str, user: User, policy_id: str) -> None:
    require(org_id, user)
    if not store().get_doc("POLICY", f"{org_id}#{policy_id}"):
        raise AccountError("That policy no longer exists.", 404)
    store().put_doc("ACK", f"{org_id}#{policy_id}#{user.id}", {"at": int(time.time())})


def acknowledged(org_id: str, user_id: str) -> int:
    """How many of the company's current policies this member has acknowledged."""
    s = store()
    current = {p["id"] for _, p in s.docs("POLICY", f"{org_id}#")}
    return sum(1 for key, _ in s.docs("ACK", f"{org_id}#") if key.endswith(f"#{user_id}") and key.split("#")[1] in current)


# --- company customization -------------------------------------------------------------------
#
# What a company sets for its own people: its accent colour across the app, its logo, a welcome message,
# and which training levels are required by when. Only owners and admins change them.

ACCENTS = ("default", "series-1", "series-2", "series-5", "series-6", "series-7")
"""Accents a company may choose: the site's teal or one of the validated chart hues whose steps keep
white button text readable in both themes (globals.css --series-*). Yellow, aqua and red are left out."""

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UNSAFE_URL = set(' "<>\'`')


def settings(org: dict) -> dict:
    return {"accent": "default", "logo": None, "welcome": "", "required": [], "due": None, **org.get("settings", {})}


def update_settings(org_id: str, actor: User, changes: dict) -> dict:
    org = require(org_id, actor, "owner", "admin")
    current = settings(org)
    if "name" in changes and changes["name"] is not None:
        name = str(changes["name"]).strip()[:80]
        if len(name) < 2:
            raise AccountError("Give the company a name.")
        org["name"] = name
    if "accent" in changes:
        if changes["accent"] not in ACCENTS:
            raise AccountError("Pick one of the offered colours.")
        current["accent"] = changes["accent"]
    if "logo" in changes:
        logo = (changes["logo"] or "").strip()
        if logo and (not logo.startswith("https://") or len(logo) > 400 or UNSAFE_URL & set(logo)):
            raise AccountError("The logo must be an https:// image address.")
        current["logo"] = logo or None
    if "welcome" in changes:
        current["welcome"] = str(changes["welcome"] or "").strip()[:600]
    if "required" in changes:
        required = [str(s) for s in (changes["required"] or [])]
        if any(not SLUG.match(s) for s in required) or len(required) > 20:
            raise AccountError("Unknown training level.")
        current["required"] = sorted(set(required))
    if "due" in changes:
        due = changes["due"] or None
        if due is not None and not DATE.match(str(due)):
            raise AccountError("Give the due date as a date.")
        current["due"] = due
    org["settings"] = current
    store().put_doc("ORG", org_id, org)
    return {**settings(org), "name": org["name"]}


# --- platform administration ---------------------------------------------------------------


def is_platform_admin(user: User | None) -> bool:
    return bool(user) and user.provider != "guest" and user.id in get_settings().platform_admins


def overview(actor: User) -> dict:
    """Every account and company, for the platform's administrators."""
    if not is_platform_admin(actor):
        raise AccountError("Only a platform administrator can see this.", 403)
    s = store()
    users = [doc for _, doc in s.docs("USER")]
    orgs = [doc for _, doc in s.docs("ORG")]
    counts: dict[str, int] = {}
    for _, member in s.docs("MEMBER"):
        counts[member["org"]] = counts.get(member["org"], 0) + 1
    return {
        "users": sorted(
            ({"id": u["id"], "name": u["name"], "email": u.get("email"), "provider": u["provider"],
              "created": u.get("created"), "admin": u["id"] in get_settings().platform_admins} for u in users),
            key=lambda u: -(u["created"] or 0),
        ),
        "companies": sorted(
            ({"id": o["id"], "name": o["name"], "members": counts.get(o["id"], 0), "created": o.get("created"),
              "accent": settings(o)["accent"]} for o in orgs),
            key=lambda o: -(o["created"] or 0),
        ),
    }


# --- server-marked tests ----------------------------------------------------------------------
#
# The answer keys are exported from the site's own questions (scripts/exportquiz.mjs → quizkeys.json, with
# a web test that fails if they drift). The browser sends the option it chose for each question; the score
# is worked out here, so a record marked this way cannot be a number someone typed. The questions are
# also in the page, so this is an open-book test, not a proctored exam: what it guarantees is that the
# score is the score of the answers given.

QUIZ_KEYS = Path(__file__).with_name("quizkeys.json")


@lru_cache
def _keys() -> dict:
    return json.loads(QUIZ_KEYS.read_text(encoding="utf-8"))


def mark_attempt(user: User, slug: str, answers: list[str]) -> dict:
    """Marks one test from the options chosen, records it as verified, and says which were right."""
    keys = _keys()
    questions = keys["modules"].get(slug)
    if questions is None:
        raise AccountError("Unknown module.", 404)
    if len(answers) != len(questions):
        raise AccountError(f"Answer all {len(questions)} questions.")
    correct = [given == q["answer"] for given, q in zip(answers, questions, strict=True)]
    score = sum(correct) / len(questions)
    passed = score >= float(keys["pass_mark"])
    training = record_training(user.id, slug, score, passed, verified=True)
    return {"score": score, "passed": passed, "correct": correct, "training": training}
