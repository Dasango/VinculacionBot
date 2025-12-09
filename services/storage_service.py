
import sqlite3
import datetime
import logging
import os

DB_PATH = 'bot_data.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_limits (
                    user_id TEXT,
                    command TEXT,
                    date TEXT,
                    count INTEGER,
                    PRIMARY KEY (user_id, command, date)
                )
            ''')
            conn.commit()
            
            # Tabla para configuración de usuarios (límites)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_configs (
                    user_id TEXT PRIMARY KEY,
                    max_uses INTEGER
                )
            ''')
            conn.commit()
            conn.close()
            logging.info("Base de datos de límites inicializada.")
        except Exception as e:
            logging.error(f"Error inicializando DB: {e}")

def get_today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def get_usage(user_id, command):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = get_today_str()
        cursor.execute('SELECT count FROM usage_limits WHERE user_id = ? AND command = ? AND date = ?', (str(user_id), command, today))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['count']
        return 0
    except Exception as e:
        logging.error(f"Error obteniendo uso: {e}")
        return 0

def increment_usage(user_id, command):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = get_today_str()
        
        # Check current usage
        cursor.execute('SELECT count FROM usage_limits WHERE user_id = ? AND command = ? AND date = ?', (str(user_id), command, today))
        row = cursor.fetchone()
        
        if row:
            new_count = row['count'] + 1
            cursor.execute('UPDATE usage_limits SET count = ? WHERE user_id = ? AND command = ? AND date = ?', (new_count, str(user_id), command, today))
        else:
            cursor.execute('INSERT INTO usage_limits (user_id, command, date, count) VALUES (?, ?, ?, 1)', (str(user_id), command, today))
            
        conn.commit()
        conn.close()
        logging.info(f"Incrementado uso para {user_id} en comando {command}.")
        return True
    except Exception as e:
        logging.error(f"Error incrementando uso: {e}")
        return False
        return False

def get_user_limit(user_id, default_limit=1):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT max_uses FROM user_configs WHERE user_id = ?', (str(user_id),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['max_uses']
        return default_limit
    except Exception as e:
        logging.error(f"Error obteniendo límite de usuario: {e}")
        return default_limit

def set_user_limit(user_id, limit):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Upsert (SQLite >= 3.24 supports ON CONFLICT)
        # Using classic approach for broader compatibility:
        cursor.execute('INSERT OR REPLACE INTO user_configs (user_id, max_uses) VALUES (?, ?)', (str(user_id), limit))
        conn.commit()
        conn.close()
        logging.info(f"Límite actualizado para {user_id}: {limit}")
        return True
    except Exception as e:
        logging.error(f"Error estableciendo límite: {e}")
        return False
