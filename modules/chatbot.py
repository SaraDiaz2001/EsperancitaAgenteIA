from langchain.schema import HumanMessage, AIMessage  
from modules.google_calendar import GoogleCalendarManager
from modules.gmail import GmailManager
from modules.database import get_vectorstore
from datetime import datetime
from modules.audio import transcribe_audio_google_simple
from gtts import gTTS
import speech_recognition as sr
import tempfile
import re
import openai
import json
import os
import requests
import logging
import random

# Lista de analistas disponibles
ANALISTAS = [
    {"nombre": "Sara Milena Díaz Pérez", "correo": "sara.diaz1@udea.edu.co"},
    {"nombre": "Karol Escudero Gutierrez", "correo": "karol.escudero@udea.edu.co"},
    {"nombre": "Cristian Mora", "correo": "cristian.morag@udea.edu.co"},
    {"nombre": "Maria Camila Perez Hincapie", "correo": "maria.perez29@udea.edu.co"}
]

analistas = {
                "Sara Milena Díaz Pérez": "sara.diaz1@udea.edu.co",
                "Karol Escudero Gutierrez": "karol.escudero@udea.edu.co",
                "Cristian Mora": "cristian.morag@udea.edu.co",
                "Maria Camila Perez Hincapie": "maria.perez29@udea.edu.co"
            }

# Diccionario global para almacenar contexto de archivos adjuntos
event_context = {}  

# Definir un estado inicial que controle el flujo
estado = "esperando_intencion"

# Instancias de los manejadores
calendar = GoogleCalendarManager()
gmail = GmailManager()

# Configurar el cliente de Together AI
client = openai.OpenAI(api_key="TOGETHER_API_KEY", base_url="https://api.together.xyz/v1")

# Configurar logging para errores
logger = logging.getLogger(__name__)

# Definir la ruta de la carpeta de archivos
CARPETA_ARCHIVOS = r"C:\Users\Usuario\Documents\ChatBot\Chat\data\archivos"

# Archivo de historial
HISTORY_FILE = "data/historial/search_history.json"

def ensure_history_file():
    """
    Verifica la existencia del archivo de historial y lo inicializa si está vacío.
    """
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    
    if not os.path.exists(HISTORY_FILE) or os.stat(HISTORY_FILE).st_size == 0:
        with open(HISTORY_FILE, "w") as f:
            json.dump([], f)

def save_search(user_input, response):
    """
    Guarda una consulta y su respuesta en el historial de búsquedas.
    """
    try:
        ensure_history_file()
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        history.append({"user": user_input, "bot": response})

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

        logger.info("Historial guardado correctamente.")
    except Exception as e:
        logger.error(f"Error al guardar el historial de chat: {e}")

def get_chat_history():
    """
    Recupera el historial de conversación desde el archivo JSON.
    """
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            return [{"role": "user", "content": h["user"]} if i % 2 == 0 else {"role": "assistant", "content": h["bot"]}
                    for i, h in enumerate(history)]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def generate_image(prompt):
    """Genera una imagen basada en un texto con Stable Diffusion XL 1.0 en Together AI."""
    try:
        response = client.images.generate(
            model="stabilityai/stable-diffusion-xl-base-1.0",
            prompt=prompt,
            size="1024x1024",
            n=1
        )
        
        image_url = response.data[0].url  # URL de la imagen generada
        logger.info(f"✅ Imagen generada con éxito: {image_url}")
        return image_url  # ⬅️ Devolvemos solo la URL

    except Exception as e:
        logger.error(f"❌ Error al generar la imagen: {str(e)}")
        return None  # ⬅️ Retornamos `None` si hay error


