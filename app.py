import streamlit as st
import pandas as pd
from workalendar.america.brazil import Brazil
from datetime import timedelta
import streamlit.components.v1 as components

# =========================
# CONFIGURAÇÃO
# =========================
st.set_page_config(page_title="Fluxo de Caixa Diário", layout="wide")

# =========================
# TOPO
# =========================
col_title, col_logo = st.columns([3, 2])
with col_title:
    st.markdown("## 📊 Quadro de Fluxo de Caixa Diário")
with col_logo:
    st.image("logo.png", width=220)

# =========================
# CONFIGURAÇÃO FIXA
# =========================
URL_PLANILHA = "https://raw.githubusercontent.com/marielanatal/fluxo-de-caixa/main/fluxo.xlsx"
cal = Brazil()

# =========================
# FUNÇÕES
# =========================
def proximo_dia_util(data):
    data += timedelta(days=1)
    while not cal.is_working_day(data):
        data += timedelta(days=1)
    return data

def calcular_data_real(row):
    if row["TIPO"] == "RECEITA":
        if row["NATUREZA"] in ["PIX", "TED"]:
            return row["DATA_VENCIMENTO"]
        if row["NATUREZA"] == "BOLETO":
            return proximo_dia_util(row["DATA_VENCIMENTO"])
    return row["DATA_VENCIMENTO"]

def formatar_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# INPUT
# =========================
saldo_inicial = st.number_input("Saldo atual em conta", value=0.0, format="%.2f")

# =========================
# PROCESSAMENTO
# =========================
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

receitas = df[df["TIPO"] == "RECEITA"].groupby("DATA_REAL")["VALOR"].sum()
despesas = df[df["TIPO"] == "DESPESA"].groupby("DATA_REAL")["VALOR"].sum()

quadro = pd.concat([receitas, despesas], axis=1).fillna(0)
quadro.columns = ["Receita", "Despesa"]
quadro["Saldo Final do Dia"] = saldo_inicial + (quadro["Receita"] - quadro["Despesa"]).cumsum()
quadro = quadro.reset_index()
quadro["Data"] = pd.to_datetime(quadro["DATA_REAL"]).dt.strftime("%d/%m/%Y")

# =========================
# RESUMOS
# =========================
c1, c2, c3 = st.columns(3)
c1.metric("Saldo Inicial", formatar_real(saldo_inicial))
c2.metric("Saldo Final Projetado", formatar_real(quadro["Saldo Final do Dia"].iloc[-1]))
c3.metric("Resultado do Período", formatar_real(quadro["Receita"].sum() - quadro["Despesa"].sum()))

# =========================
# HTML DA TABELA (FULL WIDTH REAL)
# =========================
html = f"""
<style>
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 16px;
}}
th {{
    background-color: #1f4fd8;
    color: white;
    padding: 12px;
    text-align: center;
}}
td {{
    padding: 10px;
    text-align: center;
}}
.neg {{
    color: red;
    font-weight: bold;
}}
.pos {{
    color: green;
    font-weight: bold;
}}
</style>

<table>
<tr>
    <th>Data</th>
    <th>Receita</th>
    <th>Despesa</th>
    <th>Saldo Final do Dia</th>
</tr>
"""

for _, row in quadro.iterrows():
    cls = "neg" if row["Saldo Final do Dia"] < 0 else "pos"
    html += f"""
    <tr>
        <td>{row['Data']}</td>
        <td>{formatar_real(row['Receita'])}</td>
        <td>{formatar_real(row['Despesa'])}</td>
        <td class="{cls}">{formatar_real(row['Saldo Final do Dia'])}</td>
    </tr>
    """

html += "</table>"

components.html(html, height=650, scrolling=True)

# =========================
# GRÁFICO
# =========================
st.line_chart(quadro.set_index("Data")["Saldo Final do Dia"])

