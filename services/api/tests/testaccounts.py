"""Accounts, companies and training records (app/accounts.py, adr/Accounts)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import accounts
from app.main import app


@pytest.fixture(autouse=True)
def fresh():
    accounts.reset_memory()
    yield
    accounts.reset_memory()


client = TestClient(app)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(email="ana@northwind.example", password="orbit pencil velvet", name="Ana") -> str:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password, "name": name})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_a_session_token_is_signed_and_expires():
    token = accounts.issue("u_1", now=1_000)
    assert accounts.verify(token, now=1_001) == "u_1"
    assert accounts.verify(token, now=1_000 + 31 * 86400) is None
    payload, signature = token.split(".")
    assert accounts.verify(f"{payload}.{signature[:-2]}xx", now=1_001) is None
    assert accounts.verify("not-a-token") is None


def test_register_login_and_the_same_refusal_for_a_wrong_email_or_password():
    register()
    ok = client.post("/api/v1/auth/login", json={"email": "ANA@northwind.example", "password": "orbit pencil velvet"})
    assert ok.status_code == 200 and ok.json()["user"]["name"] == "Ana"
    wrong_password = client.post("/api/v1/auth/login", json={"email": "ana@northwind.example", "password": "nope nope nope"})
    no_account = client.post("/api/v1/auth/login", json={"email": "bo@northwind.example", "password": "nope nope nope"})
    assert wrong_password.status_code == no_account.status_code == 401
    assert wrong_password.json() == no_account.json()


def test_weak_passwords_and_duplicate_emails_are_refused():
    assert client.post("/api/v1/auth/register", json={"email": "a@b.example", "password": "short"}).status_code == 400
    register()
    again = client.post("/api/v1/auth/register", json={"email": "ana@northwind.example", "password": "another long one"})
    assert again.status_code == 409


def test_the_password_is_never_stored_or_returned():
    token = register()
    me = client.get("/api/v1/me", headers=auth(token)).json()
    assert "hash" not in str(me) and "orbit pencil velvet" not in str(me)
    stored = accounts.store().get_doc("USER", me["user"]["id"])
    assert "orbit pencil velvet" not in str(stored)


def test_a_guest_can_train_but_cannot_own_a_company():
    token = client.post("/api/v1/auth/guest").json()["token"]
    put = client.put("/api/v1/me/training/phishing", json={"score": 0.8, "passed": True}, headers=auth(token))
    assert put.json()["training"]["phishing"]["passed"] is True
    assert client.post("/api/v1/orgs", json={"name": "Northwind"}, headers=auth(token)).status_code == 403


def test_a_company_admin_sees_employees_training_and_an_employee_does_not():
    owner = register()
    created = client.post("/api/v1/orgs", json={"name": "Northwind"}, headers=auth(owner)).json()
    org = created["orgs"][0]
    assert org["role"] == "owner" and len(org["invite"]) == 8

    employee = register("bo@northwind.example", name="Bo")
    joined = client.post("/api/v1/orgs/join", json={"code": org["invite"].lower()}, headers=auth(employee)).json()
    assert joined["orgs"][0]["role"] == "employee" and "invite" not in joined["orgs"][0]
    client.put("/api/v1/me/training/phishing", json={"score": 0.9, "passed": True}, headers=auth(employee))
    client.put("/api/v1/me/training/phishing", json={"score": 0.4, "passed": False}, headers=auth(employee))

    team = client.get(f"/api/v1/orgs/{org['id']}/members", headers=auth(owner)).json()
    bo = next(m for m in team["members"] if m["name"] == "Bo")
    # Best score kept, and a later failed attempt does not undo a pass.
    assert bo["passed"] == ["phishing"] and bo["attempts"] == 2 and bo["average"] == 0.9
    assert client.get(f"/api/v1/orgs/{org['id']}/members", headers=auth(employee)).status_code == 403


def test_rotating_the_invite_retires_the_old_code():
    owner = register()
    org = client.post("/api/v1/orgs", json={"name": "Northwind"}, headers=auth(owner)).json()["orgs"][0]
    new = client.post(f"/api/v1/orgs/{org['id']}/invite", headers=auth(owner)).json()["invite"]
    late = register("cy@northwind.example")
    assert client.post("/api/v1/orgs/join", json={"code": org["invite"]}, headers=auth(late)).status_code == 404
    assert client.post("/api/v1/orgs/join", json={"code": new}, headers=auth(late)).status_code == 200


def test_only_the_owner_changes_roles_and_the_owner_cannot_be_removed():
    owner = register()
    org = client.post("/api/v1/orgs", json={"name": "Northwind"}, headers=auth(owner)).json()["orgs"][0]
    bo = register("bo@northwind.example", name="Bo")
    bo_id = client.post("/api/v1/orgs/join", json={"code": org["invite"]}, headers=auth(bo)).json()["user"]["id"]
    owner_id = client.get("/api/v1/me", headers=auth(owner)).json()["user"]["id"]
    assert client.put(f"/api/v1/orgs/{org['id']}/members/{bo_id}", json={"role": "admin"}, headers=auth(owner)).status_code == 200
    assert client.delete(f"/api/v1/orgs/{org['id']}/members/{owner_id}", headers=auth(bo)).status_code == 400


def test_deleting_an_account_removes_everything_it_was():
    token = register()
    client.put("/api/v1/me/training/phishing", json={"score": 1, "passed": True}, headers=auth(token))
    user_id = client.get("/api/v1/me", headers=auth(token)).json()["user"]["id"]
    assert client.delete("/api/v1/me", headers=auth(token)).json() == {"deleted": True}
    assert client.get("/api/v1/me", headers=auth(token)).status_code == 401
    assert accounts.store().get_doc("TRAINING", user_id) is None
    # The email is free again.
    register()


def test_google_sign_in_checks_the_audience_and_the_verified_email(monkeypatch):
    monkeypatch.setattr(accounts.get_settings(), "google_client_id", "site.apps.googleusercontent.com")
    good = {"aud": "site.apps.googleusercontent.com", "iss": "accounts.google.com", "sub": "123",
            "email": "dee@northwind.example", "email_verified": "true", "name": "Dee"}
    first = accounts.google("t", claims_for=lambda _: good)
    assert first.provider == "google" and first.name == "Dee"
    assert accounts.google("t", claims_for=lambda _: good).id == first.id  # the same person, the same account
    with pytest.raises(accounts.AccountError):
        accounts.google("t", claims_for=lambda _: {**good, "aud": "someone-else"})
    with pytest.raises(accounts.AccountError):
        accounts.google("t", claims_for=lambda _: {**good, "sub": "9", "email_verified": "false"})


def test_audit_records_never_name_the_account():
    register(email="secret.person@northwind.example", name="Secret Person")
    audit = client.get("/api/v1/audit").text
    assert "secret.person" not in audit and "Secret Person" not in audit


def test_ten_wrong_passwords_lock_the_email_for_fifteen_minutes():
    register()
    for _ in range(accounts.LOCK_AFTER):
        with pytest.raises(accounts.AccountError):
            accounts.login("ana@northwind.example", "wrong wrong wrong", now=1_000)
    with pytest.raises(accounts.AccountError) as locked:
        accounts.login("ana@northwind.example", "orbit pencil velvet", now=1_001)
    assert locked.value.status == 429
    assert accounts.login("ana@northwind.example", "orbit pencil velvet", now=1_000 + accounts.LOCK_SECONDS + 1).name == "Ana"
