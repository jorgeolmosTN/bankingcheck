import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(page_title="ICBC Pro Analyzer", layout="wide", page_icon="💳")

# Estilos para que las tablas y métricas se vean impecables
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 20px; }
    .main .block-container { padding-top: 2rem; }
    th { background-color: #f0f2f6 !important; }
    </style>
    """, unsafe_allow_html=True)

def extraer_datos_completos(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # 1. BUSCADOR DE CABECERA
    def buscar(patron, texto):
        m = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else "0,00"

    datos = {
        "titular": "JORGE EDUARDO OLMOS",
        "cierre": buscar(r"CIERRE ACTUAL:\n\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "vencimiento": buscar(r"VENCIMIENTO ACTUAL:\n\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "saldo_ant_pesos": buscar(r"SALDO ANTERIOR\s+([\d\.,]+)\s+[\d\.,]+", texto_completo),
        "saldo_ant_dolares": buscar(r"SALDO ANTERIOR\s+[\d\.,]+\s+([\d\.,]+)", texto_completo),
    }

    # 2. PAGOS Y SEGMENTACIÓN
    pagos_raw = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)-", texto_completo)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos_raw])

    # 3. EXTRACCIÓN POR TARJETAS E IMPUESTOS
    bloques = re.split(r"(TOTAL TARJETA XXXX XXXX XXXX \d{4})", texto_completo)
    
    dict_tarjetas = {}
    texto_impuestos = texto_completo # Por defecto buscamos en todo, pero refinaremos
    
    for i in range(1, len(bloques), 2):
        id_tarjeta = bloques[i].split()[-1] # Toma los últimos 4 dígitos
        contenido = bloques[i-1]
        
        # Regex para TODOS los consumos (Fecha | Detalle | Cuota Opcional | Monto)
        # Filtra para que no agarre los que terminan en "-" (pagos)
        patron_todo = r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\s\.\*\/]+?)\s+(?:C\.(\d{2}/\d{2}))?\s+([\d\.,]+)(?!\-)"
        matches = re.findall(patron_todo, contenido)
        
        movs = []
        for m in matches:
            if any(x in m[1] for x in ["IVA", "IMP.", "PERCEP", "RETEN", "SELLOS"]): continue
            movs.append({
                "Fecha": m[0],
                "Detalle": m[1].strip(),
                "Cuota": m[2] if m[2] else "Un solo pago",
                "Monto": float(m[3].replace('.', '').replace(',', '.'))
            })
        if movs: dict_tarjetas[id_tarjeta] = pd.DataFrame(movs)

    # 4. EXTRACCIÓN DE IMPUESTOS
    # Buscamos términos fiscales después de la última tarjeta
    patron_impuestos = r"(\d{2}/\d{2}/\d{2})\s+(IVA|IMP|PERCEP|RG\s\d+|SELLOS|LEY|TASA).*?\s+([\d\.,]+)"
    imp_matches = re.findall(patron_impuestos, texto_completo, re.IGNORECASE)
    
    lista_imp = []
    for im in imp_matches:
        lista_imp.append({
            "Fecha": im[0],
            "Concepto": im[1].strip() + " " + "Fiscal",
            "Monto": float(im[2].replace('.', '').replace(',', '.'))
        })
    df_impuestos = pd.DataFrame(lista_imp).drop_duplicates()

    return datos, total_pagos, dict_tarjetas, df_impuestos

# --- INTERFAZ ---
st.title("💳 Dashboard Financiero ICBC")

archivo = st.file_uploader("Sube tu resumen PDF", type="pdf")

if archivo:
    datos, total_p, tarjetas, df_imp = extraer_datos_completos(archivo)

    # SIDEBAR
    with st.sidebar:
        st.header("👤 Titular")
        st.write(datos['titular'])
        st.divider()
        st.metric("Saldo Anterior $", f"$ {datos['saldo_ant_pesos']}")
        st.metric("Saldo Anterior u$s", f"u$s {datos['saldo_ant_dolares']}")
        st.divider()
        st.metric("PAGOS RECIBIDOS", f"$ {total_p:,.2f}")

    # CUERPO PRINCIPAL - 3 COLUMNAS
    st.subheader(f"Resumen al {datos['cierre']} - Vencimiento: {datos['vencimiento']}")
    
    col1, col2, col3 = st.columns(3)

    # Columna 1: Tarjeta Principal
    with col1:
        id1 = list(tarjetas.keys())[0] if tarjetas else "N/A"
        st.markdown(f"### 💳 Tarjeta ...{id1}")
        if id1 in tarjetas:
            st.dataframe(tarjetas[id1], hide_index=True, use_container_width=True)
            st.metric("Subtotal", f"$ {tarjetas[id1]['Monto'].sum():,.2f}")

    # Columna 2: Tarjeta Adicional
    with col2:
        id2 = list(tarjetas.keys())[1] if len(tarjetas) > 1 else None
        if id2:
            st.markdown(f"### 💳 Tarjeta ...{id2}")
            st.dataframe(tarjetas[id2], hide_index=True, use_container_width=True)
            st.metric("Subtotal", f"$ {tarjetas[id2]['Monto'].sum():,.2f}")
        else:
            st.info("No se detectó segunda tarjeta.")

    # Columna 3: Impuestos
    with col3:
        st.markdown("### 🏦 Impuestos y Tasas")
        if not df_imp.empty:
            st.dataframe(df_imp, hide_index=True, use_container_width=True)
            st.metric("Total Impuestos", f"$ {df_imp['Monto'].sum():,.2f}", delta_color="inverse")
        else:
            st.write("No se detectaron impuestos desglosados.")

    # Botón Global de Excel
    st.divider()
    if st.button("🚀 Preparar descarga consolidada"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            for k, v in tarjetas.items():
                v.to_excel(writer, sheet_name=f"Tarjeta_{k}", index=False)
            df_imp.to_excel(writer, sheet_name="Impuestos", index=False)
        
        st.download_button("📥 Descargar Excel con todas las pestañas", buf.getvalue(), "Resumen_Completo.xlsx")

else:
    st.info("Esperando PDF para procesar las 3 tablas en paralelo...")
