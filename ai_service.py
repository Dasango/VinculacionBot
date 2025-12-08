import os

import google.generativeai as genai

from dotenv import load_dotenv

from bot_proxy import APIKeyMissingError



# Cargar variables por si acaso, aunque app.py ya lo hace

load_dotenv()



class AIService:

    @staticmethod

    def configure():

        api_key = os.getenv('GEMINI_API_KEY')

        if not api_key:

            raise APIKeyMissingError("GEMINI_API_KEY no encontrada en variables de entorno")

       

        genai.configure(api_key=api_key)



    @staticmethod

    def generate_summary(text_content):

        """

        Genera un resumen o respuesta basado en el contenido proporcionado.

        """

        AIService.configure()

       

        try:

            model = genai.GenerativeModel('gemini-pro')

           

            prompt = f"""

            Actúa como un estudiante que esta documentando lo que hizo el dia de hoy en vinculación.

            Utiliza las siguientes mensajes que el fue documentando durante el día de trabajo:

            Mensajes:

            {text_content}

           

            Resumen:

            """

           

            response = model.generate_content(prompt)

            return response.text

        except Exception as e:

            # Re-lanzar para que el proxy lo capture si es necesario o manejarlo aquí

            raise e