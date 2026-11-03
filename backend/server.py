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
from mailer import send_email, build_editora_email_html, build_autor_email_html
import zipfile
import re


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
    email: Optional[str] = ""


class AutorPatch(BaseModel):
    name: Optional[str] = None
    editora_id: Optional[str] = None
    admin_fee_percent: Optional[float] = None
    email: Optional[str] = None


class RepasseIn(BaseModel):
    scope: str  # 'editora' or 'autor'
    scope_id: str
    competencia: str
    status: str  # 'pendente' or 'pago'
    valor: float = 0.0
    observacao: Optional[str] = ""
    data_pagamento: Optional[str] = None  # ISO date


class SendNotificationsIn(BaseModel):
    competencia: str
    target: str = "editoras"  # 'editoras' or 'autores' or 'both'
    only_ids: Optional[list[str]] = None  # if provided, send only to these ids


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
    await db.repasses.create_index([("scope", 1), ("scope_id", 1), ("competencia", 1)], unique=True)

    # seed admin
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    admin_name = os.environ.get("ADMIN_NAME", "Admin")
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
        "needs_review": bool(doc.get("needs_review", False)),
        "auto_created": bool(doc.get("auto_created", False)),
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
    # Any manual edit clears the pending-review flag
    updates["needs_review"] = False
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
                {"$set": {
                    "admin_fee_percent": r["taxa_admin"],
                    "cnpj": r.get("cnpj") or existing.get("cnpj", ""),
                    "email": r.get("email") or existing.get("email", ""),
                    "needs_review": False,
                }},
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
                    "needs_review": False,
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
        "email": doc.get("email", ""),
        "needs_review": bool(doc.get("needs_review", False)),
        "auto_created": bool(doc.get("auto_created", False)),
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
        "email": (payload.email or "").lower().strip(),
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
    if "email" in updates:
        updates["email"] = (updates["email"] or "").lower().strip()
    updates["needs_review"] = False
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
                {"_id": existing["_id"]}, {"$set": {"admin_fee_percent": r["taxa_admin"], "needs_review": False}}
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
                        "needs_review": False,
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


async def _auto_discover(rtype: str, rows: list[dict]) -> dict:
    """After an upload, auto-create stub editoras/autores for every unique
    titular/nome found in the data. Existing records are preserved untouched.
    Stubs have admin_fee_percent=0 and needs_review=True so they appear as
    'pending' until an admin configures the taxa."""
    now = datetime.now(timezone.utc).isoformat()
    new_editoras, new_autores = 0, 0

    if rtype in ("geral", "editora"):
        # unique editoras
        seen = {}
        for r in rows:
            name = (r.get("editora_nome") or r.get("titular") or "").strip()
            if not name:
                continue
            key = _norm(name)
            if key and key not in seen:
                seen[key] = name
        for name_norm, name in seen.items():
            existing = await db.editoras.find_one({"name_norm": name_norm})
            if not existing:
                await db.editoras.insert_one({
                    "name": name,
                    "name_norm": name_norm,
                    "cnpj": "",
                    "email": "",
                    "admin_fee_percent": 0.0,
                    "needs_review": True,
                    "auto_created": True,
                    "created_at": now,
                })
                new_editoras += 1

    if rtype == "autor":
        # unique (titular, nome) pairs, resolving editora_id by titular_norm
        pairs = {}
        for r in rows:
            name = (r.get("nome") or "").strip()
            titular = (r.get("titular") or "").strip()
            if not name:
                continue
            key = (_norm(name), _norm(titular))
            if key not in pairs:
                pairs[key] = (name, titular)
        # make sure the editoras exist first (same auto-stub logic)
        unique_editoras = {}
        for (_, t_norm), (_, titular) in pairs.items():
            if t_norm and t_norm not in unique_editoras:
                unique_editoras[t_norm] = titular
        for t_norm, titular in unique_editoras.items():
            existing = await db.editoras.find_one({"name_norm": t_norm})
            if not existing:
                await db.editoras.insert_one({
                    "name": titular,
                    "name_norm": t_norm,
                    "cnpj": "",
                    "email": "",
                    "admin_fee_percent": 0.0,
                    "needs_review": True,
                    "auto_created": True,
                    "created_at": now,
                })
                new_editoras += 1
        # now autores
        for (n_norm, t_norm), (name, titular) in pairs.items():
            editora_id = None
            if t_norm:
                ed = await db.editoras.find_one({"name_norm": t_norm})
                if ed:
                    editora_id = str(ed["_id"])
            existing = await db.autores.find_one({"name_norm": n_norm, "editora_id": editora_id})
            if not existing:
                try:
                    await db.autores.insert_one({
                        "name": name,
                        "name_norm": n_norm,
                        "editora_id": editora_id,
                        "email": "",
                        "admin_fee_percent": 0.0,
                        "needs_review": True,
                        "auto_created": True,
                        "created_at": now,
                    })
                    new_autores += 1
                except Exception:
                    pass

    return {"new_editoras": new_editoras, "new_autores": new_autores}


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
    discovery = await _auto_discover(report_type, rows)
    # Update upload with discovery results
    await db.uploads.update_one({"_id": res.inserted_id}, {"$set": {"discovery": discovery}})

    pending_editoras = await db.editoras.count_documents({"needs_review": True})
    pending_autores = await db.autores.count_documents({"needs_review": True})

    return {
        "upload_id": upload_id,
        "type": report_type,
        "rows": stored,
        "competencia": competencia,
        "discovery": discovery,
        "pending_editoras": pending_editoras,
        "pending_autores": pending_autores,
    }


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


