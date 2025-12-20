import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

class EmailService:
    def __init__(self):
        # Default to Brevo SMTP host
        self.smtp_host = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", "no-reply@kairn.app")
        self.sender_name = "MyKairn"
        # Ensure base_url doesn't have a trailing slash
        self.base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip('/')

    def _get_html_template(self, title: str, body_content: str, action_url: str = None, action_text: str = None) -> str:
        """
        Returns a beautiful HTML template wrapper with MyKairn branding.
        """
        action_button = ""
        if action_url and action_text:
            action_button = f"""
            <div style="text-align: center; margin: 30px 0;">
                <a href="{action_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; font-family: sans-serif;">{action_text}</a>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #334155; bg-color: #f8fafc; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
                <!-- Header -->
                <div style="background-color: #0f172a; padding: 24px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: -1px;">
                        <span style="color: #3b82f6;">⚡</span> MyKairn
                    </h1>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 24px;">
                    <h2 style="color: #0f172a; font-size: 20px; font-weight: 700; margin-top: 0; margin-bottom: 16px;">
                        {title}
                    </h2>
                    
                    <div style="color: #475569; font-size: 16px;">
                        {body_content}
                    </div>
                    
                    {action_button}
                    
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;">
                    
                    <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">
                        © {os.getenv('YEAR', '2025')} MyKairn. Tous droits réservés.<br>
                        Vous recevez cet email car vous êtes inscrit sur notre plateforme.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def send_email(self, to_email: str, subject: str, html_content: str):
        """
        Generic method to send any email.
        """
        # In development/if no creds, just log it
        if not self.smtp_user or not self.smtp_password:
            logging.warning("SMTP credentials not set. Mocking email send.")
            print(f"------------ MOCK EMAIL ------------")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"Body: {html_content[:100]}...")
            print(f"------------------------------------")
            return True

        msg = MIMEMultipart()
        msg['From'] = f"{self.sender_name} <{self.from_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            logging.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logging.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_verification_email(self, to_email: str, token: str):
        """
        Sends a verification email to the user using the generic sender.
        """
        verification_link = f"{self.base_url}/verify-email?token={token}"
        
        body = f"""
        <p>Merci de vous être inscrit sur <strong>MyKairn</strong> !</p>
        <p>Pour activer pleinement votre compte et accéder à toutes les fonctionnalités, veuillez confirmer votre adresse email en cliquant sur le bouton ci-dessous.</p>
        <p style="margin-top: 20px;">Si le bouton ne fonctionne pas, copiez ce lien :<br>
        <a href="{verification_link}" style="color: #2563eb; word-break: break-all;">{verification_link}</a></p>
        """
        
        html = self._get_html_template(
            title="Bienvenue ! Vérifiez votre compte",
            body_content=body,
            action_url=verification_link,
            action_text="Vérifier mon email"
        )
        
        return self.send_email(to_email, "Vérifiez votre compte MyKairn", html)
