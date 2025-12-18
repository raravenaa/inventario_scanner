# Inventario Scanner (Code128) — Streamlit + SQLite

App de inventario orientada a **celulares**: escanea **Code128** con la cámara en el navegador, busca en SQLite y:
- si existe → permite marcar **Verificado + Fecha**
- si no existe → muestra formulario para **agregar nuevo** (marcado como `nuevo=1`)
- listado con colores (nuevo/verificado/no verificado)

## 1) Requisitos
- Python 3.10+
- (Local) PyCharm recomendado

## 2) Instalar
```bash
python -m venv .venv
# activar venv...
pip install -r requirements.txt
```

## 3) Crear DB
```bash
python scripts/01_crear_db.py
```

## 4) Importar Excel
Coloca tu archivo Excel y ejecuta:

```bash
python scripts/02_importar_excel.py --excel "TU_ARCHIVO.xlsx"
```

> Importa por `Codigo` (se normaliza a `strip().upper()`).
> Los registros importados quedan con `nuevo=0` y `verificado=0`.

## 5) Ejecutar app
```bash
streamlit run app.py
```

Abre desde el celular (misma red o url pública) y da permisos de cámara.

## 6) Despliegue en Streamlit Community Cloud
1. Sube este repo a GitHub
2. En https://share.streamlit.io/ elige repo y `app.py`

⚠️ Nota sobre SQLite en Cloud:
- Puede resetearse con redeploy. Si necesitas persistencia fuerte, migra a Postgres/Supabase.

## 7) Escáner (componente)
Se usa ZXing en el navegador para leer Code128 (y otros formatos). El escaneo ocurre **en el cliente**.
