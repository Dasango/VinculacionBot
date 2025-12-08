import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from flask import Flask

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
    await update.message.reply_text("¡Hola! Envíame una foto con una descripción para procesarla.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes que contienen fotos"""
    # Obtener el archivo de la foto (la última es la de mayor resolución)
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    caption = update.message.caption
    
    # Log para depuración
    logging.info(f"Foto recibida. Caption: {caption}")
    
    response_text = "✅ Foto recibida correctamente."
    if caption:
        response_text += f"\n📝 Descripción: {caption}"
    else:
        response_text += "\n⚠️ No olvidaste la descripción, ¿verdad?"

    await update.message.reply_text(response_text)

if __name__ == '__main__':
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN no encontrado en .env")
    else:
        print("Iniciando Bot en modo Polling...")
        application = ApplicationBuilder().token(TOKEN).build()
        
        start_handler = CommandHandler('start', start)
        photo_handler = MessageHandler(filters.PHOTO, handle_photo)
        
        application.add_handler(start_handler)
        application.add_handler(photo_handler)
        
        application.run_polling()
