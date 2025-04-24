from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
from openai import OpenAI
from datetime import datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2 import sql

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configuración para OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

# Configuración de correo electrónico
EMAIL_CONFIG = {
    'sender': 'corporationeconeuralia@gmail.com',
    'password': 'bsvy ncuq kggb etjv',
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'company_name': 'Econeural IA'
}

# Contexto del chatbot
CHATBOT_CONTEXT = """
Eres EconeuralBot, el asistente virtual de Econeural IA, empresa líder en soluciones tecnológicas para la agricultura. 

Debes seguir estas reglas:
1. Presentarte siempre como asistente de Econeural IA
2. Responder solo sobre temas agrícolas y tecnológicos
3. Usar texto plano sin formatos especiales
4. Ser preciso y profesional
5. Limitar respuestas a 300 palabras máximo
"""

# Conexión a PostgreSQL

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
    
def get_db_connection():
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

# Inicialización de la base de datos
def init_db():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # Crear tabla de usuarios si no existe
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        phone VARCHAR(20),
                        email VARCHAR(255) PRIMARY KEY,
                        password_hash VARCHAR(255),
                        verified BOOLEAN,
                        registration_date TIMESTAMP
                    )
                """)
                
                # Crear tabla de verificaciones temporales
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS temp_verifications (
                        phone VARCHAR(20),
                        email VARCHAR(255),
                        password VARCHAR(255),
                        verification_code VARCHAR(6),
                        timestamp TIMESTAMP
                    )
                """)
                
                # Crear tabla de sesiones activas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_sessions (
                        session_id VARCHAR(50) PRIMARY KEY,
                        email VARCHAR(255),
                        login_time TIMESTAMP
                    )
                """)
                
                conn.commit()
            print("✅ Tablas creadas/existen en PostgreSQL!")
        except psycopg2.Error as e:
            print(f"Error al crear tablas: {e}")
        finally:
            conn.close()

# Función para enviar correos 
def send_verification_email(email, code):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Verificación de cuenta - {EMAIL_CONFIG["company_name"]}'
        msg['From'] = EMAIL_CONFIG['sender']
        msg['To'] = email
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
                    <h2 style="color: #2c3e50;">Verificación de cuenta</h2>
                    <p>Tu código de verificación es:</p>
                    <div style= background-color: #f8f9fa; padding: 15px; text-align: center; margin: 20px 0; 
                                border-radius: 5px; font-size: 24px; font-weight: bold; color: #2c3e50;">
                        {code}
                    </div>
                    <p>Este código expira en 10 minutos.</p>
                </div>
            </body>
        </html>
        """
        
        text = f"Tu código de verificación es: {code}\n\nExpira en 10 minutos."
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            server.sendmail(EMAIL_CONFIG['sender'], email, msg.as_string())
        
        return True
    except Exception as e:
        print(f"Error al enviar correo: {str(e)}")
        return False

