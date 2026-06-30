import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import asyncio
import requests

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
EVENT_TYPES = ["Vuelo", "Tren", "Rent a Car", "Hospedaje", "Excursion", "Comida", "Reserva"]

USERNAME_MAP = {
    "dz": "Dieguito",
    "tominatomina": "Ollaze",
    "chinitocava": "Chinito",
    "pablodmmm": "Pablito"
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

# ===== GASTOS =====
def add_gasto(fecha, persona, categoria, monto, moneda, descripcion):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        gastos = sheet.worksheet("Gastos")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [fecha, persona, categoria, monto, moneda, descripcion, "", timestamp]
        gastos.append_row(row)
        logger.info(f"✅ Gasto: {persona} {monto} {moneda}")
        return True
    except Exception as e:
        logger.error(f"Error add_gasto: {e}")
        return False

def get_gastos_list():
    try:
        sheet = init_sheets()
        if not sheet:
            return []
        gastos = sheet.worksheet("Gastos")
        data = gastos.get_all_records()
        return data
    except Exception as e:
        logger.error(f"Error get_gastos_list: {e}")
        return []

def delete_gasto(index):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        gastos = sheet.worksheet("Gastos")
        gastos.delete_rows(index + 2)
        logger.info(f"✅ Gasto eliminado: fila {index + 2}")
        return True
    except Exception as e:
        logger.error(f"Error delete_gasto: {e}")
        return False

def get_gastos_summary():
    try:
        sheet = init_sheets()
        if not sheet:
            return {}
        gastos = sheet.worksheet("Gastos")
        data = gastos.get_all_records()
        
        resumen = {p: 0 for p in PEOPLE}
        
        for row in data:
            row_clean = {k.strip(): v for k, v in row.items()}
            persona_raw = row_clean.get("Persona", "").strip()
            monto_str = row_clean.get("Monto", "0")
            
            persona_match = None
            for p in PEOPLE:
                if p.lower() == persona_raw.lower():
                    persona_match = p
                    break
            
            if persona_match:
                try:
                    monto = float(str(monto_str).strip() or 0)
                    resumen[persona_match] += monto
                except Exception as e:
                    logger.error(f"Error parsing monto: {e}")
        
        return resumen
    except Exception as e:
        logger.error(f"Error get_gastos_summary: {e}")
        return {}

# ===== EVENTOS =====
def parse_fecha(fecha_str, year=2026):
    """Parsea fechas flexibles: 23-07, 23/07, 23.07, 2026-07-23"""
    try:
        formatos = ["%d-%m-%Y", "%d-%m", "%d/%m/%Y", "%d/%m", "%d.%m.%Y", "%d.%m", "%Y-%m-%d"]
        for fmt in formatos:
            try:
                dt = datetime.strptime(fecha_str, fmt)
                if dt.year == 1900:
                    dt = dt.replace(year=year)
                return dt.date()
            except:
                continue
        return None
    except Exception as e:
        logger.error(f"Error parse_fecha: {e}")
        return None

def add_evento(fecha, hora, tipo, lugar, descripcion="", ref="", maps_link="", voucher_link=""):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        eventos = sheet.worksheet("Eventos")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            f"{fecha} {hora}",
            tipo,
            f"{lugar} {descripcion}".strip(),
            ref,
            "",
            "",
            maps_link,
            voucher_link,
            "2h",
            timestamp
        ]
        eventos.append_row(row)
        logger.info(f"✅ Evento: {tipo} {lugar}")
        return True
    except Exception as e:
        logger.error(f"Error add_evento: {e}")
        return False

def get_eventos_list():
    try:
        sheet = init_sheets()
        if not sheet:
            return []
        eventos = sheet.worksheet("Eventos")
        data = eventos.get_all_records()
        return data
    except Exception as e:
        logger.error(f"Error get_eventos_list: {e}")
        return []

