import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from flask import Flask
from io import BytesIO
import datetime
from zoneinfo import ZoneInfo
from services.google import drive_service as drive_utils
from utils.bot_proxy import safe_command, DescriptionEmptyError, APIKeyMissingError, set_user_limit

from services.ai.context import AIContext

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ECUADOR_TZ = ZoneInfo("America/Guayaquil")

# --- SETUP PARA RAILWAY (Crear archivos de credenciales desde ENV) ---
def setup_google_credentials():
    # 1. token.json
    token_content = os.getenv('GOOGLE_TOKEN_JSON')
    if token_content:
        with open('token.json', 'w') as f:
            f.write(token_content)
        print("✅ token.json creado desde variable de entorno.")
    
    # 2. config/credentials.json
    creds_content = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if creds_content:
        # Asegurar que existe la carpeta config
        if not os.path.exists('config'):
            os.makedirs('config')
            
        with open('config/credentials.json', 'w') as f:
            f.write(creds_content)
        print("✅ config/credentials.json creado desde variable de entorno.")

setup_google_credentials()

app = Flask(__name__)

@app.route('/')
def home():
    return "VinculacionBot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    await update.message.reply_text("¡Hola! Envia mensajes cortos describiendo lo que hiciste en el dia. Y envia las fotos, el resto del reporte se llena solo :D. ENVIA /help para ver los comandos")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help"""
    help_text = """
📚 **Comandos disponibles:**

/send - Envia los datos a la IA para generar el reporte
/remove - Remueve algo de la bitacora
/get - Obtiene el reporte
/help - Muestra esto

📱 **Funcionalidades:**
• Algo hace tu confía
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def show_remove_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    user_id = update.effective_user.id
    messages = drive_utils.get_day_messages(user_id)
    
    if not messages:
        text = "📭 Ya no hay mensajes."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    items_per_page = 10
    total_pages = (len(messages) + items_per_page - 1) // items_per_page
    
    # Validar página
    if page < 0: page = 0
    if total_pages > 0 and page >= total_pages: page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(messages))
    
    current_items = messages[start_idx:end_idx]
    
    # Construir texto
    text = f"🗑 **Eliminar Mensajes (Página {page + 1}/{total_pages})**\n\n"
    text += "Cuidado que si borras algo, no se puede recuperar :c"
    text += "Solo clickea una vez y espera a que se borre NO TE APRESURES"
    for i, msg in enumerate(current_items):
        # Truncar mensaje muy largo
        display_msg = (msg[:50] + '...') if len(msg) > 50 else msg
        text += f"{i + 1}. {display_msg}\n"
        
    text += "\nSelecciona el número para borrar:"
    
    # Construir botones
    keyboard = []
    row = []
    for i in range(len(current_items)):
        # El callback data tendrá el ÍNDICE REAL (global) de la lista
        real_idx = start_idx + i
        row.append(InlineKeyboardButton(str(i + 1), callback_data=f"rm_del_{real_idx}"))
        if len(row) == 5: # 5 por fila
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    # Botones de navegación
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"rm_page_{page-1}"))
    
    nav_row.append(InlineKeyboardButton("❌ Cancelar", callback_data="rm_cancel"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"rm_page_{page+1}"))
        
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

@safe_command
async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú para eliminar mensajes."""
    user_id = update.effective_user.id
    messages = drive_utils.get_day_messages(user_id)
    
    if not messages:
        await update.message.reply_text("📭 No hay mensajes en la bitácora de hoy para eliminar.")
        return

    await show_remove_menu(update, context, page=0)

async def remove_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "rm_cancel":
        await query.delete_message()
        return
        
    if data.startswith("rm_page_"):
        new_page = int(data.split("_")[-1])
        await show_remove_menu(update, context, page=new_page)
        return
        
    if data.startswith("rm_del_"):
        idx_to_del = int(data.split("_")[-1])
        
        # Eliminar
        success = drive_utils.delete_message_line(user_id, idx_to_del)
        
        if success:
            # Volver a cargar la página 0 (o intentar mantener estado, pero 0 es seguro)
            await show_remove_menu(update, context, page=0)
        else:
            await query.message.reply_text("❌ Error eliminando o el mensaje ya no existe.")
            await show_remove_menu(update, context, page=0)


@safe_command
async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /send para generar reporte con IA"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("🤔 Analizando tus mensajes de hoy...")
    
    # 1. Obtener mensajes del día
    descriptions = drive_utils.get_day_descriptions(user_id)
    
    if not descriptions:
        raise DescriptionEmptyError("No hay descripciones")
        
    await update.message.reply_text("🧠 Generando reporte con IA...")
    
    # 2. Generar respuesta con IA
    try:
        ai_context = AIContext()
        ai_response = ai_context.generate_summary(descriptions)
    except Exception as e:
        # Si es error de API Key, relanzar especificamente si podemos detectarlo, 
        # sino dejar que el proxy capture el genérico
        if "API_KEY" in str(e).upper(): # Simple check
             raise APIKeyMissingError()
        raise e
    
    # 3. Guardar en Column F
    drive_utils.update_ai_response(ai_response, user_id)
    
    await update.message.reply_text(f"✨ Reporte generado y guardado:\n\n{ai_response}")

