import streamlit as st
import pandas as pd
import numpy as np
from math import acos, tan, sqrt
from fpdf import FPDF
from io import BytesIO

# --- Configuración de la página ---
st.set_page_config(page_title="Selección de Transformadores", layout="wide")

# --- Constantes ---
TABLA_EFICIENCIA_DOE = {
    15: {"Seco": 0.9789, "Aceite": 0.9865},
    30: {"Seco": 0.9823, "Aceite": 0.9883},
    45: {"Seco": 0.9840, "Aceite": 0.9892},
    75: {"Seco": 0.9860, "Aceite": 0.9903},
    112.5: {"Seco": 0.9874, "Aceite": 0.9911},
    150: {"Seco": 0.9883, "Aceite": 0.9916},
    225: {"Seco": 0.9894, "Aceite": 0.9923},
    300: {"Seco": 0.9902, "Aceite": 0.9927},
    500: {"Seco": 0.9914, "Aceite": 0.9935},
    750: {"Seco": 0.9923, "Aceite": 0.9940},
    1000: {"Seco": 0.9928, "Aceite": 0.9943},
    1500: {"Seco": 0.99, "Aceite": 0.9948},
    2000: {"Seco": 0.99, "Aceite": 0.9951},
    2500: {"Seco": 0.99, "Aceite": 0.9953}
}

# --- Clases y Funciones ---
class Carga:
    def __init__(self, datos):
        self.datos = datos

    def calcular_potencias(self):
        tipo = self.datos["Tipo"]
        vfd = self.datos["VFD"]
        unidad = self.datos["Potencia_Unidad"]
        valor = self.datos["Potencia_Valor"]
        tipo_uso = self.datos["Tipo_de_Uso"]

        # Validar tipo de carga
        tipos_permitidos = ["Iluminación", "Motor", "Eq Cómputo", "Aire acondicionado"]
        if tipo not in tipos_permitidos:
            raise ValueError(f"Tipo de carga '{tipo}' no válido. Opciones: {tipos_permitidos}")

        # Factor de potencia
        if tipo == "Iluminación":
            fp = 0.9
        elif tipo == "Eq Cómputo":
            fp = 0.92
        elif tipo == "Aire acondicionado":
            fp = 0.88
        elif tipo == "Motor":
            fp = 0.98 if vfd == "Sí" else 0.88

        # Eficiencia
        if tipo == "Iluminación":
            eff = 0.95
        elif tipo == "Eq Cómputo":
            eff = 0.95
        elif tipo == "Aire acondicionado":
            eff = 0.95
        elif tipo == "Motor":
            eff = 0.9 if vfd == "Sí" else 0.95

        # Factor de utilización
        if tipo_uso not in ["Contínuo", "Intermitente", "Stand By"]:
            raise ValueError("Tipo de uso debe ser 'Contínuo', 'Intermitente' o 'Stand By'")
        fu = 0 if tipo_uso == "Stand By" else 1

        # Potencia activa (P)
        if unidad == "hp":
            p_kw = (valor * 0.746 / eff) * fu
        elif unidad == "kW":
            p_kw = (valor / eff) * fu
        elif unidad == "kVA":
            p_kw = (valor * fp / eff) * fu
        else:
            raise ValueError("Unidad de potencia debe ser 'hp', 'kW' o 'kVA'")

        # Potencia reactiva (Q) y aparente (S)
        q_kvar = p_kw * tan(acos(fp))
        s_kva = round(sqrt(p_kw**2 + q_kvar**2), 2)

        return {
            "P_kW": round(p_kw, 2),
            "Q_kVAR": round(q_kvar, 2),
            "S_kVA": s_kva,
            "FP": fp,
            "Eficiencia": eff,
            "Factor_Uso": fu
        }