def get_eventos_by_date(fecha):
    try:
        eventos = get_eventos_list()
        resultado = []
        for e in eventos:
            evento_fecha = e.get("Fecha/Hora", "").split()[0]
            if evento_fecha == str(fecha):
                resultado.append(e)
        return sorted(resultado, key=lambda x: x.get("Fecha/Hora", ""))
    except Exception as e:
        logger.error(f"Error get_eventos_by_date: {e}")
        return []

def generate_maps_link(tipo, lugar):
    """Genera link a Google Maps más específico según tipo de evento"""
    tipo_lower = tipo.lower()
    
    # Agregar contexto según tipo
    if "hospedaje" in tipo_lower or "hotel" in tipo_lower:
        busqueda = f"Hotel {lugar}"
    elif "vuelo" in tipo_lower or "aeropuerto" in tipo_lower:
        busqueda = f"Aeropuerto {lugar}"
    elif "tren" in tipo_lower or "estacion" in tipo_lower:
        busqueda = f"Estación {lugar}"
    elif "rent" in tipo_lower or "auto" in tipo_lower:
        busqueda = f"Rent a Car {lugar}"
    elif "comida" in tipo_lower or "restaurante" in tipo_lower:
        busqueda = f"Restaurante {lugar}"
    else:
        busqueda = lugar
    
    return f"https://www.google.com/maps/search/{busqueda.replace(' ', '+')}"

# ===== COMANDOS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🤖 Bot Gastos Puglia 2026\n\n💰 /gasto - Registrar gasto\n📊 /resumen - Ver totales\n🗓️ /evento - Agregar evento\n📅 /calendario - Ver eventos\n🕐 /hoy - Eventos hoy\n❓ /help - Ayuda"
    await update.message.reply_text(msg)

async def process_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    username = update.message.from_user.username
    persona_auto = USERNAME_MAP.get(username.lower()) if username else None
    
    pattern = r'/gasto\s+(.+)'
    match = re.match(pattern, text, re.IGNORECASE)
    
    if not match:
        if persona_auto:
            await update.message.reply_text(f"👤 Detectado: {persona_auto}\n💬 Formato: /gasto 25 EUR comida - descripcion")
        else:
            await update.message.reply_text("💬 Formato: /gasto 25 EUR comida persona - descripcion")
        return
    
    args_text = match.group(1)
    parts = args_text.split()
    
    if len(parts) < 3:
        await update.message.reply_text("💬 Mínimo: /gasto MONTO MONEDA CATEGORIA")
        return
    
    monto = parts[0]
    moneda = parts[1]
    categoria = parts[2]
    descripcion = " ".join(parts[3:]) if len(parts) > 3 else ""
    
    # Extraer persona si está en descripción
    persona_match = None
    for p in PEOPLE:
        if p.lower() in descripcion.lower():
            persona_match = p
            break
    
    if not persona_match and persona_auto:
        persona_match = persona_auto
    
    if not persona_match:
        await update.message.reply_text(f"⚠️ Persona no detectada. Menciona: {', '.join(PEOPLE)}")
        return
    
    if categoria.lower() not in [c.lower() for c in CATEGORIES]:
        await update.message.reply_text(f"⚠️ Categoría inválida: {', '.join(CATEGORIES)}")
        return
    
    if descripcion.startswith("-"):
        descripcion = descripcion[1:].strip()
    
    fecha = datetime.now().strftime("%Y-%m-%d")
    if add_gasto(fecha, persona_match, categoria, monto, moneda, descripcion):
        msg = f"✅ Gasto registrado:\n👤 {persona_match}\n💵 {monto} {moneda}\n🏷️ {categoria}"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Error al guardar")

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = get_gastos_summary()
    msg = "📊 RESUMEN:\n\n"
    for persona in PEOPLE:
        total = summary.get(persona, 0)
        msg += f"👤 {persona}: 💵 ${total:.2f}\n"
    await update.message.reply_text(msg)

