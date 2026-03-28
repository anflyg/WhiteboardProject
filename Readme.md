# Whiteboard Assist (Qt)

Ett enkelt verktyg för att se en whiteboard via webbkamera. Stöd för zoom, pan, keystone med hörnpunkter samt kamerabyte via menyrad. GUI:t är byggt med PySide6 så att menyraden fungerar både på macOS och Windows.

## Arkitektur (MVC-inspirerad)
- **Model:** `AppState` (`src/state.py`) håller zoom/pan, keystone, valda hörn, hjälp-overlay, aktiva/tillgängliga kameror.
- **Controller:** `WhiteboardWindow` (`src/app.py`) kopplar menyval, shortcuts och mus till state och kamerabyte. Återanvänder `on_mouse` för keystone-klick.
- **View:** Qt-fönstret + `VideoLabel` visar bilden som QImage/QPixmap. Överlagringsgrafiken (hjälptext, hörnmarkörer) ritas med OpenCV-funktioner i `src/overlay.py`.
- **Bildbehandling:** `apply_keystone` (`src/keystone.py`) och `crop_zoom` (`src/zoom.py`) manipulerar varje frame innan visning. `src/capture.py` hanterar öppning och uppräkning av kameror.

## Installation
```bash
pip install -r Requirements.txt
```
Kräver PySide6 och OpenCV med GUI-stöd (inte `opencv-python-headless`).

Systemkrav:
- `ffmpeg` behövs för Whisper-transkription (installera t.ex. `brew install ffmpeg` på macOS eller motsvarande på Windows/Linux).

### Whisper utan nedladdning
- Standardprofilen är `recommended` och använder Whisper `turbo`.
- Lägg din nedladdade modellfil (t.ex. `turbo.pt` eller `turbo.pt.bin`) i en mapp `whisper_models/` bredvid projektet, eller peka ut filen med `WHISPER_MODEL_PATH=/full/path/till/turbo.pt`.
- Alternativt kan du sätta `WHISPER_MODEL_DIR` till en katalog som innehåller modellen.
- Om ingen lokal fil hittas försöker Whisper annars ladda ner modellen, vilket kan misslyckas utan rätt certifikat/nät.

### Körprofiler (AI-pipeline)
- `quick`: lätt/snabbläge (Whisper `tiny`).
- `recommended` (default): balanserat standardläge (Whisper `turbo`).
- `full_local`: tyngre lokal kvalitet (Whisper `large`).

## Kör
```bash
python src/main.py            # starta med default-kamera (index 0)
python src/main.py -c 1       # starta med kamera 1
python src/main.py --list-cameras  # lista tillgängliga kameror och avsluta
```

## Menyer och genvägar
- **Menyrad**
  - Camera: byt kamera, uppdatera lista.
  - View: zoom in/ut, återställ vy, toggle hjälp-overlay.
  - Keystone: toggle/reset keystone, starta hörnläge, nudga/markera hörn.
  - Help: visa hjälp-overlay, avsluta.
- **Shortcuts (fungera parallellt):**
  - `+ / -` zooma in/ut
  - `piltangenter` eller `WASD` pan
  - `0` reset vy
  - `h` toggle hjälp-overlay
  - `t` toggle keystone, `r` reset keystone
  - `m` starta hörnläge (klicka 4 hörn)
  - `1-4` välj hörn, `i/j/k/l` nudga valt hörn
  - `q` avsluta

## Flöde per frame
1. Läs frame från aktiv `cv2.VideoCapture`.
2. Perspektivkorrigera om keystone är på (`apply_keystone`).
3. Zooma/pana (`crop_zoom`).
4. Rita hjälp-overlay och hörnmarkörer (OpenCV).
5. Konvertera BGR → RGB → `QImage` → `QPixmap` och visa i `VideoLabel`.

## Vidareutveckling
- Lägg till TTS/OCR (pytesseract/easyocr) i separata moduler.
- Lägga till fler menyer/verktygsfält i Qt utan att röra bildpipeline.
- Auto-följ text via rörelsedetektering eller OCR-bounding-boxar. 

## Samlad dokumentation
Se `docs/overview.md` för en sammanhängande beskrivning av app + AI-pipeline och UML-översikt.
För macOS/Qt-startproblem (cocoa-plugin) se `docs/qt_troubleshooting.md`.
