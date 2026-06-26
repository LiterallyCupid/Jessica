from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="sk_8736622f584dd2e3153fcf4777994a4c76f7251040e51acb")

audio = client.text_to_speech.convert(
    voice_id="cgSgspJ2msm6clMCkdW9",
    model_id="eleven_multilingual_v2",
    text="Welcome home sir. The time is ten forty-five PM. All systems are operational. Awaiting your command."
)

with open("brian.mp3", "wb") as f:
    for chunk in audio:
        f.write(chunk)

print("Saved brian.mp3")