async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "/borrar":
        gastos = get_gastos_list()
        if not gastos:
            await update.message.reply_text("📭 Sin gastos")
            return
        
        ultimos = gastos[-5:] if len(gastos) > 5 else gastos
        msg = "🗑️ Últimos gastos:\n\n"
        for i, gasto in enumerate(ultimos):
            fecha = gasto.get("Fecha", "")
            persona = gasto.get("Persona", "")
            monto = gasto.get("Monto", "")
            moneda = gasto.get("Moneda ", "")
            msg += f"{i}: 📅 {fecha} - 👤 {persona} - 💵 {monto} {moneda}\n"
        
        msg += "\n💬 Borrar: /borrar 0"
        await update.message.reply_text(msg)
        return
    
    match = re.match(r'/borrar\s+(\d+)', text)
    if match:
        try:
            num = int(match.group(1))
            gastos = get_gastos_list()
            if 0 <= num < len(gastos):
                gasto = gastos[num]
                if delete_gasto(num):
                    msg = f"✅ Borrado:\n👤 {gasto.get('Persona')} - 💵 {gasto.get('Monto')}"
                    await update.message.reply_text(msg)
                else:
                    await update.message.reply_text("❌ Error")
            else:
                await update.message.reply_text("⚠️ Número inválido")
        except Exception as e:
            logger.error(f"Error cmd_borrar: {e}")
            await update.message.reply_text("❌ Error")

async def cmd_evento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    pattern = r'/evento\s+(.+)'
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text("💬 Formato: /evento 23-07 14:48 vuelo Aeropuerto Descripcion [Ref] [MapLink] [VoucherLink]")
        return
    
    args = match.group(1).split()
    if len(args) < 4:
        await update.message.reply_text("💬 Mínimo: /evento FECHA HORA TIPO LUGAR")
        return
    
    fecha_str = args[0]
    hora_str = args[1]
    tipo_str = args[2].lower()
    lugar = args[3]
    
    # Validar fecha
    fecha = parse_fecha(fecha_str)
    if not fecha:
        await update.message.reply_text("⚠️ Fecha inválida: 23-07 o 2026-07-23")
        return
    
    # Validar hora
    try:
        datetime.strptime(hora_str, "%H:%M")
    except:
        await update.message.reply_text("⚠️ Hora inválida: 14:48")
        return
    
    # Validar tipo
    tipo_match = None
    for t in EVENT_TYPES:
        if t.lower() == tipo_str:
            tipo_match = t
            break
    if not tipo_match:
        tipo_match = tipo_str.capitalize()
    
    # Recopilar opcionales
    descripcion = " ".join(args[4:]) if len(args) > 4 else ""
    ref = ""
    maps_link = generate_maps_link(tipo_match, lugar)
    voucher_link = ""
    
    # Separar referencias y links si existen
    if "http" in descripcion:
        partes = descripcion.split("http")
        descripcion = partes[0]
        for i, parte in enumerate(partes[1:]):
            url = "http" + parte
            if "drive" in url:
                voucher_link = url.split()[0]
            elif "maps" in url:
                maps_link = url.split()[0]
    
    if add_evento(str(fecha), hora_str, tipo_match, lugar, descripcion, ref, maps_link, voucher_link):
        msg = f"✅ Evento agregado:\n🗓️ {tipo_match}\n📅 {fecha} {hora_str}\n📍 {lugar}"
        if descripcion:
            msg += f"\n📝 {descripcion}"
        if voucher_link:
            msg += f"\n📄 [Voucher]({voucher_link})"
        msg += f"\n🗺️ [Maps]({maps_link})"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Error al guardar evento")

async def cmd_calendario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eventos = get_eventos_list()
    if not eventos:
        await update.message.reply_text("📭 Sin eventos")
        return
    
    msg = "📅 CALENDARIO:\n\n"
    for i, evento in enumerate(eventos, 1):
        fecha_hora = evento.get("Fecha/Hora", "")
        tipo = evento.get("Tipo", "")
        desc = evento.get("Descripción", "")
        maps = evento.get("Link Google Maps", "")
        voucher = evento.get("Link Google Drive", "")
        
        msg += f"{i}. {tipo.upper()} - {fecha_hora}\n"
        msg += f"   📝 {desc}\n"
        if maps:
            msg += f"   🗺️ [Maps]({maps})\n"
        if voucher:
            msg += f"   📄 [Voucher]({voucher})\n"
        msg += "\n"
    
    await update.message.reply_text(msg)

