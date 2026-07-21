# 🎙️ ASTERIQ AI — Conversational Interview Assistant

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?logo=flask&logoColor=white)](#backend-stack)
[![LangChain](https://img.shields.io/badge/LangChain-🦜%20Orchestrator-green)](#rag-pipeline)
[![Vercel](https://img.shields.io/badge/Vercel-Frontend-black?logo=vercel)](https://vercel.com/)
[![Render](https://img.shields.io/badge/Render-Backend-46E3B7?logo=render&logoColor=white)](https://render.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)

**ASTERIQ AI** is a state-of-the-art, speech-driven conversational AI mock interviewer (codename **ANZ**) built to help candidates prepare for real-world corporate tech interviews. Using a native HTML5 audio engine and intelligent RAG-driven prompt injection, ANZ acts as a live, adaptive interviewer that reads your resume/JD and engages in a verbal technical debate.

---

## 🌟 Core Features

### 1. Adaptive Speech-to-Speech Dialogue (`ANZ`)
* **Low-Latency Synthesis**: Powered by `Edge-TTS` to generate smooth, natural, and custom-pitched neural voice responses.
* **Instant Voice Transcription**: Uses `Groq Whisper-large-v3` API to translate candidate microphone answers to text in milliseconds. 
* **Native Audio Delivery**: Raw audio files are compiled and sent directly to the client as base64 data URLs inside JSON payloads, eliminating browser-level MediaSource stutters and pitch drifts.

### 2. Intelligent Resume & JD Integration (RAG)
* **Document Ingestion**: Automatically reads candidate-uploaded resume PDFs, docx files, or job descriptions.
* **Semantic Search**: Text is chunked with LangChain's `RecursiveCharacterTextSplitter` and stored locally in a `FAISS` vector index.
* **Contextual Interviewing**: Retrieval-augmented generation feeds matching snippets of your background directly into the interviewer's prompt, ensuring technical follow-ups target your exact stack.

### 3. Self-Healing Multi-Key Fallback & Rotation
* **Automatic Failovers**: Sequential cycling through multiple API keys (`GOOGLE_API_KEYS`) to route around free-tier rate limits (429) or service outages (503).
* **Smart 404 Interceptor**: Automatically detects model compatibility errors (e.g. legacy model restrictions on newly created keys) and rotates to older legacy keys without interrupting the user's interview.

### 4. Production-Optimized Database Pooling
* **Zero-Latency Handshakes**: Utilizes a thread-safe PostgreSQL `ThreadedConnectionPool` (Supabase host), dropping remote SSL database handshakes from **~1.5 seconds down to 0ms** for active auth and session operations.

### 5. Automated Grading & Roadmaps
* **Stateless Feedback Grading**: Dialogues are loaded statelessly from the database, preventing Gunicorn worker memory losses.
* **Visual Evaluation Cards**: Rates candidates on communication, confidence, technical accuracy, and alignment, followed by a personalized learning roadmap.

---

## 🏗️ Architecture & Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor Candidate as Candidate (Browser)
    participant UI as Frontend (index.js)
    participant Flask as Backend (app.py)
    participant DB as PostgreSQL (Supabase)
    participant RAG as Ingestion & Retrieval (FAISS)
    participant LLM as Orchestrator (LangChain / Gemini)
    participant TTS as Voice Engine (Edge-TTS)

    Candidate->>UI: Select Subject / Upload Resume -> "Start Interview"
    UI->>Flask: POST /start-interview (with credentials)
    Flask->>DB: Check/Register profile details
    Flask->>RAG: Retrieve matching resume/JD context
    Flask->>LLM: Generate opening question (Gemini 2.5/1.5)
    LLM-->>Flask: Text Question
    Flask->>TTS: Synthesize text question to neural MP3
    TTS-->>Flask: Binary Audio Data
    Flask-->>UI: Return JSON { question: Text, audio: Base64 }
    UI->>Candidate: Play Native Audio (Browser Speaker) & Display Question
```

---

## 🛠️ Tech Stack

* **Frontend**: Vanilla JavaScript (HTML5 Web Audio APIs, dynamic DOM scripting), modern responsive styling (Vanilla CSS with custom glassmorphism systems).
* **Backend**: Flask REST API, Gunicorn WSGI.
* **Orchestration**: LangChain Core, LangGraph (agent session isolation & checkpointers).
* **Vector Store**: FAISS (Facebook AI Similarity Search).
* **Databases**: Supabase PostgreSQL.
* **Voice Engines**: Microsoft Edge-TTS (via `edge-tts` python bindings), Groq API (Whisper-large-v3).

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the `/backend` folder:

```ini
# API Keys (Comma-separated for auto-rotation)
GOOGLE_API_KEYS="AIzaSyYourPrimaryLegacyKey,AIzaSyYourBackupKey"
GROQ_API_KEY="gsk_YourGroqWhisperKey"

# Database Connection (Supabase PostgreSQL Pooler)
DATABASE_URL="postgresql://postgres.yourproject:yourpassword@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"

# SMTP Email Configuration (For welcome mailers)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-sender-email@gmail.com
SMTP_PASSWORD=your-16-char-google-app-password
```

---

## 🚀 Getting Started

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Abhisheksh8217/asteriq-ai.git
   cd asteriq-ai
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Create and populate the `/backend/.env` file with your credentials.

4. **Launch Backend Server:**
   ```bash
   python app.py
   ```
   The backend will start running locally at `http://127.0.0.1:8000`.

5. **Launch Frontend:**
   You can serve the `/frontend` directory using any local static web server (such as Live Server in VS Code, or python's `http.server` module):
   ```bash
   cd ../frontend
   python -m http.server 3000
   ```
   Open your browser and navigate to `http://localhost:3000`.

---

## 📦 Deployment

* **Backend (Render)**: Deploy as a Python Web Service. Use Gunicorn as the start command (`gunicorn app:app`). Ensure all `.env` variables are added to the Render **Environment Table**.
* **Frontend (Vercel)**: Connect your repository and deploy the `/frontend` directory as a static site. Configure the frontend API endpoint URLs in `index.js` to point to your live Render backend URL.

---

## 📄 License
This project is configured for secure local deployment and private distribution. All rights reserved.
