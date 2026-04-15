from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.db import (
    count_assets,
    get_asset_by_codigo,
    get_conn,
    get_stats,
    init_db_if_missing,
    insert_new_asset,
    invalidate_caches,
    list_assets,
    mark_verified_by_codigo,
    update_assets_bulk,
)


EDITABLE_COLUMNS = [
    "responsable",
    "dependencia",
    "establecimiento",
    "estado",
    "en_uso",
    "tipo_control",
    "ocompra",
    "descripcion",
]

LISTADO_FILTER_DEFAULTS = {
    "show_only": "Todos",
    "query": "",
    "limit": 500,
    "offset": 0,
}

SCAN_STATE_DEFAULTS = {
    "scan_code_input": "",
    "scan_buffer_code": "",
    "scan_last_code": "",
    "scan_last_component_code": "",
    "scan_asset": None,
    "scan_not_found": False,
    "scan_component_version": 0,
    "scan_input_version": 0,
}

BASE_DIR = Path(__file__).parent
barcode_scanner = components.declare_component(
    "barcode_scanner",
    path=str(BASE_DIR / "components" / "barcode_scanner"),
)


st.set_page_config(
    page_title="Inventario con Escaner (Code128)",
    layout="wide",
)

init_db_if_missing()


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def render_asset_detail(asset: dict):
    st.subheader("Detalle del activo")

    c1, c2 = st.columns(2)

    with c1:
        st.write(f"**Codigo:** {asset.get('codigo')}")
        st.write(f"**Nombre del Bien:** {asset.get('nombre_bien', '')}")
        st.write(f"**Familia:** {asset.get('familia', '')}")
        st.write(f"**Responsable:** {asset.get('responsable', '')}")

    with c2:
        st.write(f"**Establecimiento:** {asset.get('establecimiento', '')}")
        st.write(f"**Verificado:** {'Si' if asset.get('verificado') else 'No'}")
        st.write(f"**Fecha verificacion:** {asset.get('fecha_verificacion', '')}")
        st.write(f"**Nuevo:** {'Si' if asset.get('nuevo') else 'No'}")

    with st.expander("Ver registro completo"):
        st.json(asset)


def style_rows(df: pd.DataFrame):
    def color_row(row):
        if int(row.get("nuevo", 0)) == 1:
            return ["background-color: #fff3cd"] * len(row)
        if int(row.get("verificado", 0)) == 1:
            return ["background-color: #d4edda"] * len(row)
        return ["background-color: #f8d7da"] * len(row)

    return df.style.apply(color_row, axis=1)


def get_listado_filter() -> dict:
    filtro = st.session_state.get("listado_filter")
    if not filtro:
        filtro = LISTADO_FILTER_DEFAULTS.copy()
        st.session_state["listado_filter"] = filtro
    return filtro


def ensure_scan_state():
    for key, value in SCAN_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_scan_result(code: str, asset: dict | None):
    st.session_state["scan_buffer_code"] = code
    st.session_state["scan_last_code"] = code
    st.session_state["scan_asset"] = asset
    st.session_state["scan_not_found"] = asset is None and bool(code)


def clear_scan_result(clear_input: bool = False):
    st.session_state["scan_buffer_code"] = ""
    st.session_state["scan_last_code"] = ""
    st.session_state["scan_last_component_code"] = ""
    st.session_state["scan_asset"] = None
    st.session_state["scan_not_found"] = False
    if clear_input:
        st.session_state["scan_input_version"] += 1
        st.session_state["scan_component_version"] += 1


def sync_scan_input_to_buffer(input_key: str):
    code = normalize_code(st.session_state.get(input_key, ""))
    if code:
        st.session_state["scan_buffer_code"] = code


def restart_scanner():
    clear_scan_result(clear_input=True)


def values_equal(old_value, new_value) -> bool:
    if isinstance(old_value, pd.Series):
        old_value = old_value.iloc[0] if not old_value.empty else None
    if isinstance(new_value, pd.Series):
        new_value = new_value.iloc[0] if not new_value.empty else None

    old_is_na = pd.isna(old_value)
    new_is_na = pd.isna(new_value)

    if isinstance(old_is_na, (pd.Series, list, tuple)):
        old_is_na = bool(pd.Series(old_is_na).all())
    if isinstance(new_is_na, (pd.Series, list, tuple)):
        new_is_na = bool(pd.Series(new_is_na).all())

    if old_is_na and new_is_na:
        return True
    return old_value == new_value


