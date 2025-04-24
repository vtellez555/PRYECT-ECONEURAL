from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
from openai import OpenAI
from datetime import datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import csv
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
CORS(app, supports_credentials=True)

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

# Archivos de almacenamiento
USERS_FILE = 'users.csv'
TEMP_VERIFICATIONS_FILE = 'temp_verifications.csv'
SESSION_FILE = 'active_sessions.csv'

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

# Inicialización de archivos
def init_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['phone', 'email', 'password_hash', 'verified', 'registration_date'])
    
    if not os.path.exists(TEMP_VERIFICATIONS_FILE):
        with open(TEMP_VERIFICATIONS_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['phone', 'email', 'password', 'verification_code', 'timestamp'])
    
    if not os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['session_id', 'email', 'login_time'])

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
                    <div style="background-color: #f8f9fa; padding: 15px; text-align: center; margin: 20px 0; 
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

# Manejo de sesiones
def create_session(email):
    session_id = generate_password_hash(f"{email}{datetime.now().timestamp()}")[:50]
    with open(SESSION_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([session_id, email, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    return session_id

def validate_session(session_id):
    if not os.path.exists(SESSION_FILE):
        return False
        
    with open(SESSION_FILE, mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for session in reader:
            if len(session) > 0 and session[0] == session_id:
                return True
    return False

def delete_session(session_id):
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, mode='r') as file:
            sessions = list(csv.reader(file))
        
        updated_sessions = [s for s in sessions if len(s) > 0 and s[0] != session_id]
        
        with open(SESSION_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(updated_sessions)

# Rutas de autenticación
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
        
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, mode='r') as file:
                reader = csv.reader(file)
                next(reader)
                for user in reader:
                    if len(user) > 1 and user[1] == email:
                        return jsonify({"error": "Este correo ya está registrado"}), 400
        
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        if not send_verification_email(email, verification_code):
            return jsonify({"error": "Error al enviar código de verificación"}), 500
        
        with open(TEMP_VERIFICATIONS_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                phone, 
                email, 
                password, 
                verification_code,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        
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
        
        temp_users = []
        if os.path.exists(TEMP_VERIFICATIONS_FILE):
            with open(TEMP_VERIFICATIONS_FILE, mode='r') as file:
                reader = csv.reader(file)
                temp_users = list(reader)
        
        for user in temp_users:
            if len(user) >= 4 and user[1] == email and user[3] == code:
                reg_time = datetime.strptime(user[4], '%Y-%m-%d %H:%M:%S') if len(user) > 4 else datetime.now()
                if (datetime.now() - reg_time).total_seconds() > 600:
                    return jsonify({"error": "Código expirado"}), 400
                
                with open(USERS_FILE, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([
                        user[0],  # phone
                        user[1],  # email
                        generate_password_hash(user[2]),  # password hash
                        True,  # verified
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ])
                
                updated_temp = [u for u in temp_users if u[1] != email]
                with open(TEMP_VERIFICATIONS_FILE, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerows(updated_temp)
                
                session_id = create_session(email)
                response = jsonify({
                    "success": True, 
                    "message": "Cuenta verificada",
                    "redirect": "/Pagina_principal.html"
                })
                response.set_cookie('session_id', session_id, httponly=True)
                return response
        
        return jsonify({"error": "Código inválido"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login_user():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        with open(USERS_FILE, mode='r') as file:
            reader = csv.reader(file)
            next(reader)
            for user in reader:
                if len(user) >= 3 and user[1] == email and check_password_hash(user[2], password):
                    if user[3] != 'True':
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

# Rutas de la aplicación
@app.route('/')
def home():
    return send_from_directory('.', 'login_registro.html')

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
    init_files()
    app.run(host='0.0.0.0', port=5000, debug=True)