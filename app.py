import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from flask import Flask
from io import BytesIO
import datetime
import drive_utils
from bot_proxy import safe_command, DescriptionEmptyError, APIKeyMissingError
import ai_service
# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

app = Flask(__name__)

@app.route('/')
def home():
    return "VinculacionBot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    await update.message.reply_text("¡Hola! Empecemos a documentar vinculación.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help"""
    help_text = """
📚 **Comandos disponibles:**

/send - No hace nada
/help - Muestra esto

📱 **Funcionalidades:**
• Algo hace tu confía
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


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
        ai_response = ai_service.AIService.generate_summary(descriptions)
    except Exception as e:
        # Si es error de API Key, relanzar especificamente si podemos detectarlo, 
        # sino dejar que el proxy capture el genérico
        if "API_KEY" in str(e).upper(): # Simple check
             raise APIKeyMissingError()
        raise e
    
    # 3. Guardar en Column F
    drive_utils.update_ai_response(ai_response, user_id)
    
    await update.message.reply_text(f"✨ Reporte generado y guardado:\n\n{ai_response}")

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
    
    await update.message.reply_text("🎵 Audio recibido correctamente. Procesando...")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Método para manejar mensajes de voz (voice notes)"""
    voice = update.message.voice
    
    # Log para depuración
    logging.info(f"Mensaje de voz recibido. Duración: {voice.duration} segundos")
    
    # AQUÍ PUEDES IMPLEMENTAR TU LÓGICA PARA NOTAS DE VOZ
    # Por ejemplo: transcribir, procesar, etc.
    
    await update.message.reply_text("🎤 Nota de voz recibida correctamente. Procesando...")

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
        await update.message.reply_text(f"📄 Documento recibido: {document.file_name}")

if __name__ == '__main__':
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN no encontrado en .env")
    else:
        print("Iniciando Bot en modo Polling...")
        application = ApplicationBuilder().token(TOKEN).build()
        
        # Handlers de comandos
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('send', send_command))
        
        # Handlers de mensajes por tipo
        application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_image_with_description))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        
        # Handler para fotos sin descripción
        application.add_handler(MessageHandler(filters.PHOTO & ~filters.CAPTION, handle_image_with_description))
        
        application.run_polling()