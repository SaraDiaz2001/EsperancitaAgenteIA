# app.py
import streamlit as st
from modules.chatbot import chat_with_us
from modules.embeddings import load_and_store_documents
from modules.logger import logger
from modules.audio import convert_text_to_audio, transcribe_audio_google_simple, record_audio_file
from modules.google_calendar import GoogleCalendarManager
import os
from modules.database import get_existing_document_ids  # Importa la función para obtener documentos existentes

calendar = GoogleCalendarManager()

# Definir la ruta de la carpeta de archivos
CARPETA_ARCHIVOS = r"C:\Users\Usuario\Documents\ChatBot\Chat\data\archivos"

# Crear la carpeta si no existe
if not os.path.exists(CARPETA_ARCHIVOS):
    os.makedirs(CARPETA_ARCHIVOS)

# 🖥️ **Configuración de la página**
st.set_page_config(page_title="Esperancita", layout="wide")
st.title("Ordene su merced")

# 🔄 **Columnas para la interfaz**
col1, col2 = st.columns([1, 3])  # 🐂 1/4 izquierda - 💬 3/4 derecha

# 🐂 **Columna izquierda: Carga de documentos y archivos adjuntos**
with col1:
    st.header("🔍 Cuentame tu caso y lo analizaremos")
    uploaded_file = st.file_uploader("Carga un archivo (.txt, .csv) para alimentar el contexto", type=["txt", "csv"])
    
    # Botón para elegir entre texto o audio
    st.header("💬 Formato de respuesta")
    response_format = st.radio("¿Cómo te gustaría la respuesta?", ("Texto", "Audio"))

    if uploaded_file is not None:
        try:
            # Verificar si el archivo ya ha sido cargado antes
            existing_docs = get_existing_document_ids()  # Obtiene los documentos existentes
            if uploaded_file.name in existing_docs:
                st.warning(f"⚠️ El documento '{uploaded_file.name}' ya está indexado. No se volverá a cargar.")
            else:
                # Guardar el archivo en la carpeta de archivos
                filepath = os.path.join(CARPETA_ARCHIVOS, uploaded_file.name)
                with open(filepath, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Llamar a la función para almacenar el documento
                load_and_store_documents(uploaded_file, uploaded_file.name)
                st.success(f"✅ Archivo '{uploaded_file.name}' cargado y guardado correctamente.")
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")

    # 📎 **Subida de archivos adjuntos para correos (debajo de documentos)**
    st.header("📎 Adjuntar Archivos para Correo")
    uploaded_files = st.file_uploader("Selecciona archivos para enviar por correo", accept_multiple_files=True)

    # Guardamos los archivos subidos en la carpeta de archivos
    if uploaded_files:
        for uploaded in uploaded_files:
            filepath = os.path.join(CARPETA_ARCHIVOS, uploaded.name)
            with open(filepath, "wb") as f:
                f.write(uploaded.getbuffer())

    # 📅 **Google Calendar: Eventos Públicos**
    st.header("📅 Consulta de Eventos Públicos")

    if st.button("🔍 Ver próximos eventos públicos"):
        eventos = calendar.consultar_eventos_publicos()

        if isinstance(eventos, str):  # Si hay un error, se muestra el mensaje
            st.write(eventos)
        elif eventos:
            for event in eventos:
                start = event["start"].get("dateTime", event["start"].get("date"))
                st.write(f"📌 {start} - {event['summary']}")
        else:
            st.write("No hay eventos públicos próximos.")

    st.subheader("📆 Agendate una cita")
    event_summary = st.text_input("Tipo de cita y Nombre del consultante")
    event_start = st.text_input("Fecha y hora de inicio (YYYY-MM-DDTHH:MM:SS)")
    event_end = st.text_input("Fecha y hora de finalización (YYYY-MM-DDTHH:MM:SS)")
    event_timezone = st.text_input("Zona horaria (Ej: America/Bogota)", value="America/Bogota")
    event_attendees = st.text_area("Correos de asistentes (separados por comas)")

    if st.button("📌 Crear evento"):
        if event_summary and event_start and event_end:
            attendee_list = [email.strip() for email in event_attendees.split(",")] if event_attendees else None
            response = calendar.agendar_cita(event_summary, event_start, event_end, event_timezone, attendee_list)
            st.success(response)
        else:
            st.warning("Por favor, completa todos los campos requeridos.")

# 💬 **Columna derecha: Chatbot**
with col2:
    st.header("👵🏼 Esperancita: ¿En qué le colaboro mijito?")
    st.write("💬 Cantelas")

    # 👌 **Entrada fija del usuario**
    user_input = st.chat_input("¿Cómo te puedo ayudar...?")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if user_input:
        # 📬 **Guarda y muestra el mensaje del usuario**
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # 🔥 **Generar respuesta con archivos adjuntos si hay**
        response = chat_with_us(user_input, uploaded_files)
                # Si la respuesta es en audio

        if response_format == "Audio":
            # Convertir respuesta a audio
            audio_file = convert_text_to_audio(response)
            st.session_state.messages.append({"role": "assistant", "content": audio_file})
            with st.chat_message("assistant"):
                st.audio(audio_file, format="audio/mp3")  # Reproducir el archivo de audio
        else:
            # Si la respuesta es en texto
            #st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                if response.startswith("http"):  # Si la respuesta es una imagen
                    st.image(response, caption="Imagen generada", use_container_width=True)
                else:
                    st.markdown(response)

        # 🐟 **Guardar respuesta del bot**
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Botón de grabación de audio
    if st.button("Grabar Audio"):
        st.write("🔴 Grabando...")  # Indicador visual de grabación
        audio_file = record_audio_file(duration=6)  # Graba por 5 segundos o más
        if audio_file:
            try:
                # No reproducir el audio, solo procesarlo
                logger.info(f"Audio grabado correctamente: {audio_file}")
                
                # Guarda el archivo y transcribe con Google
                transcription = transcribe_audio_google_simple(audio_file)
                logger.info(f"Transcripción: {transcription}")

                # Mostrar la transcripción del audio
                st.session_state.messages.append({"role": "user", "content": transcription})
                with st.chat_message("user"):
                    st.markdown(transcription)

                # Obtener la respuesta del chatbot
                response = chat_with_us(transcription)

                # Mostrar la respuesta del bot
                if response_format == "Audio":
                    # Convertir respuesta a audio
                    audio_file = convert_text_to_audio(response)
                    st.session_state.messages.append({"role": "assistant", "content": audio_file})
                    with st.chat_message("assistant"):
                        st.audio(audio_file, format="audio/mp3")  # Reproducir el archivo de audio
                else:
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"):
                        if response.startswith("http"):  # Si la respuesta es una imagen
                            st.image(response, caption="Imagen generada", use_container_width=True)
                        else:
                            st.markdown(response)
            except Exception as e:
                st.error(f"❌ Error al procesar el audio: {e}")
                logger.error(f"❌ Error al procesar el audio: {e}")

    # 📝 **Mostrar historial de chat en orden cronológico (lo más viejo arriba)**
    chat_history_container = st.container()
    with chat_history_container:
        for msg in st.session_state.messages:  # Mostrar en orden normal (antiguo a reciente)
            with st.chat_message(msg["role"]):
                if isinstance(msg["content"], str) and msg["content"].startswith("http"):  # Si la respuesta es una imagen
                    st.image(msg["content"], caption="Imagen generada", use_container_width=True)
                else:
                    st.markdown(msg["content"])




