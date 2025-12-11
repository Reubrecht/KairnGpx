import os
import google.generativeai as genai

def load_env():
    if os.path.exists("local.env"):
        print("Reading local.env...")
        with open("local.env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
                    if key == "GEMINI_API_KEY":
                        print("Found GEMINI_API_KEY in local.env")
    else:
        print("local.env not found!")

def test_key():
    load_env()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in environment variables.")
        return

    print(f"Testing API Key: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello, can you confirm you are working?")
        print("\n--- SUCCESS ---")
        print(f"Response from Gemini: {response.text}")
    except Exception as e:
        print("\n--- FAILURE ---")
        print(f"Error testing Gemini API Key: {e}")

if __name__ == "__main__":
    test_key()
