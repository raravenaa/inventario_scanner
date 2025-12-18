import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

from src.db import (
    init_db_if_missing,
    get_asset_by_codigo,
    mark_verified_by_codigo,
    insert_new_asset,
    list_assets,
    get_stats,
    invalidate_caches,
)

# --------------------------------------------------
# CONFIGURACIÓN GENERAL
# --------------------------------------------------
st.set_page_config(
    page_title="Inventario con Escáner (Code128)",
    layout="wide"
)

init_db_if_missing()

# --------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------
def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def render_asset_detail(asset: dict):
    st.subheader("📋 Detalle del activo")

    c1, c2 = st.columns(2)

    with c1:
        st.write(f"**Código:** {asset.get('codigo')}")
        st.write(f"**Nombre del Bien:** {asset.get('nombre_bien', '')}")
        st.write(f"**Familia:** {asset.get('familia', '')}")
        st.write(f"**Responsable:** {asset.get('responsable', '')}")

    with c2:
        st.write(f"**Establecimiento:** {asset.get('establecimiento', '')}")
        st.write(f"**Verificado:** {'Sí' if asset.get('verificado') else 'No'}")
        st.write(f"**Fecha verificación:** {asset.get('fecha_verificacion', '')}")
        st.write(f"**Nuevo:** {'Sí' if asset.get('nuevo') else 'No'}")

    with st.expander("Ver registro completo"):
        st.json(asset)


def style_rows(df: pd.DataFrame):
    def color_row(row):
        if int(row.get("nuevo", 0)) == 1:
            return ["background-color: #fff3cd"] * len(row)   # Amarillo
        if int(row.get("verificado", 0)) == 1:
            return ["background-color: #d4edda"] * len(row)   # Verde
        return ["background-color: #f8d7da"] * len(row)       # Rojo

    return df.style.apply(color_row, axis=1)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
st.sidebar.title("📦 Inventario")
page = st.sidebar.radio(
    "Menú",
    ["Escanear", "Listado", "Dashboard"]
)

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------
if page == "Dashboard":
    st.title("📊 Dashboard")

    stats = get_stats()
    c1, c2, c3 = st.columns(3)

    c1.metric("Total activos", stats["total"])
    c2.metric("Verificados", stats["verificados"])
    c3.metric("Nuevos", stats["nuevos"])

# --------------------------------------------------
# LISTADO
# --------------------------------------------------
elif page == "Listado":
    st.title("📄 Listado de activos")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        filtro_estado = st.selectbox(
            "Mostrar",
            ["Todos", "Solo nuevos", "Solo verificados", "Solo no verificados"]
        )

    with col2:
        limite = st.number_input(
            "Máx registros",
            min_value=50,
            max_value=20000,
            value=2000,
            step=50
        )

    with col3:
        busqueda = st.text_input("Buscar por código o nombre")

    filtro = {
        "show_only": filtro_estado,
        "query": busqueda,
        "limit": int(limite)
    }

    df = list_assets(filtro)

    st.caption("🟡 Nuevo | 🟢 Verificado | 🔴 No verificado")
    st.dataframe(style_rows(df), width="stretch", height=550)

# --------------------------------------------------
# ESCANEAR (CÁMARA REAL EN CELULAR)
# --------------------------------------------------
else:
    st.title("📷 Escanear activo (Code128)")

    st.info(
        "Apunta la cámara al código de barras. "
        "La cámara trasera se abrirá automáticamente."
    )

    # --- HTML + JS ESTABLE PARA MÓVIL ---
    html_scanner = """
    <script src="https://unpkg.com/html5-qrcode"></script>

    <div id="reader" style="width:100%;"></div>

    <script>
    const html5QrCode = new Html5Qrcode("reader");

    html5QrCode.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 300, height: 150 } },
      (decodedText, decodedResult) => {
        window.parent.postMessage(
          { type: "barcode", value: decodedText },
          "*"
        );
        html5QrCode.stop();
      },
      (errorMessage) => {}
    );
    </script>
    """

    if "barcode" not in st.session_state:
        st.session_state.barcode = None

    # Listener para mensajes desde el iframe
    st.markdown("""
    <script>
    window.addEventListener("message", (event) => {
      if (event.data?.type === "barcode") {
        window.streamlitWebSocket.send(
          JSON.stringify({
            type: "streamlit:setSessionState",
            key: "barcode",
            value: event.data.value
          })
        );
      }
    });
    </script>
    """, unsafe_allow_html=True)

    codigo = st.session_state.barcode
    codigo = normalize_code(codigo)

    if codigo:
        st.success(f"✅ Código leído: {codigo}")

        asset = get_asset_by_codigo(codigo)

        if asset:
            render_asset_detail(asset)

            if st.button("✅ Marcar como verificado", type="primary"):
                mark_verified_by_codigo(codigo)
                invalidate_caches()
                st.success("Activo verificado correctamente")
                st.rerun()

        else:
            st.warning("⚠️ Código NO existe en la base de datos")

            with st.form("nuevo_activo"):
                st.subheader("➕ Agregar nuevo activo")

                st.text_input("Código", value=codigo, disabled=True)
                nombre = st.text_input("Nombre del Bien")
                familia = st.text_input("Familia")
                responsable = st.text_input("Responsable")
                establecimiento = st.text_input("Establecimiento")

                guardar = st.form_submit_button("💾 Guardar")

                if guardar:
                    insert_new_asset({
                        "codigo": codigo,
                        "nombre_bien": nombre,
                        "familia": familia,
                        "responsable": responsable,
                        "establecimiento": establecimiento
                    })
                    invalidate_caches()
                    st.success("Nuevo activo agregado correctamente")
                    st.rerun()
