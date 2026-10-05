"""Acorde Backend — FastAPI app serving the royalties processor."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, Request
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_factory,
    require_admin,
)
from parsers import (
    parse_general_zip_or_csv,
    parse_editora_xlsx,
    parse_autor_xlsx,
    parse_bulk_fees_csv,
    _norm,
)
from pdf_generator import generate_editora_pdf, generate_autor_pdf


# ------------------------------------------------------------------ DB

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]

# ------------------------------------------------------------------ App

app = FastAPI(title="Acorde Royalties API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("acorde")


get_current_user = None  # set at startup


# ----------------------------------------------------- Pydantic models

class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EditoraIn(BaseModel):
    name: str
    cnpj: Optional[str] = ""
    admin_fee_percent: float = 0.0
    email: Optional[str] = None


class EditoraPatch(BaseModel):
    name: Optional[str] = None
    cnpj: Optional[str] = None
    admin_fee_percent: Optional[float] = None
    email: Optional[str] = None


class EditoraLoginIn(BaseModel):
    editora_id: str
    email: EmailStr
    password: str


class AutorIn(BaseModel):
    name: str
    editora_id: Optional[str] = None
    admin_fee_percent: float = 0.0


class AutorPatch(BaseModel):
    name: Optional[str] = None
    editora_id: Optional[str] = None
    admin_fee_percent: Optional[float] = None


# ------------------------------------------------------------- Startup

@app.on_event("startup")
async def _startup():
    global get_current_user
    await db.users.create_index("email", unique=True)
    await db.editoras.create_index("name_norm", unique=True)
    await db.autores.create_index([("name_norm", 1), ("editora_id", 1)], unique=True)
    await db.royalty_rows.create_index("competencia")
    await db.royalty_rows.create_index("type")
    await db.royalty_rows.create_index("editora_norm")
    await db.royalty_rows.create_index("nome_norm")
    await db.uploads.create_index("uploaded_at")

    # seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "aline@acordemusica.com.br").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "acorde2026")
    admin_name = os.environ.get("ADMIN_NAME", "Aline")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one(
            {
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": admin_name,
                "role": "admin",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info("Seeded admin user %s", admin_email)
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password), "name": admin_name, "role": "admin"}},
        )
        logger.info("Rotated admin password for %s", admin_email)

    get_current_user = await get_current_user_factory(db)


@app.on_event("shutdown")
async def _shutdown():
    mongo_client.close()


# ------------------------------------------------------------ Auth routes

@api.post("/auth/login")
async def login(data: LoginIn, response: Response):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    user_id = str(user["_id"])
    token = create_access_token(user_id, user["email"], user["role"])
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=12 * 3600,
        path="/",
    )
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user["role"],
            "editora_id": user.get("editora_id"),
        },
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request):
    user = await get_current_user(request)
    return user


# ------------------------------------------------------------ Editoras

def _dump_editora(doc):
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "cnpj": doc.get("cnpj", ""),
        "admin_fee_percent": doc.get("admin_fee_percent", 0.0),
        "email": doc.get("email", ""),
        "has_login": bool(doc.get("user_id")),
        "created_at": doc.get("created_at"),
    }


@api.get("/editoras")
async def list_editoras(request: Request):
    user = await get_current_user(request)
    if user["role"] == "editora":
        doc = await db.editoras.find_one({"_id": ObjectId(user["editora_id"])})
        return [_dump_editora(doc)] if doc else []
    docs = await db.editoras.find({}).sort("name", 1).to_list(2000)
    return [_dump_editora(d) for d in docs]


@api.post("/editoras")
async def create_editora(payload: EditoraIn, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Nome obrigatório")
    name_norm = _norm(name)
    doc = {
        "name": name,
        "name_norm": name_norm,
        "cnpj": payload.cnpj or "",
        "admin_fee_percent": float(payload.admin_fee_percent or 0),
        "email": (payload.email or "").lower().strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = await db.editoras.insert_one(doc)
    except Exception as e:
        raise HTTPException(400, f"Editora já existe: {e}")
    doc["_id"] = res.inserted_id
    return _dump_editora(doc)


@api.patch("/editoras/{editora_id}")
async def update_editora(editora_id: str, payload: EditoraPatch, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "name" in updates:
        updates["name_norm"] = _norm(updates["name"])
    if "email" in updates:
        updates["email"] = (updates["email"] or "").lower().strip()
    await db.editoras.update_one({"_id": ObjectId(editora_id)}, {"$set": updates})
    doc = await db.editoras.find_one({"_id": ObjectId(editora_id)})
    return _dump_editora(doc)


@api.delete("/editoras/{editora_id}")
async def delete_editora(editora_id: str, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    await db.editoras.delete_one({"_id": ObjectId(editora_id)})
    return {"ok": True}


@api.post("/editoras/bulk")
async def bulk_editoras(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request)
    require_admin(user)
    content = await file.read()
    rows = parse_bulk_fees_csv(content)
    created, updated = 0, 0
    for r in rows:
        if not r["nome"]:
            continue
        name_norm = _norm(r["nome"])
        existing = await db.editoras.find_one({"name_norm": name_norm})
        if existing:
            await db.editoras.update_one(
                {"_id": existing["_id"]},
                {"$set": {"admin_fee_percent": r["taxa_admin"], "cnpj": r.get("cnpj") or existing.get("cnpj", ""), "email": r.get("email") or existing.get("email", "")}},
            )
            updated += 1
        else:
            await db.editoras.insert_one(
                {
                    "name": r["nome"],
                    "name_norm": name_norm,
                    "cnpj": r.get("cnpj", ""),
                    "email": r.get("email", "").lower(),
                    "admin_fee_percent": r["taxa_admin"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            created += 1
    return {"created": created, "updated": updated, "total": created + updated}


@api.post("/editoras/{editora_id}/login")
async def create_editora_login(editora_id: str, payload: EditoraLoginIn, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    editora = await db.editoras.find_one({"_id": ObjectId(editora_id)})
    if not editora:
        raise HTTPException(404, "Editora não encontrada")
    email = payload.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"password_hash": hash_password(payload.password), "role": "editora", "editora_id": editora_id, "name": editora["name"]}},
        )
        uid = existing["_id"]
    else:
        res = await db.users.insert_one(
            {
                "email": email,
                "password_hash": hash_password(payload.password),
                "name": editora["name"],
                "role": "editora",
                "editora_id": editora_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        uid = res.inserted_id
    await db.editoras.update_one({"_id": ObjectId(editora_id)}, {"$set": {"user_id": str(uid), "email": email}})
    return {"ok": True, "email": email}


# ------------------------------------------------------------- Autores

def _dump_autor(doc, editora_name=""):
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "editora_id": doc.get("editora_id"),
        "editora_name": editora_name,
        "admin_fee_percent": doc.get("admin_fee_percent", 0.0),
        "created_at": doc.get("created_at"),
    }


@api.get("/autores")
async def list_autores(request: Request, editora_id: Optional[str] = None):
    user = await get_current_user(request)
    q = {}
    if user["role"] == "editora":
        q["editora_id"] = user["editora_id"]
    elif editora_id:
        q["editora_id"] = editora_id
    docs = await db.autores.find(q).sort("name", 1).to_list(5000)
    # map editora names
    ed_ids = {d.get("editora_id") for d in docs if d.get("editora_id")}
    ed_map = {}
    if ed_ids:
        async for e in db.editoras.find({"_id": {"$in": [ObjectId(x) for x in ed_ids]}}):
            ed_map[str(e["_id"])] = e["name"]
    return [_dump_autor(d, ed_map.get(d.get("editora_id", ""), "")) for d in docs]


@api.post("/autores")
async def create_autor(payload: AutorIn, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Nome obrigatório")
    doc = {
        "name": name,
        "name_norm": _norm(name),
        "editora_id": payload.editora_id,
        "admin_fee_percent": float(payload.admin_fee_percent or 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = await db.autores.insert_one(doc)
    except Exception as e:
        raise HTTPException(400, f"Autor já existe nessa editora: {e}")
    doc["_id"] = res.inserted_id
    return _dump_autor(doc)


@api.patch("/autores/{autor_id}")
async def update_autor(autor_id: str, payload: AutorPatch, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "name" in updates:
        updates["name_norm"] = _norm(updates["name"])
    await db.autores.update_one({"_id": ObjectId(autor_id)}, {"$set": updates})
    doc = await db.autores.find_one({"_id": ObjectId(autor_id)})
    return _dump_autor(doc)


@api.delete("/autores/{autor_id}")
async def delete_autor(autor_id: str, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    await db.autores.delete_one({"_id": ObjectId(autor_id)})
    return {"ok": True}


@api.post("/autores/bulk")
async def bulk_autores(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request)
    require_admin(user)
    content = await file.read()
    rows = parse_bulk_fees_csv(content)
    created, updated, skipped = 0, 0, 0
    for r in rows:
        if not r["nome"]:
            continue
        editora_id = None
        if r.get("editora"):
            e = await db.editoras.find_one({"name_norm": _norm(r["editora"])})
            if e:
                editora_id = str(e["_id"])
        name_norm = _norm(r["nome"])
        existing = await db.autores.find_one({"name_norm": name_norm, "editora_id": editora_id})
        if existing:
            await db.autores.update_one(
                {"_id": existing["_id"]}, {"$set": {"admin_fee_percent": r["taxa_admin"]}}
            )
            updated += 1
        else:
            try:
                await db.autores.insert_one(
                    {
                        "name": r["nome"],
                        "name_norm": name_norm,
                        "editora_id": editora_id,
                        "admin_fee_percent": r["taxa_admin"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                created += 1
            except Exception:
                skipped += 1
    return {"created": created, "updated": updated, "skipped": skipped}


# ------------------------------------------------------------- Uploads

async def _store_rows(rows: list[dict], upload_id: str, rtype: str):
    if not rows:
        return 0
    for r in rows:
        r["upload_id"] = upload_id
        r["type"] = rtype
    await db.royalty_rows.insert_many(rows)
    return len(rows)


@api.post("/uploads/{report_type}")
async def upload_report(report_type: str, request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request)
    require_admin(user)
    if report_type not in ("geral", "editora", "autor"):
        raise HTTPException(400, "Tipo inválido")
    content = await file.read()
    filename = file.filename or ""
    if report_type == "geral":
        rows = parse_general_zip_or_csv(content, filename)
    elif report_type == "editora":
        rows = parse_editora_xlsx(content, filename)
    else:
        rows = parse_autor_xlsx(content, filename)

    competencias = sorted({(r.get("competencia") or r.get("periodo") or "").strip() for r in rows if (r.get("competencia") or r.get("periodo"))})
    competencia = competencias[0] if competencias else ""

    upload_doc = {
        "filename": filename,
        "type": report_type,
        "competencia": competencia,
        "rows_count": len(rows),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": user["email"],
    }
    res = await db.uploads.insert_one(upload_doc)
    upload_id = str(res.inserted_id)
    stored = await _store_rows(rows, upload_id, report_type)
    return {"upload_id": upload_id, "type": report_type, "rows": stored, "competencia": competencia}


@api.get("/uploads")
async def list_uploads(request: Request):
    user = await get_current_user(request)
    require_admin(user)
    docs = await db.uploads.find({}).sort("uploaded_at", -1).to_list(200)
    for d in docs:
        d["id"] = str(d["_id"])
        d.pop("_id", None)
    return docs


@api.delete("/uploads/{upload_id}")
async def delete_upload(upload_id: str, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    await db.royalty_rows.delete_many({"upload_id": upload_id})
    await db.uploads.delete_one({"_id": ObjectId(upload_id)})
    return {"ok": True}


@api.get("/competencias")
async def list_competencias(request: Request):
    user = await get_current_user(request)
    docs = await db.royalty_rows.distinct("competencia")
    comps = sorted([c for c in docs if c], reverse=True)
    return comps


# ------------------------------------------------------------- Reports

async def _editora_report(editora_id: str, competencia: Optional[str]):
    editora = await db.editoras.find_one({"_id": ObjectId(editora_id)})
    if not editora:
        raise HTTPException(404, "Editora não encontrada")
    q = {"type": "editora", "titular_norm": editora["name_norm"]}
    if competencia:
        q["$or"] = [{"competencia": competencia}, {"periodo": competencia}]
    rows_raw = await db.royalty_rows.find(q).to_list(100000)
    fee_percent = float(editora.get("admin_fee_percent", 0) or 0)
    fee_mult = fee_percent / 100.0
    rows_out = []
    total_bruto = 0.0
    total_taxa = 0.0
    for r in rows_raw:
        bruto = float(r.get("vl_editora", 0) or 0)
        taxa = round(bruto * fee_mult, 6)
        liquido = round(bruto - taxa, 6)
        rows_out.append(
            {
                "fonte": r.get("fonte", ""),
                "obra": r.get("obra", ""),
                "autores": r.get("autores", ""),
                "unidades": r.get("unidades", 0),
                "perc_editora": r.get("perc_editora", 0),
                "pagamento": r.get("pagamento", ""),
                "vl_editora_bruto": bruto,
                "taxa_admin_valor": taxa,
                "vl_editora_liquido": liquido,
                "competencia": r.get("competencia") or r.get("periodo", ""),
            }
        )
        total_bruto += bruto
        total_taxa += taxa
    return {
        "editora": {
            "id": str(editora["_id"]),
            "name": editora["name"],
            "cnpj": editora.get("cnpj", ""),
            "admin_fee_percent": fee_percent,
        },
        "competencia": competencia or "",
        "rows": rows_out,
        "totals": {
            "bruto": round(total_bruto, 2),
            "taxa": round(total_taxa, 2),
            "liquido": round(total_bruto - total_taxa, 2),
        },
    }


async def _autor_report(autor_id: str, competencia: Optional[str]):
    autor = await db.autores.find_one({"_id": ObjectId(autor_id)})
    if not autor:
        raise HTTPException(404, "Autor não encontrado")
    editora_name = ""
    if autor.get("editora_id"):
        e = await db.editoras.find_one({"_id": ObjectId(autor["editora_id"])})
        if e:
            editora_name = e["name"]
    q = {"type": "autor", "nome_norm": autor["name_norm"]}
    if competencia:
        q["$or"] = [{"competencia": competencia}, {"periodo": competencia}]
    rows_raw = await db.royalty_rows.find(q).to_list(100000)
    fee_percent = float(autor.get("admin_fee_percent", 0) or 0)
    fee_mult = fee_percent / 100.0
    rows_out = []
    total_bruto = 0.0
    total_liquido = 0.0
    total_units = 0
    obras = set()
    for r in rows_raw:
        bruto = float(r.get("vl_autor", 0) or 0)
        liquido = round(bruto * (1 - fee_mult), 6)
        rows_out.append(
            {
                "fonte": r.get("fonte", ""),
                "formato": r.get("formato", ""),
                "territorio": r.get("territorio", ""),
                "obra": r.get("obra", ""),
                "periodo": r.get("periodo") or r.get("competencia", ""),
                "unidades": r.get("unidades", 0),
                "perc_autor": r.get("perc_autor", 0),
                "vl_bruto": bruto,  # hidden on PDF, admin-only
                "vl_liquido": liquido,
                "autores": r.get("autores", ""),
            }
        )
        total_bruto += bruto
        total_liquido += liquido
        total_units += int(r.get("unidades", 0) or 0)
        obras.add(r.get("obra", ""))
    return {
        "autor": {
            "id": str(autor["_id"]),
            "name": autor["name"],
            "admin_fee_percent": fee_percent,
            "editora_id": autor.get("editora_id"),
            "editora_name": editora_name,
        },
        "competencia": competencia or "",
        "rows": rows_out,
        "totals": {
            "bruto": round(total_bruto, 2),
            "liquido": round(total_liquido, 2),
            "unidades": total_units,
            "obras": len({o for o in obras if o}),
        },
    }


def _check_editora_scope(user, editora_id):
    if user["role"] == "editora" and user.get("editora_id") != editora_id:
        raise HTTPException(403, "Sem acesso a esta editora")


@api.get("/reports/editora/{editora_id}")
async def report_editora(editora_id: str, request: Request, competencia: Optional[str] = None):
    user = await get_current_user(request)
    _check_editora_scope(user, editora_id)
    return await _editora_report(editora_id, competencia)


@api.get("/reports/autor/{autor_id}")
async def report_autor(autor_id: str, request: Request, competencia: Optional[str] = None):
    user = await get_current_user(request)
    autor = await db.autores.find_one({"_id": ObjectId(autor_id)})
    if not autor:
        raise HTTPException(404, "Autor não encontrado")
    if user["role"] == "editora" and autor.get("editora_id") != user.get("editora_id"):
        raise HTTPException(403, "Sem acesso a este autor")
    return await _autor_report(autor_id, competencia)


@api.get("/reports/editora/{editora_id}/pdf")
async def report_editora_pdf(editora_id: str, request: Request, competencia: Optional[str] = None):
    user = await get_current_user(request)
    _check_editora_scope(user, editora_id)
    data = await _editora_report(editora_id, competencia)
    pdf = generate_editora_pdf(
        editora_name=data["editora"]["name"],
        cnpj=data["editora"].get("cnpj", ""),
        competencia=data["competencia"],
        admin_fee_percent=data["editora"]["admin_fee_percent"],
        rows=data["rows"],
        totals=data["totals"],
    )
    safe = data["editora"]["name"].replace(" ", "_")[:40]
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Acorde_Editora_{safe}.pdf"'},
    )


@api.get("/reports/autor/{autor_id}/pdf")
async def report_autor_pdf(autor_id: str, request: Request, competencia: Optional[str] = None):
    user = await get_current_user(request)
    autor = await db.autores.find_one({"_id": ObjectId(autor_id)})
    if not autor:
        raise HTTPException(404, "Autor não encontrado")
    if user["role"] == "editora" and autor.get("editora_id") != user.get("editora_id"):
        raise HTTPException(403, "Sem acesso a este autor")
    data = await _autor_report(autor_id, competencia)
    pdf = generate_autor_pdf(
        autor_name=data["autor"]["name"],
        editora_name=data["autor"]["editora_name"],
        competencia=data["competencia"],
        rows=data["rows"],
        totals=data["totals"],
    )
    safe = data["autor"]["name"].replace(" ", "_")[:40]
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Acorde_Autor_{safe}.pdf"'},
    )


# -------------------------------------------------------- Dashboard

@api.get("/dashboard/summary")
async def dashboard_summary(request: Request, competencia: Optional[str] = None):
    user = await get_current_user(request)
    is_admin = user["role"] == "admin"

    match_autor = {"type": "autor"}
    match_editora = {"type": "editora"}
    match_geral = {"type": "geral"}
    if competencia:
        match_autor["$or"] = [{"competencia": competencia}, {"periodo": competencia}]
        match_editora["$or"] = [{"competencia": competencia}, {"periodo": competencia}]
        match_geral["$or"] = [{"competencia": competencia}, {"periodo": competencia}]

    if not is_admin:
        # scope to editora
        editora = await db.editoras.find_one({"_id": ObjectId(user["editora_id"])})
        if not editora:
            raise HTTPException(404, "Editora não encontrada")
        match_autor["titular_norm"] = editora["name_norm"]
        match_editora["titular_norm"] = editora["name_norm"]
        match_geral["editora_norm"] = editora["name_norm"]

    pipeline_sum = lambda match, field: [
        {"$match": match},
        {"$group": {"_id": None, "total": {"$sum": f"${field}"}, "count": {"$sum": 1}}},
    ]

    total_autor = await db.royalty_rows.aggregate(pipeline_sum(match_autor, "vl_autor")).to_list(1)
    total_editora = await db.royalty_rows.aggregate(pipeline_sum(match_editora, "vl_editora")).to_list(1)
    total_geral = await db.royalty_rows.aggregate(pipeline_sum(match_geral, "val_liquido")).to_list(1)

    def _val(x):
        return (x[0]["total"] if x else 0) or 0

    def _cnt(x):
        return (x[0]["count"] if x else 0) or 0

    # breakdown by fonte (autor rows)
    por_fonte = await db.royalty_rows.aggregate(
        [
            {"$match": match_autor},
            {"$group": {"_id": "$fonte", "total": {"$sum": "$vl_autor"}, "count": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": 10},
        ]
    ).to_list(10)

    # Top editoras (admin only)
    top_editoras = []
    if is_admin:
        top_editoras = await db.royalty_rows.aggregate(
            [
                {"$match": match_editora},
                {"$group": {"_id": "$titular", "total": {"$sum": "$vl_editora"}}},
                {"$sort": {"total": -1}},
                {"$limit": 10},
            ]
        ).to_list(10)

    editoras_count = await db.editoras.count_documents({})
    autores_count = await db.autores.count_documents({"editora_id": user["editora_id"]} if not is_admin else {})

    return {
        "role": user["role"],
        "competencia": competencia or "",
        "totals": {
            "valor_total_geral": round(_val(total_geral), 2),
            "valor_total_editora": round(_val(total_editora), 2),
            "valor_total_autor": round(_val(total_autor), 2),
            "linhas_autor": _cnt(total_autor),
            "linhas_editora": _cnt(total_editora),
            "linhas_geral": _cnt(total_geral),
            "editoras_cadastradas": editoras_count,
            "autores_cadastrados": autores_count,
        },
        "por_fonte": [{"fonte": p["_id"] or "—", "total": round(p["total"], 2), "count": p["count"]} for p in por_fonte],
        "top_editoras": [{"titular": t["_id"] or "—", "total": round(t["total"], 2)} for t in top_editoras],
    }


@api.get("/")
async def health():
    return {"status": "ok", "service": "Acorde Royalties API"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
