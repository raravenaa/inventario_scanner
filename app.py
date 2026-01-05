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
page = st.sidebar.radio("Menú", ["Escanear", "Listado", "Dashboard", "Importar Excel"])


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
# IMPORTAR (OJO: tu bloque actual es SQLite)
# --------------------------------------------------
elif page == "Importar Excel":
    st.title("📥 Importar Excel a SQLite (Cloud)")

    file = st.file_uploader("Sube tu Excel .xlsx", type=["xlsx"])
    sheet = st.text_input("Nombre de hoja (opcional)", value="BD AREA SALUD")

    if file and st.button("Importar"):
        import pandas as pd
        from src.db import get_conn, init_db_if_missing

        init_db_if_missing()
        df = pd.read_excel(file, sheet_name=sheet if sheet else None)

        if "Codigo" not in df.columns:
            st.error("No existe la columna 'Codigo' en el Excel.")
            st.stop()

        df["Codigo"] = df["Codigo"].astype(str).str.strip().str.upper()
        df = df.dropna(subset=["Codigo"]).drop_duplicates(subset=["Codigo"])

        conn = get_conn()
        rows = []
        for _, r in df.iterrows():
            rows.append((r["Codigo"], r.get("Nombre del Bien", None), r.get("Familia", None)))

        conn.executemany(
            "INSERT OR IGNORE INTO assets (codigo, nombre_bien, familia, verificado, nuevo, creado_en) "
            "VALUES (?, ?, ?, 0, 0, datetime('now'))",
            rows
        )
        conn.commit()

        st.success(f"Importación OK. Registros procesados: {len(rows)}")
        invalidate_caches()

# --------------------------------------------------
# ESCANEAR (CÁMARA + AUTO BÚSQUEDA + VERIFICAR)
# --------------------------------------------------
else:
    st.title("📷 Escanear / Ingresar activo")

    st.info("Escanea el código con la cámara o ingrésalo manualmente. Al detectar un código, se buscará automáticamente.")

    # Estado base
    if "codigo" not in st.session_state:
        st.session_state.codigo = ""
    if "last_codigo" not in st.session_state:
        st.session_state.last_codigo = ""

    # Input manual (fuente de verdad)
    codigo_input = st.text_input(
        "Código del activo",
        placeholder="Ej: SLD-001002",
        value=st.session_state.last_codigo,
        key="codigo_input",
    )
    st.session_state.codigo = codigo_input

    # Script: asignar id fijo al input por label (robusto en móvil)
    components.html(
        """
        <script>
        function ensureInputId() {
          const labels = Array.from(window.parent.document.querySelectorAll('label'));
          const target = labels.find(l => (l.innerText || '').trim() === 'Código del activo');
          if (!target) return false;

          const container = target.closest('div');
          if (!container) return false;

          const input = container.querySelector('input');
          if (!input) return false;

          input.id = 'codigo_activo_input';
          return true;
        }

        let tries = 0;
        const timer = setInterval(() => {
          tries++;
          const ok = ensureInputId();
          if (ok || tries > 30) clearInterval(timer);
        }, 200);
        </script>
        """,
        height=0,
    )

    # Escáner HTML (escribe en input por ID)
    html_scanner = """
    <script src="https://unpkg.com/html5-qrcode"></script>

    <div id="reader" style="width:100%;"></div>

    <script>
    const html5QrCode = new Html5Qrcode("reader");

    html5QrCode.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 300, height: 150 } },
      (decodedText) => {
        const input = window.parent.document.getElementById('codigo_activo_input');
        if (input) {
          input.value = decodedText;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        html5QrCode.stop();
      },
      () => {}
    );
    </script>
    """
    components.html(html_scanner, height=420)

    # Normalizar código
    codigo = normalize_code(st.session_state.codigo)

    # Botones
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🔄 Limpiar código"):
            st.session_state.codigo = ""
            st.session_state.last_codigo = ""
            st.rerun()

    with c2:
        buscar_manual = st.button("🔍 Buscar ahora")

    # Buscar solo cuando cambie el código o sea manual
    codigo_cambio = bool(codigo) and (codigo != st.session_state.last_codigo)

    if buscar_manual or codigo_cambio:
        if codigo:
            st.session_state.last_codigo = codigo

            asset = get_asset_by_codigo(codigo)

            if asset:
                render_asset_detail(asset)

                if st.button("✅ Marcar como verificado", type="primary"):
                    mark_verified_by_codigo(codigo)
                    invalidate_caches()
                    st.success("Activo verificado correctamente")
                    st.session_state.codigo = ""
                    st.session_state.last_codigo = ""
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
                        st.session_state.codigo = ""
                        st.session_state.last_codigo = ""
                        st.rerun()
