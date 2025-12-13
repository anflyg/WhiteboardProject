# Whiteboard AI-pipeline – design och krav

## Målbild
- Kombinera transkription av föreläsningen med innehållet på whiteboarden i ett leverabelt dokument (Markdown → PDF/HTML).
- Hantera 30–60 min video med robusthet mot brus, occlusioner (lärare som skymmer) och successiva ändringar på tavlan (små justeringar, sudda/skriva om).
- Separera text/handstil/matte från ritade bilder och inkludera båda i resultatet.

## Övergripande beslut
- **Separat AI-paket:** Ett eget paket `src/ai_pipeline/` kapslar all hantering av ljud, tavelframes, OCR/vision, matte, segmentering och alignering. Övriga app-komponenter (UI, I/O) anropar paketet via tydliga gränssnitt.
- **Hybrid bildanalys:** Adaptiv frame-extraktion (förändringsdetektion via SSIM/delta) + fallback på fast intervall för att inte missa långsamma ändringar.
- **Regional state-tracking:** Tavlan delas i tiles; varje tile får versioner över tid så vi kan hantera små ändringar och omskrivningar utan att OCR:a hela tavlan varje gång.
- **Occlusion-tålighet:** Person-/huvudmask på varje frame för att blockera OCR när tavlan är skymd; tvingad keyframe när masken försvinner.
- **Matte/handstil:** Pluggbar modellstrategi: lokalt/offline där möjligt, men med möjlighet att skicka osäkra regioner till en kraftfull vision-/math-modell.

## Funktionella krav
- Transkribera tal med tidsstämplar.
- Extrahera och OCR:a tavlans text/handstil och identifiera matematiska uttryck.
- Segmentera ritblock (bilder/figurer) och spara dessa som bilder med tidsstämplar.
- Hantera occlusioner: hoppa över skymda frames och uppdatera när tavlan syns igen.
- Hantera små ändringar och omskrivningar per region; versionera per tile med tidsstämplar.
- Hantera raderingar: upptäck wipe och behandla efterföljande innehåll som ny version.
- Sammanfoga transkription + tavlainnehåll tidsmässigt och exportera dokument.

## Icke-funktionella krav
- Skala till 30–60 min video utan orimlig OCR-kostnad (adaptiv sampling, tile-baserad OCR).
- Robust mot brus (ljud- och bildförbättring).
- Utbyggbart: nya modeller ska kunna bytas utan att påverka pipeline-orchestreringen.

## Paketstruktur (ny)
```
src/ai_pipeline/
  __init__.py
  audio.py          # Ljudextraktion, brusreducering, transkription (Whisper/annat).
  frames.py         # Frame-extraktion, SSIM/delta, occlusionmask, keyframe-logik.
  board_state.py    # Tile-state, versionering, wipe-detektion, stabiliseringsfönster.
  vision.py         # Text/handstil/matte-OCR + ritblocksegmentering, pluggbar backend (lokal/remote).
  align.py          # Synka transkriptsegment med tavlans state över tid.
  export.py         # Bygg Markdown/HTML och bädda in bilder + text.
  config.py         # Modellval, trösklar, intervall, paths.
```