def collect_asset_changes(
    original_df: pd.DataFrame,
    edited_df: pd.DataFrame,
    editable_cols: list[str],
) -> list[dict]:
    if original_df.empty or edited_df.empty:
        return []

    changes = []
    df_idx = original_df.drop_duplicates(subset=["codigo"], keep="first").set_index("codigo")
    ed_idx = edited_df.drop_duplicates(subset=["codigo"], keep="first").set_index("codigo")

    for codigo in ed_idx.index.intersection(df_idx.index):
        item = {"codigo": codigo}

        for col in editable_cols:
            if col not in ed_idx.columns or col not in df_idx.columns:
                continue

            old_value = df_idx.at[codigo, col]
            new_value = ed_idx.at[codigo, col]
            if values_equal(old_value, new_value):
                continue

            item[col] = None if pd.isna(new_value) else new_value

        if len(item) > 1:
            changes.append(item)

    return changes


def render_listado_page():
    st.title("Listado de activos")

    filtro_actual = get_listado_filter()
    opciones_estado = ["Todos", "Solo nuevos", "Solo verificados", "Solo no verificados"]

    with st.form("filtros_listado"):
        col1, col2, col3, col4 = st.columns([1, 1, 2, 1])

        with col1:
            filtro_estado = st.selectbox(
                "Mostrar",
                opciones_estado,
                index=opciones_estado.index(filtro_actual["show_only"]),
            )

        with col2:
            limite = st.number_input(
                "Max registros",
                min_value=50,
                max_value=20000,
                value=int(filtro_actual["limit"]),
                step=50,
            )

        with col3:
            busqueda = st.text_input(
                "Buscar por codigo o nombre",
                value=filtro_actual["query"],
            )

        with col4:
            st.write("")
            aplicar = st.form_submit_button("Aplicar filtros", type="primary")
            recargar = st.form_submit_button("Recargar")

    if aplicar or recargar:
        st.session_state["listado_filter"] = {
            "show_only": filtro_estado,
            "query": busqueda.strip(),
            "limit": int(limite),
            "offset": 0,
        }
        if recargar:
            invalidate_caches()

    filtro = get_listado_filter()
    total_filtrado = count_assets(filtro)
    limite_actual = int(filtro["limit"])
    total_paginas = max(1, (total_filtrado + limite_actual - 1) // limite_actual)
    pagina_actual = min(
        total_paginas,
        (int(filtro.get("offset", 0)) // limite_actual) + 1,
    )

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("Anterior", disabled=(pagina_actual <= 1), use_container_width=True):
            st.session_state["listado_filter"]["offset"] = max(0, (pagina_actual - 2) * limite_actual)
            st.rerun()
    with nav2:
        selected_page = st.number_input(
            "Pagina",
            min_value=1,
            max_value=total_paginas,
            value=pagina_actual,
            step=1,
        )
        if selected_page != pagina_actual:
            st.session_state["listado_filter"]["offset"] = (int(selected_page) - 1) * limite_actual
            st.rerun()
    with nav3:
        if st.button("Siguiente", disabled=(pagina_actual >= total_paginas), use_container_width=True):
            st.session_state["listado_filter"]["offset"] = pagina_actual * limite_actual
            st.rerun()

    filtro = get_listado_filter()
    df = list_assets(filtro)
    inicio = int(filtro.get("offset", 0)) + 1 if total_filtrado else 0
    fin = min(int(filtro.get("offset", 0)) + len(df), total_filtrado)

    m1, m2, m3 = st.columns(3)
    m1.metric("Registros mostrados", len(df))
    m2.metric("Nuevos en vista", int(df["nuevo"].sum()) if "nuevo" in df.columns else 0)
    m3.metric("Verificados en vista", int(df["verificado"].sum()) if "verificado" in df.columns else 0)
    st.caption(f"Mostrando {inicio}-{fin} de {total_filtrado} registros filtrados.")

    st.caption("Edita las columnas habilitadas y luego presiona Guardar cambios.")

    missing = [c for c in EDITABLE_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"Faltan columnas necesarias para editar el listado: {missing}")
        st.stop()

    if df.empty:
        st.info("No hay activos para los filtros seleccionados.")
        return

    edited_df = st.data_editor(
        df,
        width="stretch",
        height=550,
        hide_index=True,
        disabled=[c for c in df.columns if c not in (["codigo"] + EDITABLE_COLUMNS)],
        column_config={
            "codigo": st.column_config.TextColumn("Codigo", disabled=True),
            "verificado": st.column_config.NumberColumn("Verificado", disabled=True),
            "nuevo": st.column_config.NumberColumn("Nuevo", disabled=True),
        },
        key="editor_listado",
    )

    changes = collect_asset_changes(df, edited_df, EDITABLE_COLUMNS)
    st.caption(f"Cambios pendientes: {len(changes)} fila(s)")

    if st.button("Guardar cambios", type="primary", disabled=(len(changes) == 0)):
        updated_rows = update_assets_bulk(changes)
        invalidate_caches()
        st.success(f"Cambios guardados. Filas actualizadas: {updated_rows}")
        st.rerun()

    st.caption("Amarillo = Nuevo | Verde = Verificado | Rojo = No verificado")
    st.dataframe(style_rows(edited_df), width="stretch", height=350)


def render_dashboard_page():
    st.title("Dashboard")

    stats = get_stats()
    c1, c2, c3 = st.columns(3)

    c1.metric("Total activos", stats["total"])
    c2.metric("Verificados", stats["verificados"])
    c3.metric("Nuevos", stats["nuevos"])


def render_import_page():
    st.title("Importar Excel a Supabase")

    file = st.file_uploader("Sube tu Excel .xlsx", type=["xlsx"])
    sheet = st.text_input("Nombre de hoja (opcional)", value="BD AREA SALUD")

    if file and st.button("Importar"):
        workbook = pd.ExcelFile(file)
        available_sheets = workbook.sheet_names
        requested_sheet = sheet.strip() if sheet else ""

        if requested_sheet:
            selected_sheet = next(
                (name for name in available_sheets if name.strip().casefold() == requested_sheet.casefold()),
                None,
            )
        else:
            selected_sheet = None

        if selected_sheet is None:
            selected_sheet = available_sheets[0]
            if requested_sheet:
                st.warning(
                    "La hoja solicitada no existe en el archivo. "
                    f"Se usara '{selected_sheet}'. Hojas disponibles: {', '.join(available_sheets)}"
                )
            else:
                st.info(f"Se usara la primera hoja disponible: '{selected_sheet}'.")

        df = workbook.parse(sheet_name=selected_sheet)

        if "Codigo" not in df.columns:
            st.error("No existe la columna 'Codigo' en el Excel.")
            st.stop()

        column_map = {
            "Codigo": "codigo",
            "Nombre del Bien": "nombre_bien",
            "Familia": "familia",
            "Responsable": "responsable",
            "Dependencia": "dependencia",
            "Establecimiento": "establecimiento",
            "Estado": "estado",
            "En Uso": "en_uso",
            "OCompra": "ocompra",
            "Descripcion": "descripcion",
            "TIPO DE CONTROL": "tipo_control",
            "Tipo Control": "tipo_control",
        }

        existing_columns = {source: target for source, target in column_map.items() if source in df.columns}
        df = df[list(existing_columns.keys())].rename(columns=existing_columns)

        df["codigo"] = df["codigo"].astype(str).str.strip().str.upper()
        df = df.dropna(subset=["codigo"]).drop_duplicates(subset=["codigo"])

        text_columns = [
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
        ]
        for column in text_columns:
            if column in df.columns:
                df[column] = df[column].where(df[column].notna(), None)

        rows = list(
            df.reindex(
                columns=[
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
                ]
            ).itertuples(index=False, name=None)
        )

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.executemany(
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
                        %s, FALSE, FALSE, NOW()
                    )
                    ON CONFLICT (codigo) DO UPDATE SET
                        nombre_bien = EXCLUDED.nombre_bien,
                        familia = EXCLUDED.familia,
                        responsable = EXCLUDED.responsable,
                        dependencia = EXCLUDED.dependencia,
                        establecimiento = EXCLUDED.establecimiento,
                        estado = EXCLUDED.estado,
                        en_uso = EXCLUDED.en_uso,
                        tipo_control = EXCLUDED.tipo_control,
                        ocompra = EXCLUDED.ocompra,
                        descripcion = EXCLUDED.descripcion
                    """,
                    rows,
                )
            conn.commit()
        finally:
            conn.close()

        st.success(f"Importacion OK. Registros procesados: {len(rows)}")
        invalidate_caches()


def render_scan_page():
    st.title("Escanear / Ingresar activo")
    st.info("Puedes escanear el codigo con la camara o ingresarlo manualmente.")

    ensure_scan_state()

    input_key = f"scan_code_input_{st.session_state['scan_input_version']}"
    codigo_input = st.text_input(
        "Codigo del activo",
        value=st.session_state.get("scan_buffer_code", ""),
        placeholder="Ej: SLD-001002",
        key=input_key,
        on_change=sync_scan_input_to_buffer,
        args=(input_key,),
    )

    scanner_version = st.session_state["scan_component_version"]
    scanned_value = barcode_scanner(
        key=f"barcode_scanner_{scanner_version}",
        default="",
        height=520,
    )
    scanned_code = normalize_code(scanned_value)
    if (
        scanned_code
        and scanned_code != st.session_state.get("scan_last_component_code", "")
    ):
        st.session_state["scan_buffer_code"] = scanned_code
        st.session_state["scan_last_component_code"] = scanned_code
        st.session_state["scan_input_version"] += 1
        st.rerun()

    codigo = normalize_code(codigo_input)
    if codigo:
        st.session_state["scan_buffer_code"] = codigo

    action1, action2, action3 = st.columns([2, 1, 1])
    with action1:
        buscar = st.button("Buscar activo", type="primary", use_container_width=True)
    with action2:
        limpiar = st.button("Limpiar", use_container_width=True)
    with action3:
        escanear_nuevamente = st.button("Escanear nuevamente", use_container_width=True)

    if limpiar:
        clear_scan_result(clear_input=True)
        st.rerun()

    if escanear_nuevamente:
        restart_scanner()
        st.rerun()

    if buscar:
        search_code = codigo or normalize_code(st.session_state.get("scan_buffer_code", ""))

        if not search_code:
            st.warning("Ingresa o escanea un codigo antes de buscar.")
        else:
            asset = get_asset_by_codigo(search_code)
            set_scan_result(search_code, asset)

    current_code = st.session_state.get("scan_last_code", "")
    current_asset = st.session_state.get("scan_asset")
    not_found = st.session_state.get("scan_not_found", False)

    if current_asset:
        st.success(f"Activo encontrado: {current_code}")
        render_asset_detail(current_asset)

        with st.form("verificar_activo_form"):
            decision = st.radio(
                "Estado de verificacion",
                ["Marcar como verificado", "Dejar sin cambios"],
                horizontal=True,
            )
            submit_verificacion = st.form_submit_button("Confirmar accion")

        if submit_verificacion:
            if decision == "Marcar como verificado":
                mark_verified_by_codigo(current_code)
                invalidate_caches()
                refreshed_asset = get_asset_by_codigo(current_code)
                set_scan_result(current_code, refreshed_asset)
                st.success("Activo verificado correctamente.")
                st.rerun()
            else:
                st.info("No se realizaron cambios en el activo.")

    elif not_found and current_code:
        st.warning(f"El codigo {current_code} no existe en la base de datos.")

        with st.form("nuevo_activo"):
            st.subheader("Registrar nuevo activo")

            st.text_input("Codigo", value=current_code, disabled=True)
            nombre = st.text_input("Nombre del Bien")
            familia = st.text_input("Familia")
            responsable = st.text_input("Responsable")
            dependencia = st.text_input("Dependencia")
            establecimiento = st.text_input("Establecimiento")
            estado = st.text_input("Estado")
            en_uso = st.text_input("En uso")
            tipo_control = st.text_input("Tipo control")
            ocompra = st.text_input("OCompra")
            descripcion = st.text_area("Descripcion")

            guardar = st.form_submit_button("Guardar nuevo activo")

            if guardar:
                insert_new_asset(
                    {
                        "codigo": current_code,
                        "nombre_bien": nombre,
                        "familia": familia,
                        "responsable": responsable,
                        "dependencia": dependencia,
                        "establecimiento": establecimiento,
                        "estado": estado,
                        "en_uso": en_uso,
                        "tipo_control": tipo_control,
                        "ocompra": ocompra,
                        "descripcion": descripcion,
                    }
                )
                invalidate_caches()
                refreshed_asset = get_asset_by_codigo(current_code)
                set_scan_result(current_code, refreshed_asset)
                st.success("Nuevo activo agregado correctamente.")
                st.rerun()


st.sidebar.title("Inventario")
page = st.sidebar.radio("Menu", ["Escanear", "Listado", "Dashboard", "Importar Excel"])

if page == "Dashboard":
    render_dashboard_page()
elif page == "Listado":
    render_listado_page()
elif page == "Importar Excel":
    render_import_page()
else:
    render_scan_page()
