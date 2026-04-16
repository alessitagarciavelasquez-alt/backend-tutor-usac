import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from markitdown import MarkItDown

# Llamamos a la variable 'app' para que Render la encuentre
app = Flask(__name__)
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

# Clase corregida sin guiones bajos para evitar errores de NameError
class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    respuesta = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return "Tutor AI - Sistema Académico USAC Online"

@app.route('/procesar', methods=['POST'])
def procesar():
    try:
        tipo_solicitud = request.form.get('tipo', 'resumen')
        texto_usuario = request.form.get('texto', '')
        contenido_extraido = ""

        # Procesamiento de archivos (PDF, Word, Excel, Imagen)
        if 'file' in request.files:
            archivo = request.files['file']
            extension = os.path.splitext(archivo.filename)[1]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                archivo.save(tmp.name)
                # MarkItDown hace la magia de leer cualquier formato
                conversion = md.convert(tmp.name)
                contenido_extraido = conversion.text_content
                os.remove(tmp.name)

        prompt_final = f"{texto_usuario}\n\n[Contenido del Documento]:\n{contenido_extraido}"

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system", 
                    "content": "Eres Tutor AI, un asistente académico experto. Analiza el material y genera contenido útil. Si piden diagramas, usa Mermaid.js."
                },
                {"role": "user", "content": prompt_final}
            ]
        )
        
        resultado_ai = response.choices[0].message.content

        # Guardado en base de datos
        nuevo = Historial(tipo=tipo_solicitud, respuesta=resultado_ai)
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({"respuesta": resultado_ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
