import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(page_title="Analizador ICBC Pro", layout="wide", page_icon="💳")

# Estilo para las métricas y el diseño de tablas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 20px; color: #1E3A8A; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    h3 { margin-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

def procesar_resumen_icbc(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # --- 1. DATOS DE CABECERA ---
    def buscar_dato(patron, texto):
        m = re.search(patron, texto, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else "0,00"

    # Captura de Saldos Anteriores (Pesos y Dólares)
    # Buscamos la línea de SALDO ANTERIOR y tomamos los dos montos
    match_saldos = re.search(r"SALDO ANTERIOR\s+([\d\.,]+)\s+([\d\.,]+)", texto_completo)
    s_pesos = match_saldos.group(1) if match_saldos else "0,00"
    s_dolares = match_saldos.group(2) if match_saldos else "0,00"

    cabecera = {
        "titular": "JORGE EDUARDO OLMOS",
        "cierre": buscar_dato(r"CIERRE ACTUAL:\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "vencimiento": buscar_dato(r"VENCIMIENTO ACTUAL:\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "saldo_ant_pesos": s_pesos,
        "saldo_ant_dolares": s_dolares
    }

    # --- 2. PAGOS ---
    pagos_raw = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)-", texto_completo)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos_raw])

    # --- 3. SEGMENTACIÓN POR TARJETAS E IMPUESTOS ---
    # Dividimos el texto por los totales de tarjeta
    patron_total = r"(TOTAL TARJETA XXXX XXXX XXXX \d{4})"
    partes = re.split(patron_total, texto_completo)
    
    tablas_tarjetas = {}
    ultimo_idx = 0
    
    # Recorremos los bloques encontrados
    for i in range(1, len(partes), 2):
        label_tarjeta = partes[i].split()[-1] # Los 4 dígitos finales
        bloque_gastos = partes[i-1] # Lo que está ANTES del total
        
        # Regex para capturar consumos (Fecha | Detalle | Monto)
        # Incluye letras, números, asteriscos, barras y espacios
        patron_item = r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\s\.\*\/%()-]+?)\s+([\d\.,]+)(?!\-)"
        items = re.findall(patron_item, bloque_gastos)
        
        df_temp = []
        for it in items:
            # Filtrar si es un impuesto o palabra de sistema
            if any(x in it[1] for x in ["IVA", "IIBB", "DB.RG", "PERCEP", "SELLOS", "FECHA"]): continue
            df_temp.append({
                "Fecha": it[0],
                "Detalle": it[1].strip(),
                "Monto ($)": float(it[2].replace('.', '').replace(',', '.'))
            })
        
        if df_temp:
            tablas_tarjetas[label_tarjeta] = pd.DataFrame(df_temp)
        ultimo_idx = i

    # --- 4. EXTRACCIÓN DE IMPUESTOS ---
    # Buscamos en el bloque que queda después de la última tarjeta
    resto_texto = partes[ultimo_idx + 1] if (ultimo_idx + 1) < len(partes) else texto_completo
    
    # Palabras clave de impuestos solicitadas
    keywords_imp = ["IIBB", "IVA RG", "DB.RG", "PERCEP", "SELLOS", "LEY", "TASA"]
    regex_imp = r"(\d{2}/\d{2}/\d{2})\s+(" + "|".join(keywords_imp) + r".*?)\s+([\d\.,]+)"
    
    imp_matches = re.findall(regex_imp, resto_texto, re.IGNORECASE)
    df_imp = []
    for im in imp_matches:
        df_imp.append({
            "Fecha": im[0],
            "Impuesto": im[1].strip(),
            "Monto ($)": float(im[2].replace('.', '').replace(',', '.'))
        })
    
    df_impuestos = pd.DataFrame(df_imp).drop_duplicates()

    return cabecera, total_pagos, tablas_tarjetas, df_impuestos

# --- INTERFAZ STREAMLIT ---
st.title("💳 Analizador de Gastos ICBC")

archivo = st.file_uploader("Sube tu resumen PDF", type="pdf")

if archivo:
    try:
        datos, pagos, tarjetas, impuestos = procesar_resumen_icbc(archivo)

        # SIDEBAR CON MÉTRICAS
        with st.sidebar:
            st.header("📌 Resumen General")
            st.info(f"**Titular:** {datos['titular']}")
            st.write(f"📅 Cierre: {datos['cierre']}")
            st.write(f"📅 Vto: {datos['vencimiento']}")
            st.divider()
            
            st.subheader("Saldos Anteriores")
            st.metric("Saldo Anterior ($)", f"$ {datos['saldo_ant_pesos']}")
            st.metric("Saldo Anterior (u$s)", f"u$s {datos['saldo_ant_dolares']}")
            
            st.divider()
            st.subheader("Pagos Realizados")
            st.metric("SU PAGO EN PESOS", f"$ {pagos:,.2f}", delta="Recibido")

        # CUERPO PRINCIPAL: 3 COLUMNAS EN PARALELO
        st.subheader(f"Desglose de la Liquidación - Cierre {datos['cierre']}")
        
        col1, col2, col3 = st.columns(3)

        # Columna 1: Tarjeta 2448
        with col1:
            id1 = "2448" # Puedes hacerlo dinámico con list(tarjetas.keys())[0]
            st.markdown(f"### 💳 Tarjeta ...{id1}")
            if id1 in tarjetas:
                st.dataframe(tarjetas[id1], use_container_width=True, hide_index=True)
                st.metric("Subtotal", f"$ {tarjetas[id1]['Monto ($)'].sum():,.2f}")
            else:
                st.warning(f"No se hallaron datos para {id1}")

        # Columna 2: Tarjeta 6600
        with col2:
            id2 = "6600"
            st.markdown(f"### 💳 Tarjeta ...{id2}")
            if id2 in tarjetas:
                st.dataframe(tarjetas[id2], use_container_width=True, hide_index=True)
                st.metric("Subtotal", f"$ {tarjetas[id2]['Monto ($)'].sum():,.2f}")
            else:
                st.warning(f"No se hallaron datos para {id2}")

        # Columna 3: Impuestos
        with col3:
            st.markdown("### 🏦 Impuestos y Tasas")
            if not impuestos.empty:
                st.dataframe(impuestos, use_container_width=True, hide_index=True)
                st.metric("Total Impuestos", f"$ {impuestos['Monto ($)'].sum():,.2f}")
            else:
                st.info("No se detectaron impuestos.")

        # BOTÓN DE EXCEL CONSOLIDADO
        st.divider()
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            for k, v in tarjetas.items():
                v.to_excel(writer, sheet_name=f"Tarjeta_{k}", index=False)
            impuestos.to_excel(writer, sheet_name="Impuestos", index=False)
        
        st.download_button(
            label="📥 Descargar Reporte Completo (Excel)",
            data=buf.getvalue(),
            file_name=f"Resumen_ICBC_{datos['cierre'].replace('/','-')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

