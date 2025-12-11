import asyncio
import logging
import os
import sys

# Añadir el directorio actual al path para importar app.py si es necesario
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_application

# Configuración de logging para ver qué pasa
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def run_cron_job():
    """
    Ejecuta el bot por un tiempo limitado (ej. 5 minutos).
    Esto permite procesar todos los mensajes pendientes de las últimas horas
    y luego apagar el proceso para ahorrar recursos en Railway.
    """
    print("🚀 Iniciando VinculacionBot en modo Cron Job...")
    
    application = create_application()
    if not application:
        print("❌ No se pudo crear la aplicación (¿Falta TELEGRAM_TOKEN?)")
        return

    # 1. Inicializar y Arrancar
    await application.initialize()
    await application.start()
    
    # 2. Iniciar Polling para recibir mensajes
    # Esto procesará los mensajes acumulados en las últimas 24h
    print("📥 Iniciando polling para procesar mensajes pendientes...")
    await application.updater.start_polling()
    
    # 3. Mantener vivo por X tiempo
    # 5 minutos (300 segundos) es suficiente para procesar una cola larga y permitir
    # interacciones breves si el usuario está atento.
    RUNTIME_SECONDS = 300 
    print(f"⏱️ El bot permanecerá activo por {RUNTIME_SECONDS} segundos...")
    
    try:
        await asyncio.sleep(RUNTIME_SECONDS)
    except KeyboardInterrupt:
        print("⚠️ Interrupción de teclado recibida.")
    
    # 4. Apagar ordenadamente
    print("🛑 Tiempo cumplido. Deteniendo bot...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    print("✅ Proceso Cron Job finalizado exitosamente.")

if __name__ == "__main__":
    try:
        asyncio.run(run_cron_job())
    except Exception as e:
        print(f"❌ Error fatal en el Cron Job: {e}")
        sys.exit(1)
