import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Analizador de Tarjeta", layout="wide")

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_datos_tarjeta(pdf_file):
    texto_completo = ""
    filas_detalles = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
            # Intentar extraer tablas de cada página
            table = page.extract_table()
            if table:
                filas_detalles.extend(table)

    # Búsqueda de valores específicos con Regex
    def buscar(patron, texto):
        match = re.search(patron, texto, re.IGNORECASE)
        return match.group(1) if match else "No encontrado"

    datos = {
        "cierre": buscar(r"CIERRE\s+ACTUAL[:\s]+(\d{2}/\d{2}/\d{4})", texto_completo),
        "titular": buscar(r"TITULAR[:\s]+(.+)", texto_completo),
        "saldo_ant_pesos": buscar(r"SALDO\s+ANTERIOR\s+PESOS[:\s]+([\d\.,]+)", texto_completo),
        "saldo_ant_dolares": buscar(r"SALDO\s+ANTERIOR\s+DOLARES[:\s]+([\d\.,]+)", texto_completo),
    }

    # Sumatoria de "SU PAGO EN PESOS"
    pagos = re.findall(r"SU PAGO EN PESOS.*?([\d\.,]+)", texto_completo, re.IGNORECASE)
    # Limpiar puntos de miles y comas decimales para sumar
    total_pagos = sum([float(p.replace('.', '').replace(',', '.')) for p in pagos])

    return datos, texto_completo, total_pagos

# --- INTERFAZ DE USUARIO ---
st.title("💳 Análisis de Resumen de Tarjeta")

uploaded_file = st.file_uploader("Sube tu resumen PDF", type="pdf")

if uploaded_file:
    datos, texto, total_pagos = extraer_datos_tarjeta(uploaded_file)

    # --- MENÚ IZQUIERDO (SIDEBAR) ---
    with st.sidebar:
        st.header("Resumen General")
        st.write(f"**CIERRE ACTUAL:** {datos['cierre']}")
        st.write(f"**VENCIMIENTO ACTUAL:** 10/02/2026") # Fecha fija según pediste
        st.write(f"**TIT. DE CUENTA:** {datos['titular']}")
        st.divider()
        st.write(f"**Saldo Anterior ($):** {datos['saldo_ant_pesos']}")
        st.write(f"**Saldo Anterior (u$s):** {datos['saldo_ant_dolares']}")
        st.subheader(f"Total Pagos: ${total_pagos:,.2f}")

    # --- CUERPO PRINCIPAL ---
    # Aquí simulamos la creación de un DataFrame basado en los consumos
    # En una versión real, aquí procesarías la lista 'filas_detalles'
    st.subheader("Análisis de Consumos")
    
    # Ejemplo de cómo se vería el DataFrame
    # (Esto debería ser el resultado de filtrar 'texto' buscando montos y cuotas)
    st.info("A continuación se muestran los movimientos detectados en el PDF:")
    
    # Simulación de DataFrame (sustituir por lógica de filtrado real)
    df_ejemplo = pd.DataFrame({
        "Fecha": ["15/01", "18/01", "20/01"],
        "Detalle": ["Amazon", "Supermercado", "Cuota Gimnasio"],
        "Cuota": ["02/06", "01/01", "03/12"],
        "Monto ($)": [15000.50, 4500.00, 8900.00]
    })
    
    st.dataframe(df_ejemplo, use_container_width=True)
    
    # Métricas rápidas
    total_cuotas = df_ejemplo["Monto ($)"].sum()
    st.metric("Suma de ítems encontrados", f"${total_cuotas:,.2f}")

else:
    st.warning("Por favor, sube un archivo PDF para comenzar el análisis.")


import io

# ... (dentro de tu bloque 'if uploaded_file:')

st.subheader("📋 Detalle de Transacciones")

# Aquí usamos el DataFrame con los datos extraídos
# (Asegúrate de que 'df_ejemplo' contenga todos los datos procesados)
st.dataframe(df_ejemplo, use_container_width=True)

# --- LÓGICA PARA DESCARGAR EXCEL ---

# 1. Creamos un buffer en memoria
buffer = io.BytesIO()

# 2. Escribimos el DataFrame en el buffer usando ExcelWriter
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_ejemplo.to_excel(writer, index=False, sheet_name='Transacciones')

# 3. Creamos el botón de descarga
st.download_button(
    label="📥 Descargar detalle en Excel",
    data=buffer.getvalue(),
    file_name=f"analisis_tarjeta_{datos['cierre'].replace('/','-')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