## Designbeslut och motivering
- **Adaptiv sampling + fallback**: SSIM/delta detekterar förändring; fallback var 20–30 s så långsamma eller ljusa ändringar inte missas. Reducerar OCR-kostnad jämfört med 2–3 s fast sampling.
- **Tile-baserad state**: Vi uppdaterar bara regioner som faktiskt ändras, vilket minskar OCR-belastning och hanterar små justeringar under skrivande.
- **Stabiliseringsfönster (t.ex. 0.5–1 s utan förändring)**: Förhindrar OCR på halvskrivna ord eller pågående suddningar.
- **Occlusionmask**: Person-segmentation (lätt modell) markerar skymda områden. Frames med hög mask-andel flaggas och hoppar över OCR. När masken försvinner tvingas ny keyframe.
- **Wipe-detektion**: Kraftig ökning av ljusa pixlar och rörelse i en tile → markera som rensad; efterföljande stabila innehåll sparas som ny version.
- **Pluggbar vision-backend**: `vision.py` exponerar ett gränssnitt; backend kan vara lokalt (`nougat`, `pix2tex`, `tesseract` med handskriftsmodell) eller API (MathPix/GPT-4o mini). Osäkra regioner kan eskaleras till starkare modell.
- **Mattehantering**: Matteblock skickas till modell som kan producera LaTeX; övrig text körs i handskrifts-OCR. Behåller ritblock som bilder och lägger LaTeX/text separat.
- **Export**: Markdown + referenser till sparade ritbilder; kan renderas till PDF. Topp-sammanfattning kan genereras via språkmodell om tillgänglig.

## Modellstrategi (lokal först, cloud-senare)
- Primär körning: lokala modeller (open source) för transkription (Whisper lokalt), handstil/matte (`nougat`, `pix2tex`, ev. Tesseract-handstil). Inga licensavgifter, kräver GPU/CPU.
- Modularitet: `vision.py` och `audio.py` definierar ett backend-API (t.ex. `Transcriber`, `BoardRecognizer`) med enhetliga svar: text + osäkerhet/konfidens + ev. LaTeX. Lokala backends implementerar detta interface.
- Uppgradering: Nya lokala modeller kan ersätta befintliga backends utan att ändra övrig pipeline.
- Cloud-plugg: Lägg till en `remote`-backend som använder OpenAI/MathPix via samma interface. `config.py` styr prioritet: försök lokal, fall back till cloud, eller hybrid (skicka endast låg-konfidens regioner).
- Säkerhetsventil: Cloud-stöd kan hållas avstängt tills API-nycklar finns; togglas i konfig.
- Lokalmodell för tal: Whisper `small` (ca 466 MB) som standard, klarar svenska/engelska. Läggs lokalt (t.ex. `WHISPER_MODEL_DIR`) så ingen nätåtkomst krävs vid körning. Högre kvalitet: `medium` (~1.4 GB) eller `large` (~3 GB) kan väljas i config vid bättre hårdvara.

## Körningsprofiler och prestanda (lokal laptop, macOS/Windows)
- Quick mode (live): Whisper medium/small (CPU/Apple Silicon), enkel handskriftsmodell, adaptiv sampling (SSIM/delta), glest fallback (20–30 s), tile-uppdatering endast vid förändring, nedskalad tavla/ROI. Syfte: körbar på MacBook Air/Windows-laptop utan kraftig GPU.
- Full mode (offline): Tyngre modeller (Whisper large eller större handskrifts/matte), körs efter inspelning. Samma pipeline men högre OCR-kvalitet och tätare sampling kan aktiveras.
- Acceleration: Använd fp16/int8 där stöd finns (Metal/CoreML på Apple Silicon; CUDA om Nvidia finns). På Windows utan GPU håll modeller små.
- Resursstyrning via config: trösklar för SSIM, tile-grid, stabiliseringsfönster, fallback-intervall, modellval och max samtidiga OCR-jobb. Gör det möjligt att skruva ned kraven på svagare maskin.
- Minimal lokalkrav: ffmpeg för dekodning, SSIM/delta i CPU går snabbt på nedskalade frames; OCR körs bara på ändrade tiles för att spara CPU.

