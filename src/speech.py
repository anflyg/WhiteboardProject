"""
Text-to-speech helpers using pyttsx3 (offline).
"""
import pyttsx3


def speak(text: str) -> None:
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
