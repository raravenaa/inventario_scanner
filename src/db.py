from __future__ import annotations

import pandas as pd
import psycopg2
import streamlit as st
from psycopg2.extras import RealDictCursor


LIST_ASSET_COLUMNS = [
    "codigo",
    "nombre_bien",
    "familia",
    "responsable",
    "dependencia",
    "establecimiento",
    "estado",
    "en_uso",
    "tipo_control",
    "ocompra",
    "descripcion",
    "verificado",
    "fecha_verificacion",
    "nuevo",
]


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _get_pg_config() -> dict:
    required = ["PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD", "PG_SSLMODE"]
    missing = [key for key in required if key not in st.secrets]
    if missing:
        raise RuntimeError(f"Faltan secrets: {missing}. Configuralos en Streamlit Cloud > Secrets.")

    return {
        "host": st.secrets["PG_HOST"],
        "port": int(st.secrets["PG_PORT"]),
        "dbname": st.secrets["PG_DB"],
        "user": st.secrets["PG_USER"],
        "password": st.secrets["PG_PASSWORD"],
        "sslmode": st.secrets["PG_SSLMODE"],
    }


def get_conn():
    """
    Crea una conexion nueva por operacion para evitar snapshots viejos
    o conexiones persistentes desalineadas con la base remota.
    """
    return psycopg2.connect(
        **_get_pg_config(),
    )


def init_db_if_missing():
    return


def invalidate_caches():
    get_stats.clear()
    get_dashboard_data.clear()
    count_assets.clear()
    list_assets.clear()


def build_assets_where(filtro: dict) -> tuple[str, list]:
    show_only = filtro.get("show_only", "Todos")
    query = (filtro.get("query") or "").strip()

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
    return where_sql, params


