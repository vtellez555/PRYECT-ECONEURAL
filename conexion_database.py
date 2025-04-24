import os
import psycopg2

def load_env(env_file='data_base_registros.env'):
    """Lee el archivo .env"""
    config = {}
    try:
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    config[key] = value
        return config
    except Exception as e:
        print(f"Error leyendo .env: {e}")
        return None

def connect_postgresql():
    """Establece conexión con PostgreSQL"""
    config = load_env()
    if not config:
        return None

    try:
        conn = psycopg2.connect(
            dbname=config.get('DB_NAME'),
            user=config.get('DB_USER'),
            password=config.get('DB_PASSWORD'),
            host=config.get('DB_HOST'),
            port=config.get('DB_PORT')
        )
        print("✅ Conexión exitosa a PostgreSQL!")
        return conn
    except psycopg2.Error as e:
        print(f" Error de conexión: {e}")
        return None

# Uso:
if __name__ == "__main__":
    conn = connect_postgresql()
    if conn:
        conn.close()