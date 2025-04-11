import streamlit as st
import pandas as pd
import re
import io
from PyPDF2 import PdfReader
from openpyxl import Workbook

def extrair_dados(nome_arquivo, texto):
    dados = {
        "Arquivo": nome_arquivo,
        "Código": "",
        "Rent. Mês": "",
        "Rent. Ano": "",
        "%CDI Ano": ""
    }

    match = re.search(r"XPerformance\s*-\s*(\d+)", nome_arquivo)
    if match:
        dados["Código"] = match.group(1)

    linhas = texto.splitlines()

    for linha in linhas:
        if "Portf" in linha:
            percentuais = re.findall(r"\d+,\d+%", linha)
            if len(percentuais) >= 2:
                dados["Rent. Mês"] = percentuais[0]
                dados["Rent. Ano"] = percentuais[1]

        if linha.strip().startswith("ANO"):
            percentuais = re.findall(r"\d+,\d+%", linha)
            if len(percentuais) >= 2:
                dados["%CDI Ano"] = percentuais[1]

    return dados

def gerar_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rentabilidades')
    output.seek(0)
    return output

st.set_page_config(page_title="Extrator de Rentabilidades XP", layout="wide")
st.title("📊 Extrator de Rentabilidades - XP")

uploaded_files = st.file_uploader("Envie os relatórios PDF gerados pelo XP Advisor:", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []

    for arquivo in uploaded_files:
        try:
            reader = PdfReader(arquivo)
            texto = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            dados = extrair_dados(arquivo.name, texto)
            resultados.append(dados)
        except Exception as e:
            st.error(f"Erro ao processar {arquivo.name}: {e}")

    if resultados:
        df = pd.DataFrame(resultados)

        # Converter colunas percentuais para float para ordenação e filtro
        df["Rent. Mês Num"] = df["Rent. Mês"].str.replace("%", "").str.replace(",", ".").astype(float)
        df["%CDI Num"] = df["%CDI Ano"].str.replace("%", "").str.replace(",", ".").astype(float)

        # Filtro por %CDI
        opcao_filtro = st.selectbox("Filtrar por %CDI Ano:", ["Todos", "Acima de 100%", "Abaixo de 100%"])
        if opcao_filtro == "Acima de 100%":
            df = df[df["%CDI Num"] > 100]
        elif opcao_filtro == "Abaixo de 100%":
            df = df[df["%CDI Num"] <= 100]

        # Ordenar por Rent. Mês
        df = df.sort_values(by="Rent. Mês Num", ascending=False)

        # Ocultar colunas numéricas internas
        df_exibido = df.drop(columns=["Rent. Mês Num", "%CDI Num"])

        with st.expander("📄 Visualizar Tabela"):
            st.dataframe(df_exibido, use_container_width=True)

        excel_data = gerar_excel(df_exibido)
        st.download_button("📥 Baixar Excel com Resultados", data=excel_data,
                           file_name="rentabilidades.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Nenhum dado encontrado nos PDFs enviados.")
else:
    st.info("Envie um ou mais arquivos PDF para iniciar a extração.")