def detectar_intencion(user_input):
    """
    Usa un LLM para detectar la intención del usuario: crear evento, consultar eventos, enviar correo o simplemente charlar.
    """
    messages = [
        {"role": "system", "content": (
            "Eres Esperancita, una secretaria virtual amigable y eficiente. "
            "Analiza el mensaje del usuario y determina su intención. Las opciones son:\n"
            "- 'crear_cita' si quiere agendar una cita en Google Calendar.\n"
            "- 'consultar_eventos' si quiere ver eventos próximos.\n"
            "- 'enviar_correo' si quiere mandar un email.\n"
            "- 'charlar' si solo está conversando o preguntando algo distinto.\n\n"
            "Devuelve solo una de estas etiquetas: crear_cita, consultar_eventos, enviar_correo, charlar."
        )},
        {"role": "user", "content": user_input}
    ]

    response = client.chat.completions.create(model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free", messages=messages)
    return response.choices[0].message.content.strip()

def procesar_evento(user_input):
    """
    Usa un LLM para procesar la información del evento que el usuario desea agendar.
    Analiza el mensaje del usuario y extrae los detalles necesarios para crear el evento.
    """
    # Mensajes para enviar al modelo
    messages = [
        {"role": "system", "content": (
            "Eres Esperancita, una secretaria virtual de Dataconsult. "
            "Tu tarea es ayudar a los usuarios a agendar eventos en el calendario de Google. "
            "Por favor, analiza el mensaje del usuario y extrae la siguiente información:\n"
            "- Tipo de servicio (Ej: Consulta estadística, Capacitación, Reunión de seguimiento).\n"
            "- Nombre del cliente o empresa.\n"
            "- Correo del cliente (Ej: cliente@empresa.com).\n"
            "- Fecha y hora de inicio (Formato: '2025-03-25T14:00:00').\n"
            "- Fecha y hora de finalización (Formato: '2025-03-25T15:00:00').\n\n"
            "Devuelve los detalles del evento en este formato:\n"
            "{\n"
            "  \"tipo_servicio\": \"...\",\n"
            "  \"cliente\": \"...\",\n"
            "  \"correo_cliente\": \"...\",\n"
            "  \"start\": \"...\",\n"
            "  \"end\": \"...\"\n"
            "}\n"
            "Si algún dato no está presente en el mensaje, simplemente devuelve un valor vacío para ese campo."
        )},
        {"role": "user", "content": user_input}
    ]
    
    # Realizamos la llamada al LLM para obtener la respuesta
    response = client.chat.completions.create(model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free", messages=messages)
    
    # Procesamos la respuesta del modelo y extraemos los detalles
    evento_info = response.choices[0].message.content.strip()

    try:
        # Intentamos convertir la respuesta en formato JSON usando json.loads()
        evento_info_dict = json.loads(evento_info)
        return evento_info_dict
    except json.JSONDecodeError as e:
        return f"❌ Hubo un error al procesar los detalles del evento: {e}"


def buscar_en_chroma(query):
    """
    Busca en ChromaDB información relevante para enriquecer la respuesta del chatbot.
    """
    vectorstore = get_vectorstore()
    if vectorstore is None:
        return ""

    try:
        results = vectorstore.similarity_search(query, k=3)  # Busca los 3 documentos más similares
        contexto = "\n".join([doc.page_content for doc in results])
        return contexto
    except Exception as e:
        logger.error(f"❌ Error en la búsqueda de ChromaDB: {e}")
        return ""


def chat_with_us(user_input, uploaded_files=None, audio_file_path=None, response_format="text"):
    """
    Procesa la solicitud del usuario y ejecuta la acción correspondiente según la intención detectada.
    """
    # Recuperamos el historial de chat
    chat_history = get_chat_history()

    global estado, event_context

    try:
        analistas = {
                "Sara Milena Díaz Pérez": "sara.diaz1@udea.edu.co",
                "Karol Escudero Gutierrez": "karol.escudero@udea.edu.co",
                "Cristian Mora": "cristian.morag@udea.edu.co",
                "Maria Camila Perez Hincapie": "maria.perez29@udea.edu.co"
            }
        if audio_file_path:
            transcription = transcribe_audio_google_simple(audio_file_path)  # Usamos la transcripción con Google
            if transcription:  # Si la transcripción es válida, usarla como entrada
                user_input = transcription
            else:
                return "Lo siento, no pude entender el audio."    
        # Almacenamos temporalmente los datos del evento
        eventos_temporales = {}  # Aquí guardamos la información mientras el proceso está en curso

        # Estado inicial
        estado = "esperando_informacion"  # Este estado comienza como 'esperando_informacion'

        # 🔍 Detectar la intención del usuario con el LLM
        intencion = detectar_intencion(user_input)
        print("Intención detectada:", intencion)

        # Si la intención es crear un evento, gestionar el flujo del evento
        # Detectar la intención
        # Detectar palabras clave para agendar una cita
        # Detectar la intención
        if "agendar cita" in user_input.lower():
            print("DEBUG: Intención detectada: Agendar cita")  # Debug: Si detectamos la intención
            # Si estamos esperando los datos de la cita
            if event_context.get("estado", "") == "esperando_datos_cita":
                print("DEBUG: Estado actual: esperando_datos_cita")  # Debug: Estado antes de solicitar datos
                return (
                    "📅 ¡Entendido! Para agendar una cita, por favor proporciona los siguientes datos:\n\n"
                    "📌 **1. Tipo de servicio:** (Ej. Consulta estadística, Capacitación)\n"
                    "📌 **2. Nombre del cliente o empresa:**\n"
                    "📌 **3. Correo del cliente:** (Ej. cliente@empresa.com)\n"
                    "📌 **4. Fecha y hora de inicio:** (Ej. 2025-03-25T14:00:00)\n"
                    "📌 **5. Fecha y hora de finalización:** (Ej. 2025-03-25T15:00:00)\n\n"
                    "✍️ **Ejemplo:** Capacitación en análisis de datos, Empresa XYZ, cliente@xyz.com, "
                    "2025-03-25T14:00:00, 2025-03-25T16:00:00"
                )
            # Marcar que estamos esperando los datos para la cita
            event_context["estado"] = "esperando_datos_cita"
            print(f"DEBUG: Estado cambiado a 'esperando_datos_cita'")  # Debug: Estado cambiado
            return "📅 ¡Entendido! Para agendar la cita, por favor proporciona los detalles del tipo de servicio, cliente, correo, inicio y fin."

        # Extraer datos de la cita y validarlos
        match = re.search(r"(?i)tipo de servicio:\s*(.*?),\s*cliente:\s*(.*?),\s*correo del cliente:\s*(.*?),\s*inicio:\s*(.*?),\s*fin:\s*(.*)", user_input, re.IGNORECASE)
        print("DEBUG: Intentando extraer los datos con la expresión regular...")  # Debug: Intentando hacer la extracción

        if match:
            tipo_servicio = match.group(1).strip()
            cliente = match.group(2).strip()
            correo_cliente = match.group(3).strip()
            inicio = match.group(4).strip()
            fin = match.group(5).strip()

            print(f"DEBUG: Datos extraídos - Tipo de servicio: {tipo_servicio}, Cliente: {cliente}, Correo: {correo_cliente}, Inicio: {inicio}, Fin: {fin}")  # Debug: Datos extraídos

            # Validar si la fecha y hora están en el formato correcto
            try:
                inicio_dt = datetime.strptime(inicio, "%Y-%m-%dT%H:%M:%S")
                fin_dt = datetime.strptime(fin, "%Y-%m-%dT%H:%M:%S")
                print(f"DEBUG: Fechas validadas - Inicio: {inicio_dt}, Fin: {fin_dt}")  # Debug: Fechas validadas correctamente
            except ValueError:
                print("DEBUG: Error al validar las fechas")  # Debug: Error al validar las fechas
                return "⚠️ Las fechas deben estar en formato 'YYYY-MM-DDTHH:MM:SS'. Por favor, revisa la entrada."

            # Validar si el correo del cliente tiene el formato adecuado
            if "@" not in correo_cliente:
                print(f"DEBUG: El correo del cliente no es válido: {correo_cliente}")  # Debug: Correo no válido
                return "⚠️ El correo del cliente no tiene un formato válido. Por favor, revisa el correo."

            # Asignar un analista de manera aleatoria
            analista = "Sara Milena Díaz Pérez"  # En un caso real podrías seleccionar un analista aleatorio
            correo_analista = analistas.get(analista)

            print(f"DEBUG: Analista asignado: {analista} ({correo_analista})")  # Debug: Analista asignado

            # Asegúrate de que las fechas sean cadenas en el formato adecuado
            inicio_dt_str = inicio_dt.isoformat()  # Convierte la fecha de inicio a string
            fin_dt_str = fin_dt.isoformat()        # Convierte la fecha de fin a string

            # Llamada a la función agendar_cita con las fechas convertidas
            resultado = calendar.agendar_cita(
                tipo_servicio,         # summary
                inicio_dt_str,         # start_time como string
                fin_dt_str,            # end_time como string
                "America/Bogota",      # timezone
                attendees=[correo_cliente],  # Lista con el correo del cliente
                analista=correo_analista     # Correo del analista
            )

            # Limpiar el contexto
            event_context.clear()
            print(f"DEBUG: Contexto limpiado.")  # Debug: Limpiamos el contexto después de agendar

            # Volver al estado inicial
            event_context["estado"] = "esperando_intencion"
            print(f"DEBUG: Estado cambiado a 'esperando_intencion'")  # Debug: Estado cambiado a esperando_intencion
            
            return resultado


        # 🎯 Consultar eventos públicos de Dataconsult
        if intencion == "consultar_eventos":
            # Obtener eventos y citas
            events = calendar.list_upcoming_events()
            
            # Acceder a las listas dentro del diccionario
            eventos_publicos = events.get('eventos_publicos', [])
            citas = events.get('citas', [])
            
            # Combinar los eventos y citas
            all_events = eventos_publicos + citas
            
            if all_events:
                eventos_texto = "\n".join([ 
                    f"📅 {e['start'].get('dateTime', e['start'].get('date'))} - {e['summary']}" 
                    for e in all_events
                ])
                return f"📆 Aquí tienes los próximos eventos públicos y citas de Dataconsult:\n\n{eventos_texto}"
            else:
                return "📭 No hay eventos ni citas programadas en este momento."

        # 🎯 Enviar un correo
        if intencion == "enviar_correo":
            # Si estamos esperando los datos del correo
            if event_context.get("estado", "") == "esperando_datos_correo":
                return (
                    "📤 ¡Entendido! Para enviar un correo desde **Dataconsult**, por favor proporciona lo siguiente:\n\n"
                    "📌 **1. Destinatario:** (ej. Nombre del analista, ej. Sara Milena Díaz Pérez)\n"
                    "📌 **2. Asunto:** (ej. Recordatorio de consulta estadística)\n"
                    "📌 **3. Mensaje:** (contenido del correo)\n"
                    "📌 **4. Archivos adjuntos:** (Nombres de archivos separados por coma o escribe 'No' si no hay adjuntos)\n\n"
                    "✍️ **Ejemplo:** Destinatario: Sara Milena Díaz Pérez, Asunto: Consulta estadística, Mensaje: Hola, nos vemos mañana para la consulta, Archivos: No"
                )

            # Marcar estado de espera por datos del correo
            event_context["estado"] = "esperando_datos_correo"
            return "📤 ¡Entendido! Para enviar un correo, por favor proporciona los detalles del destinatario, asunto, mensaje y archivos."

        # 🎯 Extraer datos del correo y validar archivos
        match = re.search(r"(?i)destinatario:\s*(.*?),\s*asunto:\s*(.*?),\s*mensaje:\s*(.*?),\s*archivos:\s*(.*)", user_input, re.IGNORECASE)

        if match:
            destinatario = match.group(1).strip()
            asunto = match.group(2).strip()
            mensaje = match.group(3).strip()
            archivos_raw = match.group(4).strip()

            analistas = {
                "Sara Milena Díaz Pérez": "sara.diaz1@udea.edu.co",
                "Karol Escudero Gutierrez": "karol.escudero@udea.edu.co",
                "Cristian Mora": "cristian.morag@udea.edu.co",
                "Maria Camila Perez Hincapie": "maria.perez29@udea.edu.co"
            }

            # Validar si el destinatario es un analista
            email_destinatario = analistas.get(destinatario)
            if not email_destinatario:
                return f"⚠️ No encontré el correo para '{destinatario}'. Por favor, revisa el nombre del destinatario o asegúrate de que esté bien escrito."

            # Validar si el asunto y el mensaje están presentes
            if not asunto:
                return "⚠️ El asunto está vacío. Por favor, asegúrate de incluir un asunto para el correo."
            
            if not mensaje:
                return "⚠️ El mensaje está vacío. Por favor, asegúrate de incluir un mensaje para el correo."

            # Validar archivos adjuntos
            attachments = []
            if archivos_raw.lower() != "no":
                archivos_solicitados = [archivo.strip() for archivo in archivos_raw.split(",")]
                
                # Aquí, obtenemos los archivos disponibles de la carpeta CARPETA_ARCHIVOS
                archivos_disponibles = {filename: os.path.join(CARPETA_ARCHIVOS, filename) for filename in os.listdir(CARPETA_ARCHIVOS)}

                archivos_adjuntos = [
                    (nombre, archivos_disponibles.get(nombre))
                    for nombre in archivos_solicitados
                    if nombre in archivos_disponibles
                ]
                
                if len(archivos_adjuntos) < len(archivos_solicitados):
                    archivos_faltantes = set(archivos_solicitados) - set(archivos_disponibles)
                    return f"⚠️ No encontré estos archivos: {', '.join(archivos_faltantes)}. Asegúrate de haberlos subido."

                attachments.extend(archivos_adjuntos)



            # Si todo está bien, enviar el correo
            try:
                # Aquí debes llamar a la función que envía el correo usando la API de Gmail
                gmail_manager = GmailManager()
                send_result = gmail_manager.send_email(
                    sender="tu_correo@gmail.com", 
                    recipient=email_destinatario, 
                    subject=asunto, 
                    body=mensaje, 
                    attachments=attachments
                )
                # Si todo va bien, actualizamos el estado y devolvemos el mensaje
                event_context["estado"] = "correo_enviado"
                return f"✅ Correo enviado a {destinatario} ({email_destinatario}) con el asunto '{asunto}' y el mensaje: '{mensaje}'."
            except Exception as e:
                return f"❌ Error al enviar el correo: {str(e)}"

        # 🗣 Conversación con contexto de Chroma
        contexto_adicional = ""
        if intencion == "charlar":
            contexto_adicional = buscar_en_chroma(user_input)

        # 🎯 Enviar contexto y pregunta al modelo
        # 🎯 Enviar contexto y pregunta al modelo
        messages = [
            {"role": "system", "content": (
                "Eres Esperancita, la secretaria virtual de Dataconsult, una consultoría estadística. "
                "Debes responder únicamente con la información contenida en el siguiente contexto:\n\n"
                "**Historia de Dataconsult**\n\n"
                "Dataconsult es una empresa de consultoría estadística fundada en 2022 con el objetivo de ofrecer soluciones basadas en análisis de datos para la toma de decisiones estratégicas. Desde su creación, la empresa se ha especializado en diversas áreas, como análisis estadístico, investigación de mercado, inteligencia de negocios y auditoría de datos.\n\n"
                "Inicialmente, Dataconsult comenzó trabajando con pequeñas y medianas empresas, ayudándolas a comprender mejor sus datos y a optimizar sus procesos. Gracias a la calidad y precisión de su trabajo, la empresa creció rápidamente y amplió su portafolio de servicios, incorporando modelos predictivos, análisis de riesgos y soluciones automatizadas de clasificación de datos.\n\n"
                "Uno de sus principales logros ha sido la implementación de herramientas avanzadas basadas en modelos bayesianos para la predicción y gestión de incidentes, así como el desarrollo de dashboards interactivos para la visualización de datos empresariales.\n\n"
                "Hoy en día, Dataconsult es reconocida por su enfoque en la innovación y su capacidad para transformar datos en información valiosa para la toma de decisiones. La empresa sigue expandiéndose y adaptándose a las nuevas tendencias del análisis de datos, brindando asesoría a organizaciones de diferentes sectores.\n\n"
                
                "📌 **Reglas estrictas para responder:**\n"
                "1️⃣ **Solo si** te saludan con **Hola Esperancita**, responde con un saludo cálido y preséntate como secretaria virtual de Dataconsult.\n"
                "2️⃣ Si la pregunta está cubierta en el contexto, responde con información clara y precisa.\n"
                "3️⃣ **No inventes ni asumas información adicional.**\n"
                "4️⃣ Mantén un tono **formal, amigable y accesible**, evitando respuestas demasiado secas.\n"
                "5️⃣ Si es necesario, ofrece ayuda adicional o sugiere opciones dentro de los servicios de Dataconsult.\n"
                "6️⃣ **Solo si** te preguntan por la historia de la empresa das esa información.\n\n"

                
                "📍 **Servicios de Dataconsult y Precios**\n"
                "   ✅ **Análisis Estadístico y Modelado**: \n"
                "      - Análisis simple de datos y reportes: 600,000 COP.\n"
                "      - Encuestas personalizadas: 700,000 COP.\n"
                "      - Revisión y validación de datos: 750,000 COP.\n"
                "      - Modelado predictivo y análisis avanzado: 1,200,000 COP.\n"
                "      - Análisis financiero y proyecciones: 1,000,000 COP.\n"
                "      - Segmentación de mercado y tendencias: 850,000 COP.\n"
                "      - Visualización de datos y dashboards: 1,300,000 COP.\n\n"
                
                "   ✅ **Capacitación y Asesoría**: \n"
                "      - Curso de análisis de datos con software estadístico: 500,000 COP por persona (mínimo 5 personas).\n\n"
                
                "   ✅ **Paquetes de Servicios**: \n"
                "      - Paquete Básico (2 consultas de análisis básico): 1,100,000 COP.\n"
                "      - Paquete Avanzado (3 consultas avanzadas): 3,200,000 COP.\n\n"
                
                "   ✅ **Servicios Adicionales**: \n"
                "      - Entrega Expresa de Reportes (24 horas): 250,000 COP.\n\n"
                
                "📢 *Nota:* \n"
                "- Las consultas básicas incluyen análisis descriptivo y revisión de datos.\n"
                "- Las consultas avanzadas incluyen modelado predictivo, análisis financiero y segmentación de mercado.\n"
                "Si necesitas más detalles sobre un servicio en particular, pregúntame y te ayudaré."
            )},
            {"role": "user", "content": user_input}
        ]


        response = client.chat.completions.create(model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free", messages=messages)
        # Obtener la respuesta del modelo
        bot_response = response.choices[0].message.content

        # Guardar la conversación en el historial
        save_search(user_input, bot_response)
        
        if response_format == "audio":
            # Convertir el texto en audio (usa gTTS o un servicio similar)

            tts = gTTS(text=bot_response, lang='es')
            with tempfile.NamedTemporaryFile(delete=False) as temp_audio_file:
                temp_audio_file_path = temp_audio_file.name + '.mp3'
                tts.save(temp_audio_file_path)

            return temp_audio_file_path  # Devolvemos la ruta al archivo de audio generado

        return bot_response        


    except Exception as e:
        logging.error(f"Error en el chatbot: {str(e)}")
        return f"⚠️ Hubo un error al procesar tu solicitud: {str(e)}"
