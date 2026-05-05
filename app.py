import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman 
from openai import OpenAI
from markitdown import MarkItDown

app = Flask(__name__)

# SEGURIDAD: Permite que el micrófono y archivos funcionen en Brave y móviles
Talisman(app, content_security_policy=None) 
CORS(app)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

        # 1. EXTRACCIÓN DE DATOS CON MANEJO DE ERRORES (Evita el fallo de conexión)
        if 'file' in request.files and request.files['file'].filename != '':
            archivo = request.files['file']
            extension = os.path.splitext(archivo.filename)[1].lower()
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                    archivo.save(tmp.name)
                    # Forzamos la conversión a texto
                    conversion = md.convert(tmp.name)
                    contenido_extraido = conversion.text_content
                    os.remove(tmp.name)
            except Exception as e_file:
                # Si falla la extracción de texto, enviamos una nota a la IA
                contenido_extraido = f"[Error al leer el archivo directamente: {str(e_file)}]"

        # 2. CONFIGURACIÓN DE IDENTIDAD (Tutor AI)
        system_msg = (
            "Tu nombre es exclusivamente 'Tutor AI'. Eres un asistente experto de ingeniería de la USAC. "
            "Eres autónomo: si hay un archivo, úsalo de base; si no, investiga por tu cuenta. "
            "Si recibes un error de lectura de archivo, intenta deducir el problema o pide al usuario que describa la imagen."
        )

        # 3. LÓGICA DE FUSIÓN DE CONTEXTO
        if contenido_extraido:
            prompt_final = (
                f"CONTEXTO DEL ARCHIVO:\n{contenido_extraido}\n\n"
                f"ORDEN DEL ESTUDIANTE: {texto_usuario}\n\n"
                "EJECUCIÓN: Analiza el contexto y cumple la orden proactivamente."
            )
        else:
            prompt_final = f"INVESTIGACIÓN PROACTIVA: {texto_usuario}"

        # 4. LLAMADA A LA NUBE (DeepSeek)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt_final}
            ]
        )
        
        resultado_ai = response.choices[0].message.content
        
        # 5. PERSISTENCIA
        nuevo = Historial(tipo=tipo_solicitud, respuesta=resultado_ai)
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({"respuesta": resultado_ai})

    except Exception as e:
        # LOG PARA DEPURACIÓN: Esto ayuda a ver qué falló en Render
        print(f"ERROR CRÍTICO: {str(e)}")
        return jsonify({"error": "Fallo en la conexión con la nube. Reintenta en un momento."}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
