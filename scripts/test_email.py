import sys
import os
from dotenv import load_dotenv

# Add project root to python path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env variables
load_dotenv()

from app.services.email import EmailService

def test_email():
    destination = "reubrechtj@gmail.com" # Votre email
    print(f"Tentative d'envoi d'email à {destination}...")
    
    service = EmailService()
    success = service.send_verification_email(destination, "token-de-test-uuid")
    
    if success:
        print("✅ Email envoyé avec succès ! Vérifiez votre boîte de réception (et spams).")
    else:
        print("❌ Échec de l'envoi. Vérifiez les logs ci-dessus.")

if __name__ == "__main__":
    test_email()