## Inspelning, postprocessing och städning
- Sessionsmappar: råmaterial (ljud, keyframes, manifest) sparas under `captures/run-<timestamp>/` så att postprocessing kan köras efter stopp och återupptas vid krasch.
- Postprocessing-trigger: startar när användaren stoppar inspelningen. Ordning: 1) flush/stäng inspelning, 2) transkribera ljud, 3) OCR/vision på keyframes/tiles, 4) align, 5) generera Markdown/PDF.
- Städpolicy: när PDF/MD är producerad och verifierad, rensa sessionens temporära filer (ljud, frames). Behåll endast slutdokument och ev. logg. Config-flagga `keep_intermediates` kan styra om man vill behålla rådata.
- Tidsåtgång postprocessing (estimat): Quick mode på MacBook Air/CPU med Whisper medium och adaptiv sampling ~0.5–1.5× realtid för 30–60 min ljud. Vision/OCR tillkommer (några minuter för 300–600 keyframes/timme med lätta modeller). Fullmode med tyngre modeller tar längre.
- Robusthet: skriv manifest och delresultat inkrementellt (JSON/logg) så att en krasch/batteridöd inte förlorar allt. Vid uppstart kan användaren välja att återuppta/efterbearbeta en ofullständig session. Rensa inte pågående sessionsfiler förrän postprocessing är klar och PDF finns.
- Feedback: UI visar inspelningstid, antal sparade keyframes, och progress för postprocessing.

## Tidsstämplingsstrategi
- Keyframes vid SSIM-underskridande (t.ex. 0.97) mellan nedskalade frames.
- Fallback-keyframe var 20–30 s om ingen förändring detekteras.
- Efter occlusion: tvingad keyframe.
- Versionering per tile: varje stabilt läge sparas med `t_start, t_end`. Raderade tiles får ny version när nytt innehåll uppstår.

## Datatyper (skiss)
- Transkription: lista av `{start, end, text}`.
- Frame-event: `{ts, keyframe_path, occluded: bool}`.
- Tile-version: `{tile_id, start, end, text?, latex?, image_path?}`.
- Align-block: `{start, end, speech_text, board_text[], board_images[]}`.

## Nästa steg
- Skapa `src/ai_pipeline/` med stubbar enligt ovan och koppla in minimal pipeline från `main.py`.
- Välja initial backend (t.ex. Whisper + enkel handskrifts-OCR) och sätta rimliga default-trösklar för SSIM, tile-grid, stabiliseringsfönster.

## Driftsnoteringar (Qt/venv, macOS + Homebrew Python 3.12)
- Använd alltid projektets venv: `source .venv/bin/activate`. Venv är byggd med `/opt/homebrew/bin/python3.12`.
- Kör appen via VS Code-launchen “Whiteboard (PySide6)” eller via `./run.sh`. Båda sätter QT/DYLD-paths till venv:ets PySide6 (inte Homebrew-globala).
- Om Cocoa-plugin-fel återkommer: rensa QT_* och DYLD_* i terminalen, sedan kör `./run.sh` eller sätt env manuellt:
  ```
  unset QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH QT_QPA_PLATFORM DYLD_FRAMEWORK_PATH DYLD_LIBRARY_PATH
  QT_MAC_DISABLE_LIBRARY_VALIDATION=1 \
  QT_QPA_PLATFORM_PLUGIN_PATH=.venv/lib/python3.12/site-packages/PySide6/Qt/plugins/platforms \
  QT_PLUGIN_PATH=.venv/lib/python3.12/site-packages/PySide6/Qt/plugins \
  DYLD_FRAMEWORK_PATH=.venv/lib/python3.12/site-packages/PySide6/Qt/lib \
  DYLD_LIBRARY_PATH=.venv/lib/python3.12/site-packages/PySide6/Qt/lib \
  QT_QPA_PLATFORM=cocoa \
  python src/main.py
  ```
- Om venv tas bort: återskapa med `/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -r Requirements.txt`. PySide6 installeras i venv och env-variablerna ovan pekar då rätt.
- Whisper (svenska): default språk i config är `whisper_language="sv"`. Har du en lokal modell, sätt `WHISPER_MODEL_PATH=whisper_models/<modell>.pt` eller lägg filen i `whisper_models/`. För andra språk, ändra `whisper_language` i config.
