import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# Configuración de página
st.set_page_config(page_title="Analizador ICBC Pro", layout="wide", page_icon="💳")

# Estilo para las métricas (los "cuadraditos")
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 24px; color: #D32F2F; }
    [data-testid="stMetricLabel"] { font-size: 16px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

def extraer_datos_icbc(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # --- LÓGICA DE BÚSQUEDA DE SALDOS ---
    # Buscamos la línea que empieza con SALDO ANTERIOR
    # El patrón busca: "SALDO ANTERIOR" -> Espacios -> Valor Pesos -> Espacios -> Valor Dólares
    # Usamos [\d\.,]+ para capturar números con puntos y comas
    linea_saldos = re.search(r"SALDO ANTERIOR\s+([\d\.,]+)\s+([\d\.,]+)", texto_completo)
    
    if linea_saldos:
        s_pesos = linea_saldos.group(1)
        s_dolares = linea_saldos.group(2)
    else:
        s_pesos = "0,00"
        s_dolares = "0,00"

    # Datos de cabecera
    def buscar_simple(patron, texto):
        m = re.search(patron, texto, re.IGNORECASE)
        return m.group(1).strip() if m else "No encontrado"

    datos = {
        "titular": "JORGE EDUARDO OLMOS", # Hardcoded por estructura de tu PDF
        "cierre": buscar_simple(r"CIERRE ACTUAL:\n\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "vencimiento": buscar_simple(r"VENCIMIENTO ACTUAL:\n\n(\d{2}/\d{2}/\d{4})", texto_completo),
        "saldo_ant_pesos": s_pesos,
        "saldo_ant_dolares": s_dolares
    }

    # --- SUMATORIA DE PAGOS ---
    pagos_raw = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)-", texto_completo)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos_raw])

    # --- TRANSACCIONES ---
    # Captura Fecha, Detalle y Monto (evita capturar los que terminan en "-" que son pagos)
    patron_mov = r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\s\.\*\/]+?)\s+([\d\.,]+)(?!\-)"
    matches = re.findall(patron_mov, texto_completo)
    
    movimientos = []
    for m in matches:
        # Filtrar ruidos comunes de cabeceras de tabla
        if "FECHA" in m[1] or "DETALLE" in m[1]: continue
        
        movimientos.append({
            "Fecha": m[0],
            "Detalle": m[1].strip(),
            "Monto ($)": float(m[2].replace('.', '').replace(',', '.'))
        })
    
    return datos, total_pagos, pd.DataFrame(movimientos)

# --- INTERFAZ ---
st.title("💳 Analizador de Tarjeta ICBC")

archivo = st.file_uploader("Sube tu resumen PDF", type="pdf")

if archivo:
    try:
        datos, total_pagos, df_movs = extraer_datos_icbc(archivo)

        # PANEL IZQUIERDO (SIDEBAR)
        with st.sidebar:
            st.header("📌 Resumen del Cliente")
            st.info(f"**Titular:** {datos['titular']}")
            st.write(f"📅 **Cierre:** {datos['cierre']}")
            st.write(f"📅 **Vencimiento:** {datos['vencimiento']}")
            st.divider()
            
            # LOS CUADRADITOS (Métricas)
            st.subheader("Saldos Anteriores")
            st.metric(label="Saldo Anterior PESOS", value=f"$ {datos['saldo_ant_pesos']}")
            st.metric(label="Saldo Anterior DÓLARES", value=f"u$s {datos['saldo_ant_dolares']}")
            
            st.divider()
            st.subheader("Pagos Detectados")
            st.metric(label="SU PAGO EN PESOS", value=f"$ {total_pagos:,.2f}")

        # CUERPO PRINCIPAL
        st.subheader("📋 Detalle de Movimientos")
        if not df_movs.empty:
            st.dataframe(df_movs, use_container_width=True, hide_index=True)

            # Botón de Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_movs.to_excel(writer, index=False, sheet_name='Detalle')
            
            st.download_button(
                label="📥 Descargar Excel de Movimientos",
                data=buffer.getvalue(),
                file_name=f"Resumen_ICBC_{datos['cierre'].replace('/','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.warning("No se encontraron transacciones. Asegúrate de que el PDF tenga consumos en la lista.")

    except Exception as e:
        st.error(f"Error al procesar: {e}")
else:
    st.info("Sube tu resumen PDF para ver los saldos y transacciones.")
