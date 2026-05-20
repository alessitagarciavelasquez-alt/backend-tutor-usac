# app.py - Archivo de lógica de producción para la plataforma académica Tutor AI
import os  # Permite leer variables de entorno y manejar rutas del sistema de archivos
import io  # Permite trabajar con archivos en memoria sin necesidad de guardarlos en disco
import base64  # Convierte imágenes binarias a texto Base64 para enviarlas a la API de visión de IA
from flask import Flask, request, jsonify  # Flask crea el servidor web; request lee datos entrantes; jsonify convierte respuestas a JSON
from flask_cors import CORS  # Permite que el frontend en Netlify se comunique con este backend sin bloqueos de seguridad
from flask_sqlalchemy import SQLAlchemy  # ORM para manejar la base de datos SQLite sin escribir SQL directo
from flask_talisman import Talisman  # Aplica cabeceras de seguridad HTTP y fuerza el uso de HTTPS
from openai import OpenAI  # Cliente compatible con DeepSeek para enviar consultas a la inteligencia artificial

app = Flask(__name__)  # Crea la instancia principal del servidor Flask usando el nombre de este archivo

CORS(  # Configura los permisos de acceso cruzado para que Netlify pueda llamar a este backend
    app,  # Vincula la configuración CORS a la instancia de Flask
    resources={  # Define las rutas y permisos específicos que se aplicarán
        r"/*": {  # Aplica la configuración a absolutamente todas las rutas del servidor
            "origins": "*",  # Acepta peticiones desde cualquier dominio externo sin restricciones
            "methods": ["POST", "OPTIONS"],  # Solo permite los métodos POST y OPTIONS
            "allow_headers": ["Content-Type"]  # Solo acepta la cabecera Content-Type en las peticiones
        }
    }
)

Talisman(  # Inicializa el módulo de seguridad y lo vincula al servidor Flask
    app,  # Le pasa la instancia de Flask para aplicar las políticas de seguridad
    content_security_policy=None,  # Desactiva CSP para no bloquear scripts externos usados en el frontend
    force_https=True,  # Obliga a que todas las conexiones sean por HTTPS seguro
    strict_transport_security=False,  # Desactiva HSTS para evitar conflictos durante el despliegue en Render
    session_cookie_secure=False,  # Permite cookies sin requerir HTTPS en todas las circunstancias
    frame_options='ALLOWALL'  # Permite que la app pueda mostrarse dentro de iframes desde cualquier origen
)

basedir = os.path.abspath(os.path.dirname(__file__))  # Obtiene la ruta absoluta de la carpeta donde vive este archivo app.py
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tutor_ai.db')  # Define la ubicación del archivo de base de datos SQLite en la misma carpeta del proyecto
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desactiva las notificaciones de cambios de SQLAlchemy para ahorrar memoria y recursos

db = SQLAlchemy(app)  # Crea el objeto de base de datos vinculado a la configuración de Flask

client = OpenAI(  # Crea el cliente que se conectará a la API de DeepSeek para procesar las consultas
    api_key=os.getenv("DEEPSEEK_API_KEY"),  # Lee la clave secreta de la API desde las variables de entorno de Render
    base_url="https://api.deepseek.com"  # Apunta el cliente al servidor de DeepSeek en lugar del de OpenAI por defecto
)

class Historial(db.Model):  # Define la estructura de la tabla historial en la base de datos
    id = db.Column(db.Integer, primary_key=True)  # Identificador único autoincremental para cada registro
    tipo = db.Column(db.String(50))  # Guarda el tipo de solicitud: consulta, mapa, resumen, etc.
    respuesta = db.Column(db.Text)  # Guarda la respuesta completa que generó la IA

with app.app_context():  # Abre el contexto de Flask para ejecutar operaciones de base de datos al iniciar
    db.create_all()  # Crea las tablas en el archivo .db si todavía no existen en el disco


