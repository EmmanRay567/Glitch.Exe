from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

output_file = Path("glitch_voice_test.wav").resolve()

print("Generating GLITCH voice...")

response = client.audio.speech.create(
    model="gpt-4o-mini-tts",
    voice="onyx",
    input="GLITCH dot E X E online. All systems operational.",
    instructions="""
Speak in a calm, polished, intelligent voice.

Use a medium-low register.
Sound futuristic and sophisticated.
Speak slowly and clearly.
Add a subtle synthetic character.
Do not imitate any existing fictional character.
""",
    response_format="wav"
)

response.write_to_file(
    output_file
)

print(f"Created: {output_file}")
print("Opening voice file...")

os.startfile(
    str(output_file)
)