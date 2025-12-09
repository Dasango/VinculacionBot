from .drive_service import get_credentials

def main():
    print("Iniciando proceso de autenticación con Google Drive...")
    print("Se abrirá una ventana de navegador para que autorices la aplicación.")
    try:
        creds = get_credentials()
        if creds and creds.valid:
            print("¡Autenticación exitosa! El archivo token.json ha sido creado/actualizado.")
            print("Ahora puedes ejecutar el bot.")
        else:
            print("No se pudo obtener credenciales válidas.")
    except Exception as e:
        print(f"Ocurrió un error: {e}")

if __name__ == '__main__':
    main()
