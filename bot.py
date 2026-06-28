import os
import json
import logging
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
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
except Exception as e:
    logger.error(f"Error parsing SERVICE_ACCOUNT_JSON: {e}")
    SERVICE_ACCOUNT_JSON = {}

PEOPLE = ["Chinito", "Dieguito", "Pablito", "Ollaze"]
CATEGORIES = ["Alojamiento", "Comida", "Transporte", "Drinks", "Actividades", "Misc"]

# Mapeo de usernames a personas
USERNAME_MAP = {
    "dz": "Dieguito",
    "tominatomina": "Ollaze",
    "chinitocava": "Chinito",
    "pablitodm": "Pablito"
}

def init_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_JSON, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID)
    except Exception as e:
        logger.error(f"Error init_sheets: {e}")
        return None

def add_gasto(fecha, persona, categoria, monto, moneda, descripcion):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        gastos = sheet.worksheet("Gastos")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [fecha, persona, categoria, monto, moneda, descripcion, "", timestamp]
        gastos.append_row(row)
        logger.info(f"Gasto: {persona} {monto} {moneda}")
        return True
    except Exception as e:
        logger.error(f"Error add_gasto: {e}")
        return False

def get_gastos_summary():
    try:
        sheet = init_sheets()
        if not sheet:
            logger.error("No se pudo conectar a Sheets")
            return {}
        gastos = sheet.worksheet("Gastos")
        data = gastos.get_all_records()
        
        logger.info(f"Leyendo {len(data)} filas de Gastos")
        if data:
            logger.info(f"Headers: {list(data[0].keys())}")
        
        resumen = {p: 0 for p in PEOPLE}
        
        for i, row in enumerate(data):
            row_clean = {k.strip(): v for k, v in row.items()}
            logger.info(f"Fila {i}: {row_clean}")
            
            persona_raw = row_clean.get("Persona", "").strip()
            monto_str = row_clean.get("Monto", "0")
            
            # Buscar la persona correcta en PEOPLE
            persona_match = None
            for p in PEOPLE:
                if p.lower() == persona_raw.lower():
                    persona_match = p
                    break
            
            if persona_match:
                try:
                    monto = float(str(monto_str).strip() or 0)
                    resumen[persona_match] += monto
                    logger.info(f"Agregado: {persona_match} + {monto}")
                except Exception as e:
                    logger.error(f"Error parsing monto '{monto_str}': {e}")
        
        logger.info(f"Resumen final: {resumen}")
        return resumen
    except Exception as e:
        logger.error(f"Error get_gastos_summary: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "Bot Gastos Puglia 2026\n\n/gasto - Registrar gasto\n/resumen - Ver totales\n/help - Ayuda"
    await update.message.reply_text(msg)

async def process_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    username = update.message.from_user.username
    
    # Auto-detectar persona por username
    persona_auto = USERNAME_MAP.get(username.lower()) if username else None
    
    # Patrón más flexible
    pattern = r'/gasto\s+(.+)'
    match = re.match(pattern, text, re.IGNORECASE)
    
    if not match:
        # Si solo escribió /gasto, usar persona auto-detectada
        if persona_auto:
            await update.message.reply_text(f"Persona detectada: {persona_auto}\n\nFormato: /gasto 25 EUR comida - descripcion")
        else:
            await update.message.reply_text("Formato: /gasto 25 EUR comida chinito - descripcion")
        return
    
    # Parsear: "25 EUR comida chinito - test"
    args_text = match.group(1)
    parts = args_text.split()
    
    if len(parts) < 3:
        await update.message.reply_text("Formato: /gasto 25 EUR comida [persona] - descripcion")
        return
    
    monto = parts[0]
    moneda = parts[1]
    categoria = parts[2]
    
    # Si hay 4+ partes, la 4ta es persona. Si no, usar auto-detectada
    if len(parts) >= 4 and parts[3].lower() in [p.lower() for p in PEOPLE]:
        persona = parts[3]
        descripcion = " ".join(parts[4:]) if len(parts) > 4 else ""
    elif persona_auto:
        persona = persona_auto
        descripcion = " ".join(parts[3:]) if len(parts) > 3 else ""
    else:
        await update.message.reply_text("Persona no especificada y no detectada por username")
        return
    
    # Limpiar descripción (remover guión al inicio si existe)
    if descripcion.startswith("-"):
        descripcion = descripcion[1:].strip()
    
    if persona.lower() not in [p.lower() for p in PEOPLE]:
        await update.message.reply_text(f"Persona invalida. Usa: {', '.join(PEOPLE)}")
        return
    
    if categoria.lower() not in [c.lower() for c in CATEGORIES]:
        await update.message.reply_text(f"Categoria invalida. Usa: {', '.join(CATEGORIES)}")
        return
    
    fecha = datetime.now().strftime("%Y-%m-%d")
    if add_gasto(fecha, persona, categoria, monto, moneda, descripcion):
        msg = f"Gasto registrado:\n{persona}\n{monto} {moneda}\n{categoria}"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Error al guardar")

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = get_gastos_summary()
    msg = "RESUMEN:\n\n"
    for persona in PEOPLE:
        total = summary.get(persona, 0)
        msg += f"{persona}: ${total:.2f}\n"
    await update.message.reply_text(msg)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """AYUDA

/gasto - Registrar gasto
Formato: /gasto 25 EUR comida - descripcion

Ejemplos:
/gasto 25 EUR comida - Pasta en Bari
/gasto 45 EUR transporte - Uber desde hotel
/gasto 10 EUR drinks - Cerveza en playa

Después del - puedes escribir cualquier cosa como descripción.

Categorías: Alojamiento, Comida, Transporte, Drinks, Actividades, Misc
Monedas: EUR, USD, ARS

/resumen - Ver totales por persona"""
    await update.message.reply_text(msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot running')
    
    def log_message(self, format, *args):
        pass

def main():
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            app = Application.builder().token(TELEGRAM_TOKEN).build()
            
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("resumen", cmd_resumen))
            app.add_handler(CommandHandler("help", cmd_help))
            app.add_handler(MessageHandler(filters.Regex(r"^/gasto"), process_gasto))
            app.add_error_handler(error_handler)
            
            port = int(os.getenv("PORT", 10000))
            server = HTTPServer(('0.0.0.0', port), HealthHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            logger.info(f"Health check puerto {port}")
            logger.info("Bot iniciado - intento {}/{}".format(retry_count + 1, max_retries))
            
            try:
                app.run_polling()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())
                app.run_polling()
                
        except Exception as e:
            retry_count += 1
            logger.error(f"Error en bot (intento {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                logger.info(f"Reintentando en 10 segundos...")
                time.sleep(10)
            else:
                logger.error("Máximo de reintentos alcanzado")
                raise

if __name__ == "__main__":
    main()
