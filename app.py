import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI

app = Flask(_name_)
CORS(app) # Permite que el sitio de tu compañero se conecte a tu servidor

# Configuración de Base de Datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usac_estudio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuración de DeepSeek
client = OpenAI(api_key="TU_API_KEY_AQUI", base_url="https://api.deepseek.com")

# Modelo de la Base de Datos
class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, server_default=db.func.now())
    analisis = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return "Servidor de Alessia Activo - Sección F"

@app.route('/analizar', methods=['POST'])
def analizar():
    try:
        data = request.json
        img_b64 = data.get('image')

        # Llamada a DeepSeek
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Eres un asistente de ingeniería USAC. Transcribe con exactitud. Si algo es ambiguo indica: DATO NO LEGIBLE."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analiza esta imagen y genera apuntes técnicos:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]}
            ]
        )
        
        resultado = response.choices[0].message.content

        # Guardar en SQL
        nuevo_registro = Registro(analisis=resultado)
        db.session.add(nuevo_registro)
        db.session.commit()

        return jsonify({"respuesta": resultado})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if _name_ == "_main_":
    app.run()
