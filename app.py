# app.py - Archivo de lógica de producción para la plataforma académica Tutor AI
import os  # Importa el módulo nativo del sistema operativo para interactuar con rutas y entornos dinámicos
import tempfile  # Importa la librería para la creación y destrucción de archivos temporales en el disco duro
from flask import Flask, request, jsonify  # Importa las clases base del framework Flask para construir APIs y manejar JSONs
from flask_cors import CORS  # Importa la extensión para mitigar bloqueos de seguridad por intercambio de recursos cruzados
from flask_sqlalchemy import SQLAlchemy  # Importa el ORM relacional para conectar y manipular bases de datos SQL de forma abstracta
from flask_talisman import Talisman  # Importa el paquete de seguridad web para forzar políticas de cabecera y conexiones HTTPS
from openai import OpenAI  # Importa la interfaz cliente oficial para la comunicación e inferencias con inteligencias artificiales
from markitdown import MarkItDown  # Importa el procesador multimedia especializado en transformar archivos PDF e imágenes en texto plano

app = Flask(__name__)  # Instancia la aplicación web de Flask tomando como núcleo el nombre de este archivo fuente

# ==========================================================================================
# SOLUCIÓN CRÍTICA DE CONECTIVIDAD: Configuración explícita de CORS y Talisman sin conflicto
# ==========================================================================================
# 1. Configuramos CORS detallado antes que Talisman para que registre los métodos de control previos (OPTIONS)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

# 2. Forzamos HTTPS mediante Talisman pero desactivamos la inyección rígida de políticas que borran las cabeceras de CORS externo
Talisman(
    app,
    content_security_policy=None,
    force_https=True,
    strict_transport_security=True,
    session_cookie_secure=True
)
# ==========================================================================================

basedir = os.path.abspath(os.path.dirname(__file__))  # Determina de manera absoluta la ubicación de la carpeta raíz del proyecto
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')  # Configura la ruta de la base de datos SQLite local
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desactiva las notificaciones del ORM en consola para ahorrar recursos del procesador
db = SQLAlchemy(app)  # Inicializa el entorno de persistencia de datos vinculándolo con la configuración de Flask anterior

client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")  # Inicializa el cliente API de DeepSeek
md = MarkItDown()  # Instancia el motor MarkItDown para habilitar el despiece de archivos e imágenes dentro de la aplicación

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
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:  # Crea un archivo temporal seguro en el almacenamiento
                archivo.save(tmp.name)  # Guarda físicamente el flujo binario subido por el estudiante dentro del archivo temporal
                conversion = md.convert(tmp.name)  # Ejecuta el algoritmo de transcripción léxica e interpretación sobre el temporal
                contenido_extraido = conversion.text_content  # Extrae la cadena de caracteres procesada del documento hacia la memoria
                os.remove(tmp.name)  # Destruye el archivo temporal del disco duro de inmediato para evitar desbordamientos de cuota
        
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
                f"INSTRUCCIÓN DEL ESTUDIANTE: {texto_usuario}\n"  # Añade la orden textual escrita o dictada por voz del usuario
                "EJECUCIÓN: Analiza el contexto y resuelve de forma proactiva la instrucción."  # Define la directiva final de procesamiento
            )  # Cierra el bloque de asignación de la variable para adjuntos
        else:  # Define el flujo operativo alterno en caso de que la consulta sea estrictamente textual, sin archivos
            prompt_final = (  # Construye el prompt limpio aislado de manera que no herede basura analítica del historial anterior
                f"ORDEN DIRECTA ACTUAL: {texto_usuario}\n"  # Asigna directamente el comando puro ingresado por el estudiante
                "EJECUCIÓN: Resuelve esta consulta de forma aislada y limpia. Olvida contextos matemáticos anteriores."  # Fuerza aislamiento lógico
            )  # Cierra la construcción del prompt simple de texto

        response = client.chat.completions.create(  # Despierta el canal asíncrono para enviar los datos de ingeniería al servidor DeepSeek
            model="deepseek-chat",  # Especifica el modelo optimizado de procesamiento de texto a invocar en los servidores de la IA
            messages=[  # Abre el arreglo de roles exigido por la arquitectura para la construcción secuencial del diálogo
                {"role": "system", "content": system_msg},  # Carga el mensaje estructural de sistema con las directivas de Tutor AI
                {"role": "user", "content": prompt_final}  # Adjunta la instrucción académica final formateada con o sin PDF
            ],  # Cierra el arreglo de control de roles lingüísticos de la inferencia
            temperature=0.3  # Setea una temperatura baja para garantizar el rigor matemático y erradicar alucinaciones analíticas
        )  # Cierra el objeto constructor de la petición de red asíncrona
        
        resultado_ai = response.choices[0].message.content  # Extrae el texto plano de respuesta generado del objeto respuesta de DeepSeek
        
        nuevo = Historial(tipo=tipo_solicitud, respuesta=resultado_ai)  # Instancia una nueva fila de la entidad Historial para la base de datos
        db.session.add(nuevo)  # Encola la fila recién estructurada en la cola de transacciones pendientes del motor ORM
        db.session.commit()  # Consolida los cambios impactando físicamente el archivo relacional de la base de datos de auditoría

        return jsonify({"respuesta": resultado_ai})  # Retorna hacia el cliente HTML un objeto JSON codificado con la respuesta limpia

    except Exception as e:  # Captura de forma segura cualquier fallo físico de red, API o base de datos que ocurra en el trayecto
        return jsonify({"error": str(e)}), 500  # Envía una respuesta JSON con código de estado HTTP 500 para notificar fallos en el Frontend

if __name__ == "__main__":  # Evalúa si el script está siendo ejecutado directamente por la consola y no invocado por otra rutina externos
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))  # Arranca el servidor de Flask en el puerto físico de producción asignado
