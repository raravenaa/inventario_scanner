from pathlib import Path
import sqlite3

DB_PATH = Path("db") / "inventario.db"


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.as_posix())
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
    conn.close()
    print(f"OK: DB creada/verificada en {DB_PATH}")


if __name__ == "__main__":
    main()
