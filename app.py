import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman  # Nueva para forzar HTTPS
from openai import OpenAI
from markitdown import MarkItDown

app = Flask(__name__)

# CONFIGURACIÓN DE SEGURIDAD PARA BRAVE Y MÓVILES
# Talisman fuerza HTTPS y configura políticas de seguridad para que Brave no bloquee el sitio
Talisman(app, content_security_policy=None) 
CORS(app)

# Configuración de Base de Datos
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Clientes de Procesamiento
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)
md = MarkItDown()

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    respuesta = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return "Tutor AI - Sistema Académico USAC Online (Secure Mode)"

@app.route('/procesar', methods=['POST'])
def procesar():
    try:
        tipo_solicitud = request.form.get('tipo', 'investigacion')
        texto_usuario = request.form.get('texto', '')
        contenido_extraido = ""

        # LÓGICA DE VELOCIDAD Y COMPATIBILIDAD
        # Si no hay archivo, saltamos el procesamiento pesado para responder instantáneamente
        if 'file' in request.files and request.files['file'].filename != '':
            archivo = request.files['file']
            extension = os.path.splitext(archivo.filename)[1]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                archivo.save(tmp.name)
                conversion = md.convert(tmp.name)
                contenido_extraido = f"\n[Contenido del Documento]:\n{conversion.text_content}"
                os.remove(tmp.name)
        
        # PROMPT OPTIMIZADO PARA INVESTIGACIÓN AUTÓNOMA
        # Si contenido_extraido está vacío, la IA entiende que debe investigar por su cuenta
        system_msg = (
            "Eres Tutor AI, un asistente experto de la Facultad de Ingeniería de la USAC. "
            "Si el usuario te da un tema, investígalo y desarróllalo profundamente. "
            "Si te da un documento, úsalo como base. Usa Mermaid.js para diagramas si es necesario."
        )

        prompt_final = f"Tarea: {tipo_solicitud}. Tema o consulta: {texto_usuario} {contenido_extraido}"

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt_final}
            ],
            stream=False # Mantener en False para estabilidad en dispositivos móviles
        )
        
        resultado_ai = response.choices[0].message.content

        # Guardado en base de datos (Trabajo de Alessia y Stefan)
        nuevo = Historial(tipo=tipo_solicitud, respuesta=resultado_ai)
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({"respuesta": resultado_ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
