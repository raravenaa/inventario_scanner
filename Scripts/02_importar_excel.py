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

    # Fast import: one transaction
    rows = [tuple(df.iloc[i][c] for c in cols) for i in range(len(df))]
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
