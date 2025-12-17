
SUMMARY_PROMPT_TEMPLATE = """
Vas a recibir una serie de mensajes que describen lo que se trabajo en vinculación el dia de hoy.
En máximo 500 letras genera una descripción de la actividad realizada. 
Si se nombra a un calvo es el ingeniero Yuri, ponle su nombre no su apodo. 
La descripción tiene que ser formal. Escribela como si fueras el estudiante

Si te envio: IA!  es para que tengas algo en consideracion

Mensajes:
{text_content}

Resumen:
"""
