async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    stato = context.user_data.get("stato")

    # -------- ANNULLA --------
    if text == "❌ Annulla":
        context.user_data.clear()
        await update.message.reply_text("Operazione annullata.", reply_markup=menu_principale())
        return

    # -------- STATI (PRIORITÀ) --------

    # selezione mese
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

    # categoria
    if stato == "categoria":
        tipo = context.user_data["tipo"]
        categorie = CATEGORIE_USCITE if tipo == "uscita" else CATEGORIE_ENTRATE

        if text not in categorie and text != "altro":
            keyboard = [[c] for c in categorie] + [["❌ Annulla"]]
            await update.message.reply_text(
                "Scegli categoria:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        context.user_data["categoria"] = text
        context.user_data["stato"] = "conto"

        keyboard = [["banca"], ["salvadanaio"], ["❌ Annulla"]]
        await update.message.reply_text(
            "Conto?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # conto
    if stato == "conto":
        if text not in ["banca", "salvadanaio"]:
            await update.message.reply_text("Scegli banca o salvadanaio")
            return

        context.user_data["conto"] = text
        context.user_data["stato"] = "importo"

        await update.message.reply_text(
            "Importo?",
            reply_markup=ReplyKeyboardMarkup([["❌ Annulla"]], resize_keyboard=True)
        )
        return

    # importo
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

    # -------- MENU (DOPO GLI STATI) --------

    if text == "➖ Spesa":
        context.user_data["tipo"] = "uscita"
        context.user_data["stato"] = "categoria"

        categorie = CATEGORIE_USCITE
        keyboard = [[c] for c in categorie] + [["❌ Annulla"]]

        await update.message.reply_text(
            "Scegli categoria:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    elif text == "➕ Entrata":
        context.user_data["tipo"] = "entrata"
        context.user_data["stato"] = "categoria"

        categorie = CATEGORIE_ENTRATE
        keyboard = [[c] for c in categorie] + [["❌ Annulla"]]

        await update.message.reply_text(
            "Scegli categoria:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
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

    # -------- FALLBACK --------
    await update.message.reply_text("Usa i pulsanti.", reply_markup=menu_principale())
