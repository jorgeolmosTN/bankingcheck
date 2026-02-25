import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(page_title="ICBC Card Analyzer", layout="wide", page_icon="💳")

# Estilo para las métricas (los "cuadraditos")
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 22px; border-radius: 10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

def extraer_datos_icbc(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # 1. EXTRACCIÓN DE CABECERA (Fechas y Titular)
    def buscar(patron, texto):
        m = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else "No encontrado"

    datos = {
        "titular": "JORGE EDUARDO OLMOS",
        "cierre": buscar(r"CIERRE ACTUAL:\n\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "vencimiento": buscar(r"VENCIMIENTO ACTUAL:\n\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "saldo_ant_pesos": buscar(r"SALDO ANTERIOR\s+([\d\.,]+)\s+[\d\.,]+", texto_completo),
        "saldo_ant_dolares": buscar(r"SALDO ANTERIOR\s+[\d\.,]+\s+([\d\.,]+)", texto_completo),
    }

    # 2. SUMATORIA DE PAGOS
    pagos_raw = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)-", texto_completo)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos_raw])

    # 3. SEGMENTACIÓN POR TARJETA (2448 y 6600)
    # Dividimos el texto por las líneas de "TOTAL TARJETA"
    bloques = re.split(r"(TOTAL TARJETA XXXX XXXX XXXX \d{4})", texto_completo)
    
    dict_tarjetas = {}
    # Recorremos los bloques: el bloque i es el contenido, el i-1 es el nombre de la tarjeta
    for i in range(1, len(bloques), 2):
        nombre_tarjeta = bloques[i].replace("TOTAL TARJETA XXXX XXXX XXXX ", "")
        contenido = bloques[i-1] # El contenido está ANTES de la línea de TOTAL
        
        # Extraer movimientos del bloque
        patron_mov = r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\s\.\*\/]+?)\s+(?:C\.(\d{2}/\d{2}))?\s+([\d\.,]+)(?!\-)"
        matches = re.findall(patron_mov, contenido)
        
        movs = []
        for m in matches:
            if "FECHA" in m[1]: continue
            movs.append({
                "Fecha": m[0],
                "Detalle": m[1].strip(),
                "Cuota": m[2] if m[2] else "01/01",
                "Monto": float(m[3].replace('.', '').replace(',', '.'))
            })
        
        if movs:
            dict_tarjetas[nombre_tarjeta] = pd.DataFrame(movs)

    return datos, total_pagos, dict_tarjetas

# --- INTERFAZ ---
st.title("💳 Analizador de Tarjeta ICBC")

archivo = st.file_uploader("Sube el PDF de tu resumen", type="pdf")

if archivo:
    datos, total_pagos, tarjetas = extraer_datos_icbc(archivo)

    # --- SIDEBAR (IZQUIERDA) ---
    with st.sidebar:
        st.header("📌 Información General")
        st.info(f"**Titular:** {datos['titular']}")
        st.write(f"📅 **Cierre:** {datos['cierre']}")
        st.write(f"📅 **Vencimiento:** {datos['vencimiento']}")
        
        st.divider()
        st.subheader("Saldos Anteriores")
        st.metric("Saldo Anterior ($)", f"$ {datos['saldo_ant_pesos']}")
        st.metric("Saldo Anterior (u$s)", f"u$s {datos['saldo_ant_dolares']}")
        
        st.divider()
        st.subheader("Pagos")
        st.metric("SU PAGO EN PESOS", f"$ {total_pagos:,.2f}", delta="Recibido")

    # --- CUERPO PRINCIPAL ---
    if tarjetas:
        st.subheader("📋 Detalle de Consumos por Tarjeta")
        
        # Creamos las pestañas dinámicamente según las tarjetas encontradas
        tabs = st.tabs([f"Tarjeta terminada en {n}" for n in tarjetas.keys()])
        
        for idx, (num_tarjeta, df) in enumerate(tarjetas.items()):
            with tabs[idx]:
                st.write(f"### Movimientos Tarjeta XXXX-{num_tarjeta}")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Resumen de esta tarjeta
                total_t = df["Monto"].sum()
                st.metric(f"Total Tarjeta {num_tarjeta}", f"$ {total_t:,.2f}")
                
                # Botón de descarga para ESTA tarjeta
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    label=f"📥 Descargar Excel Tarjeta {num_tarjeta}",
                    data=buf.getvalue(),
                    file_name=f"Gastos_Tarjeta_{num_tarjeta}.xlsx",
                    key=num_tarjeta # Clave única para evitar conflictos
                )
    else:
        st.warning("No se pudieron separar los gastos por tarjeta. Verifica el formato del PDF.")
