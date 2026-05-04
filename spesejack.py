import os
import csv
import json
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

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

# ---------------- UI ----------------

def menu_principale():
    return ReplyKeyboardMarkup([
        ["➖ Spesa", "➕ Entrata"],
        ["💰 Saldo", "📊 Riepilogo"],
        ["📂 Storico", "🧾 Ultime"],
        ["❌ Annulla"]
    ], resize_keyboard=True)

# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cosa vuoi fare?", reply_markup=menu_principale())

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    stato = context.user_data.get("stato")

    # -------- ANNULLA --------
    if text == "❌ Annulla":
        context.user_data.clear()
        await update.message.reply_text("Operazione annullata.", reply_markup=menu_principale())
        return

    # -------- MENU --------
    if text == "➖ Spesa":
        context.user_data["tipo"] = "uscita"
        context.user_data["stato"] = "categoria"

    elif text == "➕ Entrata":
        context.user_data["tipo"] = "entrata"
        context.user_data["stato"] = "categoria"

    elif text == "💰 Saldo":
        totale = SALDI["banca"] + SALDI["salvadanaio"]
        await update.message.reply_text(
            f"Banca: {SALDI['banca']}€\nSalvadanaio: {SALDI['salvadanaio']}€\nTotale: {totale}€",
            reply_markup=menu_principale()
        )
        return

    # -------- CATEGORIA --------
    if context.user_data.get("stato") == "categoria":
        tipo = context.user_data["tipo"]
        categorie = CATEGORIE_USCITE if tipo == "uscita" else CATEGORIE_ENTRATE

        if text not in categorie and text != "altro":
            keyboard = [[c] for c in categorie] + [["❌ Annulla"]]
            await update.message.reply_text("Scegli categoria:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return

        context.user_data["categoria"] = text
        context.user_data["stato"] = "conto"

        keyboard = [["banca"], ["salvadanaio"], ["❌ Annulla"]]
        await update.message.reply_text("Conto?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    # -------- CONTO --------
    if stato == "conto":
        if text not in ["banca", "salvadanaio"]:
            await update.message.reply_text("Scegli banca o salvadanaio")
            return

        context.user_data["conto"] = text
        context.user_data["stato"] = "importo"

        await update.message.reply_text("Importo?", reply_markup=ReplyKeyboardMarkup([["❌ Annulla"]], resize_keyboard=True))
        return

    # -------- IMPORTO --------
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

    # -------- FALLBACK --------
    await update.message.reply_text("Usa i pulsanti.", reply_markup=menu_principale())

# ---------------- WEBHOOK ----------------

inizializza_file()

app = ApplicationBuilder().token(TOKEN).build()

async def setup():
    await app.initialize()

asyncio.run(setup())

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", start)) 
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)
    asyncio.run(app.process_update(update))
    return "ok"

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=10000)
