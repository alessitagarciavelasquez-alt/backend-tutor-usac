import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from markitdown import MarkItDown

_app = Flask(__name__)
CORS(_app)

# Configuración de Base de Datos
_basedir = os.path.abspath(os.path.dirname(__file__))
_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(_basedir, 'tutor_ai.db')
_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

_db = SQLAlchemy(_app)

# Clientes de Procesamiento
_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)
_md = MarkItDown()

# Clase corregida (usando un solo _ para evitar el error de Render)
class Historial(_db.Model):
    id = _db.Column(_db.Integer, primary_key=True)
    tipo = _db.Column(_db.String(50))
    respuesta = _db.Column(_db.Text)

with _app.app_context():
    _db.create_all()

@_app.route('/')
def home():
    return "Tutor AI - Sistema Académico USAC Online"

@_app.route('/procesar', methods=['POST'])
def procesar():
    try:
        _tipo = request.form.get('tipo', 'resumen')
        _texto_dictado = request.form.get('texto', '')
        _contenido_extraido = ""

        if 'file' in request.files:
            _file = request.files['file']
            _extension = os.path.splitext(_file.filename)[1]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=_extension) as _temp:
                _file.save(_temp.name)
                _conversion = _md.convert(_temp.name)
                _contenido_extraido = _conversion.text_content
                os.remove(_temp.name)

        _prompt_final = f"{_texto_dictado}\n\nContenido extraído:\n{_contenido_extraido}"

        _response = _client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system", 
                    "content": "Eres Tutor AI, asistente de ingeniería. Genera contenido educativo. Para mapas, usa Mermaid.js."
                },
                {"role": "user", "content": _prompt_final}
            ]
        )
        
        _resultado = _response.choices[0].message.content

        # Guardado en base de datos
        _nuevo_registro = Historial(tipo=_tipo, respuesta=_resultado)
        _db.session.add(_nuevo_registro)
        _db.session.commit()

        return jsonify({"respuesta": _resultado})

    except Exception as _e:
        return jsonify({"error": str(_e)}), 500

if __name__ == "__main__":
    _port = int(os.environ.get("PORT", 5000))
    _app.run(host='0.0.0.0', port=_port)
