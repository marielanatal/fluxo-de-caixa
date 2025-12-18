import os
import pandas as pd
import streamlit as st
from datetime import timedelta
import streamlit.components.v1 as components
from workalendar.america.brazil import Brazil

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Fluxo de Caixa Projetado", layout="wide")

# =========================
# ARQUIVOS DO REPO (AUTOMÁTICO)
# =========================
PLANILHA_LOCAL = "fluxo.xlsx"   # fica no seu GitHub, junto do app.py
LOGO_LOCAL = "logo.png"        # opcional, se existir

cal = Brazil()

# =========================
# FUNÇÕES
# =========================
def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def proximo_dia_util(d):
    # dia útil = seg-sex e não feriado (Brasil)
    while not cal.is_working_day(d):
        d += timedelta(days=1)
    return d

def proximo_dia_util_apos(d):
    # próximo dia útil depois de d
    return proximo_dia_util(d + timedelta(days=1))

def normalizar_forma(s):
    s = str(s).upper().strip()
    # padrões da sua planilha
    if "BOLETO" in s:
        return "BOLETO"
    if "TED" in s or "PIX" in s:
        return "TED/PIX"
    return s  # outros ficam como estão

def calcular_data_real(row):
    """
    REGRA IGUAL AO EXCEL:
    1) Primeiro normaliza o vencimento para dia útil (se cair em fim de semana/feriado)
    2) Depois aplica a regra do boleto (D+1 útil)
    """
    venc = row["DATA_VENCIMENTO"]
    tipo = row["TIPO"]
    forma = row["FORMA_N"]

    venc_util = proximo_dia_util(venc)

    if tipo == "RECEITA" and forma == "BOLETO":
        # Boleto cai no "dia seguinte" (próximo dia útil após o vencimento útil)
        return proximo_dia_util_apos(venc_util)

    # TED/PIX e DESPESA: ficam no dia útil (não deixa cair em sábado/domingo/feriado)
    return venc_util

@st.cache_data(show_spinner=False)
def carregar_planilha(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.upper()

    # mapeia colunas
    df = df.rename(columns={
        "DT. VENCIMENTO": "DATA_VENCIMENTO",
        "FORMA DE PAGAMENTO": "FORMA_PAGAMENTO"
    })

    obrig = {"TIPO", "DATA_VENCIMENTO", "VALOR", "FORMA_PAGAMENTO"}
    faltando = obrig - set(df.columns)
    if faltando:
        raise ValueError(f"Faltam colunas na planilha: {', '.join(sorted(faltando))}")

    df["TIPO"] = df["TIPO"].astype(str).str.upper().str.strip()
    df["DATA_VENCIMENTO"] = pd.to_datetime(df["DATA_VENCIMENTO"]).dt.date
    df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce").fillna(0.0)
    df["FORMA_N"] = df["FORMA_PAGAMENTO"].apply(normalizar_forma)

    # data real (regra final)
    df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)
    df["DATA_REAL"] = pd.to_datetime(df["DATA_REAL"])

    return df

# =========================
# TOPO
# =========================
col_titulo, col_logo = st.columns([3, 2])
with col_titulo:
    st.markdown("## 📊 Fluxo de Caixa Diário (Projetado)")
with col_logo:
    if os.path.exists(LOGO_LOCAL):
        st.image(LOGO_LOCAL, width=320)

# =========================
# SALDO INICIAL
# =========================
saldo_inicial = st.number_input("Saldo Inicial (Hoje)", value=0.0, format="%.2f")

# =========================
# LEITURA (AUTOMÁTICA)
# =========================
if not os.path.exists(PLANILHA_LOCAL):
    st.error(f"Não achei o arquivo **{PLANILHA_LOCAL}** no repositório. Coloque ele na raiz do projeto (junto do app.py).")
    st.stop()

try:
    df = carregar_planilha(PLANILHA_LOCAL)
except Exception as e:
    st.error("Erro ao processar a planilha.")
    st.exception(e)
    st.stop()

# =========================
# CONSOLIDAÇÃO DIÁRIA
# =========================
diario = (
    df.groupby(["DATA_REAL", "TIPO"])["VALOR"]
      .sum()
      .unstack(fill_value=0)
      .reset_index()
)

diario["Receita"] = diario.get("RECEITA", 0.0)
diario["Despesa"] = diario.get("DESPESA", 0.0)
diario = diario[["DATA_REAL", "Receita", "Despesa"]].sort_values("DATA_REAL")

# =========================
# SALDO ENCADEADO (IGUAL EXCEL)
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
# TABELA (CENTRALIZADA + LINHAS)
# =========================
html = """
<style>
.wrap {
  max-width: 1200px;
  margin: 0 auto;
}
table { width:100%; border-collapse:collapse; font-size:18px }
th, td { border:1px solid #cfcfcf; padding:12px; text-align:center }
th { background:#1f4fd8; color:white; font-weight:800 }
.neg { color:red; font-weight:900 }
.pos { color:green; font-weight:900 }
</style>
<div class="wrap">
<table>
<tr>
  <th>Data</th>
  <th>Receita</th>
  <th>Despesa</th>
  <th>Saldo Final do Dia</th>
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

html += "</table></div>"
components.html(html, height=650, scrolling=True)

# =========================
# GRÁFICO
# =========================
if len(diario):
    st.line_chart(diario.set_index("DATA_REAL")["Saldo Final do Dia"])

# =========================
# (Opcional) Auditoria rápida
# =========================
with st.expander("🔎 Conferência (como o app jogou as datas)"):
    aud = df[["TIPO", "FORMA_PAGAMENTO", "FORMA_N", "DATA_VENCIMENTO", "DATA_REAL", "VALOR"]].copy()
    aud["DATA_VENCIMENTO"] = pd.to_datetime(aud["DATA_VENCIMENTO"]).dt.strftime("%d/%m/%Y")
    aud["DATA_REAL"] = pd.to_datetime(aud["DATA_REAL"]).dt.strftime("%d/%m/%Y")
    st.dataframe(aud.sort_values(["DATA_REAL", "TIPO"]), use_container_width=True)

