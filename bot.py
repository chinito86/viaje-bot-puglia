import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHEET_ID = os.getenv("SHEET_ID", "1j7KnEFchIFcansWZ2ru7-UocfaNsmwg8p_0LMqeKeyw")
SERVICE_ACCOUNT_JSON_STR = os.getenv("SERVICE_ACCOUNT_JSON")

try:
    SERVICE_ACCOUNT_JSON = json.loads(SERVICE_ACCOUNT_JSON_STR)
except:
    SERVICE_ACCOUNT_JSON = {}

PEOPLE = ["Chinito", "Dieguito", "Pablito", "Ollaze"]
CATEGORIES = ["Alojamiento", "Comida", "Transporte", "Drinks", "Actividades", "Misc"]

def init_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_JSON, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def add_gasto(fecha, persona, categoria, monto, moneda, descripcion):
    try:
        sheet = init_sheets()
        gastos = sheet.worksheet("Gastos")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [fecha, persona, categoria, monto, moneda, descripcion, "", timestamp]
        gastos.append_row(row)
        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

def get_gastos_summary():
    try:
        sheet = init_sheets()
        gastos = sheet.worksheet("Gastos")
        data = gastos.get_all_records()
        resumen = {p: 0 for p in PEOPLE}
        for row in data:
            if row.get("Persona") in PEOPLE:
                try:
                    monto = float(row.get("Monto", 0))
                    resumen[row["Persona"]] += monto
                except:
                    pass
        return resumen
    except Exception as e:
        logger.error(f"Error: {e}")
        return {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🇮🇹 Bot Gastos Puglia 2026\n\n/gasto - Registrar gasto\n/resumen - Ver totales\n/help - Ayuda"
    await update.message.reply_text(msg)

async def cmd_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Formato: /gasto 25 EUR Comida Chinito - Pasta")

async def process_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    pattern = r'/gasto\s+([\d.]+)\s+([A-Z]+)\s+(\w+)\s+(\w+)\s*-?\s*(.*)'
    match = re.match(pattern, text, re.IGNORECASE)
    
    if not match:
        await update.message.reply_text("Formato incorrecto")
        return
    
    monto, moneda, categoria, persona, descripcion = match.groups()
    
    if persona.lower() not in [p.lower() for p in PEOPLE]:
        await update.message.reply_text(f"Persona no valida: {', '.join(PEOPLE)}")
        return
    
    if categoria.lower() not in [c.lower() for c in CATEGORIES]:
        await update.message.reply_text(f"Categoria no valida: {', '.join(CATEGORIES)}")
        return
    
    fecha = datetime.now().strftime("%Y-%m-%d")
    if add_gasto(fecha, persona, categoria, monto, moneda, descripcion):
        msg = f"Gasto registrado:\n{persona}\n{monto} {moneda}\n{categoria}"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Error")

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = get_gastos_summary()
    msg = "RESUMEN:\n\n"
    for persona in PEOPLE:
        total = summary.get(persona, 0)
        msg += f"{persona}: ${total:.2f}\n"
    await update.message.reply_text(msg)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "AYUDA\n\n/gasto - Registrar gasto\n/resumen - Ver totales"
    await update.message.reply_text(msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gasto", cmd_gasto))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.Regex(r"^/gasto"), process_gasto))
    app.add_error_handler(error_handler)
    
    logger.info("Bot iniciado...")
    
    try:
        app.run_polling()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
        app.run_polling()

if __name__ == "__main__":
    main()
