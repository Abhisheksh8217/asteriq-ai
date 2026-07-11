"""
services/interview_engine.py
----------------------------
Core engine managing the lifecycle of an interview session.
Handles:
  - Starting the interview (DB initialization, system prompt tailored via RAG, first question)
  - Processing candidate answers (transcription, message history updates)
  - Progressing the conversation loop
  - Thread-safe session management using database states and checkpointers

Leverages llm_service, speech_service, knowledge_manager, prompt_builder, and database layer.
"""

from typing import Optional, Generator, Tuple, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from logger import get_logger
from services.llm_service import llm_service
from services.speech_service import speech_service
from services.knowledge_manager import knowledge_manager
from services.prompt_builder import prompt_builder
import database

logger = get_logger(__name__)


class InterviewEngine:
    """
    Manages the interview flow, maps active checkpointers, and coordinates background integrations.
    """

    def __init__(self):
        # Cache active session agents: {session_id: (agent, checkpointer)}
        self._session_cache: Dict[str, Tuple[Any, Any]] = {}

    def _get_agent(self, session_id: str) -> Any:
        """
        Retrieves the LangGraph agent for the session.
        If not cached in memory, creates a new one. Re-seeds historical messages if the session exists in DB.
        """
        if session_id in self._session_cache:
            return self._session_cache[session_id][0]

        logger.info("Initializing new LangGraph agent instance for session %s", session_id)
        agent, checkpointer = llm_service.create_session_agent()
        self._session_cache[session_id] = (agent, checkpointer)

        # Restore history if session exists in DB and has history
        try:
            self._restore_history(session_id, agent, checkpointer)
        except Exception as e:
            logger.error("Failed to restore history for session %s: %s", session_id, e)

        return agent

    def _restore_history(self, session_id: str, agent: Any, checkpointer: Any) -> None:
        """
        Re-injects conversation history from SQLite into the checkpointer in case of server restart.
        """
        session = database.get_session(session_id)
        if not session:
            return

        history = database.get_interview_history(session_id)
        if not history:
            return

        logger.info("Restoring %d database dialogue records into checkpointer for session %s", len(history), session_id)

        # Re-fetch context to build system prompt
        topic = session["topic"]
        company = session.get("company")
        
        jd_context = knowledge_manager.retrieve_context(session_id, query="job description role requirements")
        company_context = ""
        if company:
            company_context = knowledge_manager.retrieve_context(
                session_id, query=f"{company} values technology culture", company=company
            )

        system_prompt = prompt_builder.build_system_prompt(
            subject=topic,
            company=company,
            jd_context=jd_context,
            company_context=company_context
        )

        # Build list of LangChain message objects
        messages = [SystemMessage(content=system_prompt)]
        
        for record in history:
            # Re-inject the question asked by the interviewer
            if record.get("question"):
                messages.append(AIMessage(content=record["question"]))
            # Re-inject the candidate response
            if record.get("answer"):
                messages.append(HumanMessage(content=record["answer"]))

        # Update the checkpointer state
        config = {"configurable": {"thread_id": session_id}}
        checkpointer.update_state(config, {"messages": messages})
        logger.info("Checkpointer state restored successfully for session %s", session_id)

    def start_interview(
        self,
        session_id: str,
        mode: str,
        topic: str,
        company: Optional[str] = None,
        total_questions: int = 5,
        email: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Initializes an interview session, compiles RAG contexts, generates the first question,
        saves state to the database, and yields text-to-speech audio chunks.

        Returns:
            A generator yielding base64-encoded audio chunk strings.
        """
        logger.info(
            "Starting interview: session=%s | mode=%s | topic=%s | company=%s",
            session_id, mode, topic, company
        )

        # 1. Create DB entry
        database.create_session(
            session_id=session_id,
            mode=mode,
            topic=topic,
            company=company,
            total_questions=total_questions,
            email=email
        )

        # 2. Setup active agent checkpointers
        agent = self._get_agent(session_id)

        # 3. Retrieve RAG contexts
        logger.info("Retrieving RAG contexts for initial prompts...")
        jd_context = knowledge_manager.retrieve_context(session_id, query="job description role requirements")
        
        company_context = ""
        if company:
            company_context = knowledge_manager.retrieve_context(
                session_id, query=f"{company} values technology culture", company=company
            )

        # 4. Construct prompts
        candidate_name = "Candidate"
        if email:
            user_profile = database.get_user(email)
            if user_profile and user_profile.get("name"):
                candidate_name = user_profile.get("name")

        system_prompt = prompt_builder.build_system_prompt(
            subject=topic,
            company=company,
            jd_context=jd_context,
            company_context=company_context,
            candidate_name=candidate_name
        )
        
        if mode == "company":
            resume_context = knowledge_manager.retrieve_context(session_id, query="candidate resume projects experience past roles", company=company)
            starter_prompt = prompt_builder.build_company_first_question_prompt(candidate_name=candidate_name, retrieved_context=resume_context)
        else:
            from fixed_questions import FIXED_QUESTIONS
            if topic in FIXED_QUESTIONS and len(FIXED_QUESTIONS[topic]) > 0:
                first_q = FIXED_QUESTIONS[topic][0]
                starter_prompt = f"Welcome {candidate_name}. Please ask the following exact question to start the interview:\n\"{first_q}\""
            else:
                starter_prompt = prompt_builder.build_first_question_prompt(topic, candidate_name=candidate_name)

        # 5. Invoke LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": starter_prompt}
        ]
 
        try:
            logger.info("Generating opening interview question...")
            question_text = llm_service.invoke(agent, messages, session_id)
            logger.info("Question 1 generated: %s", question_text)
     
            # 6. Save first question details in DB
            database.save_question(session_id, question_number=1, question=question_text)
            database.update_session_question_count(session_id, 1)
     
            # 7. Yield speech stream
            return speech_service.stream_tts(question_text)
        except Exception as e:
            logger.error("LLM service totally failed during start after all fallbacks: %s", e)
            apology = "I sincerely apologize, but my servers are currently overwhelmed and I cannot start the interview right now. Please try again later."
            return speech_service.stream_tts(apology)

    def submit_answer(self, session_id: str, audio_file: Any) -> Tuple[Generator[str, None, None], Dict[str, str]]:
        """
        Transcribes the uploaded audio, invokes the agent state loop, decides if evaluation should trigger,
        updates state counts, and streams back the next speech audio.

        Returns:
            Tuple of (audio_generator, response_headers).
        """
        logger.info("Received candidate response upload for session %s", session_id)
 
        # 1. Load session status from database
        session = database.get_session(session_id)
        if not session:
            raise ValueError(f"No active session found matching ID: {session_id}")
 
        if session["status"] != "active":
            raise ValueError(f"Session {session_id} is already marked as {session['status']}.")
 
        # 2. Transcribe voice blob
        logger.info("Transcribing audio answer...")
        answer_text = speech_service.transcribe_audio(audio_file)
        
        if not answer_text or answer_text.strip() == "":
            logger.warning("STT transcription empty. Using fallback text.")
            answer_text = "[Candidate provided a verbal response]"
 
        question_count = session["question_count"]
        total_questions = session["total_questions"]
        mode = session["mode"]
        topic = session["topic"]
 
        # 3. Save candidate response in DB
        database.save_answer(session_id, question_number=question_count, answer=answer_text)
 
        # 4. Fetch agent checkpointers and submit answer
        agent = self._get_agent(session_id)
        try:
            # Check if candidate is asking a clarifying question rather than answering
            classification_prompt = f"Analyze the candidate's recent input: \"{answer_text}\"\nDoes this input primarily contain a question directed at the interviewer (e.g., asking for clarification, repeating the question, or asking about the company) instead of answering the interview question? Reply with exactly 'YES' or 'NO'."
            is_clarification_response = llm_service.invoke_stateless([{"role": "user", "content": classification_prompt}])
            is_clarification = "YES" in is_clarification_response.strip().upper()

            llm_service.invoke(agent, [{"role": "user", "content": answer_text}], session_id)
            
            if is_clarification:
                logger.info("Candidate asked a question. Answering and staying on question %d", question_count)
                clarification_prompt = prompt_builder.build_clarification_prompt(user_question=answer_text)
                next_question_text = llm_service.invoke(agent, [{"role": "user", "content": clarification_prompt}], session_id)
                
                # Save the new question state (overwrites the current question row in DB with the clarified version)
                database.save_question(session_id, question_number=question_count, question=next_question_text)
                
                return speech_service.stream_tts(next_question_text), {"X-Question-Number": str(question_count)}
     
            # 5. Determine next state: closing or next question
            if question_count >= total_questions:
                logger.info("Interview reached final question (%d/%d). Invoking closure...", question_count, total_questions)
                
                closing_prompt = prompt_builder.build_closing_prompt()
                closing_text = llm_service.invoke(agent, [{"role": "user", "content": closing_prompt}], session_id)
                
                # Update DB session - complete status
                database.complete_session(session_id)
                
                # Clean up active cache
                self.evict_session(session_id)
     
                logger.info("Session %s completed successfully.", session_id)
                return speech_service.stream_tts(closing_text), {"X-Interview-Complete": "true"}
            
            # Proceed to next question
            next_question_num = question_count + 1
            logger.info("Progressing to question %d...", next_question_num)
     
            if mode == "company":
                if next_question_num <= 6:
                    logger.info("Retrieving resume context for question %d...", next_question_num)
                    resume_context = knowledge_manager.retrieve_context(
                        session_id=session_id,
                        query="projects portfolio experience technologies " + answer_text,
                        company=session.get("company")
                    )
                    next_prompt = prompt_builder.build_resume_focused_prompt(
                        current_question_num=next_question_num,
                        previous_answer=answer_text,
                        retrieved_context=resume_context
                    )
                else:
                    logger.info("Retrieving JD context for question %d...", next_question_num)
                    jd_context = knowledge_manager.retrieve_context(
                        session_id=session_id,
                        query="job description role technical requirements skills " + answer_text,
                        company=session.get("company")
                    )
                    next_prompt = prompt_builder.build_jd_focused_prompt(
                        current_question_num=next_question_num,
                        previous_answer=answer_text,
                        retrieved_context=jd_context
                    )
            elif mode == "general":
                from fixed_questions import FIXED_QUESTIONS
                if topic in FIXED_QUESTIONS and next_question_num <= len(FIXED_QUESTIONS[topic]):
                    next_fixed = FIXED_QUESTIONS[topic][next_question_num - 1]
                    logger.info("Using fixed question %d for topic %s", next_question_num, topic)
                    next_prompt = prompt_builder.build_fixed_question_prompt(
                        current_question_num=next_question_num,
                        previous_answer=answer_text,
                        next_fixed_question=next_fixed
                    )
                else:
                    logger.info("Retrieving dynamic RAG context for question %d...", next_question_num)
                    retrieved_context = knowledge_manager.retrieve_context(
                        session_id=session_id, query=answer_text, company=session.get("company")
                    )
                    next_prompt = prompt_builder.build_next_question_prompt(
                        current_question_num=next_question_num, previous_answer=answer_text, retrieved_context=retrieved_context
                    )
            else:
                # Retrieve dynamic context for follow-up
                logger.info("Retrieving dynamic RAG context for question %d...", next_question_num)
                retrieved_context = knowledge_manager.retrieve_context(
                    session_id=session_id,
                    query=answer_text,
                    company=session.get("company")
                )
     
                next_prompt = prompt_builder.build_next_question_prompt(
                    current_question_num=next_question_num,
                    previous_answer=answer_text,
                    retrieved_context=retrieved_context
                )
                
            next_question_text = llm_service.invoke(agent, [{"role": "user", "content": next_prompt}], session_id)
            logger.info("Question %d generated: %s", next_question_num, next_question_text)
     
            # Save question and update counts in DB
            database.save_question(session_id, question_number=next_question_num, question=next_question_text)
            database.update_session_question_count(session_id, next_question_num)
     
            return speech_service.stream_tts(next_question_text), {"X-Question-Number": str(next_question_num)}
        except Exception as e:
            logger.error("LLM service totally failed after all fallbacks: %s", e)
            apology = "I sincerely apologize, but my servers are currently overwhelmed and I cannot process your answer right now. Please try again in a few moments."
            return speech_service.stream_tts(apology), {"X-Error-Fallback": "true"}
 
    def evict_session(self, session_id: str) -> None:
        """
        Evicts cached checkpointers from memory (useful on session completion or deletion).
        """
        if session_id in self._session_cache:
            del self._session_cache[session_id]
            logger.info("Evicted session agent checkpointers from memory: %s", session_id)
 
 
# Singleton instance
interview_engine = InterviewEngine()
