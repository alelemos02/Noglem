import io
import uuid

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.integration

_sync_engine = create_engine(settings.DATABASE_URL_SYNC)


@pytest.fixture(autouse=True)
def cleanup_test_data():
    yield
    with _sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM revisoes_parecer WHERE parecer_id IN (SELECT id FROM pareceres WHERE numero_parecer LIKE 'PYTEST-%')"))
        conn.execute(text("DELETE FROM itens_parecer WHERE parecer_id IN (SELECT id FROM pareceres WHERE numero_parecer LIKE 'PYTEST-%')"))
        conn.execute(text("DELETE FROM recomendacoes WHERE parecer_id IN (SELECT id FROM pareceres WHERE numero_parecer LIKE 'PYTEST-%')"))
        conn.execute(text("DELETE FROM documentos WHERE parecer_id IN (SELECT id FROM pareceres WHERE numero_parecer LIKE 'PYTEST-%')"))
        conn.execute(text("DELETE FROM audit_logs WHERE usuario_email LIKE 'pytest_%'"))
        conn.execute(text("DELETE FROM pareceres WHERE numero_parecer LIKE 'PYTEST-%'"))
        conn.execute(text("DELETE FROM usuarios WHERE email LIKE 'pytest_%'"))


def _xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "dados"
    ws.append(["campo", "valor"])
    ws.append(["teste", "ok"])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _register_and_login(client: TestClient, role: str):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "nome": f"Pytest {role}",
        "email": f"pytest_{role}_{suffix}@example.com",
        "senha": "SenhaForte123!",
        "papel": role,
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "senha": payload["senha"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, payload


def test_crud_upload_export_revisoes_estimativa_and_auditoria():
    with TestClient(app) as client:
        headers, _payload = _register_and_login(client, "admin")
        numero = f"PYTEST-{uuid.uuid4().hex[:8]}"

        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        refreshed = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": client.post("/api/v1/auth/login", json={"email": _payload["email"], "senha": _payload["senha"]}).json()["refresh_token"]},
        )
        assert refreshed.status_code == 200

        # CRUD parecer
        create = client.post(
            "/api/v1/pareceres",
            headers=headers,
            json={
                "numero_parecer": numero,
                "projeto": "Projeto Pytest",
                "fornecedor": "Fornecedor Pytest",
                "revisao": "0",
            },
        )
        assert create.status_code == 201, create.text
        parecer_id = create.json()["id"]

        list_resp = client.get("/api/v1/pareceres?projeto=Pytest", headers=headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        detail = client.get(f"/api/v1/pareceres/{parecer_id}", headers=headers)
        assert detail.status_code == 200

        update = client.put(
            f"/api/v1/pareceres/{parecer_id}",
            headers=headers,
            json={"revisao": "1"},
        )
        assert update.status_code == 200
        assert update.json()["revisao"] == "1"

        # Upload docs (engenharia + fornecedor)
        xlsx_payload = _xlsx_bytes()
        upload_eng = client.post(
            f"/api/v1/pareceres/{parecer_id}/documentos/engenharia",
            headers=headers,
            files={"file": ("eng.xlsx", xlsx_payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert upload_eng.status_code == 201, upload_eng.text

        upload_forn = client.post(
            f"/api/v1/pareceres/{parecer_id}/documentos/fornecedor",
            headers=headers,
            files={"file": ("forn.xlsx", xlsx_payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert upload_forn.status_code == 201, upload_forn.text

        docs = client.get(f"/api/v1/pareceres/{parecer_id}/documentos", headers=headers)
        assert docs.status_code == 200
        assert len(docs.json()) == 2

        # Estimativa
        estimativa = client.get(f"/api/v1/pareceres/{parecer_id}/estimativa-custo", headers=headers)
        assert estimativa.status_code == 200
        assert "custo_estimado_usd" in estimativa.json()

        # Exportacoes
        for fmt in ("pdf", "xlsx", "docx"):
            resp = client.get(f"/api/v1/pareceres/{parecer_id}/exportar/{fmt}", headers=headers)
            assert resp.status_code == 200, resp.text
            assert len(resp.content) > 100

        # Revisoes
        rev_1 = client.post(
            f"/api/v1/pareceres/{parecer_id}/revisoes",
            headers=headers,
            json={"motivo": "snapshot 1"},
        )
        assert rev_1.status_code == 201, rev_1.text

        rev_2 = client.post(
            f"/api/v1/pareceres/{parecer_id}/revisoes",
            headers=headers,
            json={"motivo": "snapshot 2"},
        )
        assert rev_2.status_code == 201, rev_2.text

        list_revs = client.get(f"/api/v1/pareceres/{parecer_id}/revisoes", headers=headers)
        assert list_revs.status_code == 200
        assert list_revs.json()["total"] >= 2

        compare = client.get(
            f"/api/v1/pareceres/{parecer_id}/revisoes/comparar/1/2",
            headers=headers,
        )
        assert compare.status_code == 200, compare.text
        assert "diferencas" in compare.json()

        # Auditoria (admin only)
        audit = client.get("/api/v1/auditoria", headers=headers)
        assert audit.status_code == 200, audit.text
        assert audit.json()["total"] >= 1

        delete = client.delete(f"/api/v1/pareceres/{parecer_id}", headers=headers)
        assert delete.status_code == 204
