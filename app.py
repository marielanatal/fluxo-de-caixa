import streamlit as st
import pandas as pd
from workalendar.america.brazil import Brazil
from datetime import timedelta

# =========================
# CONFIGURAÇÃO
# =========================
st.set_page_config(page_title="Fluxo de Caixa Diário", layout="wide")

# =========================
# TOPO
# =========================
col_title, col_logo = st.columns([3, 2])

with col_title:
    st.markdown("## 📊 Fluxo de Caixa Diário")

with col_logo:
    st.image("logo.png", width=340)

cal = Brazil()

# =========================
# CONFIGURAÇÃO FIXA
# =========================
URL_PLANILHA = "https://raw.githubusercontent.com/marielanatal/fluxo-de-caixa/main/fluxo.xlsx"

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

def estilo_saldo(valor):
    return "color: red; font-weight: bold;" if valor < 0 else "color: green; font-weight: bold;"

# =========================
# INPUT
# =========================
saldo_inicial = st.number_input(
    "Saldo atual em conta",
    value=0.0,
    format="%.2f"
)

# =========================
# PROCESSAMENTO
# =========================
try:
    df = pd.read_excel(URL_PLANILHA)

    df.columns = df.columns.str.strip().str.upper()
    df = df.rename(columns={
        "DT. VENCIMENTO": "DATA_VENCIMENTO",
        "FORMA DE PAGAMENTO": "NATUREZA"
    })

    df["DATA_VENCIMENTO"] = pd.to_datetime(df["DATA_VENCIMENTO"]).dt.date
    df["TIPO"] = df["TIPO"].str.upper().str.strip()
    df["NATUREZA"] = df["NATUREZA"].astype(str).str.upper().str.strip()

    df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)
    df["DATA_REAL"] = pd.to_datetime(df["DATA_REAL"]).dt.date

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

    quadro = pd.merge(receitas, despesas, on="DATA_REAL", how="outer").fillna(0)
    quadro = quadro.sort_values("DATA_REAL")

    quadro["SALDO_FINAL_DIA"] = saldo_inicial + (quadro["RECEITA"] - quadro["DESPESA"]).cumsum()

    # =========================
    # TABELA HTML ESTILIZADA
    # =========================
    quadro_display = quadro.copy()
    quadro_display["DATA_REAL"] = pd.to_datetime(quadro_display["DATA_REAL"]).dt.strftime("%d/%m/%Y")

    styled = (
        quadro_display[["DATA_REAL", "RECEITA", "DESPESA", "SALDO_FINAL_DIA"]]
        .rename(columns={
            "DATA_REAL": "Data",
            "RECEITA": "Receita",
            "DESPESA": "Despesa",
            "SALDO_FINAL_DIA": "Saldo Final do Dia"
        })
        .style
        .format({
            "Receita": formatar_real,
            "Despesa": formatar_real,
            "Saldo Final do Dia": formatar_real
        })
        .applymap(estilo_saldo, subset=["Saldo Final do Dia"])
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("background-color", "#1f4fd8"),
                    ("color", "white"),
                    ("font-weight", "bold"),
                    ("font-size", "14px"),
                    ("text-align", "center"),
                    ("padding", "8px")
                ]
            },
            {
                "selector": "td",
                "props": [
                    ("font-size", "13px"),
                    ("padding", "6px")
                ]
            }
        ])
    )

    st.subheader("📅 Quadro de Fluxo de Caixa Diário")
    st.markdown(styled.to_html(), unsafe_allow_html=True)

    # =========================
    # GRÁFICO
    # =========================
    st.line_chart(quadro.set_index("DATA_REAL")["SALDO_FINAL_DIA"])

except Exception as e:
    st.error("Erro ao carregar a planilha automática.")
    st.exception(e)
