import os
import csv
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN")
FILE = "spese.csv"

CATEGORIE_USCITE = ["cibo", "affitto", "svago", "trasporti", "altro"]
CATEGORIE_ENTRATE = ["stipendio", "regalo", "rimborso", "altro"]

# ---------------- FILE ----------------

def inizializza_file():
    if not os.path.isfile(FILE):
        with open(FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["data", "tipo", "categoria", "importo", "conto"])
            writer.writeheader()

def salva_spesa(spesa):
    with open(FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["data", "tipo", "categoria", "importo", "conto"])
        writer.writerow(spesa)

# ---------------- SALDO ----------------

def calcola_saldi():
    saldi = {"banca": 0, "salvadanaio": 0}

    if not os.path.isfile(FILE):
        return saldi

    with open(FILE, "r") as f:
        for r in csv.DictReader(f):
            conto = r["conto"].strip().lower()
            if conto not in saldi:
                continue

            imp = float(r["importo"])

            if r["tipo"] == "entrata":
                saldi[conto] += imp
            else:
                saldi[conto] -= imp

    return saldi

def calcola_saldo_fino_a(mese):
    saldi = {"banca": 0, "salvadanaio": 0}

    with open(FILE, "r") as f:
        for r in csv.DictReader(f):
            if r["data"][:7] > mese:
                continue

            conto = r["conto"].strip().lower()
            if conto not in saldi:
                continue

            imp = float(r["importo"])

            if r["tipo"] == "entrata":
                saldi[conto] += imp
            else:
                saldi[conto] -= imp

    return saldi

# ---------------- ANALISI ----------------

def calcola_riepilogo_mese(mese):
    entrate, uscite, categorie = 0, 0, {}

    if not os.path.isfile(FILE):
        return 0, 0, {}

    with open(FILE, "r") as f:
        for r in csv.DictReader(f):
            if not r["data"].startswith(mese):
                continue

            imp = float(r["importo"])
            cat = r["categoria"]

            if r["tipo"] == "entrata":
                entrate += imp
                categorie[cat] = categorie.get(cat, 0) + imp
            else:
                uscite += imp
                categorie[cat] = categorie.get(cat, 0) - imp

    return entrate, uscite, categorie

def lista_mesi():
    if not os.path.isfile(FILE):
        return []

    mesi = set()
    with open(FILE, "r") as f:
        for r in csv.DictReader(f):
            mesi.add(r["data"][:7])
    return sorted(mesi, reverse=True)

def ultime_operazioni(n=5):
    if not os.path.isfile(FILE):
        return []
    with open(FILE, "r") as f:
        return list(csv.DictReader(f))[-n:]

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

    # ANNULLA
    if text == "❌ Annulla":
        context.user_data.clear()
        await update.message.reply_text("Operazione annullata.", reply_markup=menu_principale())
        return

    # BACKUP
    if text == "📥 Backup":
        await export(update, context)
        return

    # MENU
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
        e,u,c = calcola_riepilogo_mese(mese)

        await update.message.reply_text(
            f"📊 {mese}\n\nEntrate: +{e}€\nUscite: -{u}€\nSaldo mese: {e-u}€",
            reply_markup=menu_principale()
        )
        return

    if text == "📂 Storico":
        mesi = lista_mesi()
        if not mesi:
            await update.message.reply_text("Nessun dato", reply_markup=menu_principale())
            return

        context.user_data.clear()
        context.user_data["stato"] = "scegli_mese"
        await update.message.reply_text("Mesi:\n"+"\n".join(mesi))
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

    # STATI
    if stato == "scegli_mese":
        e,u,c = calcola_riepilogo_mese(text)
        saldo = calcola_saldo_fino_a(text)
        totale = saldo["banca"] + saldo["salvadanaio"]

        msg = f"📊 {text}\n\nEntrate: +{e}€\nUscite: -{u}€\nSaldo mese: {e-u}€\nSaldo totale: {totale}€"

        context.user_data.clear()
        await update.message.reply_text(msg, reply_markup=menu_principale())
        return

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

# ---------------- WEBHOOK ----------------

inizializza_file()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", start))
app.add_handler(CommandHandler("export", export))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

loop = asyncio.get_event_loop()

async def setup():
    await app.initialize()
    await app.start()

loop.run_until_complete(setup())

flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)
    loop.create_task(app.process_update(update))
    return "ok"

@flask_app.route("/")
def home():
    return "Bot online"

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=10000)
