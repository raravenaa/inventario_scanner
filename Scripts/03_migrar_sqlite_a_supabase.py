import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

from datetime import datetime

def parse_date_to_iso(s):
    """Convierte 'DD-MM-YYYY' o 'DD/MM/YYYY' a 'YYYY-MM-DD'. Si falla, retorna None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None

    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass

    # Si viene con hora (por si acaso)
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            pass

    return None

SQLITE_PATH = "db/inventario.db"
#PG_URL = os.environ["postgresql://postgres.leuoyctpmdzjsfflgweh:[Gand156638919?.]@aws-1-us-east-1.pooler.supabase.com:5432/postgres"]  # pega aquí el URL de Supabase
PG_URL = os.environ["PG_URL"]
def main():
    sconn = sqlite3.connect(SQLITE_PATH)
    sconn.row_factory = sqlite3.Row

    rows = sconn.execute("""
        SELECT 
            UPPER(TRIM(codigo)) as codigo,
            nombre_bien,
            subfamilia,
            familia ,
            denominacion,
            cuenta_contable,
            marca,
            modelo,
            serie,
            descripcion,
            origen,
            responsable,
            dependencia,
            establecimiento,
            unidad,
            fecha,
            estado,
            valor_sin_iva,
            valor_con_iva,
            ocompra,
            en_uso,
            tipo_control,
            COALESCE(verificado, 0) as verificado,
            fecha_verificacion,
            verificado_por,
            COALESCE(es_nuevo, 0) as nuevo
        FROM assets
    """).fetchall()

    print("SQLite rows:", len(rows))
    if not rows:
        return

    pconn = psycopg2.connect(
        host="aws-1-us-east-1.pooler.supabase.com",
        port=6543,
        dbname="postgres",
        user="postgres.leuoyctpmdzjsfflgweh",
        password="Anubis156638919",
        sslmode="require",
    )

    values = []
    for r in rows:
        values.append((
            r["codigo"],
            r["nombre_bien"],
            r["subfamilia"],
            r["familia"],
            r["denominacion"],
            r["cuenta_contable"],
            r["marca"],
            r["modelo"],
            r["serie"],
            r["descripcion"],
            r["origen"],
            r["responsable"],
            r["dependencia"],
            r["establecimiento"],
            r["unidad"],
            parse_date_to_iso(r["fecha"]),
            r["estado"],
            r["valor_sin_iva"],
            r["valor_con_iva"],
            r["ocompra"],
            r["en_uso"],
            r["tipo_control"],
            bool(r["verificado"]),
            parse_date_to_iso(r["fecha_verificacion"]),
            r["verificado_por"],
            bool(r["nuevo"])
        ))

    sql = """
      insert into public.assets
      (codigo, nombre_bien,subfamilia, familia, denominacion, cuenta_contable, marca, modelo, serie,descripcion,origen, responsable, 
        dependencia,establecimiento,unidad,fecha,estado,valor_sin_iva,valor_con_iva,ocompra,en_uso, tipo_control,verificado, fecha_verificacion,verificado_por, nuevo)
      values %s
      on conflict (codigo) do update set
        nombre_bien = excluded.nombre_bien,
        subfamilia = excluded.subfamilia,
        familia = excluded.familia,
        denominacion = excluded.denominacion,
        cuenta_contable = excluded.cuenta_contable,
        marca = excluded.marca,
        modelo = excluded.modelo,
        serie = excluded.serie,
        descripcion = excluded.descripcion,
        origen = excluded.origen,
        responsable = excluded.responsable,
        dependencia = excluded.dependencia,
        establecimiento = excluded.establecimiento,
        unidad = excluded.unidad,
        fecha = excluded.fecha,
        estado = excluded.estado,
        valor_sin_iva = excluded.valor_sin_iva,
        valor_con_iva = excluded.valor_con_iva,
        ocompra = excluded.ocompra,
        en_uso = excluded.en_uso,
        tipo_control = excluded.tipo_control,
        verificado = excluded.verificado,
        fecha_verificacion = excluded.fecha_verificacion,
        verificado_por = excluded.verificado_por,
        nuevo = excluded.nuevo
    """
    pcur = pconn.cursor()  #

    execute_values(pcur, sql, values, page_size=1000)
    pconn.commit()

    pcur.close()
    pconn.close()
    sconn.close()
    print("Migración OK")

if __name__ == "__main__":
    main()