def seleccionar_transformador(kva_total, fp_total, factor_div, reserva, tipo_trafo):
    kva_div = kva_total * factor_div
    kva_total_reserva = kva_div * (1 + reserva)
    
    # Seleccionar transformador (inmediato superior)
    transformadores = sorted(TABLA_EFICIENCIA_DOE.keys())
    for trafo in transformadores:
        if trafo >= kva_total_reserva:
            transformador_seleccionado = trafo
            eff_trafo = TABLA_EFICIENCIA_DOE[trafo][tipo_trafo]
            break
    
    # Cálculos finales
    perdidas = transformador_seleccionado * fp_total * (1/eff_trafo - 1)
    demanda_final = kva_total_reserva + perdidas / fp_total
    reserva_final = transformador_seleccionado - demanda_final
    
    return {
        "Transformador_seleccionado_kVA": transformador_seleccionado,
        "Eficiencia": f"{eff_trafo * 100:.2f}%",
        "Perdidas_kW": round(perdidas, 2),
        "Reserva_final_kVA": round(reserva_final, 2),
        "Reserva_final_%": f"{(reserva_final / transformador_seleccionado) * 100:.2f}%",
        "Cargabilidad_%": f"{(kva_div + perdidas / fp_total) / transformador_seleccionado * 100:.2f}%"
    }

def generar_pdf(df_cargas, resultados):
    pdf = FPDF(orientation='L')  # Horizontal
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # --- Tabla de Cargas ---
    pdf.cell(200, 10, txt="Listado de Cargas", ln=True, align='C')
    columnas = ["No", "Id", "Carga", "P [kW]", "Q [kVAR]", "S [kVA]"]
    ancho_columnas = [15, 30, 60, 25, 25, 25]
    
    # Encabezados
    for col, ancho in zip(columnas, ancho_columnas):
        pdf.cell(ancho, 10, txt=col, border=1, align='C')
    pdf.ln()
    
    # Datos
    for _, row in df_cargas.iterrows():
        pdf.cell(ancho_columnas[0], 10, txt=str(row["No"]), border=1, align='C')
        pdf.cell(ancho_columnas[1], 10, txt=str(row["Id"]), border=1)
        pdf.cell(ancho_columnas[2], 10, txt=str(row["Carga"]), border=1)
        pdf.cell(ancho_columnas[3], 10, txt=str(row["P_kW"]), border=1, align='C')
        pdf.cell(ancho_columnas[4], 10, txt=str(row["Q_kVAR"]), border=1, align='C')
        pdf.cell(ancho_columnas[5], 10, txt=str(row["S_kVA"]), border=1, align='C')
        pdf.ln()
    
    # --- Resumen Transformador ---
    pdf.ln(10)
    pdf.cell(200, 10, txt="Resumen de Transformador Seleccionado", ln=True, align='C')
    pdf.cell(60, 10, txt="Capacidad (kVA):", border=1)
    pdf.cell(40, 10, txt=str(resultados["Transformador_seleccionado_kVA"]), border=1, ln=True)
    pdf.cell(60, 10, txt="Eficiencia:", border=1)
    pdf.cell(40, 10, txt=resultados["Eficiencia"], border=1, ln=True)
    pdf.cell(60, 10, txt="Pérdidas (kW):", border=1)
    pdf.cell(40, 10, txt=str(resultados["Perdidas_kW"]), border=1, ln=True)
    pdf.cell(60, 10, txt="Reserva Final (%):", border=1)
    pdf.cell(40, 10, txt=resultados["Reserva_final_%"], border=1, ln=True)
    
    # Guardar PDF
    pdf_output = BytesIO()
    pdf.output(pdf_output)
    pdf_bytes = pdf_output.getvalue()
    return pdf_bytes