@safe_command
async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /get para obtener el reporte generado."""
    user_id = update.effective_user.id
    
    # 1. Obtener respuesta AI de Drive (Texto)
    ai_response = drive_utils.get_ai_response(user_id)
    
    if not ai_response:
        ai_response = "No se ha usado el comando /send para que la ia genere la descripcion"
    
    await update.message.reply_text(f"� Tu reporte de hoy:\n\n{ai_response}")

    # 2. Generar y enviar Excel
    status_msg = await update.message.reply_text("📊 Generando archivo Excel con historial...")
    try:
        excel_path = drive_utils.generate_excel_report(user_id)
        if excel_path and os.path.exists(excel_path):
            with open(excel_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(excel_path),
                    caption="Aquí tienes tu reporte completo en Excel."
                )
            
            # Eliminar mensaje de "Generando..." y archivo
            await status_msg.delete()
            os.remove(excel_path)
        else:
            await status_msg.edit_text("⚠️ No se encontraron datos suficientes para generar el Excel.")
    except Exception as e:
        logging.error(f"Error enviando Excel: {e}")
        await status_msg.edit_text("❌ Ocurrió un error al generar el archivo Excel.")


@safe_command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /status <clave> para modificar límites."""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /status <clave>")
        return

    key = context.args[0]
    limit = 1 # Default
    msg = ""

    if key == "dosLlamaditas":
        limit = 2
        msg = "🔓 Clave aceptada. Límite aumentado a 2 usos diarios."
    elif key == "adminEnable11":
        limit = 10
        msg = "🔓 Clave de Admin aceptada. Límite aumentado a 10 usos diarios."
    else:
        await update.message.reply_text("🔒 Clave incorrecta.")
        return

    set_user_limit(user_id, limit)
    await update.message.reply_text(msg)

# --- MÉTODOS PARA MANEJAR DIFERENTES TIPOS DE CONTENIDO ---

async def handle_image_with_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar imágenes con descripción"""
    # Obtener el archivo de la foto (la última es la de mayor resolución)
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    caption = update.message.caption
    user_id = update.effective_user.id
    
    # Log para depuración
    logging.info(f"Foto recibida. Caption: {caption}")
    
    # Notificar usuario
    status_msg = await update.message.reply_text("⏳ Recibido. Subiendo a Google Drive...")

    try:
        # Descargar imagen a memoria
        file_stream = BytesIO()
        await photo_file.download_to_memory(out=file_stream)
        file_stream.seek(0)
        
        # Definir nombre base: DD-MM-YYYY.jpg
        # drive_utils se encargará de los duplicados (ej: (1), (2))
        filename = datetime.datetime.now(ECUADOR_TZ).strftime("%d-%m-%Y.jpg")
        
        
        # Subir a Drive
        # Nota: La imagen se sube a la carpeta del día de PROCESAMIENTO por ahora (para no complicar create_doc logic)
        # pero el link se guardará en la fila correspondiente a la fecha del mensaje.
        uploaded_file, daily_folder = drive_utils.upload_image_from_stream(file_stream, filename, user_id, description=caption)
        
        # Obtener fecha del mensaje
        message_date = update.message.date.astimezone(ECUADOR_TZ)
        
        # Actualizar Sheet con Link de la Carpeta
        if daily_folder and daily_folder.get('webViewLink'):
             drive_utils.update_daily_folder_link(daily_folder.get('webViewLink'), user_id=user_id, message_date=message_date)
             
        # Si hay caption, guardarlo como texto en el Sheet también?
        # El usuario dijo: "todos los mensajes de texto se guarden en la columna description"
        # Asumo que el caption cuenta como mensaje de texto asociado.
        if caption:
            drive_utils.append_text_log(f"{caption}", user_id=user_id, message_date=message_date)
        
        response_text = f"✅ ¡Guardado en Drive!\n"
        response_text += f"📂 Archivo: {uploaded_file.get('name')}\n"
        if caption:
            response_text += f"📝 Descripción: {caption}"
            
        await status_msg.edit_text(response_text)
        
    except Exception as e:
        logging.error(f"Error subiendo imagen: {e}")
        await status_msg.edit_text(f"❌ Error al guardar en Drive: {str(e)}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de texto"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Log para depuración
    logging.info(f"Mensaje de texto recibido: {text}")
    
    # Evitar procesar comandos como texto normal
    if not text.startswith('/'):
        # Guardar en Sheets
        message_date = update.message.date.astimezone(ECUADOR_TZ)
        drive_utils.append_text_log(text, user_id=user_id, message_date=message_date)
        await update.message.reply_text(f"📝 Texto guardado en bitácora.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de audio"""
    audio = update.message.audio
    
    # Log para depuración
    logging.info(f"Audio recibido. Duración: {audio.duration} segundos")
    
    # AQUÍ PUEDES IMPLEMENTAR TU LÓGICA PARA AUDIOS
    # Por ejemplo: procesar el audio, transcribir, guardar, etc.
    
    await update.message.reply_text("🎵 Audio recibido correctamente. Pero aun no se implementa la funcionalidad. :D")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de voz (voice notes)"""
    voice = update.message.voice
    
    # Log para depuración
    logging.info(f"Mensaje de voz recibido. Duración: {voice.duration} segundos")
    
    # AQUÍ PUEDES IMPLEMENTAR TU LÓGICA PARA NOTAS DE VOZ
    # Por ejemplo: transcribir, procesar, etc.
    
    await update.message.reply_text("🎤 Nota de voz recibida correctamente. Pero aun no se implementa la funcionalidad. :D")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja documentos (podría ser audio, imagen, etc.)"""
    document = update.message.document
    
    # Log para depuración
    logging.info(f"Documento recibido: {document.file_name}")
    
    # Verificar el tipo de documento
    mime_type = document.mime_type or ""
    
    if 'audio' in mime_type:
        # Es un archivo de audio
        await handle_audio(update, context)
    elif 'image' in mime_type:
        # Es una imagen enviada como documento
        await handle_image_with_description(update, context)
    else:
        await update.message.reply_text(f"📄 Documento recibido: {document.file_name}, pero aun no se implementa la funcionalidad. :D")

