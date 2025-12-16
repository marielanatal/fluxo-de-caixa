import streamlit as st
import pandas as pd
from workalendar.america import Brazil
from datetime import timedelta

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Fluxo de Caixa Projetado", layout="wide")
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
    if row["tipo"] == "RECEITA":
        if row["natureza"] in ["PIX", "TED"]:
            return row["data_vencimento"]
        elif row["natureza"] == "BOLETO":
            return proximo_dia_util(row["data_vencimento"])
    return row["data_vencimento"]

# =========================
# INPUTS
# =========================
saldo_inicial = st.number_input(
    "Saldo atual em conta",
    value=845475.63,
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
    df = pd.read_excel(url_planilha)
    df["data_vencimento"] = pd.to_datetime(df["data_vencimento"])

    df["data_real"] = df.apply(calcular_data_real, axis=1)

    df["valor_fluxo"] = df.apply(
        lambda x: x["valor"] if x["tipo"] == "RECEITA" else -x["valor"],
        axis=1
    )

    fluxo = (
        df.groupby("data_real", as_index=False)["valor_fluxo"]
        .sum()
        .sort_values("data_real")
    )

    fluxo["saldo"] = saldo_inicial + fluxo["valor_fluxo"].cumsum()

    # =========================
    # VISUAL
    # =========================
    col1, col2, col3 = st.columns(3)

    col1.metric("Saldo Inicial", f"R$ {saldo_inicial:,.2f}")
    col2.metric("Saldo Final Projetado", f"R$ {fluxo.iloc[-1]['saldo']:,.2f}")
    col3.metric("Variação no Período", f"R$ {(fluxo['valor_fluxo'].sum()):,.2f}")

    st.subheader("📅 Evolução Diária do Saldo")
    st.dataframe(
        fluxo.rename(columns={
            "data_real": "Data",
            "valor_fluxo": "Movimento do Dia",
            "saldo": "Saldo Projetado"
        }),
        use_container_width=True
    )

    st.line_chart(fluxo.set_index("data_real")["saldo"])