# --- Interfaz Streamlit ---
def main():
    st.title("📊 Selección de Transformadores Eléctricos")
    
    # --- Formulario de Cargas ---
    st.sidebar.header("🔧 Parámetros Globales")
    factor_div = st.sidebar.slider("Factor de diversificación", 0.1, 1.0, 0.75)
    reserva = st.sidebar.slider("Reserva mínima (%)", 0, 50, 20) / 100
    tipo_trafo = st.sidebar.selectbox("Tipo de transformador", ["Seco", "Aceite"])
    
    st.header("🔌 Ingresar Cargas Eléctricas")
    n_cargas = st.number_input("Número de cargas", min_value=1, max_value=50, value=1)
    
    cargas = []
    for i in range(n_cargas):
        with st.expander(f"Carga {i + 1}"):
            cols = st.columns(4)
            with cols[0]:
                no = i + 1
                id_carga = st.text_input(f"ID Carga {i + 1}", value=f"LOAD-{i + 1}")
                nombre = st.text_input(f"Nombre Carga {i + 1}", value=f"Carga {i + 1}")
            with cols[1]:
                tension = st.selectbox("Tensión [V]", [120, 208, 220, 480], key=f"tension_{i}")
                sistema = st.selectbox("Sistema", ["1 fase", "2 fases", "3 fases"], key=f"sistema_{i}")
                tipo = st.selectbox("Tipo", ["Iluminación", "Motor", "Eq Cómputo", "Aire acondicionado"], key=f"tipo_{i}")
            with cols[2]:
                potencia_valor = st.number_input("Valor Potencia", min_value=0.1, key=f"p_valor_{i}")
                potencia_unidad = st.selectbox("Unidad", ["hp", "kW", "kVA"], key=f"p_unidad_{i}")
                tipo_uso = st.selectbox("Tipo de Uso", ["Contínuo", "Intermitente", "Stand By"], key=f"tipo_uso_{i}")
            with cols[3]:
                vfd = st.selectbox("VFD (Solo Motor)", ["N/A", "Sí", "No"], key=f"vfd_{i}", disabled=(tipo != "Motor"))
                
            cargas.append({
                "No": no,
                "Id": id_carga,
                "Carga": nombre,
                "Tensión_V": tension,
                "Sistema": sistema,
                "Tipo": tipo,
                "Potencia_Valor": potencia_valor,
                "Potencia_Unidad": potencia_unidad,
                "Tipo_de_Uso": tipo_uso,
                "VFD": vfd if tipo == "Motor" else "N/A"
            })
    
    # --- Cálculos ---
    if st.button("🔄 Calcular"):
        df_cargas = pd.DataFrame(cargas)
        resultados_cargas = []
        
        for idx, carga in df_cargas.iterrows():
            try:
                resultados = Carga(carga).calcular_potencias()
                resultados_cargas.append({
                    "No": carga["No"],
                    "Id": carga["Id"],
                    "Carga": carga["Carga"],
                    "Tipo": carga["Tipo"],
                    "FP": resultados["FP"],
                    "Eficiencia": resultados["Eficiencia"],
                    "P_kW": resultados["P_kW"],
                    "Q_kVAR": resultados["Q_kVAR"],
                    "S_kVA": resultados["S_kVA"]
                })
            except ValueError as e:
                st.error(f"Error en carga {carga['No']}: {str(e)}")
                return

        df_resultados = pd.DataFrame(resultados_cargas)
        total_p = df_resultados["P_kW"].sum()
        total_q = df_resultados["Q_kVAR"].sum()
        total_s = round(sqrt(total_p**2 + total_q**2), 2)
        fp_total = total_p / total_s if total_s > 0 else 0
        
        resultados_trafo = seleccionar_transformador(total_s, fp_total, factor_div, reserva, tipo_trafo)
        
        # --- Mostrar Resultados ---
        st.header("📋 Resultados")
        st.dataframe(df_resultados)
        
        st.subheader("📊 Totales del Sistema")
        st.write(f"**Potencia Activa Total (P):** {total_p:.2f} kW")
        st.write(f"**Potencia Reactiva Total (Q):** {total_q:.2f} kVAR")
        st.write(f"**Potencia Aparente Total (S):** {total_s:.2f} kVA")
        st.write(f"**Factor de Potencia Total:** {fp_total:.2f}")
        
        st.subheader("🔧 Transformador Seleccionado")
        st.write(f"**Capacidad:** {resultados_trafo['Transformador_seleccionado_kVA']} kVA")
        st.write(f"**Eficiencia:** {resultados_trafo['Eficiencia']}")
        st.write(f"**Pérdidas:** {resultados_trafo['Perdidas_kW']} kW")
        st.write(f"**Reserva Final:** {resultados_trafo['Reserva_final_%']}")
        
        # --- Generar PDF ---
        pdf_bytes = generar_pdf(df_resultados, resultados_trafo)
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_bytes,
            file_name="seleccion_transformador.pdf",
            mime="application/pdf"
        )

if __name__ == "__main__":
    main()
