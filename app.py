import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(page_title="Analizador ICBC", layout="wide")

def extraer_datos_icbc(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # --- 1. EXTRACCIÓN DE CABECERA (SIDEBAR) ---
    def buscar(patron, texto):
        match = re.search(patron, texto, re.IGNORECASE)
        return match.group(1).strip() if match else "No encontrado"

    # Basado en tu PDF del ICBC
    datos = {
        "cierre": buscar(r"CIERRE ACTUAL:\s*(\d{2}/\d{2}/\d{4})", texto_completo),
        "vencimiento": buscar(r"VENCIMIENTO ACTUAL:\s*(\d{2}/\d{2}/\d{4})", texto_completo),
        "titular": buscar(r"TIT\. DE CUENTA:\s*([A-Z\s]+)", texto_completo),
        "saldo_ant_pesos": buscar(r"SALDO ANTERIOR\s+([\d\.,]+)\s+[\d\.,]+\s*$", texto_completo), # Ajustado a tu tabla
    }

    # Sumatoria de pagos (Patrón: "SU PAGO EN PESOS ... 3990000,00-")
    pagos_encontrados = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)-", texto_completo)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos_encontrados])

    # --- 2. EXTRACCIÓN DE TRANSACCIONES ---
    # Patrón para: Fecha | Detalle | Cuota (opcional) | Monto
    # Ejemplo: "24/07/25 Nike Argentina SRL C.07/09 21333,14"
    patron_mov = r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\s\.\*]+?)\s+(?:C\.(\d{2}/\d{2}))?\s+([\d\.,]+)(?!\-)"
    matches = re.findall(patron_mov, texto_completo)
    
    movimientos = []
    for m in matches:
        movimientos.append({
            "Fecha": m[0],
            "Detalle": m[1].strip(),
            "Cuota": m[2] if m[2] else "1/1",
            "Monto ($)": float(m[3].replace('.', '').replace(',', '.'))
        })
    
    return datos, total_pagos, pd.DataFrame(movimientos)

# --- INTERFAZ ---
st.title("💳 Analizador de Tarjeta ICBC")

archivo = st.file_uploader("Sube el PDF de tu resumen ICBC", type="pdf")

if archivo:
    datos, total_pagos, df_movs = extraer_datos_icbc(archivo)

    # SIDEBAR
    with st.sidebar:
        st.header("Información del Resumen")
        st.write(f"**Titular:** {datos['titular']}")
        st.write(f"**Cierre:** {datos['cierre']}")
        st.write(f"**Vencimiento:** {datos['vencimiento']}")
        st.divider()
        st.metric("Total Pagos Realizados", f"${total_pagos:,.2f}")

    # CUERPO
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Consumos Identificados")
        st.dataframe(df_movs, use_container_width=True)
    
    with col2:
        st.subheader("💰 Resumen de Gastos")
        total_consumos = df_movs["Monto ($)"].sum()
        st.metric("Total de esta lista", f"${total_consumos:,.2f}")
        
        # Botón Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_movs.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel",
            data=output.getvalue(),
            file_name="gastos_icbc.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

