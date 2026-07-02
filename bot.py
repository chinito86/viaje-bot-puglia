import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# Almacenamiento temporal de gastos pendientes
gastos_pendientes = {}

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

def add_evento(fecha, hora, tipo, lugar, maps_link="", voucher_link="", fecha_retorno=""):
    try:
        logger.info(f"🔍 Intentando agregar evento: {tipo} {lugar}")
        sheet = init_sheets()
        if not sheet:
            logger.error("❌ init_sheets retornó None")
            return False
        logger.info(f"✅ Sheet conectado")
        
        try:
            eventos = sheet.worksheet("Eventos")
            logger.info(f"✅ Pestaña 'Eventos' encontrada")
        except Exception as e:
            logger.error(f"❌ Pestaña 'Eventos' no existe: {e}")
            return False
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            f"{fecha} {hora}",
            tipo,
            lugar,
            "",
            "",
            fecha_retorno,  # Columna F: Fecha/Hora Retorno
            maps_link,
            voucher_link,
            "2h",
            timestamp
        ]
        logger.info(f"📝 Intentando agregar fila: {row}")
        eventos.append_row(row)
        logger.info(f"✅ Evento: {tipo} {lugar}")
        return True
    except Exception as e:
        logger.error(f"❌ Error add_evento: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
            evento_fecha = e.get("📅 Fecha/Hora", "").split()[0]
            if evento_fecha == str(fecha):
                resultado.append(e)
        return sorted(resultado, key=lambda x: x.get("📅 Fecha/Hora", ""))
    except Exception as e:
        logger.error(f"Error get_eventos_by_date: {e}")
        return []

def add_nota(descripcion, link=""):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        try:
            notas = sheet.worksheet("Notas")
        except:
            # Crear pestaña si no existe
            notas = sheet.add_worksheet(title="Notas", rows=1000, cols=4)
            notas.append_row(["Fecha", "Descripción", "Link", "Timestamp"])
        
        fecha = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [fecha, descripcion, link, timestamp]
        notas.append_row(row)
        logger.info(f"✅ Nota: {descripcion}")
        return True
    except Exception as e:
        logger.error(f"Error add_nota: {e}")
        return False

def get_notas_list():
    try:
        sheet = init_sheets()
        if not sheet:
            return []
        try:
            notas = sheet.worksheet("Notas")
        except:
            return []
        data = notas.get_all_records()
        return data
    except Exception as e:
        logger.error(f"Error get_notas_list: {e}")
        return []

def delete_nota(index):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        notas = sheet.worksheet("Notas")
        notas.delete_rows(index + 2)  # +2 porque fila 1 es header
        logger.info(f"✅ Nota eliminada: fila {index + 2}")
        return True
    except Exception as e:
        logger.error(f"Error delete_nota: {e}")
        return False

def update_nota_link(index, link):
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        notas = sheet.worksheet("Notas")
        row_number = index + 2
        notas.update_cell(row_number, 3, link)  # Columna 3 es Link
        logger.info(f"✅ Link actualizado: nota {index}")
        return True
    except Exception as e:
        logger.error(f"Error update_nota_link: {e}")
        return False
    """Actualiza el link de voucher de un evento"""
    try:
        sheet = init_sheets()
        if not sheet:
            return False
        eventos = sheet.worksheet("Eventos")
        data = eventos.get_all_records()
        
        if index < 0 or index >= len(data):
            return False
        
        # Actualizar la fila (index + 2 porque fila 1 es header)
        row_number = index + 2
        # Columna H es "📄 Link Google Drive (vouchers)" (8)
        eventos.update_cell(row_number, 8, voucher_link)
        logger.info(f"✅ Voucher actualizado: evento {index}")
        return True
    except Exception as e:
        logger.error(f"Error update_evento_voucher: {e}")
        return False
    tipo_lower = tipo.lower()
    
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
    user_id = update.message.from_user.id
    persona_auto = USERNAME_MAP.get(username.lower()) if username else None
    
    pattern = r'/gasto\s+(.+)'
    match = re.match(pattern, text, re.IGNORECASE)
    
    if not match:
        if persona_auto:
            await update.message.reply_text(f"👤 Detectado: {persona_auto}\n💬 Formato: /gasto 25EUR comida - descripcion")
        else:
            await update.message.reply_text("💬 Formato: /gasto 25EUR comida - descripcion")
        return
    
    args_text = match.group(1)
    
    # Parsear monto y moneda flexibles (50eur o 50 eur)
    monto_match = re.match(r'([\d.]+)\s*([a-zA-Z]+)', args_text)
    if not monto_match:
        await update.message.reply_text("💬 Formato: /gasto 25EUR comida descripcion")
        return
    
    monto = monto_match.group(1)
    moneda = monto_match.group(2).upper()
    resto = args_text[monto_match.end():].strip()
    
    # Buscar categoría en TODO el texto
    categoria_encontrada = None
    for cat in CATEGORIES:
        if cat.lower() in resto.lower():
            categoria_encontrada = cat
            break
    
    if not categoria_encontrada:
        await update.message.reply_text(f"⚠️ Categoría no encontrada. Usa: {', '.join(CATEGORIES)}")
        return
    
    # Limpiar descripción
    descripcion = resto.replace(categoria_encontrada, "").replace(categoria_encontrada.lower(), "").strip()
    if descripcion.startswith("-"):
        descripcion = descripcion[1:].strip()
    
    # Extraer persona
    persona_match = None
    for p in PEOPLE:
        if p.lower() in resto.lower():
            persona_match = p
            break
    
    if not persona_match and persona_auto:
        persona_match = persona_auto
    
    # Si no hay persona, mostrar botones
    if not persona_match:
        keyboard = [
            [InlineKeyboardButton(p, callback_data=f"gasto_{user_id}_{p}_{monto}_{moneda}_{categoria_encontrada}_{descripcion}") for p in PEOPLE]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("👤 ¿Quién es?", reply_markup=reply_markup)
        return
    
    fecha = datetime.now().strftime("%Y-%m-%d")
    if add_gasto(fecha, persona_match, categoria_encontrada, monto, moneda, descripcion):
        emoji_cat = get_emoji_categoria(categoria_encontrada)
        msg = f"✅ Gasto registrado:\n👤 {persona_match}\n💵 {monto} {moneda}\n{emoji_cat} {categoria_encontrada}"
        if descripcion:
            msg += f"\n📝 {descripcion}"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Error al guardar")

def get_emoji_categoria(categoria):
    """Retorna emoji según categoría"""
    emojis = {
        "Alojamiento": "🏨",
        "Comida": "🍽️",
        "Transporte": "🚗",
        "Drinks": "🍺",
        "Actividades": "🎭",
        "Misc": "📦"
    }
    return emojis.get(categoria, "🏷️")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_", 5)
    
    if data[0] == "gasto":
        persona = data[2]
        monto = data[3]
        moneda = data[4]
        categoria = data[5]
        descripcion = data[6] if len(data) > 6 else ""
        
        fecha = datetime.now().strftime("%Y-%m-%d")
        if add_gasto(fecha, persona, categoria, monto, moneda, descripcion):
            msg = f"✅ Gasto registrado:\n👤 {persona}\n💵 {monto} {moneda}\n🏷️ {categoria}"
            await query.edit_message_text(text=msg)
        else:
            await query.edit_message_text(text="❌ Error al guardar")
    
    elif data[0] == "voucher" and data[1] == "ver":
        num_evento = int(data[2])
        eventos = get_eventos_list()
        idx = num_evento - 1
        
        if idx < 0 or idx >= len(eventos):
            await query.edit_message_text(text=f"⚠️ Evento #{num_evento} no existe")
            return
        
        evento = eventos[idx]
        voucher = evento.get("📄 Link Google Drive (vouchers)", "")
        
        if not voucher:
            await query.edit_message_text(text=f"⚠️ Evento #{num_evento} sin voucher")
            return
        
        tipo = evento.get("🏷️ Tipo (Vuelo, Tren, Rent a Car, Hospedaje, Excursión, Comida, Reserva)", "")
        desc = evento.get("📝 Descripción", "")
        fecha_hora = evento.get("📅 Fecha/Hora", "")
        
        msg = f"📄 Voucher Evento #{num_evento}:\n🗓️ {tipo}\n📝 {desc}\n📅 {fecha_hora}\n\n[Abrir Voucher]({voucher})"
        await query.edit_message_text(text=msg)

async def cmd_notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "/notas":
        notas = get_notas_list()
        if not notas:
            await update.message.reply_text("📭 Sin notas")
            return
        
        # Mostrar últimas 5
        ultimas = notas[-5:] if len(notas) > 5 else notas
        msg = "📝 NOTAS:\n\n"
        for i, nota in enumerate(ultimas):
            idx = len(notas) - len(ultimas) + i + 1
            desc = nota.get("Descripción", "")
            link = nota.get("Link", "")
            msg += f"#{idx}: {desc}\n"
            if link:
                msg += f"   🔗 [Link]({link})\n"
            msg += "\n"
        
        msg += "💬 Agregar: /notas descripción [link]\n"
        msg += "💬 Borrar: /notas delete 1"
        await update.message.reply_text(msg)
        return
    
    # Parsear: /notas delete N
    pattern_delete = r'/notas\s+delete\s+(\d+)'
    match_delete = re.match(pattern_delete, text)
    
    if match_delete:
        try:
            num = int(match_delete.group(1))
            notas = get_notas_list()
            idx = num - 1
            
            if idx < 0 or idx >= len(notas):
                await update.message.reply_text(f"⚠️ Nota #{num} no existe")
                return
            
            nota = notas[idx]
            if delete_nota(idx):
                desc = nota.get("Descripción", "")
                msg = f"✅ Nota eliminada:\n📝 {desc}"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("❌ Error al eliminar")
        except Exception as e:
            logger.error(f"Error delete nota: {e}")
            await update.message.reply_text("❌ Error")
        return
    
    # Parsear: /notas descripción [link]
    pattern_add = r'/notas\s+(.+)'
    match_add = re.match(pattern_add, text)
    
    if match_add:
        resto = match_add.group(1)
        
        # Buscar links
        urls = re.findall(r'https?://[^\s]+', resto)
        link = urls[0] if urls else ""
        
        # Limpiar descripción de links
        descripcion = resto
        for url in urls:
            descripcion = descripcion.replace(url, "").strip()
        
        descripcion = descripcion.strip()
        
        if not descripcion:
            await update.message.reply_text("💬 Formato: /notas descripción [link]")
            return
        
        if add_nota(descripcion, link):
            num_nota = len(get_notas_list())
            msg = f"✅ Nota #{num_nota}:\n📝 {descripcion}"
            if link:
                msg += f"\n🔗 [Link]({link})"
            msg += f"\n\n💬 Para actualizar link:\n/notaslink {num_nota} https://..."
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

def generate_calendar_link(fecha_str, hora_str, tipo, lugar, fecha_retorno=""):
    """Genera link a Google Calendar para agregar evento"""
    try:
        from datetime import datetime
        
        # Parsear fecha inicio
        fecha_obj = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        fecha_inicio = fecha_obj.strftime("%Y%m%dT%H%M%S")
        
        # Parsear fecha fin
        if fecha_retorno:
            try:
                fecha_retorno_obj = datetime.strptime(fecha_retorno, "%Y-%m-%d %H:%M")
                fecha_fin = fecha_retorno_obj.strftime("%Y%m%dT%H%M%S")
            except:
                # Si no se puede parsear, asumir 2 horas después
                from datetime import timedelta
                fecha_fin_obj = fecha_obj + timedelta(hours=2)
                fecha_fin = fecha_fin_obj.strftime("%Y%m%dT%H%M%S")
        else:
            # Por defecto 2 horas después
            from datetime import timedelta
            fecha_fin_obj = fecha_obj + timedelta(hours=2)
            fecha_fin = fecha_fin_obj.strftime("%Y%m%dT%H%M%S")
        
        # Construir URL
        titulo = f"{tipo} - {lugar}"
        detalles = f"Lugar: {lugar}"
        
        # URL encode
        import urllib.parse
        params = {
            "action": "TEMPLATE",
            "text": titulo,
            "dates": f"{fecha_inicio}/{fecha_fin}",
            "details": detalles,
            "location": lugar
        }
        
        query = urllib.parse.urlencode(params)
        url = f"https://calendar.google.com/calendar/render?{query}"
        return url
    except Exception as e:
        logger.error(f"Error generate_calendar_link: {e}")
        return ""

def generate_maps_link(tipo, lugar):
    """Genera link a Google Maps según el tipo de evento"""
    tipo_lower = tipo.lower()
    
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

async def cmd_evento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        logger.info(f"📍 /evento recibido: {text}")
        
        pattern = r'/evento\s+(.+)'
        match = re.match(pattern, text)
        
        if not match:
            await update.message.reply_text('💬 Formato: /evento 23-07 14:48 vuelo "Lugar" ["Retorno"]')
            return
        
        resto = match.group(1)
        partes = resto.split()
        
        if len(partes) < 4:
            await update.message.reply_text('💬 Mínimo: /evento FECHA HORA TIPO "LUGAR"')
            return
        
        fecha_str = partes[0]
        hora_str = partes[1]
        tipo_str = partes[2].lower()
        
        # Buscar lugares y retorno entre comillas
        lugares_match = re.findall(r'"([^"]+)"', resto)
        
        if not lugares_match:
            await update.message.reply_text('💬 El lugar debe ir entre comillas: "Hotel Torres"')
            return
        
        lugar = lugares_match[0]
        fecha_retorno = lugares_match[1] if len(lugares_match) > 1 else ""
        
        fecha = parse_fecha(fecha_str)
        if not fecha:
            await update.message.reply_text("⚠️ Fecha inválida: 23-07")
            return
        
        tipo_match = tipo_str.capitalize()
        maps_link = generate_maps_link(tipo_match, lugar)
        
        # Parsear voucher link si existe
        voucher_link = ""
        urls = re.findall(r'https?://[^\s"]+', resto)
        for url in urls:
            if "drive" in url:
                voucher_link = url
        
        # Contar eventos antes de agregar
        eventos_antes = len(get_eventos_list())
        
        if add_evento(str(fecha), hora_str, tipo_match, lugar, maps_link=maps_link, voucher_link=voucher_link, fecha_retorno=fecha_retorno):
            num_evento = eventos_antes + 1  # El nuevo evento es el siguiente número
            msg = f"✅ Evento #{num_evento}:\n🗓️ {tipo_match}\n📅 Entrada: {fecha} {hora_str}"
            if fecha_retorno:
                msg += f"\n📅 Salida: {fecha_retorno}"
            msg += f"\n📍 {lugar}"
            
            # Generar Google Calendar link
            cal_link = generate_calendar_link(str(fecha), hora_str, tipo_match, lugar, fecha_retorno)
            if cal_link:
                msg += f"\n\n[📅 Agregar a Google Calendar]({cal_link})"
            
            if not voucher_link:
                msg += f"\n\n👇 Para agregar voucher:\n/voucher {num_evento} https://drive.google.com/... \"Nombre\""
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("❌ Error al guardar")
            
    except Exception as e:
        logger.error(f"❌ Error cmd_evento: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def cmd_calendario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eventos = get_eventos_list()
    if not eventos:
        await update.message.reply_text("📭 Sin eventos")
        return
    
    msg = "📅 CALENDARIO:\n\n"
    for i, evento in enumerate(eventos, 1):
        fecha_hora = evento.get("📅 Fecha/Hora", "")
        tipo = evento.get("🏷️ Tipo (Vuelo, Tren, Rent a Car, Hospedaje, Excursión, Comida, Reserva)", "")
        desc = evento.get("📝 Descripción", "")
        fecha_retorno = evento.get("📅 Fecha/Hora Retorno", "")
        maps = evento.get("🗺️ Link Google Maps", "")
        voucher = evento.get("📄 Link Google Drive (vouchers)", "")
        
        msg += f"#{i}. {tipo.upper()}\n"
        msg += f"   📅 {fecha_hora}"
        if fecha_retorno:
            msg += f" → {fecha_retorno}"
        msg += "\n"
        msg += f"   📝 {desc}\n"
        
        if maps:
            msg += f"   🗺️ [Maps]({maps})\n"
        
        if voucher:
            msg += f"   📄 [Voucher]({voucher})\n"
        else:
            msg += f"   ⚠️ Sin voucher\n"
        
        msg += "\n"
    
    msg += "💬 /voucherconsultar para ver todos los vouchers"
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
            fecha_hora = e.get("📅 Fecha/Hora", "")
            hora = fecha_hora.split()[1] if " " in fecha_hora else ""
            msg += f"🕐 {hora} - {tipo}\n{desc}\n\n"
    
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
                fecha_hora = e.get("📅 Fecha/Hora", "")
                hora = fecha_hora.split()[1] if " " in fecha_hora else ""
                msg += f"🕐 {hora} - {tipo}\n{desc}\n\n"
    
    await update.message.reply_text(msg)

async def cmd_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "/voucher":
        eventos = get_eventos_list()
        if not eventos:
            await update.message.reply_text("📭 Sin eventos")
            return
        
        # Mostrar últimos 5 eventos con su número
        ultimos = eventos[-5:] if len(eventos) > 5 else eventos
        msg = "📄 VOUCHERS - Últimos eventos:\n\n"
        for i, evento in enumerate(ultimos):
            num_evento = len(eventos) - len(ultimos) + i + 1  # Número 1-based
            fecha_hora = evento.get("📅 Fecha/Hora", "")
            tipo = evento.get("🏷️ Tipo (Vuelo, Tren, Rent a Car, Hospedaje, Excursión, Comida, Reserva)", "")
            desc = evento.get("📝 Descripción", "")
            msg += f"#{num_evento}: {tipo} - {fecha_hora}\n   {desc}\n"
        
        msg += "\n💬 Para agregar voucher:\n/voucher 8 https://drive.google.com/... \"Nombre\""
        await update.message.reply_text(msg)
        return
    
    # Parsear: /voucher 8 https://link... "nombre"
    pattern = r'/voucher\s+(\d+)\s+(https://[^\s]+)(?:\s+"([^"]*)")?'
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text('💬 Formato: /voucher 8 https://drive.google.com/... "Nombre"')
        return
    
    try:
        num_evento = int(match.group(1))  # Número 1-based
        voucher_link = match.group(2)
        nombre = match.group(3) or "Voucher"
        
        eventos = get_eventos_list()
        idx = num_evento - 1  # Convertir a índice 0-based
        
        if idx < 0 or idx >= len(eventos):
            await update.message.reply_text(f"⚠️ Evento #{num_evento} no existe")
            return
        
        if update_evento_voucher(idx, voucher_link):
            evento = eventos[idx]
            tipo = evento.get("🏷️ Tipo (Vuelo, Tren, Rent a Car, Hospedaje, Excursión, Comida, Reserva)", "")
            desc = evento.get("📝 Descripción", "")
            msg = f"✅ Voucher agregado a Evento #{num_evento}:\n🗓️ {tipo}\n📝 {desc}\n📄 [{nombre}]({voucher_link})"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("❌ Error al agregar voucher")
    except Exception as e:
        logger.error(f"Error cmd_voucher: {e}")
        await update.message.reply_text("❌ Error")

async def cmd_voucher_consultar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    eventos = get_eventos_list()
    if not eventos:
        await update.message.reply_text("📭 Sin eventos")
        return
    
    if text == "/voucherconsultar":
        # Mostrar botones para eventos con voucher
        eventos_con_voucher = []
        for i, e in enumerate(eventos, 1):
            if e.get("📄 Link Google Drive (vouchers)", ""):
                eventos_con_voucher.append((i, e))
        
        if not eventos_con_voucher:
            await update.message.reply_text("📭 Sin vouchers registrados")
            return
        
        # Crear botones (máximo 3 por fila)
        keyboard = []
        fila = []
        for num, evento in eventos_con_voucher:
            tipo = evento.get("🏷️ Tipo (Vuelo, Tren, Rent a Car, Hospedaje, Excursión, Comida, Reserva)", "")
            desc = evento.get("📝 Descripción", "")[:20]  # Primeros 20 caracteres
            texto_btn = f"#{num} {tipo}"
            fila.append(InlineKeyboardButton(texto_btn, callback_data=f"voucher_ver_{num}"))
            
            if len(fila) == 3:
                keyboard.append(fila)
                fila = []
        
        if fila:
            keyboard.append(fila)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📄 VOUCHERS:\n\nSelecciona un evento:", reply_markup=reply_markup)
        return
    
    # Parsear: /voucherconsultar 8
    pattern = r'/voucherconsultar\s+(\d+)'
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text('💬 Formato: /voucherconsultar o /voucherconsultar 8')
        return
    
    try:
        num_evento = int(match.group(1))
        idx = num_evento - 1
        
        if idx < 0 or idx >= len(eventos):
            await update.message.reply_text(f"⚠️ Evento #{num_evento} no existe")
            return
        
        evento = eventos[idx]
        voucher = evento.get("📄 Link Google Drive (vouchers)", "")
        
        if not voucher:
            await update.message.reply_text(f"⚠️ Evento #{num_evento} sin voucher")
            return
        
        tipo = evento.get("🏷️ Tipo (Vuelo, Tren, Rent a Car, Hospedaje, Excursión, Comida, Reserva)", "")
        desc = evento.get("📝 Descripción", "")
        fecha_hora = evento.get("📅 Fecha/Hora", "")
        
        msg = f"📄 Voucher Evento #{num_evento}:\n🗓️ {tipo}\n📝 {desc}\n📅 {fecha_hora}\n\n[Abrir Voucher]({voucher})"
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error cmd_voucher_consultar: {e}")
        await update.message.reply_text("❌ Error")
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
            fecha_hora = e.get("📅 Fecha/Hora", "")
            hora = fecha_hora.split()[1] if " " in fecha_hora else ""
            msg += f"🕐 {hora} - {tipo}\n{desc}\n\n"
    
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
                fecha_hora = e.get("📅 Fecha/Hora", "")
                hora = fecha_hora.split()[1] if " " in fecha_hora else ""
                msg += f"🕐 {hora} - {tipo}\n{desc}\n\n"
    
    await update.message.reply_text(msg)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """❓ AYUDA - Bot Gastos Puglia 2026

💰 /gasto - Registrar gasto
   Formato: /gasto 25EUR comida - descripcion
   ✅ Auto-detecta persona por username
   ✅ Si no tiene username, muestra botones
   
📅 /evento - Agregar evento
   Formato: /evento 23-07 14:48 vuelo "Lugar" ["Retorno"]
   Ejemplo: /evento 25-07 10:00 rent-a-car "Avis" "27-07 18:00"
   ✅ Auto-genera link a Google Maps
   ✅ Muestra link para agregar a Google Calendar
   
📄 /voucher - Agregar voucher a evento
   /voucher (muestra últimos 5)
   /voucher 8 https://drive.google.com/... "Nombre"
   
📄 /voucherconsultar - Ver vouchers
   /voucherconsultar (botones interactivos)
   
📝 /notas - Guardar notas y links
   /notas (muestra últimas 5)
   /notas Polignano - Playas https://maps.google.com/...
   /notas La Praja Club (sin link)
   /notas delete 1 (borrar nota)
   
📊 /resumen - Ver totales por persona
   
🗑️ /borrar - Eliminar gasto
   /borrar (muestra últimos 5)
   /borrar 0 (borra el primero)
   
📅 /calendario - Ver todos los eventos
   
🕐 /hoy - Eventos del día
   /hoy o /hoy 25-07"""
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
            app.add_handler(CommandHandler("voucher", cmd_voucher))
            app.add_handler(CommandHandler("voucherconsultar", cmd_voucher_consultar))
            app.add_handler(CommandHandler("notas", cmd_notas))
            app.add_handler(CallbackQueryHandler(button_callback))
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
