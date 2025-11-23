# Whiteboard Assist (prototype)

Mål: hjälp en elev med synnedsättning att se whiteboarden genom webbkamera med perspektivkorrigering, zoom och OCR/TTS.

## Körning (lokalt)
```
pip install -r Requirements.txt
python -m src.main
```

## Struktur
- `src/main.py`: startar kameraloop, visar fönster.
- `src/capture.py`: initierar kamera.
- `src/keystone.py`: perspektivkorrigering (keystone).
- `src/zoom.py`: pan/zoom-logik.
- `src/text_detect.py`: OCR och textboxar via pytesseract.
- `src/speech.py`: text-till-tal (pyttsx3).

## Nästa steg
- Lägg till tangent-/muskontroller för zoom/pan i `main.py`.
- Implementera hörnval + `warpPerspective` i `keystone.py` kopplat till UI.
- Färglägg textregioner från `text_detect.py` och auto-zoom dit.
- Koppla OCR-text till `speech.speak` för uppläsning.
