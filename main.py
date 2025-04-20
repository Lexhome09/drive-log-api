from flask import Flask, jsonify, request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from docx import Document
import os
import json
from google.auth.transport.requests import Request

app = Flask(__name__)

# Google API Scopes and Globals
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = None
drive_service = None

# 🔐 Set your root logs folder ID here
root_folder_id = "1AUi1RxwYNW_jqJmaIWbONshfU_RmRp3l"

# 🔐 Authenticate using env vars
def authenticate():
    global creds, drive_service
    print("🔐 Starting authentication...")

    creds_json = os.environ.get("GOOGLE_TOKEN")
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS")

    if creds_json and credentials_json:
        try:
            creds_data = json.loads(creds_json)
            credentials_data = json.loads(credentials_json)

            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

            # Optional: refresh if expired
            if creds and creds.expired and creds.refresh_token:
                print("🔁 Refreshing expired token...")
                creds.refresh(Request())

            drive_service = build('drive', 'v3', credentials=creds)
            print("✅ Google Drive service initialized.")
        except Exception as e:
            print("❌ Failed to parse credentials or initialize service.")
            raise e
    else:
        raise ValueError("Missing GOOGLE_TOKEN or GOOGLE_CREDENTIALS")

# 🌐 Root test
@app.route('/')
def index():
    return 'Drive Log API is running!'

# 📁 List subfolders
@app.route('/list-folders', methods=['GET'])
def list_all_subfolders():
    print("🔥 /list-folders route hit")
    try:
        global root_folder_id
        authenticate()
        print("✅ Authenticated successfully!")

        query = f"'{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, createdTime)",
            pageSize=100
        ).execute()

        folders = results.get('files', [])
        print(f"📁 Found {len(folders)} folders.")
        return jsonify(folders)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("❌ Exception in /list-folders:", str(e))
        return jsonify({'error': str(e)}), 500

# 📄 List .docx files
@app.route('/list-files', methods=['GET'])
def list_files_in_folder():
    authenticate()
    folder_id = request.args.get('folder_id')
    if not folder_id:
        return jsonify({'error': 'Missing folder_id'}), 400

    query = f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        pageSize=50
    ).execute()
    return jsonify(results.get('files', []))

# 🧠 Parse DOCX file
@app.route('/parse-docx', methods=['GET'])
def parse_docx_file():
    authenticate()
    file_id = request.args.get('file_id')
    if not file_id:
        return jsonify({'error': 'Missing file_id'}), 400

    request_body = drive_service.files().get_media(fileId=file_id)
    filename = 'temp_download.docx'
    with open(filename, 'wb') as f:
        f.write(request_body.execute())

    doc = Document(filename)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    structured_logs = []
    current_site = None
    current_task = None

    for line in lines:
        if line.isalpha() and line[0].isupper():
            current_site = {'site': line, 'tasks': []}
            structured_logs.append(current_site)
            current_task = None
        elif 'main' in line.lower():
            current_task = {'main': line, 'subtasks': []}
            if current_site:
                current_site['tasks'].append(current_task)
        elif current_task:
            current_task['subtasks'].append(line)

    return jsonify(structured_logs)

# ▶️ Launch app on dynamic Render port
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
