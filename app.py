# app.py - Archivo de lógica de producción para la plataforma académica Tutor AI
import os  # Importa el módulo nativo del sistema operativo para interactuar con rutas y entornos dinámicos
import tempfile  # Importa la librería para la creación y destrucción de archivos temporales en el disco duro
from flask import Flask, request, jsonify  # Importa las clases base del framework Flask para construir APIs y manejar JSONs
from flask_cors import CORS  # Importa la extensión para mitigar bloqueos de seguridad por intercambio de recursos cruzados
from flask_sqlalchemy import SQLAlchemy  # Importa el ORM relacional para conectar y manipular bases de datos SQL de forma abstracta
from flask_talisman import Talisman  # Importa el paquete de seguridad web para forzar políticas de cabecera y conexiones HTTPS
from openai import OpenAI  # Importa la interfaz cliente oficial para la comunicación e inferencias con inteligencias artificiales

app = Flask(__name__)  # Instancia la aplicación web de Flask tomando como núcleo el nombre de este archivo fuente

# ==========================================================================================
# CONFIGURACIÓN DE CONECTIVIDAD BLINDADA (VERSIÓN PASIVA PARA EXAMEN)
# ==========================================================================================
CORS(app, resources={r"/*": {"origins": "*", "methods": ["POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

Talisman(
    app,
    content_security_policy=None,
    force_https=True,
    strict_transport_security=False,
    session_cookie_secure=False,
    frame_options='ALLOWALL'
)
# ==========================================================================================

basedir = os.path.abspath(os.path.dirname(__file__))  # Determina de manera absoluta la ubicación de la carpeta raíz del proyecto
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')  # Configura la ruta de la base de datos SQLite local
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desactiva las notificaciones del ORM en consola para ahorrar recursos del procesador
db = SQLAlchemy(app)  # Inicializa el entorno de persistencia de datos vinculándolo con la configuración de Flask anterior

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")  # Inicializa el cliente API de DeepSeek

class Historial(db.Model):  # Declara la estructura del modelo relacional para la tabla de historial académico
    id = db.Column(db.Integer, primary_key=True)  # Define una columna numérica entera para la llave primaria autoincremental
    tipo = db.Column(db.String(50))  # Define una columna de texto para guardar el tipo de herramienta analítica utilizada
    respuesta = db.Column(db.Text)  # Define una columna de texto largo para registrar la inferencia exacta devuelta por la IA

with app.app_context():  # Levanta de manera temporal el contexto global del framework para transacciones administrativas
    db.create_all()  # Ordena la creación automática de las tablas físicas y el archivo .db si estos no existen todavía

@app.route('/procesar', methods=['POST'])  # Declara la ruta transaccional central de la aplicación web restringida al método POST
def procesar():  # Define la función controladora de procesos que se ejecutará al recibir datos en el endpoint
    try:  # Abre un bloque de control de excepciones para atrapar fallos físicos o lógicos durante la ejecución
        tipo_solicitud = request.form.get('tipo', 'consulta')  # Extrae de forma segura el parámetro 'tipo' del formulario web recibido
        texto_usuario = request.form.get('texto', '').strip()  # Obtiene la cadena de texto ingresada por el estudiante limpiando espacios
        contenido_extraido = ""  # Inicializa un contenedor de texto vacío para almacenar el resultado de la lectura de archivos

        if 'file' in request.files and request.files['file'].filename != '':  # Sincronización Alessia: Evalúa si viene la clave 'file' con datos
            archivo = request.files['file']  # Aísla el objeto binario del documento adjunto en una variable local de control
            extension = os.path.splitext(archivo.filename)[1]  # Extrae la extensión del archivo para asegurar la consistencia física
            
            try:
                # Se importa localmente para que Render no muera en consultas de voz/texto puro
                from markitdown import MarkItDown
                md = MarkItDown()
                with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:  # Crea un archivo temporal seguro en el almacenamiento
                    archivo.save(tmp.name)  # Guarda físicamente el flujo binario subido por el estudiante dentro del archivo temporal
                    conversion = md.convert(tmp.name)  # Ejecuta el algoritmo de transcripción léxica e interpretación sobre el temporal
                    contenido_extraido = conversion.text_content  # Extrae la cadena de caracteres procesada del documento hacia la memoria
                    os.remove(tmp.name)  # Destruye el archivo temporal del disco duro de inmediato para evitar desbordamientos de cuota
            except Exception as err_file:
                contenido_extraido = f"[Error local al procesar archivo por límites de hardware en Render: {str(err_file)}]"
        
        system_msg = (  # Redacta las directivas del prompt de sistema para controlar el comportamiento del modelo de IA
            "Tu nombre es exclusivamente 'Tutor AI'. Eres un experto de ingeniería de la USAC. "  # Define la marca comercial obligatoria
            "Eres proactivo y autónomo. Si el usuario te realiza una pregunta simple o general, "  # Exige respuestas directas sin rodeos
            "responde con texto Markdown limpio, sin inyectar fórmulas matemáticas previas. "  # Solución Alessia: Aísla contextos lógicos rotos
            "Si la consulta es técnica, proporciona tablas estructuradas en Markdown y ecuaciones "  # Garantiza formato limpio para matemáticas
            "en notación LaTeX estándar. No menciones bajo ninguna circunstancia nombres antiguos de desarrollo."  # Filtra nombres prohibidos
        )  # Cierra la construcción de la tupla de strings del mensaje del sistema

        if contenido_extraido:  # Evalúa de manera condicional si el flujo del sistema logró extraer caracteres de un archivo adjunto
            prompt_final = (  # Estructura el prompt compuesto para inyectar la carga de datos multimedia al modelo cognitivo
                f"CONTEXTO DEL ARCHIVO SOPORTE:\n{contenido_extraido}\n\n"  # Inyecta el contenido legible recuperado del documento
                f"INSTRUCCIÓN DEL ESTUDIANTE: {texto_usuario}\n"  # Añade la orden textual escrita o dictada por voz del
