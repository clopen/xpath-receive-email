import json
import pathlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


HERE = pathlib.Path(__file__).parent
CLIENT_SECRETS_FILE = HERE / "clients.json"
CREDENTIALS_FILE = HERE / "credentials.json"


def main():
    creds = None
    if CREDENTIALS_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(CREDENTIALS_FILE.read_text())
            )
        except json.JSONDecodeError:
            pass
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, ["https://www.googleapis.com/auth/gmail.readonly"]
            )
            creds = flow.run_local_server(port=0)
    CREDENTIALS_FILE.write_text(creds.to_json())
    print(creds.to_json())


if __name__ == "__main__":
    main()
