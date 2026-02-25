import streamlit as st
import pdfplumber
import re
import pandas as pd

st.title("💳 Analizador de Tarjeta de Crédito")

uploaded_file = st.file_uploader("Sube tu resumen en PDF", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text()

    # --- Lógica de Extracción (Ejemplo conceptual) ---
    
    # Buscar cuotas: Ejemplo "02/06" o "Cuota 2 de 6"
    cuotas = re.findall(r"(\d+/\d+)\s+([\d\.,]+)", full_text)
    
    # Buscar impuestos: Ejemplo "IVA", "Imp. PAIS", "RG 4815"
    # Nota: Esto varía según el banco y el país
    impuestos_pattern = r"(IVA|IMP|RG\s\d+|PERCEPCION).+?([\d\.,]+)"
    impuestos = re.findall(impuestos_pattern, full_text, re.IGNORECASE)

    # --- Interfaz de Usuario ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total en Cuotas", "$ 150.000") # Aquí iría la suma real
        
    with col2:
        st.metric("Total Impuestos", "$ 45.000") # Aquí iría la suma real

    st.subheader("Detalle detectado")
    st.write("Aquí podrías mostrar un DataFrame con los ítems encontrados.")