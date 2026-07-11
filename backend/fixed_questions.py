"""
fixed_questions.py
------------------
Contains the fixed, hardcoded top 5 questions for each General Prep subject.
"""

FIXED_QUESTIONS = {
    "HR Interview": [
        "To kick things off, could you please introduce yourself and give me a brief overview of your background?",
        "What would you say are your greatest strengths, and what is one area you are actively working to improve?",
        "Can you describe a specific time when you faced a difficult challenge at work and how you handled it?",
        "Where do you see your career heading in the next three to five years?",
        "Finally, why do you want to work for our company, and what unique value do you bring to the team?"
    ],
    "Gen AI": [
        "Welcome! Could you start by explaining what Generative AI is and how it differs from traditional machine learning?",
        "What are Large Language Models (LLMs), and can you briefly explain the concept of attention mechanisms in Transformers?",
        "Can you describe what RAG (Retrieval-Augmented Generation) is and why it's useful for building AI applications?",
        "What are some common challenges or limitations of Generative AI models, such as hallucinations or bias?",
        "How would you approach designing a scalable and secure architecture for deploying a Generative AI application?"
    ],
    "Python": [
        "Welcome! To start, could you explain the key differences between lists and tuples in Python?",
        "How does memory management and garbage collection work in Python?",
        "Can you explain what decorators are in Python and provide an example of when you would use one?",
        "What is the difference between multithreading and multiprocessing in Python, particularly regarding the GIL?",
        "How do generators work in Python, and when would you choose to use them over standard functions?"
    ],
    "OOP": [
        "Welcome! Could you briefly explain the four main pillars of Object-Oriented Programming?",
        "What is the difference between an abstract class and an interface?",
        "Can you explain the concept of method overloading versus method overriding?",
        "What is encapsulation, and why is it important in software design?",
        "Could you explain the SOLID principles and how they help in building maintainable software?"
    ],
    "DBMS": [
        "Welcome! To start, could you explain the primary differences between SQL and NoSQL databases?",
        "What are ACID properties in the context of database transactions?",
        "Can you explain what database normalization is and why it's important?",
        "What are indexes, how do they improve database performance, and what are their drawbacks?",
        "Could you explain the difference between a clustered and a non-clustered index?"
    ]
}
