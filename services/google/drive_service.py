import os
import io
import datetime
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
import tempfile

# Scopes actualizados para Drive y Sheets
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]
PARENT_FOLDER_ID = '1sWn78Jmx0QSeOtTgdcyOonovk0jd3kgO'
SPREADSHEET_ID = '1rXGnD3XQp-ecmdxxgJGf-K-SbxLWYawKXFOqkbl_Dmw'

def get_credentials():
    """Obtiene las credenciales de usuario válidas."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'config/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return creds

def get_drive_service():
    """Retorna el servicio de la API de Drive."""
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds)

def get_sheets_service():
    """Retorna el servicio de la API de Sheets."""
    creds = get_credentials()
    return build('sheets', 'v4', credentials=creds)

# --- DRIVE FUNCTIONS ---

def get_or_create_folder(service, folder_name, parent_id):
    """Busca una carpeta por nombre dentro de un padre, si no existe la crea."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name, webViewLink)').execute()
    items = results.get('files', [])

    if not items:
        # Crear carpeta
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=file_metadata, fields='id, name, webViewLink').execute()
        logging.info(f"Carpeta creada: {folder_name} ({folder.get('id')})")
        return folder
    else:
        # Retornar la primera encontrada
        return items[0]

def get_unique_filename(service, filename, parent_id):
    """Verifica si el archivo existe y retorna un nombre único si es necesario."""
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    
    while True:
        query = f"name='{new_filename}' and '{parent_id}' in parents and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        items = results.get('files', [])
        
        if not items:
            return new_filename
            
        new_filename = f"{name} ({counter}){ext}"
        counter += 1

def upload_image_from_stream(file_stream, filename, user_id, description=None):
    """Sube una imagen desde un stream de bytes a Google Drive y retorna la carpeta del día."""
    try:
        service = get_drive_service()

        # 1. Obtener/Crear carpeta del Usuario (ID de Telegram)
        # Nota: user_id debe ser string
        user_folder = get_or_create_folder(service, str(user_id), PARENT_FOLDER_ID)
        user_folder_id = user_folder.get('id')
        
        # 2. Obtener/Crear carpeta del día (DD-MM-YYYY) DENTRO de la carpeta del usuario
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        daily_folder = get_or_create_folder(service, today_str, user_folder_id)
        daily_folder_id = daily_folder.get('id')
        
        # 3. Generar nombre de archivo único
        unique_filename = get_unique_filename(service, filename, daily_folder_id)
        
        # 4. Preparar metadata y subida
        file_metadata = {
            'name': unique_filename,
            'parents': [daily_folder_id]
        }
        
        if description:
            file_metadata['description'] = description
            
        media = MediaIoBaseUpload(file_stream, mimetype='image/jpeg', resumable=True)
        
        # 4. Ejecutar subida
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        
        logging.info(f"Archivo subido: {file.get('name')} ID: {file.get('id')}")
        return file, daily_folder
        
    except Exception as e:
        logging.error(f"Error subiendo a Drive: {str(e)}")
        raise e

# --- SHEETS FUNCTIONS ---

def find_user_today_row(service, spreadsheet_id, user_id):
    """Busca la fila correspondiente al usuario y la fecha de hoy. Retorna el índice (1-based) o None."""
    today_str = datetime.datetime.now().strftime("%d-%m-%Y")
    str_user_id = str(user_id)
    
    # Leer Columnas A (User) y B (Fecha)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range="A:B").execute()
    values = result.get('values', [])
    
    for i, row in enumerate(values):
        # Asegurarse que la fila tenga al menos 2 columnas
        if len(row) >= 2 and row[0] == str_user_id and row[1] == today_str:
            return i + 1  # 1-based index
            
    return None

def update_timer_logic(service, spreadsheet_id, row_idx):
    """Actualiza G (Inicio), H (Fin) y E (Duración) para una fila existente."""
    try:
        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 1. Chequear si G está vacío
        range_g = f"G{row_idx}"
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_g).execute()
        
        values = result.get('values', [])
        current_g = values[0][0] if values and values[0] else None
        
        data = []
        # Si G vacío, actualizarlo
        if not current_g:
            data.append({'range': f"G{row_idx}", 'values': [[now_time]]})
            
        # Siempre actualizar H
        data.append({'range': f"H{row_idx}", 'values': [[now_time]]})
        
        # Asegurar fórmula E
        formula = f"=H{row_idx}-G{row_idx}"
        data.append({'range': f"E{row_idx}", 'values': [[formula]]})
        
        body = {
            'valueInputOption': 'USER_ENTERED',
            'data': data
        }
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body).execute()
            
    except Exception as e:
        logging.error(f"Error actualizando timers: {str(e)}")

