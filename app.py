import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman 
from openai import OpenAI
from markitdown import MarkItDown

app = Flask(__name__)

# SEGURIDAD Y COMPATIBILIDAD: Habilita micrófono y archivos en Brave/Móviles
Talisman(app, content_security_policy=None) 
CORS(app)

# Configuración de Base de Datos
basedir = os.path.abspath(os.path.dirname(_file_))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Clientes de Procesamiento
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
md = MarkItDown()

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    respuesta = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route('/procesar', methods=['POST'])
def procesar():
    try:
        tipo_solicitud = request.form.get('tipo', 'investigacion')
        texto_usuario = request.form.get('texto', '')
        contenido_extraido = ""

        # Procesamiento rápido de archivos
        if 'file' in request.files and request.files['file'].filename != '':
            archivo = request.files['file']
            extension = os.path.splitext(archivo.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                archivo.save(tmp.name)
                conversion = md.convert(tmp.name)
                contenido_extraido = f"\n[Documento para analizar]:\n{conversion.text_content}"
                os.remove(tmp.name)
        
        # REFUERZO DE IDENTIDAD Y AUTONOMÍA
        # Se establece "Tutor AI" como único nombre oficial
        system_msg = (
            "Tu nombre es exclusivamente 'Tutor AI'. Eres un asistente de ingeniería de la USAC. "
            "Si te preguntan quién eres, responde siempre como Tutor AI. "
            "Posees razonamiento autónomo: si recibes un tema, desarróllalo; si recibes un problema, resuélvelo. "
            "No esperes instrucciones extras. Piensa y actúa de forma proactiva como un experto. "
            "Usa Mermaid.js para visualizaciones técnicas."
        )

        prompt_final = f"Consulta del estudiante: {texto_usuario} {contenido_extraido}"

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt_final}
            ]
        )
        
        resultado_ai = response.choices[0].message.content
        
        # Persistencia de datos
        nuevo = Historial(tipo=tipo_solicitud, respuesta=resultado_ai)
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({"respuesta": resultado_ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if _name_ == "_main_":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
