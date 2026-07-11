"""
services/speech_service.py
--------------------------
Wraps both Text-to-Speech (Edge-TTS) and Speech-to-Text (Groq Whisper).

Designed as a replaceable abstraction:
  - TTS provider can be swapped (e.g., ElevenLabs, Google TTS)
  - STT provider can be swapped (e.g., Whisper, Deepgram)
  without changing any other service.

Responsibilities:
  - Stream audio chunks from Edge-TTS (base64 encoded)
  - Transcribe audio files via Groq Whisper API
  - Handle provider failures gracefully with fallback messages
"""

import base64
import json
import tempfile
import os
import requests
import subprocess
from pathlib import Path

from config import (
    EDGE_TTS_VOICE, EDGE_TTS_RATE, EDGE_TTS_PITCH,
    GROQ_API_KEY, GROQ_WHISPER_MODEL
)
from logger import get_logger

logger = get_logger(__name__)

class SpeechService:
    """
    Handles all audio I/O for the interview platform.

    TTS: Synthesizes audio using Microsoft Edge-TTS and streams as base64-encoded chunks.
    STT: Transcribes WebM audio blobs via Groq Whisper API for ultra-low latency.
    """

    def stream_tts(self, text: str):
        """
        Streams text-to-speech audio from Edge-TTS.

        Yields base64-encoded MP3 chunks line by line so the frontend
        can decode and play them progressively via MediaSource API.

        Args:
            text: The text to convert to speech.

        Yields:
            Base64-encoded audio chunk strings terminated with newline.
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                temp_path = tmp.name

            logger.info("Synthesizing Edge-TTS audio for text (%d chars)", len(text))
            
            import sys
            command = [
                sys.executable, "-m", "edge_tts",
                "--voice", EDGE_TTS_VOICE,
                "--rate", EDGE_TTS_RATE,
                "--pitch", EDGE_TTS_PITCH,
                "--text", text,
                "--write-media", temp_path
            ]
            
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Read the generated MP3 in chunks and yield as base64
            chunk_size = 4096
            with open(temp_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield base64.b64encode(chunk).decode("utf-8") + "\n"

            logger.info("Edge-TTS stream completed successfully.")

        except subprocess.CalledProcessError as e:
            logger.error("Edge-TTS subprocess failed: %s", e.stderr.decode("utf-8"), exc_info=True)
            raise RuntimeError(f"Edge-TTS synthesis failed: {e}")
        except Exception as e:
            logger.error("TTS stream failed: %s", e, exc_info=True)
            raise RuntimeError(f"TTS service unavailable: {e}") from e
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _transcribe_with_gemini_fallback(self, file_path: str) -> str:
        """
        Fallback transcription using Google Gemini 2.5 Flash's native inline audio-understanding.
        """
        logger.info("Initiating Gemini inline audio transcription as fallback...")
        try:
            from google import genai
            from config import GOOGLE_API_KEY
            
            with open(file_path, "rb") as audio_f:
                audio_bytes = audio_f.read()
                
            file_size = len(audio_bytes)
            if file_size == 0:
                return ""

            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            client = genai.Client(api_key=GOOGLE_API_KEY)
            
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=[
                    {
                        "inline_data": {
                            "mime_type": "audio/webm",
                            "data": base64_audio
                        }
                    },
                    "Transcribe this audio response verbatim. Output only the transcripted text. Do not add metadata, comments, or explanations. If there is no voice or speech, return an empty string."
                ]
            )
            
            text = response.text.strip() if response.text else ""
            logger.info("Gemini fallback transcription complete: %d chars", len(text))
            return text
            
        except Exception as e:
            logger.error("Gemini inline transcription failed: %s", e, exc_info=True)
            return ""

    def transcribe_audio(self, audio_file) -> str:
        """
        Transcribes an uploaded audio file using Groq Whisper API for ultra-low latency.
        Falls back to Gemini Native Audio if Groq fails or rate limits.

        Args:
            audio_file: File-like object from Flask request.files.

        Returns:
            Transcribed text string.
        """
        temp_path = None
        try:
            # Save to temp file with .webm extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                temp_path = tmp.name
                audio_file.save(temp_path)

            logger.info("Attempting primary Groq Whisper transcription...")
            
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}"
            }
            
            with open(temp_path, "rb") as f:
                files = {
                    "file": ("audio.webm", f, "audio/webm")
                }
                data = {
                    "model": GROQ_WHISPER_MODEL,
                    "response_format": "json"
                }
                
                # Send to Groq
                response = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=15
                )

            if response.status_code == 200:
                transcript_data = response.json()
                text = transcript_data.get("text", "").strip()
                logger.info("Groq Whisper transcription complete: %d chars", len(text))
                return text
            else:
                logger.warning(f"Groq Whisper failed (Status {response.status_code}): {response.text}")

            # Fallback if Groq fails
            logger.warning("Falling back to Gemini...")
            fallback_text = self._transcribe_with_gemini_fallback(temp_path)
            return fallback_text

        except Exception as e:
            logger.error("Audio transcription module failed: %s", e, exc_info=True)
            return ""

        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


# Singleton instance
speech_service = SpeechService()
