from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Testing OpenAI TTS...")

response = client.audio.speech.create(
    model="tts-1",
    voice="alloy",
    input="This is a test of OpenAI text to speech."
)

with open("test_tts.mp3", 'wb') as f:
    f.write(response.content)

print("✅ Created test_tts.mp3")