async def cmd_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    args = text.replace("/hoy", "").strip().split()
    
    if not args:
        fecha_target = datetime.now().date()
    else:
        fecha_target = parse_fecha(args[0])
        if not fecha_target:
            await update.message.reply_text("⚠️ Formato: /hoy o /hoy 25-07")
            return
    
    eventos = get_eventos_by_date(fecha_target)
    
    msg = f"📅 Eventos {fecha_target}:\n\n"
    if not eventos:
        msg += "📭 Sin eventos"
    else:
        for e in eventos:
            tipo = e.get("Tipo", "")
            desc = e.get("Descripción", "")
            fecha_hora = e.get("Fecha/Hora", "")
            hora = fecha_hora.split()[1] if " " in fecha_hora else ""
            msg += f"🕐 {hora} - {tipo}\n{desc}\n\n"
    
    # Si es después de 20hs, mostrar mañana
    if datetime.now().hour >= 20:
        manana = fecha_target + timedelta(days=1)
        eventos_manana = get_eventos_by_date(manana)
        msg += f"\n📅 Mañana ({manana}):\n\n"
        if not eventos_manana:
            msg += "📭 Sin eventos"
        else:
            for e in eventos_manana:
                tipo = e.get("Tipo", "")
                desc = e.get("Descripción", "")
                fecha_hora = e.get("Fecha/Hora", "")
                hora = fecha_hora.split()[1] if " " in fecha_hora else ""
                msg += f"🕐 {hora} - {tipo}\n{desc}\n\n"
    
    await update.message.reply_text(msg)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """❓ AYUDA

💰 /gasto - Flexible: /gasto 25 EUR comida descripcion
📅 /evento - Flexible: /evento 23-07 14:48 vuelo Lugar [Desc] [Ref] [Maps] [Voucher]
📊 /resumen - Totales por persona
🗑️ /borrar - Eliminar: /borrar 0
📅 /calendario - Ver todos
🕐 /hoy - Eventos hoy

✅ Todos los campos son opcionales y flexibles"""
    await update.message.reply_text(msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ===== HEALTH CHECK =====
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot running')
    
    def log_message(self, format, *args):
        pass

class ReuseAddrHTTPServer(HTTPServer):
    def server_bind(self):
        self.socket.setsockopt(1, 15, 1)
        HTTPServer.server_bind(self)

def keep_alive():
    while True:
        try:
            time.sleep(600)
            url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000")
            requests.get(url, timeout=5)
            logger.info("✅ Keep-alive")
        except Exception as e:
            logger.debug(f"Keep-alive error: {e}")

# ===== MAIN =====
def main():
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            app = Application.builder().token(TELEGRAM_TOKEN).build()
            
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("resumen", cmd_resumen))
            app.add_handler(CommandHandler("help", cmd_help))
            app.add_handler(CommandHandler("borrar", cmd_borrar))
            app.add_handler(CommandHandler("evento", cmd_evento))
            app.add_handler(CommandHandler("calendario", cmd_calendario))
            app.add_handler(CommandHandler("hoy", cmd_hoy))
            app.add_handler(MessageHandler(filters.Regex(r"^/gasto"), process_gasto))
            app.add_handler(MessageHandler(filters.Regex(r"^/borrar"), cmd_borrar))
            app.add_error_handler(error_handler)
            
            port = int(os.getenv("PORT", 10000))
            server = ReuseAddrHTTPServer(('0.0.0.0', port), HealthHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            logger.info(f"🏥 Health check puerto {port}")
            
            keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
            keep_alive_thread.start()
            logger.info("🔄 Keep-alive")
            
            logger.info("🤖 Bot iniciado")
            
            try:
                app.run_polling()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())
                app.run_polling()
                
        except Exception as e:
            retry_count += 1
            logger.error(f"❌ Error (intento {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                logger.info(f"⏳ Reintentando...")
                time.sleep(10)
            else:
                logger.error("❌ Máximo de reintentos")
                raise

if __name__ == "__main__":
    main()