# ==============================================================
# FUNCIÓN CENTRAL: Extrae contenido de CUALQUIER tipo de archivo
# ==============================================================
def extraer_contenido(archivo, extension):  # Recibe el objeto del archivo y su extensión para decidir cómo procesarlo
    """Extrae texto, imagen Base64 única, o lista de imágenes Base64 (PDF escaneado)."""

    # ── TEXTO PLANO: TXT, MD, CSV, JSON, HTML, XML ─────────────
    if extension in ['.txt', '.md', '.csv', '.json', '.html', '.xml']:  # Verifica si es un archivo de texto simple sin librería externa
        try:  # Intenta leer el archivo directamente como texto plano
            return archivo.read().decode('utf-8', errors='ignore'), None  # Decodifica bytes a UTF-8 ignorando caracteres inválidos
        except Exception as e:  # Captura cualquier error de lectura
            return None, f"[Error leyendo archivo de texto: {str(e)}]"  # Retorna None y el mensaje de error

    # ── PDF (texto normal Y escaneado) [PASO 2 INTEGRADO] ───────
    elif extension == '.pdf':  # Verifica si el archivo es un PDF
        try:
            from pypdf import PdfReader  # Intenta primero extraer texto seleccionable
            pdf_bytes = archivo.read()  # Lee los bytes del PDF una sola vez en memoria
            reader = PdfReader(io.BytesIO(pdf_bytes))  # Carga el PDF desde memoria
            paginas = []  # Lista para acumular texto de cada página
            for pagina in reader.pages:  # Itera sobre cada página
                texto = pagina.extract_text()  # Intenta extraer texto seleccionable
                if texto and texto.strip():  # Si la página tiene texto real
                    paginas.append(texto)  # Lo acumula
            if paginas:  # Si encontró texto en al menos una página
                return "\n".join(paginas), None  # Retorna el texto extraído normalmente

            # Si no hay texto, es un PDF escaneado — lo convierte a imágenes
            import fitz  # PyMuPDF para renderizar páginas como imágenes
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # Abre el PDF desde memoria
            imagenes_b64 = []  # Lista para acumular imágenes Base64 de cada página
            max_paginas = min(len(doc), 10)  # Limita a 10 páginas para no exceder la API
            for num_pag in range(max_paginas):  # Itera sobre las páginas limitadas
                pagina = doc[num_pag]  # Obtiene la página actual
                mat = fitz.Matrix(1.5, 1.5)  # Escala de 1.5x para buena resolución sin exceder tamaño
                pix = pagina.get_pixmap(matrix=mat)  # Renderiza la página como imagen en memoria
                img_bytes = pix.tobytes("jpeg")  # Convierte el pixmap a bytes JPEG
                b64 = base64.b64encode(img_bytes).decode('utf-8')  # Codifica en Base64
                imagenes_b64.append(b64)  # Agrega la imagen de la página a la lista
            doc.close()  # Cierra el documento para liberar memoria
            return None, None, imagenes_b64  # Retorna lista de imágenes Base64 (una por página)
        except Exception as e:
            return None, f"[Error al leer PDF: {str(e)}]"

    # ── WORD (.docx) ────────────────────────────────────────────
    elif extension == '.docx':  # Verifica si es un documento de Microsoft Word
        try:  # Intenta extraer el texto de todos los párrafos del documento
            from docx import Document  # Importa python-docx solo cuando se necesita
            doc = Document(io.BytesIO(archivo.read()))  # Lee el documento Word desde memoria sin guardarlo en disco
            parrafos = [p.text for p in doc.paragraphs if p.text.strip()]  # Extrae párrafos con contenido ignorando los vacíos
            return "\n".join(parrafos), None  # Une todos los párrafos con saltos de línea y los retorna
        except Exception as e:  # Captura cualquier fallo al leer el documento Word
            return None, f"[Error al leer DOCX: {str(e)}]"  # Retorna el mensaje de error detallado

    # ── EXCEL (.xlsx / .xls) ────────────────────────────────────
    elif extension in ['.xlsx', '.xls']:  # Verifica si es una hoja de cálculo de Microsoft Excel
        try:  # Intenta leer todas las hojas y celdas del libro Excel
            import openpyxl  # Importa openpyxl solo cuando se necesita para leer Excel
            wb = openpyxl.load_workbook(io.BytesIO(archivo.read()), data_only=True)  # Carga el libro Excel mostrando valores calculados en lugar de fórmulas
            todas_hojas = []  # Lista para acumular el contenido de todas las hojas del libro
            for nombre_hoja in wb.sheetnames:  # Itera sobre el nombre de cada hoja del libro Excel
                hoja = wb[nombre_hoja]  # Obtiene el objeto completo de la hoja actual
                filas = []  # Lista para acumular las filas de texto de esta hoja
                for fila in hoja.iter_rows(values_only=True):  # Itera sobre cada fila extrayendo solo los valores
                    fila_texto = [str(c) for c in fila if c is not None]  # Convierte celdas a texto ignorando las vacías
                    if fila_texto:  # Solo agrega la fila si tiene al menos una celda con contenido
                        filas.append(" | ".join(fila_texto))  # Une las celdas con separador para simular una tabla de texto
                todas_hojas.append(f"[Hoja: {nombre_hoja}]\n" + "\n".join(filas))  # Agrega nombre de hoja y sus filas al acumulador
            return "\n\n".join(todas_hojas), None  # Une todas las hojas con doble salto de línea y las retorna
        except Exception as e:  # Captura cualquier fallo al leer el archivo Excel
            return None, f"[Error al leer Excel: {str(e)}]"  # Retorna el mensaje de error detallado

    # ── POWERPOINT (.pptx) ──────────────────────────────────────
    elif extension == '.pptx':  # Verifica si es una presentación de Microsoft PowerPoint
        try:  # Intenta extraer el texto de todas las diapositivas y sus elementos
            from pptx import Presentation  # Importa python-pptx solo cuando se necesita
            prs = Presentation(io.BytesIO(archivo.read()))  # Carga la presentación desde memoria sin guardarlo en disco
            diapositivas = []  # Lista para acumular el texto de cada diapositiva
            for i, slide in enumerate(prs.slides, 1):  # Itera sobre cada diapositiva con su número de orden
                textos = []  # Lista para el texto de los elementos de esta diapositiva
                for shape in slide.shapes:  # Itera sobre cada elemento como títulos, cuadros de texto, etc.
                    if hasattr(shape, "text") and shape.text.strip():  # Verifica si el elemento tiene texto no vacío
                        textos.append(shape.text.strip())  # Agrega el texto del elemento a la lista
                if textos:  # Solo agrega la diapositiva si tiene al menos un elemento con texto
                    diapositivas.append(f"[Diapositiva {i}]\n" + "\n".join(textos))  # Agrega número y contenido de la diapositiva
            return "\n\n".join(diapositivas), None  # Une todas las diapositivas con doble salto de línea
        except Exception as e:  # Captura cualquier fallo al leer la presentación PowerPoint
            return None, f"[Error al leer PPTX: {str(e)}]"  # Retorna el mensaje de error detallado

    # ── IMÁGENES: JPG, PNG, WEBP, GIF ──────────────────────────
    elif extension in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:  # Verifica si el archivo es una imagen
        try:  # Intenta convertir la imagen a Base64 para enviarla al modelo de visión
            from PIL import Image  # Importa Pillow solo cuando se necesita para procesar la imagen
            img_bytes = archivo.read()  # Lee los bytes completos de la imagen desde el formulario
            img = Image.open(io.BytesIO(img_bytes))  # Abre la imagen en memoria para verificar que es válida
            if img.mode != 'RGB':  # Si la imagen no está en modo RGB (RGBA, paleta, etc.)
                img = img.convert('RGB')  # Convierte a RGB para compatibilidad universal con la API
            buffer = io.BytesIO()  # Crea un buffer en memoria para guardar la imagen procesada
            img.save(buffer, format='JPEG', quality=85)  # Guarda la imagen en JPEG con 85% de calidad
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')  # Convierte los bytes a texto Base64
            return None, None, img_base64  # Retorna: texto(None), error(None), Base64 de la imagen (string)
        except Exception as e:  # Captura cualquier fallo al procesar la imagen
            return None, f"[Error al procesar imagen: {str(e)}]", None  # Retorna el mensaje de error

    # ── FORMATO NO SOPORTADO ────────────────────────────────────
    else:  # Si la extensión no coincide con ningún formato conocido
        return None, f"[Formato '{extension}' no soportado. Use: PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON, MD, JPG, PNG, WEBP.]"  # Informa los formatos aceptados