# -------------------------------------------------------- Repasses

def _dump_repasse(doc):
    return {
        "id": str(doc["_id"]),
        "scope": doc["scope"],
        "scope_id": doc["scope_id"],
        "competencia": doc["competencia"],
        "status": doc["status"],
        "valor": doc.get("valor", 0),
        "observacao": doc.get("observacao", ""),
        "data_pagamento": doc.get("data_pagamento"),
        "updated_at": doc.get("updated_at"),
        "history": doc.get("history", []),
    }


async def _check_repasse_scope(user, scope, scope_id):
    if user["role"] != "editora":
        return
    if scope == "editora" and scope_id != user.get("editora_id"):
        raise HTTPException(403, "Sem acesso a este repasse")
    if scope == "autor":
        autor = await db.autores.find_one({"_id": ObjectId(scope_id)})
        if not autor or autor.get("editora_id") != user.get("editora_id"):
            raise HTTPException(403, "Sem acesso a este repasse")


@api.get("/repasses")
async def list_repasses(request: Request, competencia: Optional[str] = None, scope: Optional[str] = None):
    user = await get_current_user(request)
    q = {}
    if competencia:
        q["competencia"] = competencia
    if scope:
        q["scope"] = scope
    if user["role"] == "editora":
        autores = await db.autores.find({"editora_id": user["editora_id"]}, {"_id": 1}).to_list(5000)
        autor_ids = [str(a["_id"]) for a in autores]
        q["$or"] = [
            {"scope": "editora", "scope_id": user["editora_id"]},
            {"scope": "autor", "scope_id": {"$in": autor_ids}},
        ]
    docs = await db.repasses.find(q).sort("updated_at", -1).to_list(5000)
    return [_dump_repasse(d) for d in docs]


@api.post("/repasses")
async def upsert_repasse(payload: RepasseIn, request: Request):
    user = await get_current_user(request)
    require_admin(user)
    if payload.scope not in ("editora", "autor"):
        raise HTTPException(400, "scope inválido")
    if payload.status not in ("pendente", "pago"):
        raise HTTPException(400, "status inválido")
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "status": payload.status,
        "valor": float(payload.valor or 0),
        "observacao": payload.observacao or "",
        "data_pagamento": payload.data_pagamento,
        "at": now,
        "by": user["email"],
    }
    existing = await db.repasses.find_one(
        {"scope": payload.scope, "scope_id": payload.scope_id, "competencia": payload.competencia}
    )
    if existing:
        new_history = (existing.get("history") or []) + [event]
        await db.repasses.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "status": payload.status,
                "valor": event["valor"],
                "observacao": event["observacao"],
                "data_pagamento": payload.data_pagamento,
                "updated_at": now,
                "history": new_history[-50:],
            }},
        )
        doc = await db.repasses.find_one({"_id": existing["_id"]})
    else:
        doc = {
            "scope": payload.scope,
            "scope_id": payload.scope_id,
            "competencia": payload.competencia,
            "status": payload.status,
            "valor": event["valor"],
            "observacao": event["observacao"],
            "data_pagamento": payload.data_pagamento,
            "created_at": now,
            "updated_at": now,
            "history": [event],
        }
        res = await db.repasses.insert_one(doc)
        doc["_id"] = res.inserted_id
    return _dump_repasse(doc)


# --------------------------------------- Bulk PDF export (ZIP)

def _safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", (s or "sem_nome"))[:80]


