import os  # Importa el módulo del sistema operativo para leer variables de entorno y rutas de archivos
import tempfile  # Importa la librería para crear archivos temporales en disco que se eliminan automáticamente
from flask import Flask, request, jsonify  # Importa Flask para crear la app web, request para leer datos entrantes y jsonify para responder en JSON
from flask_cors import CORS  # Importa CORS para permitir peticiones desde dominios externos como Netlify
from flask_sqlalchemy import SQLAlchemy  # Importa el ORM para manejar la base de datos sin escribir SQL directo
from flask_talisman import Talisman  # Importa Talisman para aplicar políticas de seguridad HTTP al servidor
from openai import OpenAI  # Importa el cliente de OpenAI compatible con DeepSeek para hacer inferencias de IA

app = Flask(__name__)  # Crea la instancia principal de la aplicación Flask usando el nombre del archivo actual

CORS(  # Activa la política de recursos cruzados para que el frontend en Netlify pueda comunicarse con este backend
    app,  # Le pasa la instancia de Flask a CORS para que la configure
    resources={  # Define las rutas y métodos permitidos para las peticiones externas
        r"/*": {  # Aplica la configuración a todas las rutas del servidor (el asterisco es comodín)
            "origins": "*",  # Acepta peticiones desde cualquier dominio externo sin restricciones
            "methods": ["POST", "OPTIONS"],  # Solo permite los métodos POST (envío de datos) y OPTIONS (verificación previa del navegador)
            "allow_headers": ["Content-Type"]  # Solo permite la cabecera Content-Type en las peticiones entrantes
        }
    }
)

Talisman(  # Inicializa el módulo de seguridad Talisman y lo vincula a la app Flask
    app,  # Le pasa la instancia de Flask para que Talisman aplique sus políticas sobre ella
    content_security_policy=None,  # Desactiva la política de seguridad de contenido para no bloquear scripts externos del frontend
    force_https=True,  # Obliga a que todas las conexiones usen HTTPS en lugar de HTTP inseguro
    strict_transport_security=False,  # Desactiva la cabecera HSTS para evitar conflictos con Render en etapa de desarrollo
    session_cookie_secure=False,  # Permite cookies de sesión sin requerir HTTPS obligatorio en todas las circunstancias
    frame_options='ALLOWALL'  # Permite que la aplicación sea embebida dentro de iframes desde cualquier origen
)

basedir = os.path.abspath(os.path.dirname(__file__))  # Calcula la ruta absoluta de la carpeta donde está guardado este archivo app.py
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')  # Define la ruta completa del archivo de base de datos SQLite que se creará en la misma carpeta
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desactiva el sistema de seguimiento de cambios de SQLAlchemy para ahorrar memoria y recursos

db = SQLAlchemy(app)  # Crea el objeto de base de datos vinculándolo con la configuración de Flask definida arriba

client = OpenAI(  # Crea el cliente que se conectará a la API de DeepSeek para procesar las consultas con IA
    api_key=os.getenv("DEEPSEEK_API_KEY"),  # Lee la clave secreta de la API desde las variables de entorno configuradas en Render
    base_url="https://api.deepseek.com"  # Apunta el cliente hacia el servidor de DeepSeek en lugar del servidor de OpenAI por defecto
)

class Historial(db.Model):  # Declara el modelo de la tabla 'historial' en la base de datos SQLite
    id = db.Column(db.Integer, primary_key=True)  # Columna numérica entera que sirve como identificador único autoincremental de cada registro
    tipo = db.Column(db.String(50))  # Columna de texto corto que guarda el tipo de solicitud: 'consulta', 'mapa', etc.
    respuesta = db.Column(db.Text)  # Columna de texto largo que almacena la respuesta completa generada por la IA

with app.app_context():  # Abre temporalmente el contexto de la aplicación Flask para ejecutar operaciones administrativas
    db.create_all()  # Crea físicamente las tablas en el archivo .db si todavía no existen en el disco

