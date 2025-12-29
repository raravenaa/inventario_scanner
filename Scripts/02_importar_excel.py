import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pandas as pd

DB_PATH = Path("db") / "inventario.db"


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_code(x):
    if pd.isna(x):
        return None
    return str(x).strip().upper()


def main(excel_path: str, sheet: str | None = None):
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No existe {DB_PATH}. Ejecuta scripts/01_crear_db.py primero.")

    df = pd.read_excel(excel_path, sheet_name=sheet)  # requires openpyxl installed

    # Map expected columns from Excel to DB columns.
    # Ajusta nombres según tu Excel real.
    # Aquí usamos algunos campos comunes y el resto queda opcional.
    colmap = {
        "Codigo": "codigo",
        "Codigo CAS-CHILE": "codigo_cas",
        "Nombre del Bien": "nombre_bien",
        "Subfamilia": "subfamilia",
        "Familia": "familia",
        "Denominación": "denominacion",
        "Cuenta Contable": "cuenta_contable",
        "Marca": "marca",
        "Modelo": "modelo",
        "Serie": "serie",
        "Descripcion": "descripcion",
        "Origen": "origen",
        "Responsable": "responsable",
        "Dependencia": "dependencia",
        "Establecimiento": "establecimiento",
        "Unidad": "unidad",
        "Fecha": "fecha",
        "Estado": "estado",
        " Valor sin iva ": "valor_sin_iva",
        " Valor con iva ": "valor_con_iva",
        "OCompra": "ocompra",
        "En Uso": "en_uso",
        "TIPO DE CONTROL": "tipo_control",
        "VIDA UTIL EN AÑOS S/CGR": "vida_util_anios",
        "VIDA UTIL EN MESES": "vida_util_meses",
        "VIDA UTIL SEGÚN CRITERIO CGR EN MESES": "vida_util_cgr_meses",
        "VIDA UTIL INSUMIDA EN MESES": "vida_util_insumida_meses",
        "VIDA UTIL RETANTE EN MESES": "vida_util_restante_meses",
        "DEPRECIACION MENSUAL": "depreciacion_mensual",
        "DEPRECIACION ACUMULADA ": "depreciacion_acumulada",
        "VALOR LIBRO": "valor_libro",
    }

    # Keep only columns that exist
    existing = {k: v for k, v in colmap.items() if k in df.columns}
    if "Codigo" not in existing:
        raise ValueError("No encontré la columna 'Codigo' en el Excel.")

    df = df[list(existing.keys())].rename(columns=existing)

    # --- Forzar columnas problemáticas a TEXTO para evitar overflow ---
    to_text = [
        "codigo", "codigo_cas", "serie", "ocompra", "modelo", "marca",
        "responsable", "dependencia", "establecimiento", "unidad", "estado",
        "tipo_control"
    ]
    for c in to_text:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("").str.strip()

    # --- Asegurar código normalizado ---
    df["codigo"] = df["codigo"].apply(normalize_code)

    # Normalize
    df["codigo"] = df["codigo"].apply(normalize_code)
    df = df.dropna(subset=["codigo"]).drop_duplicates(subset=["codigo"])

    # Default flags
    df["verificado"] = 0
    df["fecha_verificacion"] = None
    df["nuevo"] = 0
    df["creado_en"] = utc_iso_now()

    cols = list(df.columns)
    placeholders = ",".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO assets ({','.join(cols)}) VALUES ({placeholders})"

    conn = sqlite3.connect(DB_PATH.as_posix())
    cur = conn.cursor()

    # --- Filtrar columnas según esquema real de la tabla assets ---
    cur.execute("PRAGMA table_info(assets)")
    db_cols = {row[1] for row in cur.fetchall()}

    keep_cols = [c for c in df.columns if c in db_cols]
    if "codigo" not in keep_cols:
        raise ValueError("La tabla assets debe tener la columna 'codigo'.")

    df = df[keep_cols]

    cols = keep_cols
    placeholders = ",".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO assets ({','.join(cols)}) VALUES ({placeholders})"

    for c in df.columns:
        if pd.api.types.is_integer_dtype(df[c]):
            # si hay valores > 9e18, convertir a string
            if df[c].max(skipna=True) > 9_000_000_000_000_000_000:
                df[c] = df[c].astype("Int64").astype("string")

    # Fast import: one transaction
    rows = list(df[cols].itertuples(index=False, name=None))
    cur.executemany(insert_sql, rows)
    conn.commit()

    print(f"OK: importados/ignorados (por duplicado) {cur.rowcount} registros desde {excel_path}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", required=True, help="Ruta al Excel .xlsx")
    parser.add_argument("--sheet", default=None, help="Nombre de la hoja (opcional)")
    args = parser.parse_args()
    main(args.excel, args.sheet)