@api.get("/reports/bulk/{scope}/pdf")
async def bulk_pdf_zip(scope: str, request: Request, competencia: Optional[str] = None):
    """Return a ZIP containing all PDFs for the given scope (editora|autor|both)
    optionally filtered by competencia. Admin only."""
    user = await get_current_user(request)
    require_admin(user)
    if scope not in ("editora", "autor", "both"):
        raise HTTPException(400, "scope inválido")

    buf = io.BytesIO()
    files_count = 0
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if scope in ("editora", "both"):
            editoras = await db.editoras.find({}).to_list(5000)
            for e in editoras:
                data = await _editora_report(str(e["_id"]), competencia)
                if not data["rows"]:
                    continue
                pdf = generate_editora_pdf(
                    editora_name=data["editora"]["name"],
                    cnpj=data["editora"].get("cnpj", ""),
                    competencia=data["competencia"],
                    admin_fee_percent=data["editora"]["admin_fee_percent"],
                    rows=data["rows"],
                    totals=data["totals"],
                )
                fname = f"Editoras/Acorde_Editora_{_safe_filename(data['editora']['name'])}.pdf"
                zf.writestr(fname, pdf)
                files_count += 1

        if scope in ("autor", "both"):
            autores = await db.autores.find({}).to_list(10000)
            for a in autores:
                data = await _autor_report(str(a["_id"]), competencia)
                if not data["rows"]:
                    continue
                pdf = generate_autor_pdf(
                    autor_name=data["autor"]["name"],
                    editora_name=data["autor"]["editora_name"],
                    competencia=data["competencia"],
                    rows=data["rows"],
                    totals=data["totals"],
                )
                fname = f"Autores/Acorde_Autor_{_safe_filename(data['autor']['name'])}.pdf"
                zf.writestr(fname, pdf)
                files_count += 1

    buf.seek(0)
    if files_count == 0:
        raise HTTPException(404, "Nenhum relatório encontrado para essa competência")
    tag = _safe_filename(competencia or "todas")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="Acorde_Relatorios_{scope}_{tag}.zip"',
            "X-Files-Count": str(files_count),
        },
    )


# ---------------------------------------------- Notificações por email

@api.post("/notifications/send")
async def send_notifications(payload: SendNotificationsIn, request: Request):
    user = await get_current_user(request)
    require_admin(user)

    frontend_origin = os.environ.get("FRONTEND_URL") or (
        request.headers.get("origin") or "https://acordemusica.com.br"
    )
    portal_login = f"{frontend_origin.rstrip('/')}/login"

    results = {"sent": 0, "skipped": 0, "errors": []}

    async def _send_editora_batch():
        q = {}
        if payload.only_ids:
            q["_id"] = {"$in": [ObjectId(x) for x in payload.only_ids]}
        editoras = await db.editoras.find(q).to_list(5000)
        for e in editoras:
            email = (e.get("email") or "").strip()
            if not email:
                results["skipped"] += 1
                continue
            html = build_editora_email_html(e["name"], payload.competencia, portal_login)
            subject = f"Acorde • Relatório da competência {payload.competencia}"
            try:
                await send_email(to=email, subject=subject, html=html)
                results["sent"] += 1
                await db.editoras.update_one(
                    {"_id": e["_id"]},
                    {"$set": {"last_notification": {
                        "competencia": payload.competencia,
                        "at": datetime.now(timezone.utc).isoformat(),
                    }}},
                )
            except Exception as ex:
                results["errors"].append({"editora": e["name"], "error": str(ex)})

    async def _send_autor_batch():
        q = {}
        if payload.only_ids:
            q["_id"] = {"$in": [ObjectId(x) for x in payload.only_ids]}
        autores = await db.autores.find(q).to_list(10000)
        for a in autores:
            email = (a.get("email") or "").strip()
            if not email:
                results["skipped"] += 1
                continue
            editora_name = ""
            if a.get("editora_id"):
                ed = await db.editoras.find_one({"_id": ObjectId(a["editora_id"])})
                if ed:
                    editora_name = ed["name"]
            html = build_autor_email_html(a["name"], editora_name, payload.competencia, portal_login)
            subject = f"Acorde • Seu relatório da competência {payload.competencia}"
            try:
                await send_email(to=email, subject=subject, html=html)
                results["sent"] += 1
            except Exception as ex:
                results["errors"].append({"autor": a["name"], "error": str(ex)})

    if payload.target in ("editoras", "both"):
        await _send_editora_batch()
    if payload.target in ("autores", "both"):
        await _send_autor_batch()

    return results


# ---------------------------------------------- Descoberta retroativa