# Decorador para rutas protegidas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.cookies.get('session_id')
        if not session_id or not validate_session(session_id):
            return jsonify({"error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Manejo de sesiones (ahora con PostgreSQL)
def create_session(email):
    session_id = generate_password_hash(f"{email}{datetime.now().timestamp()}")[:50]
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO active_sessions (session_id, email, login_time) VALUES (%s, %s, %s)",
                    (session_id, email, datetime.now())
                )
                conn.commit()
            return session_id
        except psycopg2.Error as e:
            print(f"Error al crear sesión: {e}")
        finally:
            conn.close()
    return None

def validate_session(session_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM active_sessions WHERE session_id = %s",
                    (session_id,)
                )
                return cur.fetchone() is not None
        except psycopg2.Error as e:
            print(f"Error al validar sesión: {e}")
        finally:
            conn.close()
    return False

def delete_session(session_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM active_sessions WHERE session_id = %s",
                    (session_id,)
                )
                conn.commit()
        except psycopg2.Error as e:
            print(f"Error al eliminar sesión: {e}")
        finally:
            conn.close()

# Rutas de autenticación (modificadas para PostgreSQL)
@app.route('/api/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        phone = data.get('phone')
        email = data.get('email')
        password = data.get('password')
        
        if not all([phone, email, password]):
            return jsonify({"error": "Todos los campos son requeridos"}), 400
        
        if len(password) < 8:
            return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM users WHERE email = %s",
                        (email,)
                    )
                    if cur.fetchone():
                        return jsonify({"error": "Este correo ya está registrado"}), 400
            except psycopg2.Error as e:
                print(f"Error al verificar usuario existente: {e}")
                return jsonify({"error": "Error interno del servidor"}), 500
            finally:
                conn.close()
        
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        if not send_verification_email(email, verification_code):
            return jsonify({"error": "Error al enviar código de verificación"}), 500
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO temp_verifications (phone, email, password, verification_code, timestamp) VALUES (%s, %s, %s, %s, %s)",
                        (phone, email, password, verification_code, datetime.now())
                    )
                    conn.commit()
            except psycopg2.Error as e:
                print(f"Error al guardar verificación temporal: {e}")
                return jsonify({"error": "Error interno del servidor"}), 500
            finally:
                conn.close()
        
        return jsonify({
            "success": True, 
            "message": "Código enviado",
            "email": email
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/verify', methods=['POST'])
def verify_user():
    try:
        data = request.get_json()
        email = data.get('email')
        code = data.get('code')
        
        if not email or not code:
            return jsonify({"error": "Correo y código son requeridos"}), 400
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Buscar en verificaciones temporales
                    cur.execute(
                        "SELECT phone, email, password, verification_code, timestamp FROM temp_verifications WHERE email = %s AND verification_code = %s",
                        (email, code)
                    )
                    user_data = cur.fetchone()
                    
                    if user_data:
                        phone, email, password, verification_code, reg_time = user_data
                        
                        if (datetime.now() - reg_time).total_seconds() > 600:
                            return jsonify({"error": "Código expirado"}), 400
                        
                        # Registrar usuario en la tabla principal
                        cur.execute(
                            "INSERT INTO users (phone, email, password_hash, verified, registration_date) VALUES (%s, %s, %s, %s, %s)",
                            (phone, email, generate_password_hash(password), True, datetime.now())
                        )
                        
                        # Eliminar de verificaciones temporales
                        cur.execute(
                            "DELETE FROM temp_verifications WHERE email = %s",
                            (email,)
                        )
                        
                        conn.commit()
                        
                        session_id = create_session(email)
                        response = jsonify({
                            "success": True, 
                            "message": "Cuenta verificada",
                            "redirect": "/Pagina_principal.html"
                        })
                        response.set_cookie('session_id', session_id, httponly=True)
                        return response
                    
                    return jsonify({"error": "Código inválido"}), 400
            except psycopg2.Error as e:
                print(f"Error al verificar usuario: {e}")
                return jsonify({"error": "Error interno del servidor"}), 500
            finally:
                conn.close()
        
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login_user():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT email, password_hash, verified FROM users WHERE email = %s",
                        (email,)
                    )
                    user = cur.fetchone()
                    
                    if user and check_password_hash(user[1], password):
                        if not user[2]:  # verified
                            return jsonify({"error": "Cuenta no verificada"}), 403
                        
                        session_id = create_session(email)
                        response = jsonify({
                            "success": True,
                            "message": "Autenticación exitosa",
                            "redirect": "/Pagina_principal.html"
                        })
                        response.set_cookie('session_id', session_id, httponly=True)
                        return response
                    
                    return jsonify({"error": "Credenciales inválidas"}), 401
            except psycopg2.Error as e:
                print(f"Error al autenticar usuario: {e}")
                return jsonify({"error": "Error interno del servidor"}), 500
            finally:
                conn.close()
        
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session_id = request.cookies.get('session_id')
    if session_id:
        delete_session(session_id)
    response = jsonify({"success": True, "message": "Sesión cerrada"})
    response.set_cookie('session_id', '', expires=0)
    return response

@app.route('/api/check-auth', methods=['GET'])
@login_required
def check_auth():
    return jsonify({"success": True, "message": "Autenticado"})

# Rutas de la aplicación (igual que antes)
@app.route('/')
def home():
    return send_from_directory('.', 'login.html')

@app.route('/login.html')
def login():
    return send_from_directory('.', 'login.html')

@app.route('/register.html')
def register():
    return send_from_directory('.', 'register.html')

@app.route('/Pagina_principal.html')
@login_required
def pagina_principal():
    return send_from_directory('.', 'Pagina_principal.html')

@app.route('/chat', methods=['POST'])
@login_required
def econeural_chatbot():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({"error": "Mensaje vacío"}), 400

        completion = client.chat.completions.create(
            model="deepseek/deepseek-r1-zero:free",
            messages=[
                {"role": "system", "content": CHATBOT_CONTEXT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.6,
            max_tokens=2000
        )

        response = completion.choices[0].message.content
        response = response.replace('```', '').replace('\\boxed', '').strip()

        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat()[:19]
        })

    except Exception as e:
        return jsonify({"error": "Error en el chatbot", "details": str(e)}), 500

# Inicialización
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)