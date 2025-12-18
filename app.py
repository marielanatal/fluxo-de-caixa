import streamlit as st
import pandas as pd
from datetime import timedelta
import streamlit.components.v1 as components
from workalendar.america.brazil import Brazil

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Fluxo de Caixa Projetado", layout="wide")

# =========================
# TOPO
# =========================
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("## 📊 Fluxo de Caixa Diário")
with c2:
    st.image("logo.png", width=320)

URL_PLANILHA = "https://raw.githubusercontent.com/marielanatal/fluxo-de-caixa/main/fluxo.xlsx"
cal = Brazil()

# =========================
# FUNÇÕES DE DATA (REGRA EXCEL)
# =========================
def proximo_dia_util(data):
    """Garante que a data NÃO seja sábado/domingo (e também evita feriado BR)."""
    while not cal.is_working_day(data):
        data += timedelta(days=1)
    return data


def calcular_data_real(row):
    data = row["DATA_VENCIMENTO"]

    # BOLETO: cai D+1, depois joga para próximo dia útil (se cair em fds/feriado)
    if row["TIPO"] == "RECEITA" and row["NATUREZA"] == "BOLETO":
        data = data + timedelta(days=1)

    # REGRA ÚNICA: ninguém pode cair em sábado/domingo (nem feriado)
    return proximo_dia_util(data)


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# INPUT
# =========================
saldo_inicial = st.number_input("Saldo Inicial (Hoje)", value=0.0, format="%.2f")

# =========================
# LEITURA
# =========================
df = pd.read_excel(URL_PLANILHA)

df.columns = df.columns.str.strip().str.upper()
df = df.rename(columns={
    "DT. VENCIMENTO": "DATA_VENCIMENTO",
    "FORMA DE PAGAMENTO": "NATUREZA"
})

df["DATA_VENCIMENTO"] = pd.to_datetime(df["DATA_VENCIMENTO"]).dt.date
df["TIPO"] = df["TIPO"].astype(str).str.upper().str.strip()
df["NATUREZA"] = df["NATUREZA"].astype(str).str.upper().str.strip()

# =========================
# DATA REAL (SEM FIM DE SEMANA)
# =========================
df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)
df["DATA_REAL"] = pd.to_datetime(df["DATA_REAL"])

# =========================
# CONSOLIDAÇÃO DIÁRIA (SOMA POR DIA)
# =========================
diario = (
    df.groupby(["DATA_REAL", "TIPO"])["VALOR"]
    .sum()
    .unstack(fill_value=0)
    .reset_index()
)

diario["Receita"] = diario.get("RECEITA", 0)
diario["Despesa"] = diario.get("DESPESA", 0)
diario = diario[["DATA_REAL", "Receita", "Despesa"]].sort_values("DATA_REAL")

# =========================
# SALDO ENCADEADO (IGUAL AO EXCEL)
# =========================
saldo = saldo_inicial
saldos = []
for _, r in diario.iterrows():
    saldo = saldo + r["Receita"] - r["Despesa"]
    saldos.append(saldo)

diario["Saldo Final do Dia"] = saldos

# =========================
# RESUMOS
# =========================
a, b, c = st.columns(3)
a.metric("Saldo Inicial (Hoje)", brl(saldo_inicial))
b.metric("Saldo Final Projetado", brl(diario["Saldo Final do Dia"].iloc[-1] if len(diario) else saldo_inicial))
c.metric("Resultado do Período", brl(diario["Receita"].sum() - diario["Despesa"].sum()))

st.markdown("---")

# =========================
# TABELA (COM LINHAS)
# =========================
html = """
<style>
table { width:100%; border-collapse:collapse; font-size:16px }
th, td { border:1px solid #ccc; padding:10px; text-align:center }
th { background:#1f4fd8; color:white; font-weight:700 }
.neg { color:red; font-weight:800 }
.pos { color:green; font-weight:800 }
</style>
<table>
<tr>
<th>Data</th><th>Receita</th><th>Despesa</th><th>Saldo Final do Dia</th>
</tr>
"""

for _, r in diario.iterrows():
    cls = "neg" if r["Saldo Final do Dia"] < 0 else "pos"
    html += f"""
    <tr>
        <td>{r['DATA_REAL'].strftime('%d/%m/%Y')}</td>
        <td>{brl(r['Receita'])}</td>
        <td>{brl(r['Despesa'])}</td>
        <td class="{cls}">{brl(r['Saldo Final do Dia'])}</td>
    </tr>
    """

html += "</table>"
components.html(html, height=600, scrolling=True)

# =========================
# GRÁFICO
# =========================
if len(diario):
    st.line_chart(diario.set_index("DATA_REAL")["Saldo Final do Dia"])

