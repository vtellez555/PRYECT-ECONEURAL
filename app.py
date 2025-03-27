from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuración para OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

# Contexto especializado para Econeural IA
CHATBOT_CONTEXT = """
Eres EconeuralBot, el asistente virtual de Econeural IA, empresa líder en soluciones tecnológicas para la agricultura. 

Debes seguir estas reglas:
1. Presentarte siempre como asistente de Econeural IA
2. Responder solo sobre temas agrícolas y tecnológicos
3. Usar texto plano sin formatos especiales
4. Ser preciso y profesional
5. Limitar respuestas a 300 palabras máximo

Ejemplo de respuesta adecuada:
"En Econeural IA recomendamos sistemas de monitoreo con sensores IoT para cultivos. ¿En qué más puedo ayudarte?"
"""

@app.route('/')
def home():
    """Sirve la página principal"""
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def econeural_chatbot():
    """Endpoint para el chatbot de Econeural IA"""
    try:
        if not request.is_json:
            return jsonify({"error": "Formato no válido"}), 400
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({"error": "Mensaje vacío"}), 400

        # Procesar con el modelo
        completion = client.chat.completions.create(
            model="deepseek/deepseek-r1-zero:free",
            messages=[
                {"role": "system", "content": CHATBOT_CONTEXT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.6,
            max_tokens=2000
        )

        # Obtener y limpiar respuesta
        response = completion.choices[0].message.content
        response = response.replace('```', '').replace('\\boxed', '').strip()

        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat()[:19]  # Formato YYYY-MM-DD HH:MM:SS
        })

    except Exception as e:
        return jsonify({
            "error": "Servicio no disponible temporalmente",
            "details": str(e)
        }), 500

@app.route('/api/solutions')
def list_solutions():
    """Endpoint de soluciones disponibles"""
    solutions = [
        {"name": "AgroSense", "type": "Monitoreo de cultivos"},
        {"name": "IrriOpt", "type": "Riego inteligente"},
        {"name": "CropShield", "type": "Detección de plagas"}
    ]
    return jsonify(solutions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)