# main.py
import os
import json
import tempfile
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydub import AudioSegment

import openai
from openai import OpenAI

import gspread
from google.cloud import secretmanager
from google.oauth2.service_account import Credentials

# ---------------------------
# Load Environment Variables
# ---------------------------
load_dotenv()

# ---------------------------
# Secrets and OpenAI Configuration
# ---------------------------
def get_secret(secret_name):
    """Retrieve secret; use local environment variable when testing."""
    if os.getenv("LOCAL_DEV"):
        return os.getenv(secret_name)
    
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set.")

    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": secret_path})
    
    return response.payload.data.decode("UTF-8")

# Set OpenAI API key using the secret
openai.api_key = get_secret("OPENAI_API_KEY")
client = OpenAI()  # Initialize the OpenAI client

# ---------------------------
# Helper Functions for Google APIs
# ---------------------------
def get_gspread_client():
    """Authenticate and return a Google Sheets client using a service account."""
    if os.getenv("LOCAL_DEV"):
        print("Running in LOCAL mode: Using JSON file for authentication.")
        service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/service_account.json")
        if not os.path.exists(service_account_file):
            raise FileNotFoundError(f"Service account JSON file '{service_account_file}' not found.")
        creds = Credentials.from_service_account_file(
            service_account_file, 
            scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
    else:
        print("Running in PRODUCTION mode: Fetching secret from Secret Manager.")
        json_key = get_secret("talk-to-linkedin-connections")
        creds = Credentials.from_service_account_info(
            json.loads(json_key), 
            scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
    return gspread.authorize(creds)

def get_next_unprocessed_record(current_row: int) -> dict:
    gc = get_gspread_client()
    SHEET_ID = os.getenv("SHEET_ID")
    SHEET_NAME = os.getenv("SHEET_NAME")
    sh = gc.open_by_key(SHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)
    values = worksheet.get_all_values()  # Row 1 is header.
    for i in range(current_row + 1, len(values) + 1):
        row_values = values[i - 1]
        # If less than 6 columns or column F (index 5) is empty, treat as unprocessed.
        if len(row_values) < 6 or not row_values[5].strip():
            return {
                "row": i,
                "url": row_values[0] if len(row_values) > 0 else "",
                "company": row_values[1] if len(row_values) > 1 else "",
                "connected_on": row_values[2] if len(row_values) > 2 else "",
                "first_name": row_values[3] if len(row_values) > 3 else "",
                "last_name": row_values[4] if len(row_values) > 4 else "",
                "recording": row_values[5] if len(row_values) > 5 else ""
            }
    return {}

# ---------------------------
# Audio Processing Functions
# ---------------------------
def split_audio(file_path: str, max_size_mb: int = 25) -> list:
    """
    Splits audio into chunks each less than max_size_mb.
    Returns a list of chunk file paths.
    """
    audio = AudioSegment.from_file(file_path)
    total_length_ms = len(audio)
    chunk_size_ms = int((max_size_mb * 1024 * 1024) / (audio.frame_rate * audio.frame_width)) * 1000

    chunks = []
    for i in range(0, total_length_ms, chunk_size_ms):
        chunk = audio[i:i + chunk_size_ms]
        chunk_path = f"{file_path}_chunk{i // chunk_size_ms}.mp3"
        chunk.export(chunk_path, format="mp3")
        chunks.append(chunk_path)

    return chunks

def transcribe_audio(file_path: str) -> str:
    """
    Transcribe audio using OpenAI's Whisper API.
    Handles large files by splitting them into chunks if necessary.
    """
    # Check file size
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 25:  # OpenAI's limit is 25MB
        chunks = split_audio(file_path)
        transcription_text = ""
        for chunk in chunks:
            with open(chunk, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcription_text += transcription + "\n"
            os.remove(chunk)  # Clean up chunk file
        return transcription_text.strip()
    else:
        with open(file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        return transcription

def process_transcription(file_path: str, row: int):
    """
    Background task to transcribe the audio file and update the Sheet at the specified row.
    """
    transcription_text = transcribe_audio(file_path)
    gc = get_gspread_client()
    SHEET_ID = os.getenv("SHEET_ID")
    SHEET_NAME = os.getenv("SHEET_NAME")
    sh = gc.open_by_key(SHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)
    cell = f"F{row}"
    worksheet.update_acell(cell, transcription_text)

# ---------------------------
# FastAPI App Setup
# ---------------------------
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """
    Load the app with the first unprocessed record.
    """
    # Start from row 1 (header), so first record is row 2
    first_record = get_next_unprocessed_record(1)
    return templates.TemplateResponse("index.html", {"request": request, "record": first_record})

@app.post("/done")
async def done(
    file: UploadFile = File(...),
    current_row: int = Form(...),
    background_tasks: BackgroundTasks = None
):
    """
    Endpoint triggered when the user clicks "Done & Next".
    It saves the current recording, schedules transcription as a background task,
    and immediately returns the next unprocessed record.
    """
    # Save the uploaded file to a temporary file.
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
        temp_file.write(await file.read())
        temp_file_path = temp_file.name

    # Schedule transcription in the background for the current record.
    background_tasks.add_task(process_transcription, temp_file_path, current_row)

    # Get the next unprocessed record.
    next_record = get_next_unprocessed_record(current_row)
    if not next_record:
        return {"message": "No more unprocessed records."}
    return next_record
