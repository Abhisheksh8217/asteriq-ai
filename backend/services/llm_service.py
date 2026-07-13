"""
services/llm_service.py
-----------------------
Gemini LLM wrapper service.

Designed as a replaceable abstraction — if the provider changes
(e.g., OpenAI, Anthropic, local Ollama), only this file changes.
All other services depend on LLMService, not on LangChain directly.

Responsibilities:
  - Initialize and cache the LLM model
  - Create LangGraph agents with InMemorySaver
  - Invoke agents with message history
  - Handle Gemini-specific errors gracefully
"""

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
from config import LLM_FULL_MODEL, GOOGLE_API_KEYS
from logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    Wraps the Gemini LLM and LangGraph agent lifecycle.

    A single LLMService instance is shared across the app.
    Each interview session gets its own agent + checkpointer
    created via create_session_agent().
    """

    def __init__(self):
        self._model = None
        self._current_model_name = LLM_FULL_MODEL
        self._current_api_key = GOOGLE_API_KEYS[0] if GOOGLE_API_KEYS else ""
        self._initialize_model(self._current_model_name, self._current_api_key)

    def _initialize_model(self, model_name: str, api_key: str = None) -> None:
        """Initializes the specified Gemini model."""
        if api_key is None:
            api_key = GOOGLE_API_KEYS[0] if GOOGLE_API_KEYS else ""
        try:
            self._model = init_chat_model(
                model_name,
                api_key=api_key,
                max_retries=0
            )
            self._current_model_name = model_name
            self._current_api_key = api_key
            logger.info("LLM model initialized: %s", model_name)
        except Exception as e:
            logger.error("Failed to initialize LLM model %s: %s", model_name, e, exc_info=True)
            raise

    @property
    def model(self):
        """Returns the initialized LLM model."""
        if self._model is None:
            self._initialize_model(self._current_model_name, self._current_api_key)
        return self._model

    def create_session_agent(self) -> tuple:
        """
        Creates a new LangGraph agent + InMemorySaver for a session.

        Each session must have its own agent and checkpointer to ensure
        conversation memory is fully isolated between sessions.

        Returns:
            Tuple of (agent, checkpointer) for the session.
        """
        checkpointer = InMemorySaver()
        agent = create_agent(
            model=self.model,
            tools=[],
            checkpointer=checkpointer
        )
        logger.info("New session agent created.")
        return agent, checkpointer

    def invoke(self, agent, messages: list, thread_id: str) -> str:
        """
        Invokes the LangGraph agent with a list of messages.
        Supports automatic model fallback switching if rate limits (429) are encountered.

        Args:
            agent: The LangGraph agent for this session.
            messages: List of message dicts with 'role' and 'content'.
            thread_id: LangGraph thread ID for conversation continuity.

        Returns:
            The last message content from the agent response.

        Raises:
            RuntimeError: If the LLM call fails.
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            response = agent.invoke({"messages": messages}, config=config)
            raw_content = response["messages"][-1].content
            if isinstance(raw_content, list):
                extracted = []
                for item in raw_content:
                    if isinstance(item, dict) and "text" in item:
                        extracted.append(str(item["text"]))
                    elif isinstance(item, str):
                        extracted.append(item)
                    else:
                        extracted.append(str(item))
                content = "".join(extracted)
            else:
                content = str(raw_content)
                
            logger.debug("LLM response received (%d chars)", len(content))
            return content
        except Exception as e:
            err_str = str(e).lower()
            # Intercept 429/503 rate limits, 404 not found (e.g. for new keys), temporary overloads, or service unavailability
            if any(term in err_str for term in ["429", "503", "500", "502", "504", "404", "not_found", "not found", "resource_exhausted", "rate_limit", "rate limit", "unavailable", "high demand", "temporary"]):
                logger.warning("Primary model (%s) encountered API service error, rate limit, or model availability issue. Activating auto-fallback model/key switching...", self._current_model_name)
                
                # List of model fallbacks (using standard Google API Studio model names)
                fallback_models = [
                    "google_genai:gemini-2.5-flash",
                    "google_genai:gemini-3.5-flash",
                    "google_genai:gemini-2.0-flash",
                ]
                
                # Generate a flat list of (model, api_key) pairs to try
                fallback_combinations = []
                for m in fallback_models:
                    for k in GOOGLE_API_KEYS:
                        fallback_combinations.append((m, k))
                
                current_combo = (self._current_model_name, getattr(self, '_current_api_key', ''))
                try:
                    current_idx = fallback_combinations.index(current_combo)
                except ValueError:
                    current_idx = -1
                
                # Try each fallback combination sequentially
                for idx in range(current_idx + 1, len(fallback_combinations)):
                    fallback_model, fallback_key = fallback_combinations[idx]
                    logger.info("Attempting to switch to fallback model: %s with alternate key", fallback_model)
                    
                    try:
                        # Reinitialize internal model reference
                        self._initialize_model(fallback_model, api_key=fallback_key)
                        
                        # Get checkpointer from old agent to preserve conversation context memory
                        checkpointer = getattr(agent, "checkpointer", None)
                        if not checkpointer:
                            checkpointer = InMemorySaver()
                        
                        # Recompile agent with new fallback model
                        new_agent = create_agent(
                            model=self.model,
                            tools=[],
                            checkpointer=checkpointer
                        )
                        
                        # Retry invocation with the new model
                        logger.info("Retrying LLM invocation with fallback model: %s", fallback_model)
                        response = new_agent.invoke({"messages": messages}, config=config)
                        content = response["messages"][-1].content
                        logger.info("Successfully recovered using fallback model %s!", fallback_model)
                        
                        # Update cached agent in interview engine so all subsequent turns use the new agent
                        from services.interview_engine import interview_engine
                        if thread_id in interview_engine._session_cache:
                            interview_engine._session_cache[thread_id] = (new_agent, checkpointer)
                            
                        return content
                    except Exception as fallback_err:
                        logger.error("Fallback attempt with model %s failed: %s", fallback_model, fallback_err)
                        continue
            
            # Re-raise original error if fallback was not triggered or all attempts failed
            logger.error("LLM invocation failed: %s", e, exc_info=True)
            raise RuntimeError(f"LLM service error: {e}") from e

    def invoke_stateless(self, messages: list) -> str:
        """
        Invokes the LLM model directly without a LangGraph agent or checkpointer.
        Supports automatic key fallback switching if rate limits (429) are encountered.
        """
        try:
            from langchain_core.messages import HumanMessage
            formatted_messages = [HumanMessage(content=m["content"]) for m in messages if m["role"] == "user"]
            response = self.model.invoke(formatted_messages)

            if isinstance(response.content, list):
                content = "".join([str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in response.content])
            else:
                content = str(response.content)
            return content
        except Exception as e:
            err_str = str(e).lower()
            if any(term in err_str for term in ["429", "503", "500", "502", "504", "404", "not_found", "not found", "resource_exhausted", "rate_limit", "rate limit", "unavailable", "high demand", "temporary"]):
                logger.warning("Stateless model encountered API error, rate limit, or model availability issue. Attempting auto-fallback key switching...")
                
                # Try each API key in the list sequentially
                for fallback_key in GOOGLE_API_KEYS:
                    if fallback_key == self._current_api_key:
                        continue
                    logger.info("Attempting stateless switch to alternate key...")
                    try:
                        self._initialize_model(self._current_model_name, api_key=fallback_key)
                        from langchain_core.messages import HumanMessage
                        formatted_messages = [HumanMessage(content=m["content"]) for m in messages if m["role"] == "user"]
                        response = self.model.invoke(formatted_messages)

                        if isinstance(response.content, list):
                            content = "".join([str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in response.content])
                        else:
                            content = str(response.content)
                        logger.info("Stateless invocation successfully recovered using alternate key!")
                        return content
                    except Exception as fallback_err:
                        logger.error("Stateless fallback attempt failed: %s", fallback_err)
                        continue

            logger.error("Stateless LLM invocation failed: %s", e, exc_info=True)
            return ""


# Singleton instance
llm_service = LLMService()
