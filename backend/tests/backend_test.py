"""Acorde backend regression tests — covers auth, CRUD, reports, PDF, scopes."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://autor-editora-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


# ------- fixtures -------
@pytest.fixture(scope="session")
def admin_client():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    token = r.json()["token"]
    s.headers["Authorization"] = f"Bearer {token}"
    return s


# ------- health & auth -------
class TestAuth:
    def test_health(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_login_bad(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_login_ok_and_me(self, admin_client):
        r = admin_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == ADMIN_EMAIL
        assert d["role"] == "admin"

    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401


# ------- editoras CRUD -------
class TestEditoras:
    created_id = None

    def test_list_editoras_has_adriel(self, admin_client):
        r = admin_client.get(f"{API}/editoras")
        assert r.status_code == 200
        names = [e["name"] for e in r.json()]
        assert any("ADRIEL" in n.upper() for n in names), f"editoras: {names}"

    def test_create_edit_delete(self, admin_client):
        payload = {"name": "TEST_EDITORA_X", "cnpj": "00.000.000/0001-00", "admin_fee_percent": 12.5}
        r = admin_client.post(f"{API}/editoras", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == payload["name"]
        assert d["admin_fee_percent"] == 12.5
        eid = d["id"]
        # patch
        r = admin_client.patch(f"{API}/editoras/{eid}", json={"admin_fee_percent": 20.0})
        assert r.status_code == 200
        assert r.json()["admin_fee_percent"] == 20.0
        # verify via GET list
        r = admin_client.get(f"{API}/editoras")
        found = next((e for e in r.json() if e["id"] == eid), None)
        assert found and found["admin_fee_percent"] == 20.0
        # delete
        r = admin_client.delete(f"{API}/editoras/{eid}")
        assert r.status_code == 200


# ------- autores CRUD -------
class TestAutores:
    def test_list_autores(self, admin_client):
        r = admin_client.get(f"{API}/autores")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert any("ADRIEL" in n.upper() for n in names), f"autores: {names}"

    def test_create_delete_autor(self, admin_client):
        # need an editora
        eds = admin_client.get(f"{API}/editoras").json()
        eid = eds[0]["id"]
        r = admin_client.post(f"{API}/autores", json={"name": "TEST_AUTOR_A", "editora_id": eid, "admin_fee_percent": 15.0})
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        # patch
        r = admin_client.patch(f"{API}/autores/{aid}", json={"admin_fee_percent": 10.0})
        assert r.status_code == 200
        # filter by editora
        r = admin_client.get(f"{API}/autores", params={"editora_id": eid})
        assert any(a["id"] == aid for a in r.json())
        # delete
        r = admin_client.delete(f"{API}/autores/{aid}")
        assert r.status_code == 200


# ------- uploads & dashboard -------
class TestUploadsDashboard:
    def test_uploads_list(self, admin_client):
        r = admin_client.get(f"{API}/uploads")
        assert r.status_code == 200
        ups = r.json()
        assert len(ups) >= 3, f"Expected >=3 pre-seeded uploads, got {len(ups)}"
        types = {u["type"] for u in ups}
        assert {"geral", "editora", "autor"}.issubset(types), f"missing types, got {types}"

    def test_dashboard_summary(self, admin_client):
        r = admin_client.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "admin"
        totals = d["totals"]
        assert totals["valor_total_editora"] > 0, f"editora total should be >0: {totals}"
        assert totals["valor_total_autor"] > 0, f"autor total should be >0: {totals}"
        assert isinstance(d.get("por_fonte"), list)

    def test_competencias(self, admin_client):
        r = admin_client.get(f"{API}/competencias")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ------- reports + PDF -------
class TestReports:
    def _get_adriel_editora(self, c):
        eds = c.get(f"{API}/editoras").json()
        return next(e for e in eds if "ADRIEL" in e["name"].upper())

    def _get_adriel_autor(self, c):
        auts = c.get(f"{API}/autores").json()
        return next(a for a in auts if "ADRIEL" in a["name"].upper())

    def test_report_editora_json(self, admin_client):
        ed = self._get_adriel_editora(admin_client)
        r = admin_client.get(f"{API}/reports/editora/{ed['id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["editora"]["name"] == ed["name"]
        assert "totals" in d
        assert d["totals"]["bruto"] >= 0
        assert len(d["rows"]) > 0

    def test_report_editora_pdf(self, admin_client):
        ed = self._get_adriel_editora(admin_client)
        r = admin_client.get(f"{API}/reports/editora/{ed['id']}/pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "not a valid PDF"
        assert len(r.content) > 1000

    def test_report_autor_json(self, admin_client):
        a = self._get_adriel_autor(admin_client)
        r = admin_client.get(f"{API}/reports/autor/{a['id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["autor"]["name"] == a["name"]
        assert len(d["rows"]) > 0

    def test_report_autor_pdf(self, admin_client):
        a = self._get_adriel_autor(admin_client)
        r = admin_client.get(f"{API}/reports/autor/{a['id']}/pdf")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


# ------- editora-scope login & RBAC -------
class TestEditoraScope:
    @pytest.fixture(scope="class")
    def editora_client(self, admin_client):
        # create a second editora for cross-access test
        eds = admin_client.get(f"{API}/editoras").json()
        adriel = next(e for e in eds if "ADRIEL" in e["name"].upper())
        # make sure there is another editora
        other = next((e for e in eds if e["id"] != adriel["id"]), None)
        if other is None:
            r = admin_client.post(f"{API}/editoras", json={"name": "TEST_OTHER_ED", "admin_fee_percent": 5.0})
            other = r.json()
        # create login for ADRIEL
        email = "editora_adriel_test@example.com"
        password = "EditoraPass123!"
        r = admin_client.post(f"{API}/editoras/{adriel['id']}/login", json={"editora_id": adriel["id"], "email": email, "password": password})
        assert r.status_code == 200, r.text
        s = requests.Session()
        s.headers["Content-Type"] = "application/json"
        r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
        yield {"client": s, "editora_id": adriel["id"], "other_id": other["id"]}

    def test_editora_sees_only_own(self, editora_client):
        c = editora_client["client"]
        r = c.get(f"{API}/editoras")
        assert r.status_code == 200
        eds = r.json()
        assert len(eds) == 1
        assert eds[0]["id"] == editora_client["editora_id"]

    def test_editora_autores_scoped(self, editora_client):
        c = editora_client["client"]
        r = c.get(f"{API}/autores")
        assert r.status_code == 200
        for a in r.json():
            assert a["editora_id"] == editora_client["editora_id"]

    def test_editora_cannot_access_other_report(self, editora_client):
        c = editora_client["client"]
        r = c.get(f"{API}/reports/editora/{editora_client['other_id']}")
        assert r.status_code == 403

    def test_editora_can_access_own_report(self, editora_client):
        c = editora_client["client"]
        r = c.get(f"{API}/reports/editora/{editora_client['editora_id']}")
        assert r.status_code == 200

    def test_editora_cannot_create_editora(self, editora_client):
        c = editora_client["client"]
        r = c.post(f"{API}/editoras", json={"name": "SHOULD_FAIL"})
        assert r.status_code == 403

    def test_editora_cannot_upload(self, editora_client):
        c = editora_client["client"]
        files = {"file": ("fake.csv", b"a,b\n1,2", "text/csv")}
        hdr = {"Authorization": c.headers["Authorization"]}
        r = requests.post(f"{API}/uploads/geral", files=files, headers=hdr)
        assert r.status_code == 403



# ============================================================
# Iteration 2: repasses, bulk ZIP PDFs, notifications, mailer guard
# ============================================================
import zipfile


def _get_adriel_editora(c):
    eds = c.get(f"{API}/editoras").json()
    return next(e for e in eds if "ADRIEL" in e["name"].upper())


def _pick_competencia(c):
    comps = c.get(f"{API}/competencias").json()
    pref = "2026 - SETEMBRO"
    if pref in comps:
        return pref
    return comps[0] if comps else pref


# ------- Repasses CRUD + history -------
class TestRepasses:
    def test_create_update_history(self, admin_client):
        ed = _get_adriel_editora(admin_client)
        comp = _pick_competencia(admin_client)
        # first upsert as "pago"
        p1 = {
            "scope": "editora",
            "scope_id": ed["id"],
            "competencia": comp,
            "status": "pago",
            "valor": 238.66,
            "observacao": "Pix TEST",
            "data_pagamento": "2026-10-05",
        }
        r = admin_client.post(f"{API}/repasses", json=p1)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pago"
        assert d["valor"] == 238.66
        assert d["scope_id"] == ed["id"]
        assert len(d["history"]) >= 1
        rid1 = d["id"]

        # second upsert as pendente — should update same doc, append history
        p2 = dict(p1, status="pendente", observacao="aguardando", valor=238.66)
        r2 = admin_client.post(f"{API}/repasses", json=p2)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["id"] == rid1, "upsert should keep same id"
        assert d2["status"] == "pendente"
        assert len(d2["history"]) >= 2, f"history should have 2+ events: {d2['history']}"

        # verify via list
        rl = admin_client.get(f"{API}/repasses", params={"competencia": comp})
        assert rl.status_code == 200
        found = next((x for x in rl.json() if x["id"] == rid1), None)
        assert found and found["status"] == "pendente"

    def test_invalid_status(self, admin_client):
        ed = _get_adriel_editora(admin_client)
        comp = _pick_competencia(admin_client)
        r = admin_client.post(f"{API}/repasses", json={
            "scope": "editora", "scope_id": ed["id"], "competencia": comp,
            "status": "foo", "valor": 1, "observacao": "", "data_pagamento": None,
        })
        assert r.status_code == 400

    def test_autor_repasse(self, admin_client):
        aut = admin_client.get(f"{API}/autores").json()
        assert aut
        a = aut[0]
        comp = _pick_competencia(admin_client)
        r = admin_client.post(f"{API}/repasses", json={
            "scope": "autor", "scope_id": a["id"], "competencia": comp,
            "status": "pago", "valor": 100.0, "observacao": "TEST autor", "data_pagamento": "2026-10-05",
        })
        assert r.status_code == 200
        assert r.json()["scope"] == "autor"


# ------- Bulk ZIP PDFs -------
class TestBulkZip:
    def test_bulk_editora_zip(self, admin_client):
        comp = _pick_competencia(admin_client)
        r = admin_client.get(f"{API}/reports/bulk/editora/pdf", params={"competencia": comp})
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert any(n.startswith("Editoras/") and n.endswith(".pdf") for n in names), names
        # verify PDF signature inside
        with zf.open(names[0]) as f:
            assert f.read(4) == b"%PDF"

    def test_bulk_autor_zip(self, admin_client):
        comp = _pick_competencia(admin_client)
        r = admin_client.get(f"{API}/reports/bulk/autor/pdf", params={"competencia": comp})
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert any(n.startswith("Autores/") and n.endswith(".pdf") for n in names), names

    def test_bulk_both_zip(self, admin_client):
        comp = _pick_competencia(admin_client)
        r = admin_client.get(f"{API}/reports/bulk/both/pdf", params={"competencia": comp})
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert any(n.startswith("Editoras/") for n in names), names
        assert any(n.startswith("Autores/") for n in names), names

    def test_bulk_invalid_scope(self, admin_client):
        r = admin_client.get(f"{API}/reports/bulk/foo/pdf")
        assert r.status_code == 400


# ------- Notifications (Resend proxy) -------
class TestNotifications:
    def test_send_to_adriel_delivered_resend(self, admin_client):
        ed = _get_adriel_editora(admin_client)
        comp = _pick_competencia(admin_client)
        # ADRIEL email was set to delivered@resend.dev — verify + ensure test idempotent
        if (ed.get("email") or "").lower() != "delivered@resend.dev":
            admin_client.patch(f"{API}/editoras/{ed['id']}", json={"email": "delivered@resend.dev"})
        r = admin_client.post(f"{API}/notifications/send", json={
            "competencia": comp, "target": "editoras", "only_ids": [ed["id"]],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "sent" in d and "skipped" in d and "errors" in d
        assert d["sent"] + len(d["errors"]) >= 1
        # If sent, errors must be empty for that case
        if d["sent"] == 1:
            assert d["errors"] == []

    def test_send_autor_target(self, admin_client):
        comp = _pick_competencia(admin_client)
        # pick an autor without email -> should be skipped
        auts = admin_client.get(f"{API}/autores").json()
        no_email = next((a for a in auts if not a.get("email")), None)
        if no_email is None:
            pytest.skip("All autores already have email set")
        r = admin_client.post(f"{API}/notifications/send", json={
            "competencia": comp, "target": "autores", "only_ids": [no_email["id"]],
        })
        assert r.status_code == 200
        d = r.json()
        assert d["skipped"] >= 1
        assert d["sent"] == 0


# ------- Mailer safety guard (unit-style; imports module directly) -------
import sys as _sys
_sys.path.insert(0, "/app/backend")
from mailer import _assert_safe_email  # type: ignore  # noqa: E402


class TestMailerGuard:
    def test_blocks_form(self):
        with pytest.raises(ValueError):
            _assert_safe_email("sub", "<form><input/></form>")

    def test_blocks_non_https_link(self):
        with pytest.raises(ValueError):
            _assert_safe_email("sub", '<a href="http://example.com">x</a>')

    def test_blocks_shortener(self):
        with pytest.raises(ValueError):
            _assert_safe_email("sub", '<a href="https://bit.ly/abc">x</a>')

    def test_blocks_credential_ask(self):
        with pytest.raises(ValueError):
            _assert_safe_email("sub", "<p>please reply with your password</p>")

    def test_allows_safe_email(self):
        _assert_safe_email("Acorde", '<a href="https://acordemusica.com.br/login">Login</a>')


# ------- Editora-scope RBAC on new endpoints -------
class TestEditoraScopeNew:
    @pytest.fixture(scope="class")
    def editora_client(self, admin_client):
        ed = _get_adriel_editora(admin_client)
        email = "editora_adriel_iter2@example.com"
        password = "EditoraPass123!"
        r = admin_client.post(f"{API}/editoras/{ed['id']}/login",
                              json={"editora_id": ed["id"], "email": email, "password": password})
        assert r.status_code == 200, r.text
        s = requests.Session()
        s.headers["Content-Type"] = "application/json"
        r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
        return {"client": s, "editora_id": ed["id"]}

    def test_editora_cannot_bulk_zip(self, editora_client):
        r = editora_client["client"].get(f"{API}/reports/bulk/editora/pdf")
        assert r.status_code == 403

    def test_editora_cannot_notify(self, editora_client):
        r = editora_client["client"].post(f"{API}/notifications/send", json={
            "competencia": "x", "target": "editoras",
        })
        assert r.status_code == 403

    def test_editora_cannot_create_repasse(self, editora_client):
        r = editora_client["client"].post(f"{API}/repasses", json={
            "scope": "editora", "scope_id": editora_client["editora_id"],
            "competencia": "2026 - SETEMBRO", "status": "pago", "valor": 1,
            "observacao": "", "data_pagamento": None,
        })
        assert r.status_code == 403

    def test_editora_repasses_scoped(self, editora_client, admin_client):
        c = editora_client["client"]
        r = c.get(f"{API}/repasses")
        assert r.status_code == 200
        own_id = editora_client["editora_id"]
        # all editora-scope repasses must match own id
        for rep in r.json():
            if rep["scope"] == "editora":
                assert rep["scope_id"] == own_id, f"leak: {rep}"
