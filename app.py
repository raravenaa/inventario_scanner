import streamlit as st
import pandas as pd

from src.db import (
    init_db_if_missing,
    get_asset_by_codigo,
    mark_verified_by_codigo,
    insert_new_asset,
    list_assets,
    get_stats,
    invalidate_caches,
)

import os
import streamlit.components.v1 as components

COMPONENT_PATH = os.path.join(
    os.path.dirname(__file__),
    "components",
    "barcode_scanner"
)

barcode_scanner = components.declare_component(
    "barcode_scanner",
    path=COMPONENT_PATH
)
# --- Barcode scanner component (camera, Code128 via ZXing in browser) ---
import streamlit.components.v1 as components


barcode_scanner = components.declare_component(
    "barcode_scanner",
    path="components/barcode_scanner"
)

st.write("Cargando componente...")
codigo = barcode_scanner(key="test")
st.write("Código recibido:", codigo)

# ---------------- UI helpers ----------------
def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def render_asset_detail(asset: dict):
    # Show key fields first (extend as you like)
    st.subheader("Detalle del activo")
    cols = st.columns(2)
    with cols[0]:
        st.write(f"**Código:** {asset.get('codigo')}")
        st.write(f"**Nombre del Bien:** {asset.get('nombre_bien') or ''}")
        st.write(f"**Familia:** {asset.get('familia') or ''}")
    with cols[1]:
        st.write(f"**Responsable:** {asset.get('responsable') or ''}")
        st.write(f"**Establecimiento:** {asset.get('establecimiento') or ''}")
        st.write(f"**Verificado:** {'Sí' if asset.get('verificado') else 'No'}")
        st.write(f"**Fecha verificación:** {asset.get('fecha_verificacion') or ''}")

    with st.expander("Ver registro completo"):
        st.json(asset)


def style_rows(df: pd.DataFrame):
    # Colors:
    # nuevo=1 -> yellow
    # verificado=1 -> green
    # else -> light red
    def row_style(row):
        if int(row.get("nuevo", 0) or 0) == 1:
            return ["background-color: #fff7cc"] * len(row)
        if int(row.get("verificado", 0) or 0) == 1:
            return ["background-color: #d4f8d4"] * len(row)
        return ["background-color: #ffd6d6"] * len(row)

    return df.style.apply(row_style, axis=1)


# ---------------- App ----------------
st.set_page_config(page_title="Inventario Scanner (Code128)", layout="wide")
init_db_if_missing()

st.title("📦 Inventario con Escáner (Code128) — Streamlit + SQLite")

with st.sidebar:
    st.header("Navegación")
    page = st.radio("Ir a:", ["Escanear", "Listado", "Dashboard", "Importar (guía)"])
    st.divider()
    st.caption("Tip: en móvil, abre en Chrome/Safari. Da permisos de cámara.")

if page == "Dashboard":
    stats = get_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total activos", stats["total"])
    c2.metric("Verificados", stats["verificados"])
    c3.metric("Nuevos", stats["nuevos"])
    st.info("Si haces cambios (verificar/agregar), el dashboard se actualiza automáticamente.")

elif page == "Listado":
    st.subheader("Listado de activos")
    colf = st.columns([1, 1, 1, 2])
    with colf[0]:
        show_only = st.selectbox("Mostrar", ["Todos", "Solo nuevos", "Solo verificados", "Solo no verificados"])
    with colf[1]:
        limit = st.number_input("Máx filas", min_value=50, max_value=20000, value=2000, step=50)
    with colf[2]:
        refresh = st.button("🔄 Refrescar")
    with colf[3]:
        q = st.text_input("Buscar por código o nombre", value="")

    if refresh:
        invalidate_caches()

    filtro = {"show_only": show_only, "query": q, "limit": int(limit)}
    df = list_assets(filtro)

    st.caption("Colores: 🟡 Nuevo | 🟢 Verificado | 🔴 No verificado")
    st.dataframe(style_rows(df), use_container_width=True, height=520)

elif page == "Importar (guía)":
    st.subheader("Guía rápida de importación Excel → SQLite")
    st.markdown(
        """
1) Coloca tu Excel en la raíz del repo (o en `data/`)  
2) Ejecuta:

```bash
python scripts/01_crear_db.py
python scripts/02_importar_excel.py --excel "TU_ARCHIVO.xlsx"
```

3) Luego corre la app:

```bash
streamlit run app.py
```

> Para Streamlit Cloud: sube el repo a GitHub y despliega.
        """
    )
    st.warning(
        "Nota: en Streamlit Community Cloud, SQLite puede resetearse en redeploy. "
        "Para persistencia fuerte, migra a Postgres/Supabase."
    )

else:  # Escanear
    st.subheader("📷 Escanear código (Code128)")

    # Component returns the scanned text (string) or None
    codigo_raw = barcode_scanner(key="scanner")

    # Also allow manual fallback (useful for testing)
    st.caption("Fallback: puedes ingresar manualmente si lo necesitas.")
    manual = st.text_input("Código manual", value="", placeholder="Ej: SLD-001000")

    codigo = normalize_code(codigo_raw or manual)

    if codigo:
        st.write(f"**Código leído:** `{codigo}`")
        asset = get_asset_by_codigo(codigo)

        if asset:
            st.success("✅ Activo encontrado en base de datos")
            render_asset_detail(asset)

            if st.button("✅ Marcar como verificado", type="primary"):
                mark_verified_by_codigo(codigo)
                invalidate_caches()
                st.success("Verificación registrada")
                st.rerun()
        else:
            st.warning("⚠️ Código NO existe en la base. Puedes agregarlo como nuevo activo.")

            with st.form("form_nuevo"):
                st.write("### Agregar nuevo activo")
                codigo_form = st.text_input("Código", value=codigo, disabled=True)
                nombre = st.text_input("Nombre del Bien", value="")
                familia = st.text_input("Familia", value="")
                responsable = st.text_input("Responsable", value="")
                establecimiento = st.text_input("Establecimiento", value="")

                submitted = st.form_submit_button("💾 Guardar nuevo activo")
                if submitted:
                    insert_new_asset(
                        {
                            "codigo": codigo_form,
                            "nombre_bien": nombre,
                            "familia": familia,
                            "responsable": responsable,
                            "establecimiento": establecimiento,
                        }
                    )
                    invalidate_caches()
                    st.success("Nuevo activo agregado (marcado como NUEVO)")
                    st.rerun()

    else:
        st.info("Apunta la cámara al código Code128. Cuando se lea, aparecerá aquí.")