def append_text_log(text, user_id):
    """Agrega texto a la columna Descripción (C) para el usuario y día de hoy."""
    if not user_id:
        return

    try:
        service = get_sheets_service()
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        str_user_id = str(user_id)
        
        row_idx = find_user_today_row(service, SPREADSHEET_ID, user_id)
        
        if row_idx:
            # La fila existe, obtener contenido actual de Descripción (Col C)
            range_name = f"C{row_idx}"
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
            current_desc = result.get('values', [[None]])[0][0] or ""
            
            # Concatenar
            if current_desc:
                new_desc = current_desc + "\n" + text
            else:
                new_desc = text
                
            # Actualizar celda Descripción
            body_desc = {'values': [[new_desc]]}
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=range_name,
                valueInputOption="RAW", body=body_desc).execute()
            
            # Actualizar timers
            update_timer_logic(service, SPREADSHEET_ID, row_idx)

        else:
            # Crear nueva fila al final
            # Estructura: [User, Fecha, Descripción, Carpeta, Duración, "Filler", Inicio, Fin]
            now_time = datetime.datetime.now().strftime("%H:%M:%S")
            formula = '=INDIRECT("H"&ROW())-INDIRECT("G"&ROW())'
            
            values = [[str_user_id, today_str, text, "No se han guardaron fotos", formula, "", now_time, now_time]]
            body = {'values': values}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, range="A1",
                valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body).execute()
                
    except Exception as e:
        logging.error(f"Error actualizando Sheets (Texto): {str(e)}")

def update_daily_folder_link(folder_link, user_id):
    """Actualiza la columna Carpeta (D) con el link para el usuario y día de hoy."""
    if not user_id:
        return

    try:
        service = get_sheets_service()
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        str_user_id = str(user_id)
        
        row_idx = find_user_today_row(service, SPREADSHEET_ID, user_id)
        
        if row_idx:
            # Fila existe, actualizar Carpeta (Col D)
            range_name = f"D{row_idx}"
            body = {'values': [[folder_link]]}
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=range_name,
                valueInputOption="RAW", body=body).execute()
            
            # Actualizar timers
            update_timer_logic(service, SPREADSHEET_ID, row_idx)
                
        else:
            # Fila no existe
            # Estructura: [User, Fecha, Descripción, Carpeta, Duración, "Filler", Inicio, Fin]
            now_time = datetime.datetime.now().strftime("%H:%M:%S")
            formula = '=INDIRECT("H"&ROW())-INDIRECT("G"&ROW())'
            
            values = [[str_user_id, today_str, "", folder_link, formula, "", now_time, now_time]]
            body = {'values': values}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, range="A1",
                valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body).execute()
                
    except Exception as e:
        logging.error(f"Error actualizando Sheets (Link): {str(e)}")

def get_day_descriptions(user_id):
    """
    Obtiene el contenido de la columna C (Descripción) para el usuario y día actual.
    Retorna una lista de strings o None si no se encuentra.
    """
    if not user_id:
        return None
        
    try:
        service = get_sheets_service()
        row_idx = find_user_today_row(service, SPREADSHEET_ID, user_id)
        
        if row_idx:
            range_name = f"C{row_idx}"
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
            values = result.get('values', [])
            if values and values[0]:
                return values[0][0]
                
        return None
        
    except Exception as e:
        logging.error(f"Error leyendo descripciones: {str(e)}")
        raise e

def update_ai_response(response_text, user_id):
    """Actualiza la columna F (AI Response) con el texto generado."""
    if not user_id:
        return

    try:
        service = get_sheets_service()
        row_idx = find_user_today_row(service, SPREADSHEET_ID, user_id)
        
        if row_idx:
            # Columna F es la 6ta columna
            range_name = f"F{row_idx}"
            body = {'values': [[response_text]]}
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=range_name,
                valueInputOption="RAW", body=body).execute()
        else:
            # Si no existe la fila, no podemos guardar la respuesta IA asociada a mensajes inexistentes
            # (Aunque teóricamente se podría crear, el requerimiento es procesar mensajes existentes)
            pass
            
    except Exception as e:
        logging.error(f"Error actualizando Sheets (AI): {str(e)}")
        raise e

