import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman 
from openai import OpenAI
from markitdown import MarkItDown

app = Flask(__name__)

# SEGURIDAD: Vital para que el micrófono y archivos funcionen en móviles y Brave
Talisman(app, content_security_policy=None) 
CORS(app)

# Configuración de Base de Datos (Trabajo de Alessia y Stefan)
basedir = os.path.abspath(os.path.dirname(__file__))
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

        # 1. EXTRACCIÓN DE DATOS (Si hay archivo, se lee; si no, se ignora)
        if 'file' in request.files and request.files['file'].filename != '':
            archivo = request.files['file']
            extension = os.path.splitext(archivo.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                archivo.save(tmp.name)
                conversion = md.convert(tmp.name)
                contenido_extraido = conversion.text_content
                os.remove(tmp.name)
        
        # 2. CONFIGURACIÓN DEL CEREBRO (Tutor AI)
        system_msg = (
            "Tu nombre es exclusivamente 'Tutor AI', asistente experto de ingeniería de la USAC. "
            "Eres proactivo y autónomo. Tu misión es ejecutar órdenes con rigor académico. "
            "Si hay un documento adjunto, úsalo como base primaria de información. "
            "Si NO hay documento, realiza una investigación profunda usando tus propios conocimientos. "
            "Usa Mermaid.js para diagramas y responde siempre con autoridad técnica."
        )

        # 3. LÓGICA DE FUSIÓN (Aquí es donde "piensa sola")
        # Construimos un prompt que obliga a la IA a mezclar la orden con el archivo
        if contenido_extraido:
            prompt_final = (
                f"CONTEXTO DEL ARCHIVO ADJUNTO:\n{contenido_extraido}\n\n"
                f"INSTRUCCIÓN DEL USUARIO:\n{texto_usuario}\n\n"
                "EJECUCIÓN: Basándote en el archivo anterior (si es relevante) y en tu inteligencia, "
                "cumple la instrucción del usuario de forma completa y detallada."
            )
        else:
            prompt_final = (
                f"INSTRUCCIÓN DE INVESTIGACIÓN: {texto_usuario}\n\n"
                "EJECUCIÓN: No hay archivos adjuntos. Desarrolla este tema a profundidad, "
                "investiga conceptos relacionados y presenta una solución completa de ingeniería."
            )

        # 4. LLAMADA A LA API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt_final}
            ]
        )
        
        resultado_ai = response.choices[0].message.content
        
        # 5. GUARDADO EN SQL
        nuevo = Historial(tipo=tipo_solicitud, respuesta=resultado_ai)
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({"respuesta": resultado_ai})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
