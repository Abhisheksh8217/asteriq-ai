"""
services/feedback_service.py
----------------------------
Handles the generation of interview feedback at the end of the session.
Retrieves conversation history, constructs feedback instructions, calls the LLM,
cleans and validates JSON responses, and marks the session as completed in SQLite.
"""

import json
from typing import Dict, Any

from logger import get_logger
from services.llm_service import llm_service
from services.prompt_builder import prompt_builder
from services.interview_engine import interview_engine
import database

logger = get_logger(__name__)


class FeedbackService:
    """
    Evaluates complete interview dialogue records using structured JSON prompts.
    """

    def generate_feedback(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves the complete conversation history for the session,
        submits it to the agent, evaluates the candidate, parses the JSON feedback,
        and saves the completion state to the database.

        Args:
            session_id: The ID of the session to grade.

        Returns:
            Dict containing parsed feedback values (subject, candidate_score, feedback, areas_of_improvement).
        """
        logger.info("Generating evaluation feedback for session %s", session_id)

        # 1. Verify session in DB
        session = database.get_session(session_id)
        if not session:
            raise ValueError(f"No session record found matching ID: {session_id}")

        topic = session["topic"]

        # 2. Retrieve conversation history directly from database
        history = database.get_interview_history(session_id)
        if not history:
            logger.warning("No dialogue history found in database for session %s", session_id)
            history_text = "No conversation occurred."
        else:
            history_text = ""
            for idx, record in enumerate(history):
                q = record.get("question") or ""
                a = record.get("answer") or ""
                history_text += f"Interviewer: {q}\nCandidate: {a}\n\n"

        # 3. Build evaluation prompt containing full conversation context
        eval_prompt = prompt_builder.build_feedback_prompt(topic) + f"\n\nCONVERSATION HISTORY:\n{history_text}"

        # 4. Invoke LLM statelessly
        logger.info("Requesting evaluation metrics from LLM...")
        try:
            raw_response = llm_service.invoke_stateless(
                messages=[{"role": "user", "content": eval_prompt}]
            )
        except Exception as e:
            logger.error("Failed to query LLM for interview feedback: %s", e)
            raise RuntimeError(f"Feedback generation failed: {e}") from e

        # 5. Parse and clean JSON response
        logger.debug("Raw feedback response: %s", raw_response)
        cleaned_response = raw_response.strip()

        # Handle typical LLM markdown wrappers
        if "```" in cleaned_response:
            try:
                # Split and pull content within fences
                parts = cleaned_response.split("```")
                # Look for index after block tag (e.g. ```json <content> ```)
                for part in parts:
                    if part.strip().startswith("{") or part.strip().startswith("["):
                        cleaned_response = part.strip()
                        break
                    elif part.strip().startswith("json"):
                        cleaned_response = part.strip()[4:].strip()
                        break
            except Exception as clean_err:
                logger.warning("Fenced parser failed to unpack feedback block: %s", clean_err)

        # Remove starting/ending code blocks if fallback failed
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        
        cleaned_response = cleaned_response.strip()

        try:
            feedback_data = json.loads(cleaned_response)
            logger.info("Feedback parsed successfully for session %s. Score: %s/5", 
                        session_id, feedback_data.get("candidate_score"))
        except json.JSONDecodeError as decode_err:
            logger.error("JSON formatting error in feedback output: %s", decode_err)
            # Create a graceful fallback response if the LLM output was malformed JSON
            feedback_data = {
                "subject": topic,
                "candidate_score": 0,
                "feedback": "An error occurred while compiling feedback. Raw response: " + cleaned_response,
                "areas_of_improvement": "Please retry requesting feedback or check logs."
            }

        # 6. Ensure the database session is set to completed
        try:
            if session["status"] == "active":
                database.complete_session(session_id)
                logger.info("Marked session %s as completed in DB.", session_id)
        except Exception as e:
            logger.error("Failed to complete session status in DB: %s", e)

        # 7. Evict agent checkpointer cache to free system memory
        interview_engine.evict_session(session_id)

        return feedback_data


# Singleton instance
feedback_service = FeedbackService()