# ==============================================================
# ENDPOINT PRINCIPAL: Recibe datos del frontend y responde con IA
# ==============================================================
@app.route('/procesar', methods=['POST'])  # Registra la ruta /procesar que solo acepta peticiones POST desde el frontend
def procesar():  # Función que se ejecuta cada vez que el frontend envía un formulario con datos

    try:  # Inicia el bloque de control de errores para capturar cualquier fallo durante el procesamiento

        tipo_solicitud = request.form.get('tipo', 'consulta')  # Lee el tipo de solicitud del formulario; usa 'consulta' si no viene ninguno
        texto_usuario = request.form.get('texto', '').strip()  # Lee el texto del usuario eliminando espacios innecesarios
        contenido_extraido = ""  # Variable que almacenará el texto extraído del archivo adjunto
        imagen_base64 = None  # Variable que almacenará string Base64 (imagen) o lista de strings (PDF escaneado)

        if 'file' in request.files and request.files['file'].filename != '':  # Verifica si hay un archivo adjunto con nombre válido
            archivo = request.files['file']  # Obtiene el objeto completo del archivo enviado desde el frontend
            extension = os.path.splitext(archivo.filename)[1].lower()  # Extrae la extensión en minúsculas para comparación segura

            # [PASO 3 INTEGRADO: MANEJO DE IMÁGENES Y MÚLTIPLES PÁGINAS]
            resultado = extraer_contenido(archivo, extension)
            if len(resultado) == 3:  # Imagen o PDF escaneado
                _, error, datos_visuales = resultado
                if error:
                    contenido_extraido = error
                elif isinstance(datos_visuales, list):
                    # PDF escaneado: múltiples páginas como imágenes
                    imagen_base64 = datos_visuales  # Es una lista de Base64
                else:
                    # Imagen suelta (JPG, PNG, etc.)
                    imagen_base64 = datos_visuales  # Es un string Base64
            else:
                texto, error = resultado
                contenido_extraido = texto if texto else (error or "")

        system_msg = (  # Construye el mensaje de sistema que define el comportamiento y personalidad de Tutor AI
            "Tu nombre es exclusivamente 'Tutor AI'. Eres un experto de ingeniería de la USAC. "  # Define el nombre y rol académico del asistente
            "Eres proactivo y autónomo. Si el usuario te realiza una pregunta simple o general, "  # Debe responder directamente sin rodeos
            "responde con texto Markdown limpio, sin inyectar fórmulas matemáticas previas. "  # Para preguntas simples no usa fórmulas sin contexto
            "Si la consulta es técnica, proporciona tablas estructuradas en Markdown y ecuaciones "  # Para consultas técnicas exige tablas y ecuaciones
            "en notación LaTeX estándar. No menciones bajo ninguna circunstancia nombres antiguos de desarrollo."  # Prohíbe mencionar nombres de versiones anteriores
        )

        # ── Construcción del prompt según el tipo de entrada recibida [PASO 3 PROMPT VISUAL] ────
        if imagen_base64:
            # Construye el contenido visual (una imagen o varias páginas de PDF)
            imagenes_lista = imagen_base64 if isinstance(imagen_base64, list) else [imagen_base64]
            contenido_vision = []  # Lista de bloques para el mensaje de visión
            for b64 in imagenes_lista:  # Agrega cada imagen como bloque separado
                contenido_vision.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
            contenido_vision.append({  # Agrega la instrucción de texto al final
                "type": "text",
                "text": texto_usuario if texto_usuario else "Analiza y explica detalladamente el contenido de estas páginas."
            })
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": contenido_vision}
            ]

        elif contenido_extraido:  # Si se extrajo texto de un documento construye el prompt combinado con contexto
            prompt_final = (  # Une el contenido del archivo con la instrucción del usuario
                f"CONTEXTO DEL ARCHIVO SOPORTE:\n{contenido_extraido}\n\n"  # Inyecta el texto del documento como contexto para la IA
                f"INSTRUCCIÓN DEL ESTUDIANTE: {texto_usuario}"  # Agrega la pregunta o instrucción del usuario
            )
            messages = [  # Lista de mensajes estándar sin imagen para documentos de texto
                {"role": "system", "content": system_msg},  # Mensaje de sistema con las instrucciones de Tutor AI
                {"role": "user", "content": prompt_final}  # Mensaje del usuario con contexto del archivo y su pregunta
            ]

        else:  # Si no hay archivo adjunto el prompt es únicamente el texto del usuario
            prompt_final = texto_usuario if texto_usuario else "Preséntate brevemente."  # Usa el texto del usuario o solicita presentación breve
            messages = [  # Lista de mensajes simple solo con texto
                {"role": "system", "content": system_msg},  # Mensaje de sistema con las instrucciones de comportamiento
                {"role": "user", "content": prompt_final}  # Mensaje del usuario con su consulta de texto puro
            ]

        completion = client.chat.completions.create(  # Envía la solicitud completa a la API de DeepSeek para obtener la respuesta
            model="deepseek-chat",  # Modelo de DeepSeek con soporte de texto y visión que procesará la consulta
            messages=messages,  # Lista de mensajes construida dinámicamente según el tipo de archivo recibido
            max_tokens=2048  # Limita la respuesta a 2048 tokens para controlar tiempos y costos de API
        )

        respuesta = completion.choices[0].message.content  # Extrae el texto de la primera respuesta generada por la IA

        nuevo = Historial(tipo=tipo_solicitud, respuesta=respuesta)  # Crea el objeto de registro con el tipo de solicitud y la respuesta
        db.session.add(nuevo)  # Agrega el nuevo registro a la sesión activa de la base de datos
        db.session.commit()  # Confirma y guarda definitivamente el registro en el archivo SQLite en disco

        return jsonify({"respuesta": respuesta})  # Devuelve la respuesta de la IA al frontend en formato JSON

    except Exception as e:  # Captura cualquier error inesperado durante todo el procesamiento
        return jsonify({"error": str(e), "respuesta": f"Error interno: {str(e)}"}), 500  # Devuelve el error en JSON con código HTTP 500

if __name__ == '__main__':  # Solo se ejecuta si este archivo se corre directamente
    port = int(os.environ.get("PORT", 10000))  # Lee el puerto de las variables de entorno de Render o usa 10000 por defecto
    app.run(host='0.0.0.0', port=port)  # Inicia el servidor Flask escuchando en todas las interfaces de red
