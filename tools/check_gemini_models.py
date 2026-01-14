import google.generativeai as genai
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
project_root = Path(__file__).parent.parent.resolve()
load_dotenv(project_root / '.env')

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY or GEMINI_API_KEY not found in environment.")
    exit(1)

genai.configure(api_key=api_key)

print(f"Checking models with API key: {api_key[:5]}...")
print("\nAvailable Gemini Models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name} ({m.display_name})")
except Exception as e:
    print(f"Error listing models: {e}")
