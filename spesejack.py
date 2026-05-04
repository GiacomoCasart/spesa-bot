import os
import csv
import json
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
            writer = csv.DictWriter(
                f,
                fieldnames=["data", "tipo", "categoria", "importo", "conto"]
            )
            writer.writeheader()

def carica_saldi():
    if os.path.isfile(SALDI_FILE):
        with open(SALDI_FILE, "r") as f:
            return json.load(f)
    else:
        saldi = {"banca": 558, "salvadanaio": 732}
        salva_saldi(saldi)
        return saldi

def salva_saldi(saldi):
    with open(SALDI_FILE, "w") as f:
        json.dump(saldi, f, indent=4)

def salva_spesa(spesa):
    with open(FILE, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["data", "tipo", "categoria", "importo", "conto"]
        )
        writer.writerow(spesa)

SALDI = carica_saldi()

# ---------------- ANALISI DATI ----------------

def calcola_riepilogo_mese(mese):
    entrate = 0
    uscite = 0
    categorie = {}

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
    mesi = set()
    with open(FILE, "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            mesi.add(r["data"][:7])
    return sorted(mesi, reverse=True)

def ultime_operazioni(n=5):
    with open(FILE, "r") as f:
        reader = list(csv.DictReader(f))
        return reader[-n:]

# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["➖ Spesa", "➕ Entrata"],
        ["💰 Saldo", "📊 Riepilogo"],
        ["📂 Storico", "🧾 Ultime"],
        ["❌ Annulla"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    context.user_data.clear()
    await update.message.reply_text("Cosa vuoi fare?", reply_markup=reply_markup)

async def scegli_categoria(update, context):
    if context.user_data["tipo"] == "uscita":
        categorie = CATEGORIE_USCITE
    else:
        categorie = CATEGORIE_ENTRATE

    keyboard = [[c] for c in categorie]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    context.user_data["stato"] = "categoria"
    await update.message.reply_text("Scegli categoria:", reply_markup=reply_markup)

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "❌ Annulla":
        context.user_data.clear()

        keyboard = [
            ["➖ Spesa", "➕ Entrata"],
            ["💰 Saldo", "📊 Riepilogo"],
            ["📂 Storico", "🧾 Ultime"],
            ["❌ Annulla"]
        ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text("Operazione annullata.", reply_markup=reply_markup)
        return
    
    if text == "➖ Spesa":
        context.user_data["tipo"] = "uscita"
        await scegli_categoria(update, context)

    elif text == "➕ Entrata":
        context.user_data["tipo"] = "entrata"
        await scegli_categoria(update, context)

    elif text == "💰 Saldo":
        totale = SALDI["banca"] + SALDI["salvadanaio"]
        await update.message.reply_text(
            f"Banca: {SALDI['banca']}€\nSalvadanaio: {SALDI['salvadanaio']}€\nTotale: {totale}€"
        )

    elif text == "📊 Riepilogo":
        mese = datetime.now().strftime("%Y-%m")
        entrate, uscite, categorie = calcola_riepilogo_mese(mese)

        msg = f"📊 {mese}\n\nEntrate: +{entrate}€\nUscite: -{uscite}€\n\nSaldo: {entrate - uscite}€\n\n"
        for cat, val in categorie.items():
            segno = "+" if val >= 0 else ""
            msg += f"{cat}: {segno}{val}€\n"

        await update.message.reply_text(msg)

    elif text == "📂 Storico":
        mesi = lista_mesi()
        if not mesi:
            await update.message.reply_text("Nessun dato")
            return

        msg = "Mesi disponibili:\n" + "\n".join(mesi)
        msg += "\n\nScrivi il mese (es: 2026-05)"
        context.user_data["stato"] = "scegli_mese"
        await update.message.reply_text(msg)

    elif context.user_data.get("stato") == "scegli_mese":
        mese = text
        entrate, uscite, categorie = calcola_riepilogo_mese(mese)

        msg = f"📊 {mese}\n\nEntrate: +{entrate}€\nUscite: -{uscite}€\n\nSaldo: {entrate - uscite}€\n\n"
        for cat, val in categorie.items():
            segno = "+" if val >= 0 else ""
            msg += f"{cat}: {segno}{val}€\n"

        context.user_data.clear()
        await update.message.reply_text(msg)

    elif context.user_data.get("stato") == "categoria":
        if text == "altro":
            context.user_data["stato"] = "categoria_custom"
            await update.message.reply_text("Scrivi categoria:")
        else:
            context.user_data["categoria"] = text
            context.user_data["stato"] = "conto"
            await update.message.reply_text("Conto? (banca/salvadanaio)")

    elif context.user_data.get("stato") == "categoria_custom":
        context.user_data["categoria"] = text
        context.user_data["stato"] = "conto"
        await update.message.reply_text("Conto? (banca/salvadanaio)")

    elif context.user_data.get("stato") == "conto":
        if text not in ["banca", "salvadanaio"]:
            await update.message.reply_text("Scrivi: banca o salvadanaio")
            return

        context.user_data["conto"] = text
        context.user_data["stato"] = "importo"
        await update.message.reply_text("Importo?")

    elif context.user_data.get("stato") == "importo":
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

            spesa = {
                "data": datetime.now().strftime("%Y-%m-%d"),
                "tipo": tipo,
                "categoria": context.user_data["categoria"],
                "importo": importo,
                "conto": conto
            }

            salva_spesa(spesa)

            context.user_data.clear()
            await update.message.reply_text("✅ Salvato!")

        except:
            await update.message.reply_text("Numero non valido")

# ---------------- WEBHOOK ----------------

inizializza_file()

app = ApplicationBuilder().token(TOKEN).build()
import asyncio

async def setup():
    await app.initialize()

asyncio.run(setup())

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    import asyncio

    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)

    asyncio.run(app.process_update(update))

    return "ok"

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=10000)
