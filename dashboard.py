import pandas as pd
import psycopg2
import streamlit as st
import matplotlib.pyplot as plt
import os

from dotenv import load_dotenv

load_dotenv()

try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
except:
    DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------- DB ----------------

conn = psycopg2.connect(DATABASE_URL)

query = "SELECT * FROM spese ORDER BY id DESC"

df = pd.read_sql(query, conn)

conn.close()

# ---------------- CONFIG ----------------

st.set_page_config(
    page_title="Spese Giacomo",
    layout="wide"
)

st.title("💰 Dashboard Spese")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------- CONTI ----------------

st.subheader("🏦 Saldo conti")

saldi = {
    "banca": 0,
    "salvadanaio": 0
}

for _, row in df.iterrows():

    conto = row["conto"]

    if conto not in saldi:
        continue

    if row["tipo"] == "entrata":
        saldi[conto] += row["importo"]
    else:
        saldi[conto] -= row["importo"]

col1, col2 = st.columns(2)

with col1:

    st.markdown(f'''
    <div style="
        background-color:#1e1e1e;
        padding:30px;
        border-radius:20px;
        text-align:center;
        box-shadow:0 0 15px rgba(0,0,0,0.3);
    ">
        <h3 style="color:white;">🏦 Banca</h3>
        <h1 style="
            color:#00ff99;
            font-size:48px;
            margin-top:10px;
        ">
            € {saldi['banca']:.2f}
        </h1>
    </div>
    ''', unsafe_allow_html=True)

with col2:

    st.markdown(f'''
    <div style="
        background-color:#1e1e1e;
        padding:30px;
        border-radius:20px;
        text-align:center;
        box-shadow:0 0 15px rgba(0,0,0,0.3);
    ">
        <h3 style="color:white;">💰 Salvadanaio</h3>
        <h1 style="
            color:#66ccff;
            font-size:48px;
            margin-top:10px;
        ">
            € {saldi['salvadanaio']:.2f}
        </h1>
    </div>
    ''', unsafe_allow_html=True)

st.markdown("<br><br><br>", unsafe_allow_html=True)

# ---------------- FILTRO MESE ----------------

mesi = sorted(df["data"].str[:7].unique(), reverse=True)

mese_selezionato = st.selectbox(
    "📅 Seleziona mese",
    mesi
)

df = df[df["data"].str.startswith(mese_selezionato)]

st.markdown("<br>", unsafe_allow_html=True)


# ---------------- KPI ----------------

entrate = df[df["tipo"] == "entrata"]["importo"].sum()
uscite = df[df["tipo"] == "uscita"]["importo"].sum()

saldo = entrate - uscite

c1, c2, c3 = st.columns(3)

c1.metric(
    "Entrate",
    f"€ {entrate:.2f}"
)

c2.metric(
    "Uscite",
    f"€ {uscite:.2f}"
)

c3.metric(
    "Saldo",
    f"€ {saldo:.2f}",
    delta=f"{saldo:.2f}"
)

st.divider()

st.markdown("<br>", unsafe_allow_html=True)

# ---------------- ANDAMENTO ----------------

st.subheader("📈 Andamento saldo")

tipo_andamento = st.selectbox(
    "Periodo grafico",
    ["Mese corrente", "Storico completo"]
)

if tipo_andamento == "Storico completo":

    conn_and = psycopg2.connect(DATABASE_URL)

    df_andamento = pd.read_sql(
        "SELECT * FROM spese ORDER BY data ASC",
        conn_and
    )

    conn_and.close()

else:

    df_andamento = df.sort_values("data")

saldo_progressivo = 0
andamento = []

for _, row in df_andamento.iterrows():

    if row["tipo"] == "entrata":
        saldo_progressivo += row["importo"]
    else:
        saldo_progressivo -= row["importo"]

    andamento.append(saldo_progressivo)

df_andamento["saldo_progressivo"] = andamento

df_andamento["data"] = pd.to_datetime(
    df_andamento["data"]
)

fig_and, ax_and = plt.subplots(figsize=(7, 3))

ax_and.plot(
    df_andamento["data"],
    df_andamento["saldo_progressivo"],
    linewidth=3
)

ax_and.grid(True)

ax_and.set_xlabel("")
ax_and.set_ylabel("€")

fig_and.autofmt_xdate()

st.pyplot(
    fig_and,
    use_container_width=True
)

st.markdown("<br><br>", unsafe_allow_html=True)

# ---------------- TABELLA ----------------

st.subheader("📋 Operazioni")

mostra_tutto = st.checkbox(
    "Mostra operazioni di tutti i mesi"
)

if mostra_tutto:

    df_operazioni = pd.read_sql(
        "SELECT * FROM spese ORDER BY id DESC",
        psycopg2.connect(DATABASE_URL)
    )

else:

    df_operazioni = df.copy()

colf1, colf2 = st.columns(2)

with colf1:

    filtro_tipo = st.selectbox(
        "Tipo operazione",
        ["Tutte", "Entrate", "Uscite"]
    )

with colf2:

    categorie = sorted(df["categoria"].unique())

    filtro_categoria = st.selectbox(
        "Categoria",
        ["Tutte"] + categorie
    )

# -------- FILTRO TIPO --------

if filtro_tipo == "Entrate":

    df_operazioni = df_operazioni[
        df_operazioni["tipo"] == "entrata"
    ]

elif filtro_tipo == "Uscite":

    df_operazioni = df_operazioni[
        df_operazioni["tipo"] == "uscita"
    ]

# -------- FILTRO CATEGORIA --------

if filtro_categoria != "Tutte":

    df_operazioni = df_operazioni[
        df_operazioni["categoria"] == filtro_categoria
    ]

st.dataframe(
    df_operazioni,
    use_container_width=True
)

st.markdown("<br><br>", unsafe_allow_html=True)

# ---------------- USCITE ----------------

uscite_df = df[df["tipo"] == "uscita"]

if not uscite_df.empty:

    grouped = uscite_df.groupby("categoria")["importo"].sum()

    col1, col2 = st.columns(2)

    # -------- PIE --------

    with col1:

        st.subheader("🥧 Distribuzione uscite")

        fig2, ax2 = plt.subplots(figsize=(3, 3))

        grouped.plot(
            kind="pie",
            autopct="%1.1f%%",
            ax=ax2
        )

        ax2.set_ylabel("")

        st.pyplot(
            fig2,
            use_container_width=True
        )

    # -------- BAR --------

    with col2:

        st.subheader("📊 Uscite per categoria")

        fig, ax = plt.subplots(figsize=(4, 3))

        grouped.plot(
            kind="bar",
            ax=ax
        )

        st.pyplot(
            fig,
            use_container_width=True
        )

st.markdown("<br><br>", unsafe_allow_html=True)
