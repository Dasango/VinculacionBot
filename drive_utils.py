import os
import io
import datetime
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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

def upload_image_from_stream(file_stream, filename, description=None):
    """Sube una imagen desde un stream de bytes a Google Drive y retorna la carpeta del día."""
    try:
        service = get_drive_service()
        
        # 1. Obtener/Crear carpeta del día (DD-MM-YYYY)
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        daily_folder = get_or_create_folder(service, today_str, PARENT_FOLDER_ID)
        daily_folder_id = daily_folder.get('id')
        
        # 2. Generar nombre de archivo único
        unique_filename = get_unique_filename(service, filename, daily_folder_id)
        
        # 3. Preparar metadata y subida
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

def find_today_row(service, spreadsheet_id):
    """Busca la fila correspondiente a la fecha de hoy. Retorna el índice (1-based) o None."""
    today_str = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Leer Columna A (Fecha)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range="A:A").execute()
    values = result.get('values', [])
    
    for i, row in enumerate(values):
        if row and row[0] == today_str:
            return i + 1  # 1-based index
            
    return None

def append_text_log(text):
    """Agrega texto a la columna Descripción (C) del día de hoy."""
    try:
        service = get_sheets_service()
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        
        row_idx = find_today_row(service, SPREADSHEET_ID)
        
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
                
            # Actualizar celda
            body = {'values': [[new_desc]]}
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=range_name,
                valueInputOption="RAW", body=body).execute()
        else:
            # Crear nueva fila al final
            # Estructura: [Fecha, Duración(vacio), Descripción, LinkFoto]
            # LinkFoto default: "No se han guardaron fotos"
            values = [[today_str, "", text, "No se han guardaron fotos"]]
            body = {'values': values}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, range="A1",
                valueInputOption="RAW", insertDataOption="INSERT_ROWS", body=body).execute()
                
    except Exception as e:
        logging.error(f"Error actualizando Sheets (Texto): {str(e)}")
        # No relanzamos para no interrumpir el flujo principal del bot si falla sheets

def update_daily_folder_link(folder_link):
    """Actualiza la columna LinkFoto (D) con el link de la carpeta del día."""
    try:
        service = get_sheets_service()
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        
        row_idx = find_today_row(service, SPREADSHEET_ID)
        
        if row_idx:
            # Fila existe, actualizar LinkFoto (Col D)
            range_name = f"D{row_idx}"
            body = {'values': [[folder_link]]}
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=range_name,
                valueInputOption="RAW", body=body).execute()
        else:
            # Fila no existe (caso raro si sube foto primero que texto)
            # Crear fila
            values = [[today_str, "", "", folder_link]]
            body = {'values': values}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, range="A1",
                valueInputOption="RAW", insertDataOption="INSERT_ROWS", body=body).execute()
                
    except Exception as e:
        logging.error(f"Error actualizando Sheets (Link): {str(e)}")
