from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _get_pg_config() -> dict:
    """
    Lee secretos Opción B desde st.secrets.
    Debes tener:
      PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, PG_SSLMODE
    """
    required = ["PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD", "PG_SSLMODE"]
    missing = [k for k in required if k not in st.secrets]
    if missing:
        raise RuntimeError(f"Faltan secrets: {missing}. Configúralos en Streamlit Cloud > Secrets.")

    return {
        "host": st.secrets["PG_HOST"],
        "port": int(st.secrets["PG_PORT"]),
        "dbname": st.secrets["PG_DB"],
        "user": st.secrets["PG_USER"],
        "password": st.secrets["PG_PASSWORD"],
        "sslmode": st.secrets["PG_SSLMODE"],
    }


@st.cache_resource
def get_conn():
    """
    Conexión única (cache_resource) para la sesión del proceso Streamlit.
    """
    cfg = _get_pg_config()
    conn = psycopg2.connect(**cfg, cursor_factory=RealDictCursor)
    conn.autocommit = False
    return conn


def init_db_if_missing():
    """
    En Supabase ya tienes la tabla creada. Dejamos esto como no-op.
    Si quieres, podríamos verificar existencia, pero no es necesario.
    """
    return


def invalidate_caches():
    # Clears cached list/stats; connection stays cached
    get_stats.clear()
    list_assets.clear()


@st.cache_data(show_spinner=False, ttl=5)
def get_stats() -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM public.assets")
        total = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM public.assets WHERE verificado = TRUE")
        verificados = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM public.assets WHERE nuevo = TRUE")
        nuevos = cur.fetchone()["c"]

    return {"total": total, "verificados": verificados, "nuevos": nuevos}


def get_asset_by_codigo(codigo: str) -> dict | None:
    conn = get_conn()
    codigo = normalize_code(codigo)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM public.assets WHERE codigo = %s", (codigo,))
        row = cur.fetchone()
    return dict(row) if row else None


def mark_verified_by_codigo(codigo: str, verificado_por: str | None = None):
    """
    Marca como verificado con fecha_verificacion = CURRENT_DATE y nuevo = FALSE.
    verificado_por es opcional (si luego agregas login).
    """
    conn = get_conn()
    codigo = normalize_code(codigo)

    with conn.cursor() as cur:
        if verificado_por:
            cur.execute(
                """
                UPDATE public.assets
                SET verificado = TRUE,
                    fecha_verificacion = CURRENT_DATE,
                    nuevo = FALSE,
                    verificado_por = %s
                WHERE codigo = %s
                """,
                (verificado_por, codigo),
            )
        else:
            cur.execute(
                """
                UPDATE public.assets
                SET verificado = TRUE,
                    fecha_verificacion = CURRENT_DATE,
                    nuevo = FALSE
                WHERE codigo = %s
                """,
                (codigo,),
            )
    conn.commit()


def insert_new_asset(data: dict):
    """
    Inserción mínima para activos nuevos.
    En tu esquema: fecha es DATE (puede quedar NULL), creado_en se setea con NOW().
    """
    conn = get_conn()
    codigo = normalize_code(data.get("codigo", ""))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.assets
            (codigo, nombre_bien, familia, responsable, establecimiento, verificado, nuevo, creado_en)
            VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, NOW())
            ON CONFLICT (codigo) DO NOTHING
            """,
            (
                codigo,
                data.get("nombre_bien"),
                data.get("familia"),
                data.get("responsable"),
                data.get("establecimiento"),
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
    params: list = []

    if show_only == "Solo nuevos":
        where.append("nuevo = TRUE")
    elif show_only == "Solo verificados":
        where.append("verificado = TRUE")
    elif show_only == "Solo no verificados":
        where.append("verificado = FALSE")

    if query:
        where.append("(codigo ILIKE %s OR nombre_bien ILIKE %s)")
        q = f"%{query}%"
        params.extend([q, q])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT codigo, nombre_bien, familia, responsable, establecimiento,
               verificado, fecha_verificacion, nuevo
        FROM public.assets
        {where_sql}
        ORDER BY nuevo DESC, verificado DESC, codigo ASC
        LIMIT %s
    """
    params.append(limit)

    df = pd.read_sql_query(sql, conn, params=params)

    # Para que tu style_rows siga funcionando sin tocar app.py:
    # convierte bool -> int (0/1)
    if "verificado" in df.columns:
        df["verificado"] = df["verificado"].fillna(False).astype(bool).astype(int)
    if "nuevo" in df.columns:
        df["nuevo"] = df["nuevo"].fillna(False).astype(bool).astype(int)

    return df
