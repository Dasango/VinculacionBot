import logging
import functools
from telegram import Update
from telegram.ext import ContextTypes

from services.storage_service import get_usage, increment_usage, init_db, get_user_limit, set_user_limit

# Inicializar DB al importar
init_db()

class DescriptionEmptyError(Exception):
    """Excepción para cuando no hay descripciones para procesar."""
    pass

class APIKeyMissingError(Exception):
    """Excepción para cuando falta la API Key."""
    pass

class AIServiceError(Exception):
    """Excepción para cuando falla el servicio de IA."""
    pass

# Constantes para "Paywall"
MAGIC_WORD = "YuriCalvo"
MAX_FREE_USES_PER_COMMAND = 1

def check_quota(user_id: int, command: str) -> bool:
    """Verifica si el usuario tiene cupo para el comando específico."""
    limit = get_user_limit(user_id, default_limit=MAX_FREE_USES_PER_COMMAND)
    usage = get_usage(user_id, command)
    return usage < limit

class BotOperationProxy:
    """
    Proxy para manejar excepciones de manera centralizada en los comandos del bot.
    Permite envolver funciones de manejo de comandos y capturar errores comunes.
    """
    
    @staticmethod
    async def execute(update: Update, context: ContextTypes.DEFAULT_TYPE, func, *args, **kwargs):
        """
        Ejecuta una función asíncrona controlando excepciones específicas.
        """
        user_id = update.effective_user.id
        command_name = func.__name__
        
        # Lista de comandos limitados
        LIMITED_COMMANDS = ['send_command', 'get_command']

        if command_name in LIMITED_COMMANDS:
            if not check_quota(user_id, command_name):
                # Ya usó su cupo gratis. Verificar palabra mágica en argumentos.
                # context.args viene de CommandHandler, si existe
                user_args = getattr(context, 'args', [])
                
                has_magic_word = False
                if user_args:
                    for arg in user_args:
                        if MAGIC_WORD.lower() in arg.lower(): # Case insensitive check
                            has_magic_word = True
                            break
                            
                if not has_magic_word:
                    cmd_display = "/get" if command_name == 'get_command' else "/send"
                    await update.message.reply_text(f"🚫 Límite diario alcanzado para {cmd_display}.\nUsa la palabra mágica para continuar o espera a mañana.")
                    return # Bloquear ejecución
        
        try:
            result = await func(update, context, *args, **kwargs)
            
            # Si tuvo éxito y era un comando limitado, incrementar uso
            if command_name in LIMITED_COMMANDS:
                increment_usage(user_id, command_name)
                
            return result
            
        except DescriptionEmptyError:
            logging.warning(f"Usuario {update.effective_user.id} intentó generar reporte sin mensajes.")
            await update.message.reply_text("❌ No se encontraron mensajes para procesar el día de hoy. Envía texto o imágenes primero.")
            
        except APIKeyMissingError:
            logging.error("Falta la API Key de Gemini.")
            await update.message.reply_text("❌ Error de configuración: Falta la API Key de IA. Contacta al administrador.")
            
        except AIServiceError as e:
            logging.error(f"Fallo en la IA: {str(e)}", exc_info=True)
            await update.message.reply_text("Se frego la ia :v contactate con David")

        except Exception as e:
            logging.error(f"Error no controlado en comando: {str(e)}", exc_info=True)
            await update.message.reply_text(f"❌ Ocurrió un error inesperado: {str(e)}")

def safe_command(func):
    """Decorador para usar el proxy más fácilmente."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
             # Caso raro donde no hay usuario (ej: channel post?), dejar pasar o manejar error
             pass
        return await BotOperationProxy.execute(update, context, func, *args, **kwargs)
    return wrapper
