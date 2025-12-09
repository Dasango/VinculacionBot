import logging
import functools
from telegram import Update
from telegram.ext import ContextTypes

class DescriptionEmptyError(Exception):
    """Excepción para cuando no hay descripciones para procesar."""
    pass

class APIKeyMissingError(Exception):
    """Excepción para cuando falta la API Key."""
    pass

class BotOperationProxy:
    """
    Proxy para manejar excepciones de manera centralizada en los comandos del bot.
    Permite envolver funciones de manejo de comandos y capturar errores comunes.
    """
    
    @staticmethod
    async def execute(update: Update, context: ContextTypes.DEFAULT_TYPE, func, *args, **kwargs):
        """
        Ejecuta una función asíncrona controlando excepciones específicas.
        
        Uso:
            await BotOperationProxy.execute(update, context, mi_funcion_async)
        """
        try:
            return await func(update, context, *args, **kwargs)
            
        except DescriptionEmptyError:
            logging.warning(f"Usuario {update.effective_user.id} intentó generar reporte sin mensajes.")
            await update.message.reply_text("❌ No se encontraron mensajes para procesar el día de hoy. Envía texto o imágenes primero.")
            
        except APIKeyMissingError:
            logging.error("Falta la API Key de Gemini.")
            await update.message.reply_text("❌ Error de configuración: Falta la API Key de IA. Contacta al administrador.")
            
        except Exception as e:
            logging.error(f"Error no controlado en comando: {str(e)}", exc_info=True)
            await update.message.reply_text(f"❌ Ocurrió un error inesperado: {str(e)}")

def safe_command(func):
    """Decorador para usar el proxy más fácilmente."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        return await BotOperationProxy.execute(update, context, func, *args, **kwargs)
    return wrapper
