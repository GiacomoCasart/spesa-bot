import os
import csv
import asyncio
import psycopg2
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN")
FILE = "spese.csv"

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

CATEGORIE_USCITE = ["cibo", "affitto", "svago", "trasporti", "alcohol", "terapia", "e-cig", "altro"]
CATEGORIE_ENTRATE = ["stipendio", "regalo", "rimborso", "altro"]

# ---------------- FILE ----------------

def inizializza_file():
    if not os.path.isfile(FILE):
        with open(FILE, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["data", "tipo", "categoria", "importo", "conto"]
            )
            writer.writeheader()

def salva_spesa(spesa):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO spese (data, tipo, categoria, importo, conto)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        spesa["data"],
        spesa["tipo"],
        spesa["categoria"],
        spesa["importo"],
        spesa["conto"]
    ))

    conn.commit()
    cur.close()
    conn.close()

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS spese (
        id SERIAL PRIMARY KEY,
        data TEXT,
        tipo TEXT,
        categoria TEXT,
        importo FLOAT,
        conto TEXT
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

# ---------------- UTILS ----------------

def parse_importo(val):
    try:
        return float(val)
    except:
        return 0.0

def parse_conto(val):
    return val.strip().lower()

# ---------------- SALDO ----------------

def calcola_saldi():
    saldi = {"banca": 0, "salvadanaio": 0}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT tipo, importo, conto FROM spese")

    for tipo, imp, conto in cur.fetchall():

        if conto not in saldi:
            continue

        if tipo == "entrata":
            saldi[conto] += imp
        else:
            saldi[conto] -= imp

    cur.close()
    conn.close()

    return saldi

def calcola_saldo_fino_a(mese):
    saldi = {"banca": 0, "salvadanaio": 0}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT tipo, importo, conto, data
        FROM spese
    """)

    for tipo, imp, conto, data in cur.fetchall():

        if data[:7] > mese:
            continue

        if conto not in saldi:
            continue

        if tipo == "entrata":
            saldi[conto] += imp
        else:
            saldi[conto] -= imp

    cur.close()
    conn.close()

    return saldi

# ---------------- ANALISI ----------------

def calcola_riepilogo_mese(mese):
    entrate, uscite, categorie = 0, 0, {}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT tipo, categoria, importo
        FROM spese
        WHERE data LIKE %s
    """, (f"{mese}%",))

    for tipo, cat, imp in cur.fetchall():

        if tipo == "entrata":
            entrate += imp
            categorie[cat] = categorie.get(cat, 0) + imp
        else:
            uscite += imp
            categorie[cat] = categorie.get(cat, 0) - imp

    cur.close()
    conn.close()

    return entrate, uscite, categorie

def lista_mesi():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT data FROM spese")

    mesi = set()

    for (data,) in cur.fetchall():
        mesi.add(data[:7])

    cur.close()
    conn.close()

    return sorted(mesi, reverse=True)

