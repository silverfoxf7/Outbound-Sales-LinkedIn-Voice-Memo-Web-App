# Outbound Sales + LinkedIn + Voice Memo Web App

A FastAPI application that opens a LinkedIn URL, transcribes a voice memo from a User using OpenAI's Whisper API, and stores the transcriptions in Google Sheets.

## Features

- Voice memo recording interface
- Automatic transcription using OpenAI's Whisper API
- Google Sheets ([example](https://docs.google.com/spreadsheets/d/1xijRtA-wbrdRxIgsvD2pmxvnh-kqKVUwl4tt04sgads/edit?usp=sharing)) integration for storing transcriptions
- Background processing of transcriptions

## Prerequisites

- Python 3.8+
- OpenAI API key
- Google Cloud Project with Secret Manager enabled
- Google Sheets API enabled
- Service account credentials for Google Cloud

## Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd voice_app
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your actual values in `.env`

5. Set up Google Cloud credentials:
   - Create a service account in Google Cloud Console
   - Download the service account key JSON file
   - Place it in `credentials/service_account.json`
   - Enable necessary APIs (Sheets API, Secret Manager)

6. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

7. Visit the local URL and use the web app!

## Security Considerations

- Never commit the `.env` file or service account credentials
- Keep your OpenAI API key secure
- The application uses Google Cloud Secret Manager in production
- Local development uses environment variables for convenience

## Environment Variables

- `LOCAL_DEV`: Set to true for local development
- `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON
- `OPENAI_API_KEY`: Your OpenAI API key
- `SHEET_ID`: ID of the Google Sheet to use
- `SHEET_NAME`: Name of the worksheet to use

## License

MIT License
