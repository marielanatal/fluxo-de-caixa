import os
from io import BytesIO
from datetime import timedelta, datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from workalendar.america.brazil import Brazil

# PDF (ReportLab)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Fluxo de Caixa Projetado", layout="wide")

PLANILHA_LOCAL = "fluxo.xlsx"   # no repo
LOGO_LOCAL = "logo.png"        # opcional

cal = Brazil()

# =========================
# FUNÇÕES
# =========================
def brl(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def proximo_dia_util(d):
    # seg-sex e não feriado BR
    while not cal.is_working_day(d):
        d += timedelta(days=1)
    return d

def proximo_dia_util_apos(d):
    return proximo_dia_util(d + timedelta(days=1))

def normalizar_forma(s):
    s = str(s).upper().strip()
    if "BOLETO" in s:
        return "BOLETO"
    if "TED" in s or "PIX" in s:
        return "TED/PIX"
    return s

def calcular_data_real(row):
    """
    REGRA FINAL QUE BATEU COM SEU EXCEL:
    1) Normaliza vencimento para dia útil
    2) Se BOLETO: aplica D+1 útil (após o vencimento útil)
    3) Caso contrário: fica no vencimento útil
    """
    venc = row["DATA_VENCIMENTO"]
    tipo = row["TIPO"]
    forma = row["FORMA_N"]

    venc_util = proximo_dia_util(venc)

    if tipo == "RECEITA" and forma == "BOLETO":
        return proximo_dia_util_apos(venc_util)

    return venc_util

@st.cache_data(show_spinner=False)
def carregar_planilha(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.upper()

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

    df["DATA_REAL"] = df.apply(calcular_data_real, axis=1)
    df["DATA_REAL"] = pd.to_datetime(df["DATA_REAL"])

    return df

def gerar_pdf_tabela(diario: pd.DataFrame, saldo_inicial: float) -> bytes:
    """
    Gera PDF somente da tabela (Data, Receita, Despesa, Saldo Final do Dia),
    com estilo “corporativo” e saldo negativo em vermelho.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.2*cm,
        rightMargin=1.2*cm,
        topMargin=1.0*cm,
        bottomMargin=1.0*cm
    )

    styles = getSampleStyleSheet()
    story = []

    # Cabeçalho com logo (se existir) + título
    header = []
    if os.path.exists(LOGO_LOCAL):
        try:
            img = Image(LOGO_LOCAL, width=5.5*cm, height=2.0*cm)
            header.append(img)
        except Exception:
            pass

    titulo = Paragraph("<b>Fluxo de Caixa Projetado</b>", styles["Title"])
    subtitulo = Paragraph(
        f"Saldo inicial: <b>{brl(saldo_inicial)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles["Normal"]
    )

    if header:
        # logo + titulo lado a lado
        t = Table([[header[0], titulo]], colWidths=[6.0*cm, 20.0*cm])
        t.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING", (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(t)
    else:
        story.append(titulo)

    story.append(subtitulo)
    story.append(Spacer(1, 10))

    # Monta dados da tabela
    data = [["Data", "Receita", "Despesa", "Saldo Final do Dia"]]
    for _, r in diario.iterrows():
        data.append([
            r["DATA_REAL"].strftime("%d/%m/%Y"),
            brl(float(r["Receita"])),
            brl(float(r["Despesa"])),
            brl(float(r["Saldo Final do Dia"])),
        ])

    # Larguras (paisagem A4)
    col_widths = [4.0*cm, 6.5*cm, 6.5*cm, 7.0*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Estilo base
    style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f4fd8")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 12),

        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 11),

        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("ALIGN", (0,1), (0,-1), "CENTER"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),

        ("GRID", (0,0), (-1,-1), 0.7, colors.lightgrey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ])

    # Saldo negativo em vermelho / positivo em verde
    for i in range(1, len(data)):
        saldo_val = float(diario.iloc[i-1]["Saldo Final do Dia"])
        if saldo_val < 0:
            style.add("TEXTCOLOR", (3,i), (3,i), colors.red)
            style.add("FONTNAME", (3,i), (3,i), "Helvetica-Bold")
        else:
            style.add("TEXTCOLOR", (3,i), (3,i), colors.HexColor("#0a7a2f"))
            style.add("FONTNAME", (3,i), (3,i), "Helvetica-Bold")

    table.setStyle(style)
    story.append(table)

    doc.build(story)
    return buffer.getvalue()

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
    st.error(f"Não achei o arquivo **{PLANILHA_LOCAL}** no repositório. Coloque ele na raiz (junto do app.py).")
    st.stop()

df = carregar_planilha(PLANILHA_LOCAL)

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
# SALDO ENCADEADO
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
# BOTÃO PDF (SÓ TABELA)
# =========================
pdf_bytes = gerar_pdf_tabela(diario, saldo_inicial)
nome_pdf = f"Fluxo_Caixa_{datetime.now().strftime('%d-%m-%Y')}.pdf"

st.download_button(
    label="📄 Baixar PDF da Tabela",
    data=pdf_bytes,
    file_name=nome_pdf,
    mime="application/pdf"
)

# =========================
# TABELA (TELA)
# =========================
html = """
<style>
.wrap { max-width: 1200px; margin: 0 auto; }
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
      <td>{brl(float(r['Receita']))}</td>
      <td>{brl(float(r['Despesa']))}</td>
      <td class="{cls}">{brl(float(r['Saldo Final do Dia']))}</td>
    </tr>
    """

html += "</table></div>"
components.html(html, height=650, scrolling=True)

# =========================
# GRÁFICO
# =========================
if len(diario):
    st.line_chart(diario.set_index("DATA_REAL")["Saldo Final do Dia"])
