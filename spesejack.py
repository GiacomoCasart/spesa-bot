import os
import csv
import json
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN")

FILE = "spese.csv"
SALDI_FILE = "saldi.json"

CATEGORIE_USCITE = ["cibo", "affitto", "svago", "trasporti", "altro"]
CATEGORIE_ENTRATE = ["stipendio", "regalo", "rimborso", "altro"]

# ---------------- FILE ----------------

def inizializza_file():
    if not os.path.isfile(FILE):
        with open(FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["data", "tipo", "categoria", "importo", "conto"])
            writer.writeheader()

def carica_saldi():
    if os.path.isfile(SALDI_FILE):
        with open(SALDI_FILE, "r") as f:
            return json.load(f)
    else:
        saldi = {"banca": 0, "salvadanaio": 0}
        salva_saldi(saldi)
        return saldi

def salva_saldi(saldi):
    with open(SALDI_FILE, "w") as f:
        json.dump(saldi, f, indent=4)

def salva_spesa(spesa):
    with open(FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["data", "tipo", "categoria", "importo", "conto"])
        writer.writerow(spesa)

SALDI = carica_saldi()

# ---------------- ANALISI ----------------

def calcola_riepilogo_mese(mese):
    entrate = 0
    uscite = 0
    categorie = {}

    if not os.path.isfile(FILE):
        return 0, 0, {}

    with open(FILE, "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r["data"].startswith(mese):
                continue

            imp = float(r["importo"])
            cat = r["categoria"]
            tipo = r["tipo"]

            if tipo == "entrata":
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
        reader = csv.DictReader(f)
        for r in reader:
            mesi.add(r["data"][:7])
    return sorted(mesi, reverse=True)

def ultime_operazioni(n=5):
    if not os.path.isfile(FILE):
        return []

    with open(FILE, "r") as f:
        reader = list(csv.DictReader(f))
        return reader[-n:]

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

    if text == "❌ Annulla":
        context.user_data.clear()
        await update.message.reply_text("Operazione annullata.", reply_markup=menu_principale())
        return

    if text == "📥 Backup":
        await export(update, context)
        return

    if stato == "scegli_mese":
        mese = text
        entrate, uscite, categorie = calcola_riepilogo_mese(mese)

        msg = f"📊 {mese}\n\nEntrate: +{entrate}€\nUscite: -{uscite}€\n\nSaldo: {entrate - uscite}€\n\n"
        for cat, val in categorie.items():
            segno = "+" if val >= 0 else ""
            msg += f"{cat}: {segno}{val}€\n"

        context.user_data.clear()
        await update.message.reply_text(msg, reply_markup=menu_principale())
        return

    if stato == "categoria":
        tipo = context.user_data["tipo"]
        categorie = CATEGORIE_USCITE if tipo == "uscita" else CATEGORIE_ENTRATE

        if text not in categorie:
            keyboard = [[c] for c in categorie] + [["❌ Annulla"]]
            await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return

        context.user_data["categoria"] = text
        context.user_data["stato"] = "conto"

        keyboard = [["banca"], ["salvadanaio"], ["❌ Annulla"]]
        await update.message.reply_text("Conto?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
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
                if SALDI[conto] < importo:
                    await update.message.reply_text("❌ Fondi insufficienti")
                    return
                SALDI[conto] -= importo
            else:
                SALDI[conto] += importo

            salva_saldi(SALDI)

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
            await update.message.reply_text("Inserisci un numero valido")
        return

    # MENU
    if text == "➖ Spesa":
        context.user_data["tipo"] = "uscita"
        context.user_data["stato"] = "categoria"
        keyboard = [[c] for c in CATEGORIE_USCITE] + [["❌ Annulla"]]
        await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    elif text == "➕ Entrata":
        context.user_data["tipo"] = "entrata"
        context.user_data["stato"] = "categoria"
        keyboard = [[c] for c in CATEGORIE_ENTRATE] + [["❌ Annulla"]]
        await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    elif text == "💰 Saldo":
        totale = SALDI["banca"] + SALDI["salvadanaio"]
        await update.message.reply_text(
            f"Banca: {SALDI['banca']}€\nSalvadanaio: {SALDI['salvadanaio']}€\nTotale: {totale}€",
            reply_markup=menu_principale()
        )
        return

    elif text == "📊 Riepilogo":
        mese = datetime.now().strftime("%Y-%m")
        entrate, uscite, categorie = calcola_riepilogo_mese(mese)

        msg = f"📊 {mese}\n\nEntrate: +{entrate}€\nUscite: -{uscite}€\n\nSaldo: {entrate - uscite}€\n\n"
        for cat, val in categorie.items():
            segno = "+" if val >= 0 else ""
            msg += f"{cat}: {segno}{val}€\n"

        await update.message.reply_text(msg, reply_markup=menu_principale())
        return

    elif text == "📂 Storico":
        mesi = lista_mesi()
        if not mesi:
            await update.message.reply_text("Nessun dato", reply_markup=menu_principale())
            return

        msg = "Mesi disponibili:\n" + "\n".join(mesi)
        msg += "\n\nScrivi il mese (es: 2026-05)"
        context.user_data["stato"] = "scegli_mese"
        await update.message.reply_text(msg)
        return

    elif text == "🧾 Ultime":
        ops = ultime_operazioni()
        if not ops:
            await update.message.reply_text("Nessuna operazione", reply_markup=menu_principale())
            return

        msg = "🧾 Ultime operazioni:\n\n"
        for o in ops:
            segno = "+" if o["tipo"] == "entrata" else "-"
            msg += f"{o['data']} | {o['categoria']} | {segno}{o['importo']}€\n"

        await update.message.reply_text(msg, reply_markup=menu_principale())
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