# --- AUTHENTICATION HANDLER ---


    
    if not descriptions:
        raise DescriptionEmptyError("No hay descripciones")
        
    await update.message.reply_text("🧠 Generando reporte con IA...")
    
    # 2. Generar respuesta con IA
    try:
        ai_context = AIContext()
        ai_response = ai_context.generate_summary(descriptions)
    except Exception as e:
        # Si es error de API Key, relanzar especificamente si podemos detectarlo, 
        # sino dejar que el proxy capture el genérico
        if "API_KEY" in str(e).upper(): # Simple check
             raise APIKeyMissingError()
        raise e
    
    # 3. Guardar en Column F
    drive_utils.update_ai_response(ai_response, user_id)
    
    await update.message.reply_text(f"✨ Reporte generado y guardado:\n\n{ai_response}")

@safe_command
async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /get para obtener el reporte generado."""
    user_id = update.effective_user.id
    
    # 1. Obtener respuesta AI de Drive (Texto)
    ai_response = drive_utils.get_ai_response(user_id)
    
    if not ai_response:
        ai_response = "No se ha usado el comando /send para que la ia genere la descripcion"
    
    await update.message.reply_text(f" Tu reporte de hoy:\n\n{ai_response}")

    # 2. Generar y enviar Excel
    status_msg = await update.message.reply_text("📊 Generando archivo Excel con historial...")
    try:
        excel_path = drive_utils.generate_excel_report(user_id)
        if excel_path and os.path.exists(excel_path):
            with open(excel_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(excel_path),
                    caption="Aquí tienes tu reporte completo en Excel."
                )
            
            # Eliminar mensaje de "Generando..." y archivo
            await status_msg.delete()
            os.remove(excel_path)
        else:
            await status_msg.edit_text("⚠️ No se encontraron datos suficientes para generar el Excel.")
    except Exception as e:
        logging.error(f"Error enviando Excel: {e}")
        await status_msg.edit_text("❌ Ocurrió un error al generar el archivo Excel.")


@safe_command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /status <clave> para modificar límites."""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /status <clave>")
        return

    key = context.args[0]
    limit = 1 # Default
    msg = ""

    if key == "dosLlamaditas":
        limit = 2
        msg = "🔓 Clave aceptada. Límite aumentado a 2 usos diarios."
    elif key == "adminEnable11":
        limit = 10
        msg = "🔓 Clave de Admin aceptada. Límite aumentado a 10 usos diarios."
    else:
        await update.message.reply_text("🔒 Clave incorrecta.")
        return

    set_user_limit(user_id, limit)
    await update.message.reply_text(msg)

# --- MÉTODOS PARA MANEJAR DIFERENTES TIPOS DE CONTENIDO ---