def ultime_operazioni(n=5):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT data, tipo, categoria, importo
        FROM spese
        ORDER BY id DESC
        LIMIT %s
    """, (n,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    ops = []

    for data, tipo, categoria, importo in rows:
        ops.append({
            "data": data,
            "tipo": tipo,
            "categoria": categoria,
            "importo": importo
        })

    return reversed(ops)

# ---------------- UI ----------------

def menu_principale():
    return ReplyKeyboardMarkup([
        ["➖ Spesa", "➕ Entrata"],
        ["💰 Saldo", "📊 Riepilogo"],
        ["📂 Storico", "🧾 Ultime"],
        ["📥 Backup", "❌ Annulla"]
    ], resize_keyboard=True)

# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cosa vuoi fare?", reply_markup=menu_principale())

async def export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.isfile(FILE):
        await update.message.reply_text("Nessun file disponibile")
        return

    with open(FILE, "rb") as f:
        await update.message.reply_document(f, filename="spese.csv")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    stato = context.user_data.get("stato")

    # -------- ANNULLA --------
    if text == "❌ Annulla":
        context.user_data.clear()
        await update.message.reply_text("Operazione annullata.", reply_markup=menu_principale())
        return

    # -------- BACKUP --------
    if text == "📥 Backup":
        await export(update, context)
        return

    # -------- MENU --------

    if text == "➖ Spesa":
        context.user_data.clear()
        context.user_data.update({"tipo": "uscita", "stato": "categoria"})

        kb = [[c] for c in CATEGORIE_USCITE] + [["❌ Annulla"]]
        await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text == "➕ Entrata":
        context.user_data.clear()
        context.user_data.update({"tipo": "entrata", "stato": "categoria"})

        kb = [[c] for c in CATEGORIE_ENTRATE] + [["❌ Annulla"]]
        await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text == "💰 Saldo":
        saldi = calcola_saldi()
        tot = saldi["banca"] + saldi["salvadanaio"]

        await update.message.reply_text(
            f"Banca: {saldi['banca']}€\nSalvadanaio: {saldi['salvadanaio']}€\nTotale: {tot}€",
            reply_markup=menu_principale()
        )
        return

    if text == "📊 Riepilogo":
        mese = datetime.now().strftime("%Y-%m")
        e, u, c = calcola_riepilogo_mese(mese)

        msg = f"📊 {mese}\n\nEntrate: +{e}€\nUscite: -{u}€\nSaldo mese: {e-u}€\n\n"
        for k, v in c.items():
            msg += f"{k}: {'+' if v >= 0 else ''}{v}€\n"

        await update.message.reply_text(msg, reply_markup=menu_principale())
        return

    if text == "📂 Storico":
        mesi = lista_mesi()
        if not mesi:
            await update.message.reply_text("Nessun dato", reply_markup=menu_principale())
            return

        msg = "📂 Storico:\n\n"

        for mese in mesi:
            saldo = calcola_saldo_fino_a(mese)
            totale = saldo["banca"] + saldo["salvadanaio"]

            msg += f"{mese} → {totale}€ (B:{saldo['banca']} S:{saldo['salvadanaio']})\n"

        await update.message.reply_text(msg, reply_markup=menu_principale())
        return

    if text == "🧾 Ultime":
        ops = ultime_operazioni()

        if not ops:
            await update.message.reply_text("Nessuna operazione", reply_markup=menu_principale())
            return

        msg = "🧾 Ultime:\n\n"
        for o in ops:
            msg += f"{o['data']} | {o['categoria']} | {'+' if o['tipo']=='entrata' else '-'}{o['importo']}€\n"

        await update.message.reply_text(msg, reply_markup=menu_principale())
        return

    # -------- STATI --------

    if stato == "categoria":
        tipo = context.user_data["tipo"]
        categorie = CATEGORIE_USCITE if tipo == "uscita" else CATEGORIE_ENTRATE

        if text not in categorie:
            kb = [[c] for c in categorie] + [["❌ Annulla"]]
            await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
            return

        context.user_data["categoria"] = text
        context.user_data["stato"] = "conto"

        kb = [["banca"], ["salvadanaio"], ["❌ Annulla"]]
        await update.message.reply_text("Conto?", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if stato == "conto":
        if text not in ["banca", "salvadanaio"]:
            await update.message.reply_text("Scegli banca o salvadanaio")
            return

        context.user_data["conto"] = text
        context.user_data["stato"] = "importo"

        await update.message.reply_text("Importo?", reply_markup=ReplyKeyboardMarkup([["❌ Annulla"]], resize_keyboard=True))
        return

    if stato == "importo":
        try:
            importo = float(text)
            tipo = context.user_data["tipo"]
            conto = context.user_data["conto"]

            if tipo == "uscita":
                saldi = calcola_saldi()
                if saldi[conto] < importo:
                    await update.message.reply_text("❌ Fondi insufficienti")
                    return

            salva_spesa({
                "data": datetime.now().strftime("%Y-%m-%d"),
                "tipo": tipo,
                "categoria": context.user_data["categoria"],
                "importo": importo,
                "conto": conto
            })

            context.user_data.clear()
            await update.message.reply_text("✅ Salvato!", reply_markup=menu_principale())

        except:
            await update.message.reply_text("Numero non valido")
        return

    await update.message.reply_text("Usa i pulsanti.", reply_markup=menu_principale())

# ---------------- START BOT ----------------

inizializza_file()
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", start))
app.add_handler(CommandHandler("export", export))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

loop.run_until_complete(app.initialize())
loop.run_until_complete(app.start())

# ---------------- WEB SERVER ----------------

flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)

    loop.run_until_complete(app.process_update(update))

    return "ok"

@flask_app.route("/")
def home():
    return "Bot online"

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=10000)
