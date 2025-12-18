import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

DB_PATH = Path("db") / "inventario.db"


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_if_missing():
    """Create tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            codigo_cas TEXT,
            nombre_bien TEXT,
            subfamilia TEXT,
            familia TEXT,
            denominacion TEXT,
            cuenta_contable TEXT,
            marca TEXT,
            modelo TEXT,
            serie TEXT,
            descripcion TEXT,
            origen TEXT,
            responsable TEXT,
            dependencia TEXT,
            establecimiento TEXT,
            unidad TEXT,
            fecha TEXT,
            estado TEXT,
            valor_sin_iva REAL,
            valor_con_iva REAL,
            ocompra TEXT,
            en_uso TEXT,
            tipo_control TEXT,
            vida_util_anios INTEGER,
            vida_util_meses INTEGER,
            vida_util_cgr_meses INTEGER,
            vida_util_insumida_meses INTEGER,
            vida_util_restante_meses INTEGER,
            depreciacion_mensual REAL,
            depreciacion_acumulada REAL,
            valor_libro REAL,

            verificado INTEGER DEFAULT 0,
            fecha_verificacion TEXT,
            nuevo INTEGER DEFAULT 0,
            creado_en TEXT
        );
        """
    )
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_codigo ON assets(codigo);")
    conn.commit()


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def invalidate_caches():
    # Clears cached list/stats; connection stays cached
    get_stats.clear()
    list_assets.clear()


@st.cache_data(show_spinner=False, ttl=5)
def get_stats() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    verificados = cur.execute("SELECT COUNT(*) FROM assets WHERE verificado=1").fetchone()[0]
    nuevos = cur.execute("SELECT COUNT(*) FROM assets WHERE nuevo=1").fetchone()[0]
    return {"total": total, "verificados": verificados, "nuevos": nuevos}


def get_asset_by_codigo(codigo: str) -> dict | None:
    conn = get_conn()
    codigo = normalize_code(codigo)
    row = conn.execute("SELECT * FROM assets WHERE codigo = ?", (codigo,)).fetchone()
    return dict(row) if row else None


def mark_verified_by_codigo(codigo: str):
    conn = get_conn()
    codigo = normalize_code(codigo)
    conn.execute(
        """
        UPDATE assets
        SET verificado = 1,
            fecha_verificacion = ?,
            nuevo = 0
        WHERE codigo = ?
        """,
        (_utc_iso_now(), codigo),
    )
    conn.commit()


def insert_new_asset(data: dict):
    conn = get_conn()
    codigo = normalize_code(data.get("codigo", ""))

    # Minimal insert; expand as needed
    conn.execute(
        """
        INSERT INTO assets (codigo, nombre_bien, familia, responsable, establecimiento, verificado, nuevo, creado_en)
        VALUES (?, ?, ?, ?, ?, 0, 1, ?)
        """,
        (
            codigo,
            data.get("nombre_bien"),
            data.get("familia"),
            data.get("responsable"),
            data.get("establecimiento"),
            _utc_iso_now(),
        ),
    )
    conn.commit()


@st.cache_data(show_spinner=False, ttl=10)
def list_assets(filtro: dict) -> pd.DataFrame:
    conn = get_conn()
    show_only = filtro.get("show_only", "Todos")
    query = (filtro.get("query") or "").strip()
    limit = int(filtro.get("limit") or 2000)

    where = []
    params = []

    if show_only == "Solo nuevos":
        where.append("nuevo=1")
    elif show_only == "Solo verificados":
        where.append("verificado=1")
    elif show_only == "Solo no verificados":
        where.append("verificado=0")

    if query:
        where.append("(codigo LIKE ? OR nombre_bien LIKE ?)")
        q = f"%{query}%"
        params.extend([q, q])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT codigo, nombre_bien, familia, responsable, establecimiento,
               verificado, fecha_verificacion, nuevo
        FROM assets
        {where_sql}
        ORDER BY nuevo DESC, verificado DESC, codigo ASC
        LIMIT ?
    """
    params.append(limit)

    df = pd.read_sql_query(sql, conn, params=params)

    # Ensure numeric
    if "verificado" in df.columns:
        df["verificado"] = df["verificado"].fillna(0).astype(int)
    if "nuevo" in df.columns:
        df["nuevo"] = df["nuevo"].fillna(0).astype(int)

    return df