@api.post("/discover/sync")
async def discover_sync(request: Request):
    """Scan all royalty rows already in DB and auto-create any missing
    editoras/autores. Useful when data was imported before auto-discovery
    existed, or when a report was re-imported after record deletion.
    Returns totals and lists of pending (needs_review) items."""
    user = await get_current_user(request)
    require_admin(user)

    now = datetime.now(timezone.utc).isoformat()

    # Editoras: union of titular_norm (editora/autor rows) + editora_norm (geral)
    editoras_norms = set()
    editoras_names = {}
    async for r in db.royalty_rows.find({"type": {"$in": ["editora", "autor"]}}, {"titular": 1, "titular_norm": 1}):
        n = r.get("titular_norm")
        if n and n not in editoras_norms:
            editoras_norms.add(n)
            editoras_names[n] = r.get("titular", "")
    async for r in db.royalty_rows.find({"type": "geral"}, {"editora_nome": 1, "editora_norm": 1}):
        n = r.get("editora_norm")
        if n and n not in editoras_norms:
            editoras_norms.add(n)
            editoras_names[n] = r.get("editora_nome", "")

    new_editoras = 0
    for norm, name in editoras_names.items():
        existing = await db.editoras.find_one({"name_norm": norm})
        if not existing and name:
            await db.editoras.insert_one({
                "name": name,
                "name_norm": norm,
                "cnpj": "",
                "email": "",
                "admin_fee_percent": 0.0,
                "needs_review": True,
                "auto_created": True,
                "created_at": now,
            })
            new_editoras += 1

    # Autores: unique (nome_norm, titular_norm) from autor rows
    pairs = {}
    async for r in db.royalty_rows.find({"type": "autor"}, {"nome": 1, "nome_norm": 1, "titular": 1, "titular_norm": 1}):
        n, t = r.get("nome_norm"), r.get("titular_norm")
        if n and (n, t) not in pairs:
            pairs[(n, t)] = (r.get("nome", ""), r.get("titular", ""))

    new_autores = 0
    for (n_norm, t_norm), (name, titular) in pairs.items():
        editora_id = None
        if t_norm:
            ed = await db.editoras.find_one({"name_norm": t_norm})
            if ed:
                editora_id = str(ed["_id"])
        existing = await db.autores.find_one({"name_norm": n_norm, "editora_id": editora_id})
        if not existing:
            try:
                await db.autores.insert_one({
                    "name": name,
                    "name_norm": n_norm,
                    "editora_id": editora_id,
                    "email": "",
                    "admin_fee_percent": 0.0,
                    "needs_review": True,
                    "auto_created": True,
                    "created_at": now,
                })
                new_autores += 1
            except Exception:
                pass

    pending_editoras = await db.editoras.count_documents({"needs_review": True})
    pending_autores = await db.autores.count_documents({"needs_review": True})
    return {
        "new_editoras": new_editoras,
        "new_autores": new_autores,
        "pending_editoras": pending_editoras,
        "pending_autores": pending_autores,
    }


def _csv_response(rows: list[list[str]], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    import csv as _csv
    writer = _csv.writer(buf, delimiter=",", quotechar='"', quoting=_csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow(row)
    data = buf.getvalue().encode("utf-8-sig")  # BOM for Excel BR
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/discover/pending/editoras.csv")
async def pending_editoras_csv(request: Request):
    """CSV template with pending editoras (admin_fee=0 or needs_review=True).
    Format matches /api/editoras/bulk: nome,cnpj,taxa_admin,email."""
    user = await get_current_user(request)
    require_admin(user)
    docs = await db.editoras.find({"needs_review": True}).sort("name", 1).to_list(5000)
    rows = [["nome", "cnpj", "taxa_admin", "email"]]
    for d in docs:
        rows.append([
            d.get("name", ""),
            d.get("cnpj", ""),
            "",  # leave blank so admin fills
            d.get("email", ""),
        ])
    return _csv_response(rows, "acorde_editoras_pendentes.csv")


@api.get("/discover/pending/autores.csv")
async def pending_autores_csv(request: Request):
    user = await get_current_user(request)
    require_admin(user)
    docs = await db.autores.find({"needs_review": True}).sort("name", 1).to_list(50000)
    # map editora ids -> name
    ed_ids = {d.get("editora_id") for d in docs if d.get("editora_id")}
    ed_map = {}
    if ed_ids:
        async for e in db.editoras.find({"_id": {"$in": [ObjectId(x) for x in ed_ids if x]}}):
            ed_map[str(e["_id"])] = e["name"]
    rows = [["nome", "editora", "taxa_admin", "email"]]
    for d in docs:
        rows.append([
            d.get("name", ""),
            ed_map.get(d.get("editora_id", ""), ""),
            "",
            d.get("email", ""),
        ])
    return _csv_response(rows, "acorde_autores_pendentes.csv")


@api.get("/discover/stats")
async def discover_stats(request: Request):
    user = await get_current_user(request)
    require_admin(user)
    pending_editoras = await db.editoras.count_documents({"needs_review": True})
    total_editoras = await db.editoras.count_documents({})
    pending_autores = await db.autores.count_documents({"needs_review": True})
    total_autores = await db.autores.count_documents({})
    return {
        "pending_editoras": pending_editoras,
        "total_editoras": total_editoras,
        "pending_autores": pending_autores,
        "total_autores": total_autores,
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
