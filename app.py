import streamlit as st
import pandas as pd
from workalendar.america.brazil import Brazil
from datetime import timedelta

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Fluxo de Caixa Projetado",
    layout="wide"
)

st.title("📊 Fluxo de Caixa Projetado")

cal = Brazil()

# =========================
# FUNÇÕES
# =========================
def proximo_dia_util(data):
    data = data + timedelta(days=1)
    while not cal.is_working_day(data):
        data += timedelta(days=1)
    return data

def calcular_data_real(row):
    if row["TIPO"] == "RECEITA":
        if row["NATUREZA"] in ["PIX", "TED"]:
            return row["DATA_VENCIMENTO"]
        elif row["NATUREZA"] == "BOLETO":
            return proximo_dia_util(row["DATA_VENCIMENTO"])
    return row["DATA_VENCIMENTO"]

# =========================
# INPUTS
# =========================
saldo_inicial = st.number_input(
    "Saldo atual em conta",
    value=0.0,
    format="%.2f"
)

url_planilha = st.text_input(
    "URL RAW do Excel no GitHub",
    placeholder="https://raw.githubusercontent.com/usuario/repositorio/main/fluxo.xlsx"
)

# =========================
# PROCESSAMENTO
# =========================
if url_planilha:

    try:
        df = pd.read_excel(url_planilha)

        # Padronizar colunas
        df.columns = (
            df.columns
            .str.strip()
            .str.upper()
        )

        # Renomear colunas para padrão interno
        df = df.rename(columns={
            "DT. VENCIMENTO": "DATA_VENCIMENTO",
            "FORMA DE PAGAMENTO": "NATUREZA"
        })

        # Converter data
        df["DATA_VENCIMENTO"] = pd.to_datetime(df["DATA_VENCIMENTO"])

        # Padronizar textos
        df["TIPO"] = df["TIPO"].str.upper().str.strip()
        df["NATUREZA"] = df["NATUREZA"].str.upper().str.strip()

        # Calcular data real de entrada
        df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)

        # Criar valor de fluxo (+ receita / - despesa)
        df["VALOR_FLUXO"] = df.apply(
            lambda x: x["VALOR"] if x["TIPO"] == "RECEITA" else -x["VALOR"],
            axis=1
        )

        # Agrupar por dia
        fluxo = (
            df.groupby("DATA_REAL", as_index=False)["VALOR_FLUXO"]
            .sum()
            .sort_values("DATA_REAL")
        )

        # Calcular saldo acumulado
        fluxo["SALDO_PROJETADO"] = saldo_inicial + fluxo["VALOR_FLUXO"].cumsum()

        # =========================
        # VISUAL
        # =========================
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Saldo Inicial",
            f"R$ {saldo_inicial:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        col2.metric(
            "Saldo Final Projetado",
            f"R$ {fluxo.iloc[-1]['SALDO_PROJETADO']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        col3.metric(
            "Variação no Período",
            f"R$ {fluxo['VALOR_FLUXO'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        st.subheader("📅 Evolução Diária do Saldo")

        st.dataframe(
            fluxo.rename(columns={
                "DATA_REAL": "Data",
                "VALOR_FLUXO": "Movimento do Dia",
                "SALDO_PROJETADO": "Saldo Projetado"
            }),
            use_container_width=True
        )

        st.line_chart(
            fluxo.set_index("DATA_REAL")["SALDO_PROJETADO"]
        )

    except Exception as e:
        st.error("Erro ao processar a planilha. Verifique a URL RAW e o formato dos dados.")
        st.exception(e)

