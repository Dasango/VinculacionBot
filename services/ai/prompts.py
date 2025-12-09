
SUMMARY_PROMPT_TEMPLATE = """
Vas a recibir una serie de mensajes que describen lo que se trabajo en vinculación el dia de hoy.
En máximo 500 letras genera una descripción de la actividad realizada. 
Si se nombra a un calvo es el ingeniero Yuri, ponle su nombre no su apodo. 
La descripción tiene que ser formal 

Mensajes:
{text_content}

Resumen:
"""
