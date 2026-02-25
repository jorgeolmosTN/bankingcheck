import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

# Configuración de la página
st.set_page_config(page_title="Analizador de Tarjeta 💳", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_datos_resumen(pdf_file):
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
    
    # --- 1. Lógica para el Sidebar ---
    def buscar(patron, texto):
        match = re.search(patron, texto, re.IGNORECASE)
        return match.group(1).strip() if match else "No encontrado"

    datos_sidebar = {
        "cierre": buscar(r"CIERRE\s+ACTUAL[:\s]+(\d{2}/\d{2}/\d{4})", texto_completo),
        "titular": buscar(r"TITULAR[:\s]+([A-Z\s,]+)", texto_completo),
        "saldo_ant_pesos": buscar(r"SALDO\s+ANTERIOR\s+PESOS[:\s]+([\d\.,]+)", texto_completo),
        "saldo_ant_dolares": buscar(r"SALDO\s+ANTERIOR\s+DOLARES[:\s]+([\d\.,]+)", texto_completo),
    }

    # Sumatoria de "SU PAGO EN PESOS"
    pagos = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)", texto_completo, re.IGNORECASE)
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos])

    # --- 2. Lógica para la Tabla (Regex de ejemplo para transacciones) ---
    # Este regex busca: Fecha (DD/MM) + Descripción + Cuota (XX/XX) + Monto
    # Nota: Ajustar según el formato visual de tu resumen
    patron_transaccion = r"(\d{2}/\d{2})\s+(.*?)\s+(\d{2}/\d{2})?\s+([\d\.,]+)"
    matches = re.findall(patron_transaccion, texto_completo)
    
    df_lista = []
    for m in matches:
        df_lista.append({
            "Fecha": m[0],
            "Detalle": m[1],
            "Cuota": m[2] if m[2] else "01/01",
            "Monto": float(m[3].replace('.', '').replace(',', '.'))
        })
    
    df_transacciones = pd.DataFrame(df_lista)
    
    return datos_sidebar, total_pagos, df_transacciones

# --- INTERFAZ DE USUARIO ---
st.title("💳 Analizador de Resumen de Tarjeta")
st.markdown("Sube tu archivo PDF para desglosar cuotas, impuestos y pagos.")

archivo = st.file_uploader("Arrastra tu PDF aquí", type="pdf")

if archivo:
    try:
        datos, pagos_pesos, df_final = extraer_datos_resumen(archivo)

        # --- MENU LATERAL (SIDEBAR) ---
        with st.sidebar:
            st.header("📊 Información General")
            st.write(f"**CIERRE ACTUAL:** {datos['cierre']}")
            st.write(f"**VENCIMIENTO ACTUAL:** 10/02/2026")
            st.write(f"**TIT. DE CUENTA:** {datos['titular']}")
            st.divider()
            st.write(f"**Saldo Ant. Pesos:** ${datos['saldo_ant_pesos']}")
            st.write(f"**Saldo Ant. Dólares:** u$s {datos['saldo_ant_dolares']}")
            st.divider()
            st.subheader(f"Pagos en Pesos: ${pagos_pesos:,.2f}")

        # --- CUERPO PRINCIPAL ---
        if not df_final.empty:
            st.subheader("📋 Detalle de Transacciones Detectadas")
            
            # Mostramos la tabla interactiva
            st.dataframe(df_final, use_container_width=True)

            # --- BOTÓN DE DESCARGA EXCEL ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Detalle_Gastos')
            
            st.download_button(
                label="📥 Descargar Tabla en Excel",
                data=buffer.getvalue(),
                file_name="resumen_analizado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Métricas resumen abajo
            st.divider()
            total_gastos = df_final["Monto"].sum()
            st.info(f"**Suma total de consumos en esta tabla:** ${total_gastos:,.2f}")

        else:
            st.warning("No se detectaron transacciones con el formato estándar. Revisa el PDF.")

    except Exception as e:
        st.error(f"Hubo un error al procesar el archivo: {e}")

else:
    st.info("Esperando archivo PDF...")
