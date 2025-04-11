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
        "%CDI Ano": "",
        "Composicao": ""
    }

    match = re.search(r"XPerformance\s*-\s*(\d+)", nome_arquivo)
    if match:
        dados["Código"] = match.group(1)

    linhas = texto.splitlines()
    comp_inicio = False
    composicao_linhas = []
    patrimonio = 0.0

    for linha in linhas:
        if "PATRIMÔNIO TOTAL BRUTO" in linha.upper():
            match_patr = re.search(r"R\$\s*([\d\.]+,\d{2})", linha)
            if match_patr:
                patrimonio = float(match_patr.group(1).replace(".", "").replace(",", "."))

        if "Portf" in linha:
            percentuais = re.findall(r"\d+,\d+%", linha)
            if len(percentuais) >= 2:
                dados["Rent. Mês"] = percentuais[0]
                dados["Rent. Ano"] = percentuais[1]

        if linha.strip().startswith("ANO"):
            percentuais = re.findall(r"\d+,\d+%", linha)
            if len(percentuais) >= 2:
                dados["%CDI Ano"] = percentuais[1]

        if "COMPOSIÇÃO" in linha.upper():
            comp_inicio = True
            continue
        if comp_inicio:
            if "RENTABILIDADE" in linha.upper():
                comp_inicio = False
            else:
                composicao_linhas.append(linha.strip())

    composicao_detalhada = []
    for linha in composicao_linhas:
        partes = re.split(r"\s{2,}", linha)
        if len(partes) >= 5:
            estrategia = re.sub(r"\s*\(.*\)", "", partes[0]).strip()
            saldo = partes[1].replace("R$", "").replace(".", "").replace(",", ".")
            mes = partes[2]
            ano = partes[3]
            try:
                saldo_float = float(saldo)
                pct = f"{(saldo_float / patrimonio) * 100:.2f}%" if patrimonio > 0 else "-"
                composicao_detalhada.append([estrategia, pct, partes[1], mes, ano])
            except:
                pass

    if composicao_detalhada:
        tabela = pd.DataFrame(composicao_detalhada, columns=["Estratégia", "Composição", "Saldo Bruto", "Mês Atual", "Ano"])
        dados["Composicao"] = tabela.to_csv(index=False)
    else:
        dados["Composicao"] = ""

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
            texto = ""
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        texto += page_text + "\n"
                except:
                    continue
            dados = extrair_dados(arquivo.name, texto)
            resultados.append(dados)
        except Exception as e:
            st.error(f"Erro ao processar {arquivo.name}: {e}")

    if resultados:
        df = pd.DataFrame(resultados)

        df["Rent. Mês Num"] = df["Rent. Mês"].str.replace("%", "").str.replace(",", ".").astype(float)
        df["%CDI Num"] = df["%CDI Ano"].str.replace("%", "").str.replace(",", ".").astype(float)

        css_selectbox = """
        <style>
        div[data-baseweb="select"] > div {
            border: 2px solid #09f !important;
        }
        div[data-baseweb="select"] span[title="Acima de 100%"] {
            color: lime;
        }
        div[data-baseweb="select"] span[title="Abaixo de 100%"] {
            color: tomato;
        }
        </style>
        """
        st.markdown(css_selectbox, unsafe_allow_html=True)

        opcao_filtro = st.selectbox("Filtrar por %CDI Ano:", ["Todos", "Acima de 100%", "Abaixo de 100%"])
        if opcao_filtro == "Acima de 100%":
            df = df[df["%CDI Num"] > 100]
        elif opcao_filtro == "Abaixo de 100%":
            df = df[df["%CDI Num"] <= 100]

        df = df.sort_values(by="Rent. Mês Num", ascending=False)

        df_exibido = df.drop(columns=["Rent. Mês Num", "%CDI Num"])

        st.markdown("### 📄 Visualizar Tabela")

        st.markdown(
            """
            <style>
            .tabela-header {
                display: grid;
                grid-template-columns: 2fr 2fr 2fr 2fr 2fr;
                font-weight: bold;
                margin-bottom: 0.5rem;
            }
            .tabela-row {
                display: grid;
                grid-template-columns: 2fr 2fr 2fr 2fr 2fr;
                margin-bottom: 0.25rem;
            }
            </style>
            <div class='tabela-header'>
                <div>Arquivo</div>
                <div>Código</div>
                <div>Rentabilidade Mês</div>
                <div>Rentabilidade Ano</div>
                <div>%CDI Ano</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        for idx, row in df_exibido.iterrows():
            st.markdown(
                f"""
                <div class='tabela-row'>
                    <div>{row['Arquivo']}</div>
                    <div>{row['Código']}</div>
                    <div>{row['Rent. Mês']}</div>
                    <div>{row['Rent. Ano']}</div>
                    <div>{row['%CDI Ano']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        excel_data = gerar_excel(df_exibido)
        st.download_button("📥 Baixar Excel com Resultados", data=excel_data,
                           file_name="rentabilidades.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Nenhum dado encontrado nos PDFs enviados.")
else:
    st.info("Envie um ou mais arquivos PDF para iniciar a extração.")
