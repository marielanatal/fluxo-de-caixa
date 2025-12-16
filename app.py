import streamlit as st
import pandas as pd
from workalendar.america.brazil import Brazil
from datetime import timedelta

# =========================
# CONFIGURAÇÃO
# =========================
st.set_page_config(page_title="Fluxo de Caixa Diário", layout="wide")
st.title("📊 Fluxo de Caixa Diário")

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

def estilo_negativo(val):
    try:
        val_num = float(val)
        if val_num < 0:
            return "color: red; font-weight: bold;"
    except:
        pass
    return ""

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
        df.columns = df.columns.str.strip().str.upper()

        df = df.rename(columns={
            "DT. VENCIMENTO": "DATA_VENCIMENTO",
            "FORMA DE PAGAMENTO": "NATUREZA"
        })

        df["DATA_VENCIMENTO"] = pd.to_datetime(df["DATA_VENCIMENTO"]).dt.date
        df["TIPO"] = df["TIPO"].str.upper().str.strip()
        df["NATUREZA"] = df["NATUREZA"].astype(str).str.upper().str.strip()

        # Data real
        df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)
        df["DATA_REAL"] = pd.to_datetime(df["DATA_REAL"]).dt.date

        # Receitas e despesas por dia
        receitas = (
            df[df["TIPO"] == "RECEITA"]
            .groupby("DATA_REAL")["VALOR"]
            .sum()
            .reset_index()
            .rename(columns={"VALOR": "RECEITA"})
        )

        despesas = (
            df[df["TIPO"] == "DESPESA"]
            .groupby("DATA_REAL")["VALOR"]
            .sum()
            .reset_index()
            .rename(columns={"VALOR": "DESPESA"})
        )

        # Quadro base
        quadro = pd.merge(receitas, despesas, on="DATA_REAL", how="outer").fillna(0)
        quadro = quadro.sort_values("DATA_REAL")

        quadro["RESULTADO"] = quadro["RECEITA"] - quadro["DESPESA"]
        quadro["SALDO"] = saldo_inicial + quadro["RESULTADO"].cumsum()

        # =========================
        # CARDS
        # =========================
        col1, col2, col3 = st.columns(3)

        col1.metric("Saldo Inicial", formatar_real(saldo_inicial))
        col2.metric("Saldo Final Projetado", formatar_real(quadro["SALDO"].iloc[-1]))
        col3.metric("Resultado no Período", formatar_real(quadro["RESULTADO"].sum()))

        # =========================
        # TABELA FORMATADA
        # =========================
        quadro_exibicao = quadro.copy()

        quadro_exibicao["DATA_REAL"] = pd.to_datetime(
            quadro_exibicao["DATA_REAL"]
        ).dt.strftime("%d/%m/%Y")

        for col in ["RECEITA", "DESPESA", "RESULTADO", "SALDO"]:
            quadro_exibicao[col] = quadro_exibicao[col].apply(formatar_real)

        styled = (
            quadro_exibicao
            .rename(columns={
                "DATA_REAL": "Data",
                "RECEITA": "Receita",
                "DESPESA": "Despesa",
                "RESULTADO": "Resultado do Dia",
                "SALDO": "Saldo"
            })
            .style
            .applymap(estilo_negativo, subset=["Resultado do Dia", "Saldo"])
        )

        st.subheader("📅 Quadro de Fluxo de Caixa Diário")
        st.dataframe(styled, use_container_width=True)

        # =========================
        # GRÁFICO
        # =========================
        st.line_chart(quadro.set_index("DATA_REAL")["SALDO"])

    except Exception as e:
        st.error("Erro ao processar a planilha.")
        st.exception(e)

