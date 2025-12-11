# Instrucciones para Ahorrar Costos en Railway (Modo Cron Job)

Para reducir el consumo de recursos y "activar" el bot solo en horarios específicos (14:00, 18:00 y 00:00 hora Ecuador), sigue estos pasos:

## 1. Desactivar el Servicio 24/7 actual
Como ya tienes el bot en producción, actualmente está corriendo todo el tiempo esperando mensajes.
- Ve a tu proyecto en Railway.
- Selecciona el servicio del bot.
- Ve a **Settings** -> **Delete Service** (O simplemente pausa/elimina el deployment si es posible, pero lo ideal es cambiar el "Start Command" o borrarlo y crear un Cron Job).
- *Alternativa:* Si prefieres no borrarlo, puedes simplemente **Apagarlo** (Scale to 0 replicas) pero Railway a veces reinicia. Lo mejor es usar un Cron Job.

## 2. Crear un Cron Job
Railway permite crear "Cron Jobs" que ejecutan un comando en un horario definido y luego se apagan.

1. En tu proyecto de Railway, haz clic en **+ New** -> **Cron Job**.
2. Selecciona tu repositorio (`VinculacionBot`).
3. Configura el **Schedule** (Horario). Railway usa hora **UTC**.
   - Para las horas de Ecuador (UTC-5): 14:00, 18:00, 24:00 (Medianoche).
   - Necesitamos configurar: `0 5,19,23 * * *`
     - `19:00 UTC` = 14:00 Ecuador
     - `23:00 UTC` = 18:00 Ecuador
     - `05:00 UTC` = 00:00 Ecuador (Medianoche)
   - **Cron Schedule:** `0 5,19,23 * * *`

4. Configura el **Command** (Comando de inicio):
   - `python cron_bot.py`

5. Asegúrate de que las **Variables de Entorno** esten configuradas en este nuevo servicio de Cron Job (puedes usar "Shared Variables" en Railway para compartirlas entre servicios).
   - `TELEGRAM_TOKEN`
   - `GOOGLE_TOKEN_JSON`
   - `GOOGLE_CREDENTIALS_JSON`
   - etc.

## ¿Qué pasará?
- El bot se "despertará" 3 veces al día en los horarios indicados.
- Al despertar, descargará todos los mensajes, fotos y comandos enviados por ti en las últimas horas (Telegram guarda los mensajes pendientes por 24h).
- Procesará todo (subir a Drive, generar reportes).
- Se mantendrá encendido por **5 minutos** para que puedas interactuar si necesitas algo rápido.
- Luego se apagará automáticamente, consumiendo muchísimos menos recursos (solo 15 minutos de ejecución al día en total).
