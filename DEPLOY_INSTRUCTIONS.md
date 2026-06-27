# 🚀 DEPLOY DEL BOT EN RENDER (Opción B - Servidor Gratis)

## ✅ PASO 1: Crear una carpeta con los archivos

1. En tu computadora, crea una carpeta: `viaje-bot-puglia`
2. Descarga estos 2 archivos en esa carpeta:
   - `bot.py` (el código del bot)
   - `requirements.txt` (las dependencias)

Debería quedar así:
```
viaje-bot-puglia/
├── bot.py
├── requirements.txt
```

---

## ✅ PASO 2: Subirlo a GitHub

1. Ve a [github.com](https://github.com) y crea una cuenta (si no tienes)
2. Click en **+** (arriba a la derecha) → **New repository**
   - Nombre: `viaje-bot-puglia`
   - Descripción: `Bot Telegram para gastos viaje Puglia 2026`
   - ✅ **Public**
   - Click **Create repository**

3. Ahora sigue las instrucciones para subir archivos:
   - Click **"uploading an existing file"**
   - Arrastra los 2 archivos (`bot.py` y `requirements.txt`)
   - Click **Commit changes**

---

## ✅ PASO 3: Deployar en Render

1. Ve a [render.com](https://render.com)
2. Click **Sign up** (o Sign in si tienes cuenta)
3. Conecta con GitHub cuando te lo pida
4. Click **+ New +** (arriba a la derecha)
5. Selecciona **Web Service**
6. En **GitHub repository**, selecciona: `viaje-bot-puglia`
7. Completa así:
   ```
   Name: viaje-bot-puglia
   Environment: Python 3
   Build command: pip install -r requirements.txt
   Start command: python bot.py
   ```
8. Scroll down → **Advanced**
9. Click **Add Environment Variable**
   - Name: `TELEGRAM_TOKEN`
   - Value: `8937495308:AAF-1IXNMqu7oxkPkU8kcLjyHZkkHNXvYIA`
10. Click **Create Web Service**

✅ **¡Listo!** El bot está deployado. Verás un mensaje "Build succeeded".

---

## 🧪 PASO 4: Agregar el bot al grupo de Telegram

1. Abre Telegram
2. Ve al grupo **"Puglia 2026 - Gastos"**
3. Click en el nombre del grupo (arriba)
4. Click **"Add Members"**
5. Busca tu bot: `@viajepu_glia_2026_bot` (o el que creaste)
6. Agrégalo al grupo
7. Haz el bot **administrador** (click en su nombre → "Permissions" → marcar todo)

---

## 📝 PASO 5: Probar el bot

En el grupo, escribe:

```
/gasto 25 EUR Comida Chinito - Pasta en Bari
```

Debería responder con:
```
✅ Gasto registrado:

👤 Chinito
💰 25 EUR
📂 Comida
📝 Pasta en Bari
```

---

## 📊 PASO 6: Ver datos en Google Sheet

1. Ve a tu Google Sheet: [sheets.google.com](https://docs.google.com/spreadsheets/d/1j7KnEFchIFcansWZ2ru7-UocfaNsmwg8p_0LMqeKeyw/edit?usp=sharing)
2. En la pestaña **"Gastos"** deberías ver el gasto registrado

---

## 🎯 Comandos del Bot

**En el grupo, usa estos comandos:**

```
/gasto [monto] [moneda] [categoría] [persona] - [descripción]
Ejemplo: /gasto 25 EUR Comida Chinito - Pasta en Bari

/resumen
Ver gastos totales por persona

/eventos
Ver próximos vuelos y hoteles

/help
Ayuda
```

---

## ⚠️ NOTA IMPORTANTE

- El bot **corre 24/7** en Render (gratis)
- Los datos se guardan en Google Sheets automáticamente
- Render apaga servicios inactivos después de 15 minutos
- Para mantenerlo activo, puedes usar un "pinger" (opcional)

---

## 🔧 Si necesitas cambios

1. Edita `bot.py` en GitHub
2. Commit los cambios
3. Render se actualiza automáticamente

---

¿Problemas? Revisa los logs en Render (click en "Logs" en la página del servicio).
