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

def formatar_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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
        # Ler planilha
        df = pd.read_excel(url_planilha)

        # Padronizar nomes das colunas
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

        # Converter datas (sem hora)
        df["DATA_VENCIMENTO"] = pd.to_datetime(df["DATA_VENCIMENTO"]).dt.date

        # Padronizar textos
        df["TIPO"] = df["TIPO"].astype(str).str.upper().str.strip()
        df["NATUREZA"] = df["NATUREZA"].astype(str).str.upper().str.strip()

        # Calcular data real de entrada/saída
        df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)
        df["DATA_REAL"] = pd.to_datetime(df["DATA_REAL"]).dt.date

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
        # VISUAL - CARDS
        # =========================
        col1, col2, col3 = st.columns(3)

        col1.metric("Saldo Inicial", formatar_real(saldo_inicial))
        col2.metric("Saldo Final Projetado", formatar_real(fluxo.iloc[-1]["SALDO_PROJETADO"]))
        col3.metric("Variação no Período", formatar_real(fluxo["VALOR_FLUXO"].sum()))

        # =========================
        # TABELA FORMATADA
        # =========================
        fluxo_exibicao = fluxo.copy()

        fluxo_exibicao["DATA_REAL"] = pd.to_datetime(
            fluxo_exibicao["DATA_REAL"]
        ).dt.strftime("%d/%m/%Y")

        fluxo_exibicao["VALOR_FLUXO"] = fluxo_exibicao["VALOR_FLUXO"].apply(formatar_real)
        fluxo_exibicao["SALDO_PROJETADO"] = fluxo_exibicao["SALDO_PROJETADO"].apply(formatar_real)

        st.subheader("📅 Evolução Diária do Saldo")

        st.dataframe(
            fluxo_exibicao.rename(columns={
                "DATA_REAL": "Data",
                "VALOR_FLUXO": "Movimento do Dia",
                "SALDO_PROJETADO": "Saldo Projetado"
            }),
            use_container_width=True
        )

        # =========================
        # GRÁFICO
        # =========================
        st.line_chart(
            fluxo.set_index("DATA_REAL")["SALDO_PROJETADO"]
        )

    except Exception as e:
        st.error("Erro ao processar a planilha. Verifique a URL RAW e o formato dos dados.")
        st.exception(e)

