import os
import json
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import TelegramError
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from PIL import Image
from io import BytesIO
import re
import asyncio

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONSTANTES - Leer desde variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHEET_ID = os.getenv("SHEET_ID", "1j7KnEFchIFcansWZ2ru7-UocfaNsmwg8p_0LMqeKeyw")
SERVICE_ACCOUNT_JSON_STR = os.getenv("SERVICE_ACCOUNT_JSON")

# Parsear el JSON de la cuenta de servicio
try:
    SERVICE_ACCOUNT_JSON = json.loads(SERVICE_ACCOUNT_JSON_STR)
except:
    logger.error("Error: No se pudo leer SERVICE_ACCOUNT_JSON.")
    SERVICE_ACCOUNT_JSON = {}

PEOPLE = ["Chinito", "Dieguito", "Pablito", "Ollaze"]
CATEGORIES = ["Alojamiento", "Comida", "Transporte", "Drinks", "Actividades", "Misc"]

VIAJE_EVENTOS = [
    {"fecha": "2026-07-20", "hora": "11:45", "tipo":
