import os
import pickle
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Definir los alcances requeridos
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

class GmailManager:
    def __init__(self):
        self.creds = None
        self.token_path = os.path.join(os.path.dirname(__file__), "..", "credenciales", "token_gmail.pickle")
        self.credentials_path = os.path.join(os.path.dirname(__file__), "..", "credenciales", "client_secret_app_escritorio_oauth.json")

        # Cargar credenciales si ya fueron autenticadas
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as token:
                self.creds = pickle.load(token)

        # Si no hay credenciales válidas, iniciar autenticación
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)

            # Guardar las credenciales para la próxima vez
            with open(self.token_path, "wb") as token:
                pickle.dump(self.creds, token)

        # Crear el servicio de Gmail
        self.service = build("gmail", "v1", credentials=self.creds)

    def send_email(self, sender, recipient, subject, body, attachments=[]):
        """ Envía un correo electrónico usando Gmail API con opcionales archivos adjuntos """
        message = MIMEMultipart()
        message["to"] = recipient
        message["from"] = sender
        message["subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Adjuntar archivos si existen
        for filename, filedata in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(filedata)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            message.attach(part)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = {"raw": raw_message}

        try:
            self.service.users().messages().send(userId="me", body=send_message).execute()
            return f"📧 Correo enviado a {recipient} con éxito."
        except Exception as e:
            return f"❌ Error al enviar el correo: {str(e)}"

def test_send_email():
    sender = "sara.diaz1@udea.edu.co"
    recipient = "sara.diaz1@udea.edu.co"
    subject = "Prueba de envío"
    body = "Este es un correo de prueba para verificar que todo esté funcionando."

    gmail_manager = GmailManager()
    result = gmail_manager.send_email(sender, recipient, subject, body)
    print(result)

#test_send_email()