@st.cache_data(show_spinner=False, ttl=5)
def get_stats() -> dict:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE COALESCE(verificado, FALSE)) AS verificados,
                    COUNT(*) FILTER (WHERE NOT COALESCE(verificado, FALSE)) AS pendientes,
                    COUNT(*) FILTER (WHERE COALESCE(nuevo, FALSE)) AS nuevos,
                    COUNT(*) FILTER (
                        WHERE COALESCE(nuevo, FALSE)
                          AND NOT COALESCE(verificado, FALSE)
                    ) AS nuevos_pendientes,
                    COUNT(*) FILTER (
                        WHERE fecha_verificacion = (NOW() AT TIME ZONE 'America/Santiago')::date
                    ) AS verificados_hoy,
                    COUNT(*) FILTER (
                        WHERE fecha_verificacion >= (NOW() AT TIME ZONE 'America/Santiago')::date - INTERVAL '7 days'
                    ) AS verificados_7d
                FROM public.assets
                """
            )
            row = cur.fetchone()
        return dict(row)
    finally:
        conn.close()


@st.cache_data(show_spinner=False, ttl=10)
def get_dashboard_data() -> dict[str, pd.DataFrame | dict]:
    conn = get_conn()
    try:
        stats = get_stats()

        verification_df = pd.DataFrame(
            [
                {"categoria": "Verificados", "cantidad": int(stats.get("verificados") or 0)},
                {"categoria": "Pendientes", "cantidad": int(stats.get("pendientes") or 0)},
            ]
        )
        origin_df = pd.DataFrame(
            [
                {"categoria": "Activos existentes", "cantidad": int((stats.get("total") or 0) - (stats.get("nuevos") or 0))},
                {"categoria": "Nuevos", "cantidad": int(stats.get("nuevos") or 0)},
            ]
        )

        by_establecimiento = pd.read_sql_query(
            """
            SELECT
                COALESCE(NULLIF(TRIM(establecimiento), ''), 'Sin establecimiento') AS establecimiento,
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE COALESCE(verificado, FALSE))::int AS verificados,
                COUNT(*) FILTER (WHERE NOT COALESCE(verificado, FALSE))::int AS pendientes,
                COUNT(*) FILTER (WHERE COALESCE(nuevo, FALSE))::int AS nuevos
            FROM public.assets
            GROUP BY 1
            ORDER BY total DESC, establecimiento ASC
            LIMIT 15
            """,
            conn,
        )

        by_estado = pd.read_sql_query(
            """
            SELECT
                COALESCE(NULLIF(TRIM(estado), ''), 'Sin estado') AS estado,
                COUNT(*)::int AS total
            FROM public.assets
            GROUP BY 1
            ORDER BY total DESC, estado ASC
            LIMIT 12
            """,
            conn,
        )

        daily_verified = pd.read_sql_query(
            """
            SELECT
                fecha_verificacion::date AS fecha,
                COUNT(*)::int AS verificados
            FROM public.assets
            WHERE fecha_verificacion IS NOT NULL
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT 30
            """,
            conn,
        ).sort_values("fecha")

        return {
            "stats": stats,
            "verification": verification_df,
            "origin": origin_df,
            "by_establecimiento": by_establecimiento,
            "by_estado": by_estado,
            "daily_verified": daily_verified,
        }
    finally:
        conn.close()


@st.cache_data(show_spinner=False, ttl=10)
def count_assets(filtro: dict) -> int:
    conn = get_conn()
    try:
        where_sql, params = build_assets_where(filtro)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM public.assets{where_sql}", params)
            return cur.fetchone()["c"]
    finally:
        conn.close()


def get_asset_by_codigo(codigo: str) -> dict | None:
    conn = get_conn()
    try:
        codigo = normalize_code(codigo)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.assets WHERE codigo = %s", (codigo,))
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def mark_verified_by_codigo(codigo: str, verificado_por: str | None = None):
    conn = get_conn()
    try:
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
    finally:
        conn.close()


def insert_new_asset(data: dict):
    conn = get_conn()
    try:
        codigo = normalize_code(data.get("codigo", ""))
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.assets
                (
                    codigo, nombre_bien, familia, responsable, dependencia,
                    establecimiento, estado, en_uso, tipo_control, ocompra,
                    descripcion, verificado, nuevo, creado_en
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, FALSE, TRUE, NOW()
                )
                ON CONFLICT (codigo) DO NOTHING
                """,
                (
                    codigo,
                    data.get("nombre_bien"),
                    data.get("familia"),
                    data.get("responsable"),
                    data.get("dependencia"),
                    data.get("establecimiento"),
                    data.get("estado"),
                    data.get("en_uso"),
                    data.get("tipo_control"),
                    data.get("ocompra"),
                    data.get("descripcion"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


@st.cache_data(show_spinner=False, ttl=10)
def list_assets(filtro: dict) -> pd.DataFrame:
    conn = get_conn()
    try:
        limit = max(50, min(int(filtro.get("limit") or 500), 20000))
        offset = max(0, int(filtro.get("offset") or 0))
        where_sql, params = build_assets_where(filtro)
        select_sql = ", ".join(LIST_ASSET_COLUMNS)

        sql = f"""
            SELECT {select_sql}
            FROM public.assets
            {where_sql}
            ORDER BY nuevo DESC, verificado DESC, codigo ASC
            LIMIT %s
            OFFSET %s
        """
        params.extend([limit, offset])

        df = pd.read_sql_query(sql, conn, params=params)

        for column in LIST_ASSET_COLUMNS:
            if column not in df.columns:
                df[column] = None

        if "verificado" in df.columns:
            df["verificado"] = df["verificado"].fillna(False).astype(bool).astype(int)
        if "nuevo" in df.columns:
            df["nuevo"] = df["nuevo"].fillna(False).astype(bool).astype(int)

        return df[LIST_ASSET_COLUMNS]
    finally:
        conn.close()


def update_assets_bulk(changes: list[dict]) -> int:
    if not changes:
        return 0

    allowed = {
        "nombre_bien",
        "subfamilia",
        "familia",
        "denominacion",
        "cuenta_contable",
        "marca",
        "modelo",
        "serie",
        "descripcion",
        "origen",
        "responsable",
        "dependencia",
        "establecimiento",
        "unidad",
        "estado",
        "en_uso",
        "tipo_control",
        "ocompra",
    }

    conn = get_conn()
    try:
        updated = 0
        with conn.cursor() as cur:
            for item in changes:
                codigo = normalize_code(item.get("codigo", ""))
                if not codigo:
                    continue

                sets = []
                params = []
                for key, value in item.items():
                    if key in allowed:
                        sets.append(f"{key} = %s")
                        params.append(value)

                if not sets:
                    continue

                params.append(codigo)
                cur.execute(
                    f"UPDATE public.assets SET {', '.join(sets)} WHERE codigo = %s",
                    params,
                )
                updated += cur.rowcount

        conn.commit()
        return updated
    finally:
        conn.close()
