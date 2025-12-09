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

class AIServiceError(Exception):
    """Excepción para cuando falla el servicio de IA."""
    pass

import datetime

# Constantes para "Paywall"
MAGIC_WORD = "YuriCalvo"
MAX_FREE_USES = 1

# Estructura simple en memoria para tracking diario: { 'YYYY-MM-DD': { user_id: count } }
_daily_usage = {}

def get_today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def check_quota(user_id: int) -> bool:
    """Verifica si el usuario tiene cupo o necesita palabra mágica."""
    today = get_today_str()
    
    # Limpiar días viejos (simple logic: si la key no es hoy, reset total o ignorar)
    if get_today_str() not in _daily_usage:
        _daily_usage.clear()
        _daily_usage[today] = {}
        
    usage = _daily_usage[today].get(user_id, 0)
    return usage < MAX_FREE_USES

def increment_quota(user_id: int):
    today = get_today_str()
    if today not in _daily_usage:
        _daily_usage[today] = {}
    _daily_usage[today][user_id] = _daily_usage[today].get(user_id, 0) + 1

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
        user_id = update.effective_user.id
        
        # Lógica específica para rate-limit en el comando 'send'
        # Verificamos por nombre de función si es la que queremos limitar
        if func.__name__ == 'send_command':
            if not check_quota(user_id):
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
                    await update.message.reply_text("Sorry pero no tengo tantos tokens para generar mas de una vez, pagame y te doy mas :D")
                    return # Bloquear ejecución
        
        try:
            result = await func(update, context, *args, **kwargs)
            
            # Si tuvo éxito y era send_command, incrementar uso
            if func.__name__ == 'send_command':
                increment_quota(user_id)
                
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
        return await BotOperationProxy.execute(update, context, func, *args, **kwargs)
    return wrapper
