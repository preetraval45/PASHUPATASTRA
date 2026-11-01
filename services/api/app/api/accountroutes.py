"""Sign-in, companies and training records over HTTP (accounts.py, adr/Accounts).

Every route but the sign-ins and `/auth/config` needs `Authorization: Bearer
<token>`. Audit records say what kind of thing happened, never who: the audit
trail is public, and an account's name or email has no place in it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .. import accounts
from ..config import get_settings
from ..engines.audit import AUDIT, AuditKind, AuditRecord

router = APIRouter()


def _audit(summary: str, **detail: object) -> None:
    try:
        AUDIT.append(AuditRecord(
            at=datetime.now(UTC), kind=AuditKind.OBSERVATION, actor="accounts", incident_ref=None,
            summary=summary, detail=dict(detail),
        ))
    except Exception:  # noqa: BLE001 - an audit outage must not lock people out
        logging.getLogger(__name__).warning("audit unavailable for an account event")


def _fail(error: accounts.AccountError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=str(error))


def _user(authorization: str | None) -> accounts.User:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user_id = accounts.verify(token)
    user = accounts.get_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def _session(user: accounts.User) -> dict:
    return {"token": accounts.issue(user.id), "user": user.public()}


def _me(user: accounts.User) -> dict:
    orgs = []
    for org_id, role in accounts.memberships(user.id):
        org = accounts.get_org(org_id)
        if org:
            orgs.append({"id": org["id"], "name": org["name"], "role": role,
                         **({"invite": org["invite"]} if role in ("owner", "admin") else {})})
    return {"user": user.public(), "orgs": orgs, "training": accounts.training(user.id)}


class Register(BaseModel):
    email: str = Field(max_length=256)
    password: str = Field(max_length=256)
    name: str = Field(default="", max_length=80)


class Login(BaseModel):
    email: str = Field(max_length=256)
    password: str = Field(max_length=256)


class Google(BaseModel):
    credential: str = Field(max_length=4096)


class Named(BaseModel):
    name: str = Field(max_length=80)


class Code(BaseModel):
    code: str = Field(max_length=16)


class Role(BaseModel):
    role: str = Field(max_length=16)


class Result(BaseModel):
    score: float = Field(ge=0, le=1)
    passed: bool


@router.get("/auth/config")
def auth_config() -> dict:
    """Which sign-ins this deployment offers. The Google client id is public by design."""
    return {"google_client_id": get_settings().google_client_id, "guest": True, "email": True}


@router.post("/auth/guest")
def auth_guest() -> dict:
    user = accounts.create_guest()
    _audit("a guest session started", provider="guest")
    return _session(user)


@router.post("/auth/register")
def auth_register(body: Register) -> dict:
    try:
        user = accounts.register(body.email, body.password, body.name)
    except accounts.AccountError as error:
        raise _fail(error) from error
    _audit("an account was created", provider="email")
    return _session(user)


@router.post("/auth/login")
def auth_login(body: Login) -> dict:
    try:
        return _session(accounts.login(body.email, body.password))
    except accounts.AccountError as error:
        raise _fail(error) from error


@router.post("/auth/google")
def auth_google(body: Google) -> dict:
    try:
        user = accounts.google(body.credential)
    except accounts.AccountError as error:
        raise _fail(error) from error
    return _session(user)


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    return _me(_user(authorization))


@router.patch("/me")
def me_rename(body: Named, authorization: str | None = Header(default=None)) -> dict:
    return _me(accounts.rename(_user(authorization), body.name))


@router.delete("/me")
def me_delete(authorization: str | None = Header(default=None)) -> dict:
    accounts.delete_user(_user(authorization))
    _audit("an account was deleted at its owner's request")
    return {"deleted": True}


@router.put("/me/training/{slug}")
def me_training(slug: str, body: Result, authorization: str | None = Header(default=None)) -> dict:
    user = _user(authorization)
    try:
        return {"training": accounts.record_training(user.id, slug, body.score, body.passed)}
    except accounts.AccountError as error:
        raise _fail(error) from error


@router.post("/orgs")
def org_create(body: Named, authorization: str | None = Header(default=None)) -> dict:
    user = _user(authorization)
    try:
        org = accounts.create_org(user, body.name)
    except accounts.AccountError as error:
        raise _fail(error) from error
    _audit("a company workspace was created")
    return _me(user) | {"created": org["id"]}


@router.post("/orgs/join")
def org_join(body: Code, authorization: str | None = Header(default=None)) -> dict:
    user = _user(authorization)
    try:
        org = accounts.join(user, body.code)
    except accounts.AccountError as error:
        raise _fail(error) from error
    return _me(user) | {"joined": org["id"]}


@router.get("/orgs/{org_id}/members")
def org_members(org_id: str, authorization: str | None = Header(default=None)) -> dict:
    user = _user(authorization)
    try:
        org = accounts.require(org_id, user, "owner", "admin")
        return {"org": {"id": org["id"], "name": org["name"], "invite": org["invite"]},
                "members": accounts.members(org_id, user)}
    except accounts.AccountError as error:
        raise _fail(error) from error


@router.post("/orgs/{org_id}/invite")
def org_rotate(org_id: str, authorization: str | None = Header(default=None)) -> dict:
    try:
        return {"invite": accounts.rotate_invite(org_id, _user(authorization))}
    except accounts.AccountError as error:
        raise _fail(error) from error


@router.put("/orgs/{org_id}/members/{member_id}")
def org_role(org_id: str, member_id: str, body: Role, authorization: str | None = Header(default=None)) -> dict:
    try:
        accounts.set_role(org_id, _user(authorization), member_id, body.role)
    except accounts.AccountError as error:
        raise _fail(error) from error
    return {"ok": True}


@router.delete("/orgs/{org_id}/members/{member_id}")
def org_remove(org_id: str, member_id: str, authorization: str | None = Header(default=None)) -> dict:
    try:
        accounts.remove_member(org_id, _user(authorization), member_id)
    except accounts.AccountError as error:
        raise _fail(error) from error
    return {"ok": True}
