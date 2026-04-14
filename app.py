import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Configuración de Base de Datos para Render
basedir = os.path.abspath(os.path.dirname(_file_))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'estudiante_usac.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Cliente de DeepSeek
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)

# Modelo SQL
class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    contenido = db.Column(db.Text)
    fecha = db.Column(db.DateTime, server_default=db.func.now())

# Crear tablas al iniciar
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return "Servidor de Alessia activo y funcionando para la USAC"

@app.route('/procesar', methods=['POST'])
def procesar():
    try:
        data = request.json
        tipo_solicitud = data.get('tipo')
        texto_clase = data.get('texto')

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"Eres un tutor de ingeniería experto. Genera un {tipo_solicitud}."},
                {"role": "user", "content": texto_clase}
            ]
        )
        
        resultado = response.choices[0].message.content

        # Guardar en SQL
        nuevo = Historial(tipo=tipo_solicitud, contenido=resultado)
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({"respuesta": resultado})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
