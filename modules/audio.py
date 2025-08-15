from gtts import gTTS
import speech_recognition as sr
import pyaudio
import wave

def transcribe_audio_google_simple(audio_file_path):
    """
    Transcribe un archivo de audio utilizando la API de Google (a través de SpeechRecognition).
    """
    recognizer = sr.Recognizer()

    try:
        # Abrir el archivo de audio
        with sr.AudioFile(audio_file_path) as source:
            # Escuchar el archivo de audio
            audio_data = recognizer.record(source)

        # Usar el reconocimiento de Google para obtener la transcripción
        transcription = recognizer.recognize_google(audio_data, language="es-CO")
        return transcription
    except sr.UnknownValueError:
        return "Lo siento, no pude entender el audio."
    except sr.RequestError as e:
        return f"Error de la solicitud a Google Speech Recognition: {e}"
    except Exception as e:
        return f"Hubo un error al procesar el audio: {e}"

# Función para convertir texto a audio
def convert_text_to_audio(text):
    tts = gTTS(text, lang='es')  # Usar el idioma español, puedes cambiarlo si prefieres otro idioma
    audio_file_path = "response_audio.mp3"
    tts.save(audio_file_path)
    return audio_file_path



# Función para grabar el audio
def record_audio_file(filename="audio.wav", duration=5):
    """Graba el audio desde el micrófono y lo guarda en un archivo."""
    chunk = 1024  # Número de frames por buffer
    sample_format = pyaudio.paInt16  # Formato de audio
    channels = 1  # Monofónico
    rate = 44100  # Frecuencia de muestreo
    frames = []  # Lista para almacenar los frames grabados

    # Inicia PyAudio
    p = pyaudio.PyAudio()

    print("🎙️ Grabando audio...")

    # Inicia la grabación
    stream = p.open(format=sample_format, channels=channels,
                    rate=rate, frames_per_buffer=chunk, input=True)

    # Graba durante la duración especificada
    for _ in range(0, int(rate / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    # Detén la grabación y cierra el stream
    stream.stop_stream()
    stream.close()
    p.terminate()

    # Guarda el archivo de audio
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))

    print(f"✅ Grabación guardada como {filename}")
    return filename