def get_day_messages(user_id):
    """
    Obtiene los mensajes individuales (separados por salto de línea) 
    de la columna descripción para el usuario y día de hoy.
    Retorna lista de strings o lista vacía.
    """
    content = get_day_descriptions(user_id)
    if content:
        return content.split('\n')
    return []

def delete_message_line(user_id, line_index):
    """
    Elimina un mensaje específico (por índice 0-based) de la celda de descripción.
    """
    if not user_id:
        return False

    try:
        service = get_sheets_service()
        row_idx = find_user_today_row(service, SPREADSHEET_ID, user_id)
        
        if row_idx:
            # 1. Obtener contenido actual
            range_name = f"C{row_idx}"
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
            values = result.get('values', [[None]])
            current_desc = values[0][0] or ""
            
            if not current_desc:
                return False
                
            # 2. Procesar lista
            messages = current_desc.split('\n')
            
            if 0 <= line_index < len(messages):
                removed = messages.pop(line_index)
                logging.info(f"Eliminando mensaje índice {line_index}: {removed}")
                
                # 3. Reconstruir y guardar
                new_desc = "\n".join(messages)
                
                body_desc = {'values': [[new_desc]]}
                service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID, range=range_name,
                    valueInputOption="RAW", body=body_desc).execute()
                return True
                
        return False
            

    except Exception as e:
        logging.error(f"Error eliminando mensaje en Sheets: {str(e)}")
        raise e

def get_ai_response(user_id):
    """
    Obtiene el contenido de la columna F (AI Response) para el usuario y día actual.
    Retorna el string de la respuesta o None si no existe.
    """
    if not user_id:
        return None
        
    try:
        service = get_sheets_service()
        row_idx = find_user_today_row(service, SPREADSHEET_ID, user_id)
        
        if row_idx:
            range_name = f"F{row_idx}"
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
            values = result.get('values', [])
            if values and values[0]:
                return values[0][0]
                
        return None
        
    except Exception as e:
        logging.error(f"Error leyendo AI response: {str(e)}")
        raise e


def generate_excel_report(user_id):
    """
    Genera un archivo Excel con todos los registros del usuario.
    Retorna la ruta del archivo temporal generado.
    """
    if not user_id:
        return None

    try:
        service = get_sheets_service()
        str_user_id = str(user_id)
        
        # 1. Leer todos los datos
        # Asumiendo que las columnas son A-H. Leeremos todo el rango con datos.
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range="A:H").execute()
        
        values = result.get('values', [])
        
        if not values:
            return None
            
        # 2. Filtrar por usuario y mapear columnas
        # Indices (0-based):
        # 0: User, 1: Fecha, 2: Descripcion, 3: Carpeta (Images), 4: Duracion, 5: AI Response (Tus mensajes)
        # Output columns: Fecha, duracion, Descripcion, images, tus mensajes
        
        data = []
        for row in values:
            # Asegurar que la fila tenga suficientes columnas para chequear usuario (Indices pueden variar si la fila esta vacia al final)
            if len(row) > 0 and row[0] == str_user_id:
                # Extraer datos con manejo de indices fuera de rango
                fecha = row[1] if len(row) > 1 else ""
                desc = row[2] if len(row) > 2 else ""
                imgs = row[3] if len(row) > 3 else ""
                duracion = row[4] if len(row) > 4 else ""
                ai_msg = row[5] if len(row) > 5 else ""
                
                if not ai_msg:
                    ai_msg = "No se ha usado el comando /send para que la ia genere la descripcion"

                data.append({
                    'Fecha': fecha,
                    'duracion': duracion,
                    'Descripcion': desc,
                    'images': imgs,
                    'tus mensajes': ai_msg
                })
        
        if not data:
            return None
            
        # 3. Crear DataFrame
        df = pd.DataFrame(data)
        
        # Reordenar columnas si es necesario (el dict puede no mantener orden en versiones viejas de python, pero pandas si recibed lista de dicts usa orden de keys o alfabetico? Mejor especificar columnas)
        df = df[['Fecha', 'duracion', 'Descripcion', 'images', 'tus mensajes']]
        
        # 4. Guardar a Excel temporal
        # Usar tempfile para crear un archivo temporal seguro
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_{timestamp}.xlsx"
        filepath = os.path.join(temp_dir, filename)
        
        df.to_excel(filepath, index=False)
        
        return filepath

    except Exception as e:
        logging.error(f"Error generando reporte Excel: {str(e)}")
        raise e
