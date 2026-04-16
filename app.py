import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from markitdown import MarkItDown

__app = Flask(__name__)
CORS(__app)

# Configuración Privada de Base de Datos
__basedir = os.path.abspath(os.path.dirname(__file__))
__app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(__basedir, 'tutor_ai.db')
__app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

__db = SQLAlchemy(__app)

# Clientes de Procesamiento
__client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)
__md = MarkItDown()

class __Historial(__db.Model):
    id = __db.Column(__db.Integer, primary_key=True)
    tipo = __db.Column(__db.String(50))
    respuesta = __db.Column(__db.Text)

with __app.app_context():
    __db.create_all()

@__app.route('/procesar', methods=['POST'])
def procesar():
    try:
        __tipo = request.form.get('tipo', 'resumen')
        __texto_dictado = request.form.get('texto', '')
        __contenido_extraido = ""

        # Procesamiento de archivos multiformato
        if 'file' in request.files:
            __file = request.files['file']
            __extension = os.path.splitext(__file.filename)[1]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=__extension) as __temp:
                __file.save(__temp.name)
                __conversion = __md.convert(__temp.name)
                __contenido_extraido = __conversion.text_content
                os.remove(__temp.name)

        __prompt_final = f"{__texto_dictado}\n\nContenido extraído:\n{__contenido_extraido}"

        __response = __client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system", 
                    "content": "Eres Tutor AI, un asistente académico de ingeniería. Genera contenido educativo basado en el material proporcionado. Si se solicita un mapa, usa Mermaid.js."
                },
                {"role": "user", "content": __prompt_final}
            ]
        )
        
        __resultado = __response.choices[0].message.content

        # Guardado en base de datos
        __nuevo_registro = __Historial(tipo=__tipo, respuesta=__resultado)
        __db.session.add(__nuevo_registro)
        __db.session.commit()

        return jsonify({"respuesta": __resultado})

    except Exception as __e:
        return jsonify({"error": str(__e)}), 500

if __name__ == "__main__":
    __port = int(os.environ.get("PORT", 5000))
    __app.run(host='0.0.0.0', port=__port)
