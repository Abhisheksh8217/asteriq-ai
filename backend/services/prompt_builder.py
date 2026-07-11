"""
services/prompt_builder.py
--------------------------
Handles all prompt templates and formatting.
Centralizes the logic for injecting RAG context, candidate info, and company profiles
into agent instructions.
"""

from typing import Optional
from config import TOTAL_QUESTIONS, INTERVIEWER_NAME


class PromptBuilder:
    """
    Constructs highly-structured system, question-generation, and feedback evaluation prompts.
    """

    def build_system_prompt(
        self,
        subject: str,
        company: Optional[str] = None,
        jd_context: Optional[str] = None,
        company_context: Optional[str] = None,
        candidate_name: str = "Candidate"
    ) -> str:
        """
        Builds the primary system prompt for the LangGraph agent conducting the interview.

        Injects retrieved RAG contexts if present.
        """
        prompt = f"You are {INTERVIEWER_NAME}, a friendly and conversational interviewer conducting a natural {subject} interview. You are interviewing {candidate_name}, so address them by name throughout the interview where appropriate.\n"
        
        if company:
            prompt += f"This interview is tailored for positions at {company}.\n"

        prompt += f"\nIMPORTANT GUIDELINES:\n"
        prompt += f"1. Ask exactly {TOTAL_QUESTIONS} questions total throughout the interview.\n"
        prompt += f"2. Keep questions SHORT and CRISP (1-2 sentences maximum).\n"
        prompt += f"3. ALWAYS reference what the candidate ACTUALLY said in their previous answer - do NOT make up or assume their answers.\n"
        prompt += f"4. Show genuine interest with brief acknowledgments based on their REAL responses.\n"
        prompt += f"5. Adapt questions based on their ACTUAL responses - go deeper if they're strong, adjust if uncertain.\n"
        prompt += f"6. Be warm and conversational but CONCISE.\n"
        prompt += f"7. No lengthy explanations - just ask clear, direct questions.\n"
        
        if jd_context:
            prompt += f"\nCANDIDATE / JOB DESCRIPTION CONTEXT (Use this to tailor your technical depth and focus):\n"
            prompt += f"{jd_context}\n"

        if company_context:
            prompt += f"\nCOMPANY CONTEXT (Align questions to these guidelines, products, or values):\n"
            prompt += f"{company_context}\n"

        prompt += (
            f"\nCRITICAL: Read the conversation history carefully. Only acknowledge what the candidate "
            f"truly said, not what you think they might have said.\n"
            f"Keep it short, conversational, and adaptive!"
        )
        return prompt

    def build_first_question_prompt(self, subject: str, candidate_name: str = "Candidate") -> str:
        """
        Starter prompt for the agent to open the interview.
        """
        return f"Start the interview with a warm greeting addressing the candidate {candidate_name} by name, and ask the first question about {subject}. Keep it SHORT (1-2 sentences)."

    def build_next_question_prompt(
        self,
        current_question_num: int,
        previous_answer: str,
        retrieved_context: Optional[str] = None
    ) -> str:
        """
        Constructs the instruction for evaluating the previous answer and asking the next question.
        Injects retrieved RAG context if available.
        """
        prompt = f"""The candidate just answered question {current_question_num - 1}.
Previous answer: "{previous_answer}"

Look at their ACTUAL answer above. Do NOT assume or make up what they said.
"""
        if retrieved_context:
            prompt += f"\nRELEVANT ROLE / COMPANY CONTEXT (Reference this knowledge if relevant to guide your next question):\n"
            prompt += f"{retrieved_context}\n"

        prompt += f"""
Now ask question {current_question_num} of {TOTAL_QUESTIONS}:
1. Briefly acknowledge what they ACTUALLY said (1 sentence) - quote or paraphrase their response if appropriate.
2. Ask your next question that builds on their REAL response (1-2 sentences).
3. If they said "I don't know", gave a wrong answer, or request clarification, acknowledge that gracefully and ask something simpler.
4. Keep the TOTAL response under 3 sentences.

Be conversational but CONCISE. Only reference what they truly said."""
        return prompt

    def build_fixed_question_prompt(
        self,
        current_question_num: int,
        previous_answer: str,
        next_fixed_question: str
    ) -> str:
        """
        Forces the agent to ask an exact, pre-defined question, while acknowledging the candidate's answer.
        """
        return f"""The candidate just answered question {current_question_num - 1}.
Previous answer: "{previous_answer}"

1. Briefly acknowledge their answer (1 sentence max).
2. You MUST ask the following exact question next. Do not change it or hallucinate context:
"{next_fixed_question}"

Keep your total response under 3 sentences."""

    def build_closing_prompt(self) -> str:
        """
        Instructs the agent to close the interview session.
        """
        return (
            f"That was the final ({TOTAL_QUESTIONS}th) question. First, briefly acknowledge their ACTUAL answer. "
            f"Then, appreciate their effort and specifically tell them: 'We have completed the {TOTAL_QUESTIONS} questions. "
            f"If you want more practice, explore other sessions as well. Thank you!'. "
            f"Do not ask any more questions."
        )

    def build_company_first_question_prompt(self, candidate_name: str = "Candidate", retrieved_context: Optional[str] = None) -> str:
        """
        Starter prompt for company-tailored interviews to dive directly into technical/resume questions.
        """
        prompt = f"""Start the interview with a warm greeting addressing the candidate {candidate_name} by name.
State exactly: "Welcome. We will directly dive into the technical part of the interview, skipping the introduction. You can practice that in the HR section."
Then, ask your first question focusing on their previous experience or a specific project from their resume. Keep the question SHORT (1-2 sentences)."""
        if retrieved_context:
            prompt += f"\n\nRESUME CONTEXT:\n{retrieved_context}"
        return prompt

    def build_resume_focused_prompt(self, current_question_num: int, previous_answer: str, retrieved_context: Optional[str] = None) -> str:
        """
        Prompt instructing the agent to ask questions strictly based on the candidate's resume/projects.
        """
        prompt = f"""The candidate just answered question {current_question_num - 1}.
Previous response: "{previous_answer}"

1. Briefly acknowledge what they ACTUALLY said (1 sentence max).
2. Ask question {current_question_num} of 10. This question MUST focus strictly on their past projects, internships, or experience from their resume.
3. Keep it warm, professional, and SHORT (1-2 sentences). Do not hallucinate.
"""
        if retrieved_context:
            prompt += f"\nRESUME / PROFILE CONTEXT:\n{retrieved_context}\n"
        return prompt

    def build_jd_focused_prompt(self, current_question_num: int, previous_answer: str, retrieved_context: Optional[str] = None) -> str:
        """
        Prompt instructing the agent to shift focus to the Job Description requirements.
        """
        prompt = f"""The candidate just answered question {current_question_num - 1}.
Previous response: "{previous_answer}"

1. Briefly acknowledge what they ACTUALLY said (1 sentence max).
2. Ask question {current_question_num} of 10. This question MUST focus purely on technical requirements, skills, or responsibilities mentioned in the Job Description.
"""
        if current_question_num == 7:
            prompt += "Since this is question 7, briefly transition the conversation by saying: 'Let's shift focus to some of the specific technical requirements for this role.'\n"
            
        prompt += """3. Keep it warm, professional, and SHORT (1-2 sentences). Do not hallucinate.
"""
        if retrieved_context:
            prompt += f"\nJOB DESCRIPTION CONTEXT:\n{retrieved_context}\n"
        return prompt

    def build_clarification_prompt(self, user_question: str) -> str:
        """
        Prompt instructing the agent to answer the candidate's clarifying question and gently steer back to the interview.
        """
        return f"""The candidate just asked a question or asked for clarification instead of answering the interview question.
Candidate's input: "{user_question}"

1. Directly and briefly answer their question or provide the clarification they need (1-2 sentences).
2. Politely steer the conversation back by repeating or rephrasing the original interview question you asked previously.
3. Keep it warm, professional, and SHORT.
"""

    def build_feedback_prompt(self, subject: str) -> str:
        """
        Constructs the instruction for grading the interview.
        """
        return f"""Based ONLY on our complete interview conversation history, provide detailed feedback as JSON.
CRITICAL: DO NOT hallucinate or evaluate the candidate on skills or topics they were never asked about. Base your scores and feedback STRICTLY on the actual conversation we just had. If a topic wasn't covered, do not penalize them for it.
Ensure the output matches this exact JSON schema:
{{
  "overall_score": <integer from 1 to 5>,
  "technical_score": <integer from 1 to 5>,
  "communication_score": <integer from 1 to 5>,
  "confidence_score": <integer from 1 to 5>,
  "company_fit_score": <integer from 1 to 5>,
  "strengths": ["<strength 1 with candidate quotes>", "<strength 2>"],
  "weaknesses": ["<gap 1 noticed>", "<gap 2>"],
  "recommended_topics": ["<topic 1 for study>", "<topic 2>"],
  "learning_path": ["<step 1 recommended>", "<step 2>"],
  "summary": "<a high-level summary of their overall performance>"
}}
Be specific - reference ACTUAL things they said during the interview. Return ONLY the JSON object. Do not include markdown code block formatting like ```json."""


# Singleton instance
prompt_builder = PromptBuilder()

