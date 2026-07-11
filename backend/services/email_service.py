"""
services/email_service.py
-------------------------
Handles compiling and sending welcome emails to newly registered candidates.
Includes safe log fallback if SMTP configuration is not present in .env.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_USER, SMTP_PASSWORD
from logger import get_logger

logger = get_logger(__name__)

class EmailService:
    """
    Handles sending welcome emails containing platform guidebooks.
    """

    def get_welcome_html(self, email: str) -> str:
        """
        Generates a premium, responsive dark-themed HTML welcome email template.
        """
        import database
        profile = database.get_user(email)
        name_display = profile.get("name") if profile and profile.get("name") else email.split("@")[0].capitalize()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Welcome to ASTERIQ AI</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #09090b;
                    color: #f4f4f5;
                    margin: 0;
                    padding: 0;
                }}
                .email-container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background-color: #18181b;
                    border: 1px solid #27272a;
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 800;
                    letter-spacing: -0.5px;
                    color: #ffffff;
                }}
                .content {{
                    padding: 30px 40px;
                    line-height: 1.6;
                }}
                .welcome-text {{
                    font-size: 18px;
                    color: #e4e4e7;
                    margin-bottom: 24px;
                }}
                .feature-box {{
                    background-color: #09090b;
                    border: 1px solid #27272a;
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 20px;
                }}
                .feature-title {{
                    font-weight: 700;
                    color: #a78bfa;
                    margin-bottom: 8px;
                    font-size: 15px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .feature-desc {{
                    margin: 0;
                    font-size: 14px;
                    color: #a1a1aa;
                }}
                .steps-list {{
                    margin: 20px 0;
                    padding-left: 20px;
                    color: #d4d4d8;
                }}
                .steps-list li {{
                    margin-bottom: 12px;
                    font-size: 14px;
                }}
                .footer {{
                    background-color: #09090b;
                    padding: 24px;
                    text-align: center;
                    font-size: 12px;
                    color: #71717a;
                    border-top: 1px solid #27272a;
                }}
                .btn {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: #ffffff;
                    text-decoration: none;
                    font-weight: 600;
                    padding: 12px 30px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>Welcome to ASTERIQ AI</h1>
                </div>
                <div class="content">
                    <p class="welcome-text">Hi {name_display},</p>
                    <p>Thank you for registering with <strong>ASTERIQ AI</strong>, your tailored speech-driven conversational interview assistant. ANZ is designed to simulate authentic corporate interview settings and prepare you for any subject or specific target company role.</p>
                    
                    <h3 style="color: #e4e4e7; margin-top: 30px;">Core Platform Features</h3>
                    
                    <div class="feature-box">
                        <div class="feature-title">🎙️ Speech-Based Dialogues</div>
                        <div class="feature-desc">ANZ speaks directly to you. Reply using your microphone and experience natural, adaptive follow-up responses based on your actual answers.</div>
                    </div>
                    
                    <div class="feature-box">
                        <div class="feature-title">📄 Resume & JD Integration</div>
                        <div class="feature-desc">Upload job descriptions or resume PDFs. The RAG knowledge base automatically reads your profile, tailoring ANZ's technical questions and expectations to your stack.</div>
                    </div>

                    <div class="feature-box">
                        <div class="feature-title">📊 Instant Performance Feedback</div>
                        <div class="feature-desc">Receive immediate, detailed grading cards showing communication, confidence, technical, and company alignment scores alongside customized learning roadmaps.</div>
                    </div>

                    <h3 style="color: #e4e4e7; margin-top: 30px;">How It Works (3 Quick Steps)</h3>
                    <ul class="steps-list">
                        <li><strong>Step 1</strong>: Select your interview mode (General Prep or Company Tailored).</li>
                        <li><strong>Step 2</strong>: Pick your technical subject (Python, Generative AI, HTML, CSS, etc.) or upload your resume PDF.</li>
                        <li><strong>Step 3</strong>: Click "Start Interview" and ANZ will speak her opening question. Click Record to respond!</li>
                    </ul>

                    <p style="margin-top: 30px;">Best of luck with your preparation!</p>
                    <p><strong>— The ASTERIQ AI Team</strong></p>
                </div>
                <div class="footer">
                    <p>ASTERIQ AI Interview Assistant • 100% Secure Local Deployment</p>
                </div>
            </div>
        </body>
        </html>
        """

    def send_welcome_email(self, to_email: str) -> bool:
        """
        Sends the welcome email to the specified recipient.
        Falls back gracefully to logging to console if SMTP credentials are missing.
        """
        html_content = self.get_welcome_html(to_email)
        subject = "Welcome to ASTERIQ AI Interviewer!"

        # Fallback to local logs if credentials are missing
        if not SMTP_EMAIL or not SMTP_PASSWORD:
            logger.info("=" * 60)
            logger.info("WELCOME EMAIL SIMULATION (SMTP credentials missing in .env)")
            logger.info("Sent To: %s", to_email)
            logger.info("Subject: %s", subject)
            logger.info("HTML Body Size: %d characters", len(html_content))
            logger.info("-" * 60)
            logger.info("Logged Email Template Preview:")
            logger.info(html_content)
            logger.info("=" * 60)
            return True

        try:
            logger.info("Connecting to SMTP server %s:%d...", SMTP_SERVER, SMTP_PORT)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_EMAIL
            msg["To"] = to_email

            part_html = MIMEText(html_content, "html")
            msg.attach(part_html)

            # Establish secure connection
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            
            # Send message
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
            server.quit()
            
            logger.info("Welcome email successfully sent via SMTP to: %s", to_email)
            return True
        except Exception as e:
            logger.error("Failed to send welcome email via SMTP: %s. Logging content to console...", e)
            # Log as fallback to ensure registration still succeeds
            logger.info("Welcome Email Content for %s:\n%s", to_email, html_content)
            return False


# Singleton instance
email_service = EmailService()