async def handle_image_with_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar imágenes con descripción"""
    # Obtener el archivo de la foto (la última es la de mayor resolución)
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    caption = update.message.caption
    user_id = update.effective_user.id
    
    # Log para depuración
    logging.info(f"Foto recibida. Caption: {caption}")
    
    # Notificar usuario
    status_msg = await update.message.reply_text("⏳ Recibido. Subiendo a Google Drive...")

    try:
        # Descargar imagen a memoria
        file_stream = BytesIO()
        await photo_file.download_to_memory(out=file_stream)
        file_stream.seek(0)
        
        # Definir nombre base: DD-MM-YYYY.jpg
        # drive_utils se encargará de los duplicados (ej: (1), (2))
        filename = datetime.datetime.now().strftime("%d-%m-%Y.jpg")
        
        
        # Subir a Drive
        uploaded_file, daily_folder = drive_utils.upload_image_from_stream(file_stream, filename, user_id, description=caption)
        
        # Actualizar Sheet con Link de la Carpeta
        if daily_folder and daily_folder.get('webViewLink'):
             drive_utils.update_daily_folder_link(daily_folder.get('webViewLink'), user_id=user_id)
             
        # Si hay caption, guardarlo como texto en el Sheet también?
        # El usuario dijo: "todos los mensajes de texto se guarden en la columna description"
        # Asumo que el caption cuenta como mensaje de texto asociado.
        if caption:
            drive_utils.append_text_log(f"{caption}", user_id=user_id)
        
        response_text = f"✅ ¡Guardado en Drive!\n"
        response_text += f"📂 Archivo: {uploaded_file.get('name')}\n"
        if caption:
            response_text += f"📝 Descripción: {caption}"
            
        await status_msg.edit_text(response_text)
        
    except Exception as e:
        logging.error(f"Error subiendo imagen: {e}")
        await status_msg.edit_text(f"❌ Error al guardar en Drive: {str(e)}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de texto"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Log para depuración
    logging.info(f"Mensaje de texto recibido: {text}")
    
    # Evitar procesar comandos como texto normal
    if not text.startswith('/'):
        # Guardar en Sheets
        drive_utils.append_text_log(text, user_id=user_id)
        await update.message.reply_text(f"📝 Texto guardado en bitácora.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de audio"""
    audio = update.message.audio
    
    # Log para depuración
    logging.info(f"Audio recibido. Duración: {audio.duration} segundos")
    
    # AQUÍ PUEDES IMPLEMENTAR TU LÓGICA PARA AUDIOS
    # Por ejemplo: procesar el audio, transcribir, guardar, etc.
    
    await update.message.reply_text("🎵 Audio recibido correctamente. Pero aun no se implementa la funcionalidad. :D")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de voz (voice notes)"""
    voice = update.message.voice
    
    # Log para depuración
    logging.info(f"Mensaje de voz recibido. Duración: {voice.duration} segundos")
    
    # AQUÍ PUEDES IMPLEMENTAR TU LÓGICA PARA NOTAS DE VOZ
    # Por ejemplo: transcribir, procesar, etc.
    
    await update.message.reply_text("🎤 Nota de voz recibida correctamente. Pero aun no se implementa la funcionalidad. :D")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja documentos (podría ser audio, imagen, etc.)"""
    document = update.message.document
    
    # Log para depuración
    logging.info(f"Documento recibido: {document.file_name}")
    
    # Verificar el tipo de documento
    mime_type = document.mime_type or ""
    
    if 'audio' in mime_type:
        # Es un archivo de audio
        await handle_audio(update, context)
    elif 'image' in mime_type:
        # Es una imagen enviada como documento
        await handle_image_with_description(update, context)
    else:
        await update.message.reply_text(f"📄 Documento recibido: {document.file_name}, pero aun no se implementa la funcionalidad. :D")

# --- AUTHENTICATION HANDLER ---



def create_application():
    """Configura y retorna la aplicación del bot con todos los handlers."""
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN no encontrado en .env")
        return None

    application = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers de comandos
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('send', send_command))
    application.add_handler(CommandHandler('get', get_command))
    application.add_handler(CommandHandler('remove', remove_command))
    application.add_handler(CommandHandler('status', status_command))
    
    # Callback query handler para el menú de eliminar
    application.add_handler(CallbackQueryHandler(remove_callback_handler, pattern="^rm_"))
    
    # Handlers de mensajes por tipo
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_image_with_description))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Handler para fotos sin descripción
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.CAPTION, handle_image_with_description))
    
    return application

if __name__ == '__main__':
    application = create_application()
    
    if application:
        # Configuración Webhook vs Polling
        webhook_url = os.getenv("WEBHOOK_URL")
        
        if webhook_url:
            port = int(os.environ.get("PORT", 8443))
            print(f"Iniciando Bot en modo Webhook en puerto {port}...")
            
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=TOKEN,
                webhook_url=f"{webhook_url}/{TOKEN}"
            )
        else:
            print("Iniciando Bot en modo Polling...")
            application.run_polling()