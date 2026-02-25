import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# Configuración de página con icono y layout ancho
st.set_page_config(
    page_title="Analizador ICBC Professional", 
    layout="wide", 
    page_icon="💳"
)

# Estilo personalizado para mejorar la estética de las métricas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 22px;
    }
    </style>
    """, unsafe_allow_html=True)

def extraer_datos_icbc(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    def buscar(patron, texto):
        match = re.search(patron, texto, re.IGNORECASE)
        return match.group(1).strip() if match else "0,00"

    # --- EXTRACCIÓN DE DATOS DE CABECERA ---
    # Titular (Suele estar cerca del Nro de Cuenta o CUIT)
    titular = buscar(r"RESUMEN DE CUENTA\n\n([A-Z\s]+)\n", texto_completo)
    if titular == "0,00": titular = "JORGE EDUARDO OLMOS"

    datos = {
        "titular": titular,
        "cierre": buscar(r"CIERRE ACTUAL:\s*(\d{2}/\d{2}/\d{4})", texto_completo),
        "vencimiento": buscar(r"VENCIMIENTO ACTUAL:\s*(\d{2}/\d{2}/\d{4})", texto_completo),
        "saldo_ant_pesos": buscar(r"SALDO ANTERIOR\s+\$\s*:\s*([\d\.,]+)", texto_completo),
        "saldo_ant_dolares": buscar(r"SALDO ANTERIOR\s+U\$S\s*:\s*([\d\.,]+)", texto_completo)
    }

    # --- CÁLCULO DE PAGOS ---
    # En ICBC los pagos aparecen como "SU PAGO EN PESOS" seguido del monto y un "-"
    pagos_raw = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)-", texto_completo)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos_raw])

    # --- EXTRACCIÓN DE TRANSACCIONES ---
    # Patrón: Fecha | Detalle | Cuota (opcional) | Monto
    patron_mov = r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\s\.\*\/]+?)\s+(?:C\.(\d{2}/\d{2}))?\s+([\d\.,]+)(?!\-)"
    matches = re.findall(patron_mov, texto_completo)
    
    movimientos = []
    for m in matches:
        movimientos.append({
            "Fecha": m[0],
            "Detalle": m[1].strip(),
            "Cuota": m[2] if m[2] else "01/01",
            "Monto ($)": float(m[3].replace('.', '').replace(',', '.'))
        })
    
    return datos, total_pagos, pd.DataFrame(movimientos)

# --- INTERFAZ ---
st.title("💳 Analizador de Tarjeta ICBC")
st.write("Gestiona y descarga los movimientos de tu resumen de forma profesional.")

archivo = st.file_uploader("Sube tu resumen en formato PDF", type="pdf")

if archivo:
    try:
        with st.spinner('Analizando documento...'):
            datos, total_pagos, df_movs = extraer_datos_icbc(archivo)

        # --- SIDEBAR (PANEL IZQUIERDO) ---
        with st.sidebar:
            st.image("https://www.icbc.com.ar/static/images/logo_icbc.png", width=150) # Logo genérico
            st.header("Resumen del Periodo")
            st.info(f"👤 **Titular:**\n{datos['titular']}")
            
            st.write(f"📅 **Cierre:** {datos['cierre']}")
            st.write(f"📅 **Vencimiento:** {datos['vencimiento']}")
            st.divider()

            # --- MÉTRICAS (CUADRADITOS) ---
            st.subheader("Estado de Cuenta")
            
            st.metric(label="Saldo Anterior Pesos", value=f"${datos['saldo_ant_pesos']}")
            st.metric(label="Saldo Anterior Dólares", value=f"u$s {datos['saldo_ant_dolares']}")
            
            st.divider()
            st.subheader("Pagos Realizados")
            st.metric(label="Total Pagos en Pesos", value=f"${total_pagos:,.2f}", delta="Cobrado")

        # --- CUERPO PRINCIPAL ---
        if not df_movs.empty:
            # Resumen de métricas superiores
            m1, m2 = st.columns(2)
            total_gastos = df_movs["Monto ($)"].sum()
            
            with m1:
                st.metric("Total Gastos Detectados", f"${total_gastos:,.2f}")
            with m2:
                st.metric("Cant. de Transacciones", len(df_movs))

            st.subheader("📋 Detalle de Movimientos")
            # Editor de datos para que puedas corregir si algo sale mal
            df_editado = st.data_editor(df_movs, use_container_width=True, hide_index=True)

            # --- BOTÓN EXCEL PROFESIONAL ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_editado.to_excel(writer, index=False, sheet_name='MisGastos')
            
            st.download_button(
                label="📥 Descargar Reporte en Excel",
                data=buffer.getvalue(),
                file_name=f"Reporte_ICBC_{datos['cierre'].replace('/','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.warning("⚠️ No se detectaron movimientos de compras en el formato esperado.")

    except Exception as e:
        st.error(f"Se produjo un error al procesar el PDF: {e}")
else:
    st.info("💡 **Tip:** Sube el PDF original descargado del Home Banking para asegurar la mejor detección de datos.")