@app.route('/procesar', methods=['POST'])  # Registra la ruta '/procesar' como endpoint que solo acepta peticiones POST desde el frontend
def procesar():  # Define la función principal que se ejecuta cada vez que el frontend envía datos al endpoint

    try:  # Inicia el bloque de control de errores para capturar cualquier fallo durante el procesamiento

        tipo_solicitud = request.form.get('tipo', 'consulta')  # Lee el campo 'tipo' del formulario enviado; si no viene, usa 'consulta' por defecto
        texto_usuario = request.form.get('texto', '').strip()  # Lee el texto escrito o dictado por el usuario y elimina espacios al inicio y al final
        contenido_extraido = ""  # Inicializa una cadena vacía que almacenará el texto extraído del archivo adjunto si viene uno

        if 'file' in request.files and request.files['file'].filename != '':  # Verifica si el usuario adjuntó un archivo y que ese archivo tiene nombre
            archivo = request.files['file']  # Obtiene el objeto del archivo enviado desde el formulario del frontend
            extension = os.path.splitext(archivo.filename)[1].lower()  # Extrae la extensión del archivo (ej: .pdf, .txt) y la convierte a minúsculas

            TIPOS_SEGUROS = ['.txt', '.md', '.csv', '.json', '.html', '.xml']  # Lista de extensiones que se pueden leer directamente sin riesgo de crash por onnxruntime

            if extension in TIPOS_SEGUROS:  # Si la extensión del archivo está en la lista de tipos seguros entra a este bloque
                try:  # Intenta leer el archivo de texto de forma directa y segura
                    contenido_extraido = archivo.read().decode('utf-8', errors='ignore')  # Lee los bytes del archivo y los decodifica como texto UTF-8 ignorando caracteres inválidos
                except Exception as err_txt:  # Si la lectura directa falla captura el error sin detener el servidor
                    contenido_extraido = f"[Error leyendo archivo de texto: {str(err_txt)}]"  # Guarda el mensaje de error como texto para informar al usuario

            else:  # Si la extensión NO está en la lista segura (PDF, DOCX, etc.) entra a este bloque alternativo
                try:  # Intenta procesar el archivo con la librería MarkItDown que puede convertir documentos complejos
                    os.environ["ORT_LOGGING_LEVEL"] = "3"  # Silencia los mensajes de onnxruntime en los logs para evitar que intente acceder a la GPU inexistente en Render
                    from markitdown import MarkItDown  # Importa MarkItDown dentro del bloque para que solo cargue cuando realmente se necesita
                    md = MarkItDown()  # Crea una instancia del conversor de documentos MarkItDown
                    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:  # Crea un archivo temporal en disco con la misma extensión del archivo original
                        archivo.save(tmp.name)  # Guarda el archivo subido por el usuario dentro del archivo temporal en disco
                        conversion = md.convert(tmp.name)  # Ejecuta la conversión del archivo temporal a texto plano mediante MarkItDown
                        contenido_extraido = conversion.text_content  # Extrae el texto convertido del resultado y lo guarda en la variable principal
                        os.remove(tmp.name)  # Elimina inmediatamente el archivo temporal del disco para no acumular archivos basura en Render
                except Exception as err_file:  # Si MarkItDown falla por cualquier razón captura el error sin detener el servidor
                    contenido_extraido = (  # Construye un mensaje de error informativo para el usuario
                        f"[No se pudo procesar el archivo {extension}. "  # Informa qué extensión causó el problema
                        f"Tipos recomendados: PDF, DOCX, TXT. Error: {str(err_file)}]"  # Sugiere los tipos de archivo recomendados e incluye el detalle del error
                    )

        system_msg = (  # Construye el mensaje de sistema que define el comportamiento y personalidad de la IA
            "Tu nombre es exclusivamente 'Tutor AI'. Eres un experto de ingeniería de la USAC. "  # Define el nombre comercial y el rol académico del asistente
            "Eres proactivo y autónomo. Si el usuario te realiza una pregunta simple o general, "  # Indica que debe responder directamente sin rodeos innecesarios
            "responde con texto Markdown limpio, sin inyectar fórmulas matemáticas previas. "  # Instruye que para preguntas simples no use fórmulas matemáticas sin contexto
            "Si la consulta es técnica, proporciona tablas estructuradas en Markdown y ecuaciones "  # Para consultas técnicas exige tablas y ecuaciones bien formateadas
            "en notación LaTeX estándar. No menciones bajo ninguna circunstancia nombres antiguos de desarrollo."  # Prohíbe mencionar nombres de versiones anteriores del proyecto
        )

        if contenido_extraido:  # Si se extrajo texto de un archivo adjunto entra a este bloque para construir el prompt combinado
            prompt_final = (  # Construye el prompt uniendo el contenido del archivo con la instrucción del usuario
                f"CONTEXTO DEL ARCHIVO SOPORTE:\n{contenido_extraido}\n\n"  # Inyecta el texto extraído del documento como contexto para la IA
                f"INSTRUCCIÓN DEL ESTUDIANTE: {texto_usuario}"  # Agrega la pregunta o instrucción escrita o dictada por el usuario
            )
        else:  # Si no hay archivo adjunto el prompt es solo el texto del usuario
            prompt_final = texto_usuario if texto_usuario else "Preséntate brevemente."  # Usa el texto del usuario o pide una presentación si no escribió nada

        completion = client.chat.completions.create(  # Envía la solicitud a la API de DeepSeek para obtener la respuesta de la IA
            model="deepseek-chat",  # Especifica el modelo de DeepSeek que procesará la consulta
            messages=[  # Lista de mensajes que forman la conversación enviada al modelo
                {"role": "system", "content": system_msg},  # Mensaje de sistema que define el comportamiento y personalidad de Tutor AI
                {"role": "user", "content": prompt_final}  # Mensaje del usuario con su pregunta o instrucción y el contexto del archivo si aplica
            ],
            max_tokens=2048  # Limita la respuesta a máximo 2048 tokens para controlar el uso de la API y el tiempo de respuesta
        )

        respuesta = completion.choices[0].message.content  # Extrae el texto de la respuesta generada por la IA del primer resultado devuelto

        nuevo = Historial(tipo=tipo_solicitud, respuesta=respuesta)  # Crea un nuevo objeto de registro con el tipo de consulta y la respuesta obtenida
        db.session.add(nuevo)  # Agrega el nuevo registro a la sesión activa de la base de datos pendiente de confirmación
        db.session.commit()  # Confirma y guarda definitivamente el registro en el archivo de base de datos SQLite

        return jsonify({"respuesta": respuesta})  # Devuelve la respuesta de la IA al frontend en formato JSON con la clave 'respuesta'

    except Exception as e:  # Captura cualquier error inesperado que ocurra durante todo el proceso anterior
        return jsonify({"error": str(e), "respuesta": f"Error interno: {str(e)}"}), 500  # Devuelve el detalle del error en JSON con código HTTP 500 para que el frontend lo pueda mostrar

if __name__ == '__main__':  # Verifica si este archivo se está ejecutando directamente y no siendo importado por otro módulo
    port = int(os.environ.get("PORT", 10000))  # Lee el puerto asignado por Render desde las variables de entorno o usa 10000 como valor por defecto
    app.run(host='0.0.0.0', port=port)  # Inicia el servidor Flask escuchando en todas las interfaces de red en el puerto definido
