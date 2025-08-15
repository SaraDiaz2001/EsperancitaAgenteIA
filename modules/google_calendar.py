import os.path
import datetime as dt
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# IDs de los calendarios
CALENDARIO_EVENTOS_PUBLICOS = "c_5feb504b9e2962b77f34d63d589ee4a8a16d656d334d37b20b51696f9bb632ec@group.calendar.google.com"
CALENDARIO_CITAS = "c_7b62712679573ccab2e3cf3363cefdd6e65cc4ff20a0185a495afa3620f6e8ec@group.calendar.google.com"

class GoogleCalendarManager:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None

        if os.path.exists(os.path.join(os.path.dirname(__file__), "credenciales", "token.json")):
            creds = Credentials.from_authorized_user_file(os.path.join(os.path.dirname(__file__), "credenciales", "token.json"), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(os.path.join(os.path.dirname(__file__), "credenciales", "client_secret_app_escritorio_oauth.json"),SCOPES)
                creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    def consultar_eventos_publicos(self, max_results=10):
        """Consulta eventos públicos de la empresa."""
        now = dt.datetime.utcnow().isoformat() + "Z"

        try:
            eventos_result = self.service.events().list(
                calendarId=CALENDARIO_EVENTOS_PUBLICOS,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            eventos = eventos_result.get("items", [])

            # Verifica si no hay eventos y devuelve una lista vacía
            if not eventos:
                return []

            return eventos
        
        except HttpError as error:
            return f"❌ Error al consultar eventos: {error}"

    def listar_citas(self, max_results=10):
        """Consulta citas en el calendario de la agenda de citas."""
        now = dt.datetime.utcnow().isoformat() + "Z"

        try:
            eventos_result = self.service.events().list(
                calendarId=CALENDARIO_CITAS,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            eventos = eventos_result.get("items", [])

            # Verifica si no hay citas y devuelve una lista vacía
            if not eventos:
                return []

            return eventos
        
        except HttpError as error:
            return f"❌ Error al consultar citas: {error}"

    def agendar_cita(self, summary, start_time, end_time, timezone, attendees=None, analista=None):
        """Agenda una nueva cita en el calendario de citas y agrega al analista como asistente."""
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,  # Formato: '2025-04-01T10:00:00'
                'timeZone': timezone,    # Formato: 'America/Bogota'
            },
            'end': {
                'dateTime': end_time,    # Formato: '2025-04-01T11:00:00'
                'timeZone': timezone,    # Formato: 'America/Bogota'
            }
        }

        # Asegurarse de que la lista de asistentes esté bien definida
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        
        # Agregar el correo del analista a la lista de asistentes, si se proporciona
        if analista:
            event["attendees"] = event.get("attendees", []) + [{"email": analista}]
        
        try:
            event = self.service.events().insert(calendarId=CALENDARIO_CITAS, body=event).execute()
            return f"✅ Cita creada: {event.get('htmlLink')}"
        except HttpError as error:
            return f"❌ Error al agendar la cita: {error}"

    def list_upcoming_events(self, max_results=10):
        """Consulta tanto eventos públicos como citas agendadas próximamente."""
        eventos_publicos = self.consultar_eventos_publicos(max_results)
        citas = self.listar_citas(max_results)
        
        return {
            "eventos_publicos": eventos_publicos,
            "citas": citas
        }

# Inicializar el gestor de calendarios
calendar = GoogleCalendarManager()

# 📆 Consultar próximos eventos y citas
eventos_y_citas = calendar.list_upcoming_events()
print(eventos_y_citas)

# 📅 Agendar una nueva cita (Ejemplo)
# response = calendar.agendar_cita("Consulta Estadística", "2025-04-01T10:00:00", "2025-04-01T11:00:00", "America/Bogota", ["cliente@email.com"])
# print(response)
