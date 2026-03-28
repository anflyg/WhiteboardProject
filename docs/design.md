# WhiteboardProject – designdokument

## 1. Syfte

WhiteboardProject ska vara en lokal-first applikation för att fånga, visa, bearbeta och strukturera whiteboardgenomgångar på ett sätt som ger användaren konkret nytta utan löpande tokenkostnader.

Produkten har två sammanhängande kärnvärden:

1. **Förbättrad live-visning av whiteboard**
   - visa whiteboarden tydligare via kamera
   - stöd för zoom
   - stöd för pan
   - stöd för keystone/perspektivkorrigering
   - stöd för val av kamera och stabil visning
   - stöd för att lättare kunna läsa och följa tavlans innehåll i stunden

2. **Lokal bearbetning och valfri AI-efterbearbetning**
   - inspelning eller fångst av underlag
   - frame-urval
   - transkribering
   - OCR/whiteboardtolkning på grundnivå
   - lokal export
   - valfri export till ChatGPT med rätt underlag och prompt

Produkten ska alltså inte bara ses som en AI-pipeline, utan som ett komplett whiteboardverktyg med både **live-användning** och **efterbearbetning**.

Systemet ska alltid fungera lokalt, medan ChatGPT-export ska vara ett frivilligt kvalitetslyft.

---

## 2. Produktprinciper

### 2.1 Lokal-first
All kärnfunktion ska kunna köras lokalt på användarens dator utan krav på extern AI-tjänst.

### 2.2 Cloud-optional
Extern AI ska vara ett valbart steg för förbättrad efterbearbetning, inte ett krav för att produkten ska vara användbar.

### 2.3 Praktisk kvalitet före teknisk perfektion
Första målet är inte perfekt förståelse av all handskrift, matematik eller alla ritningar. Första målet är att få ut ett användbart underlag med hög träffsäkerhet i de vanligaste fallen.

### 2.4 Tydligt arbetsflöde
GUI och funktioner ska utformas utifrån användarens arbetsflöde, inte utifrån interna modellnamn eller tekniska implementationer.

### 2.5 Whiteboard först
Produktens grund är att ge användaren en bättre vy av whiteboarden i realtid. AI-bearbetning och export bygger vidare på detta, men ersätter inte live-användningen som kärnvärde.

### 2.6 Synk är kärnproblemet
Produktens viktigaste intelligens är inte bara att transkribera tal eller spara bilder, utan att förstå **kopplingen mellan vad läraren säger och vad som finns på tavlan vid just det tillfället**.

### 2.7 Sektioner före rådata
Målet är inte i första hand att samla rå frames och rå text, utan att skapa meningsfulla **sektioner** som motsvarar hur en elev faktiskt antecknar under en lektion.

---

## 3. Beslut som gäller nu

### 3.1 Standardbackend för lokal transkribering
Projektet ska använda **faster-whisper** som standardbackend för lokal transkribering.

### 3.2 Standardmodell för lokal transkribering
Projektets standardprofil ska använda modellen **small**.

Detta innebär:
- rimlig lokal prestanda på en MacBook Air
- tillräckligt bra basnivå för standardflödet
- möjlighet att senare lägga till tyngre kvalitetslägen utan att höja grundkravet för användaren

### 3.3 Export till ChatGPT
Systemet ska kunna exportera ett komplett AI-underlag för ChatGPT.

Exporten ska innehålla:
- transkription
- utvalda keyframes
- lokal sammanställning
- tidslinje/metadata
- färdig prompt för ChatGPT

### 3.4 Ingen direkt koppling till användarens prenumeration
Produkten ska inte bygga på att använda användarens ChatGPT-prenumeration som intern motor i appen.

I stället ska appen:
- förbereda materialet lokalt
- exportera det i rätt format
- ge användaren tydlig instruktion för uppladdning i ChatGPT

### 3.5 Nästa kärnprioritet
Nästa stora utvecklingssteg efter grundexporten är:
- board state över tid
- sektionering av lektionen
- wipe-detektion
- stabiliseringslogik
- anteckningsenheter som kopplar tavla och tal

---

## 4. Målbild för användarflödet

### 4.1 Flöde A – live-användning av whiteboard
1. Användaren startar appen
2. Användaren väljer kamera
3. Appen visar whiteboarden i realtid
4. Användaren kan justera perspektiv med keystone
5. Användaren kan zooma in för att läsa detaljer
6. Användaren kan panorera runt den inzoomade ytan
7. Appen ska ge en stabil och lättolkad vy av tavlan

### 4.2 Flöde B – helt lokalt efterarbete
1. Användaren startar inspelning eller fångst
2. Appen samlar ljud och visuellt material
3. Appen väljer relevanta keyframes
4. Ljud transkriberas lokalt med faster-whisper small
5. Whiteboardmaterial tolkas lokalt i enkel form
6. Appen genererar lokal sammanställning
7. Användaren exporterar resultatet

### 4.3 Flöde C – lokalt plus ChatGPT
1. Användaren kör samma lokala flöde
2. Användaren väljer **Exportera för ChatGPT**
3. Appen skapar ett paket med filer och prompt
4. Användaren laddar upp detta paket eller dess innehåll i ChatGPT
5. ChatGPT används för förbättrad tolkning, sammanfattning och strukturering

### 4.4 Flöde D – framtida anteckningsflöde
1. Systemet spårar hur tavlan förändras över tid
2. Systemet upptäcker när en tavelsektion börjar, stabiliseras och avslutas
3. Systemet kopplar lärarens tal till rätt taveltillstånd
4. Systemet identifierar när tavlan suddas eller när en ny uppgift börjar
5. Systemet skapar anteckningsenheter som motsvarar hur en elev skulle ha antecknat materialet

---

## 5. Funktionell design

## 5.1 Kärnfunktioner för whiteboardvisning

### Kameravisning
Systemet ska kunna visa livevideo från vald kamera.

### Kameraval
Användaren ska kunna välja mellan tillgängliga kameror.

### Keystone/perspektivkorrigering
Användaren ska kunna justera tavlans hörn så att whiteboarden visas som en rak och mer lättläst yta.

### Zoom
Användaren ska kunna zooma in tavlan för att läsa mindre detaljer.

### Pan
När användaren är inzoomad ska det gå att flytta vyn över tavlans yta.

### Overlay och visuella hjälplager
Systemet ska kunna visa hjälplager som underlättar justering, till exempel hörnmarkörer, aktivt läge eller enkel användarhjälp.

### Stabil och tydlig användning
Kärnupplevelsen ska vara att användaren snabbt kan få en bättre vy av tavlan än den råa kamerabilden ger.

## 5.2 Lokala profiler

Systemet ska ha tre profiler.

### Quick
För snabb återkoppling och enklare datorer.
- lättare modell
- snabbare körning
- lägre kvalitet

### Recommended
Detta ska vara standardläget.
- faster-whisper
- modellen small
- normal kvalitetsnivå
- bästa balans mellan kvalitet och prestanda för MacBook Air

### Full Local
För högsta lokala kvalitet.
- tyngre körning
- fler eller bättre frames
- mer noggrann bearbetning
- långsammare flöde

## 5.3 Exportformat för ChatGPT

Vid export ska appen skapa en sessionsmapp med stabil struktur.

Exempel:

```text
session_YYYY-MM-DD_HH-MM/
  transcript_sv.txt
  transcript_sv.srt
  board_summary.md
  prompt_chatgpt.txt
  manifest.json
  timeline.json
  keyframes/
    0001.jpg
    0002.jpg
    0003.jpg
```

### Filinnehåll

#### transcript_sv.txt
Rå eller lätt städad transkribering.

#### transcript_sv.srt
Tidskodad version av transkriberingen.

#### board_summary.md
Lokal första sammanställning från appen.

#### timeline.json
Maskinläsbar tidslinje med koppling mellan tal, frames och eventuella OCR-resultat.

#### manifest.json
Metadata om sessionen.

Exempel:
- datum
- språk
- vald profil
- använd backend
- använd modell
- antal frames
- exportversion

#### keyframes/
Utvalda bilder från whiteboardförloppet.

#### prompt_chatgpt.txt
Färdig prompt som användaren kan klistra in i ChatGPT.

## 5.4 Promptdesign för ChatGPT

Prompten ska vara uppgiftsstyrd och försiktig.

Den ska instruera ChatGPT att:
- läsa transkription och whiteboardbilder tillsammans
- återskapa innehåll pedagogiskt och strukturerat
- markera osäkerheter i tolkningen
- inte hitta på innehåll som inte stöds av materialet
- skapa både kort och lång sammanfattning
- lyfta centrala begrepp, formler och resonemang

Prompten ska genereras av appen och följa en fast mall med versionshantering.

## 5.5 Framtida kärnfunktioner för föreläsningsförståelse

### Board state
Systemet ska modellera tavlan som ett tillstånd över tid, inte bara som enskilda bilder.

### Delområden/regioner
Systemet ska kunna analysera förändringar i tavlans olika delar, så att nya tillägg och borttagningar kan upptäckas lokalt på ytan.

### Stabilisering
Systemet ska kunna avgöra när ett tavelinnehåll verkar vara tillräckligt stabilt för att betraktas som en färdig sektion eller deluppgift.

### Wipe-detektion
Systemet ska kunna upptäcka när innehåll suddas bort helt eller delvis, så att gamla anteckningsblock kan avslutas och nya kan börja.

### Sektionering
Systemet ska kunna dela upp en lektion i meningsfulla sektioner baserat på tavelförändring, stabilisering, wipe och lärarens tal.

### Anteckningsenheter
Systemet ska på sikt skapa anteckningsenheter som innehåller:
- tavlans innehåll i ett visst tillstånd
- tillhörande lärarprat
- start/sluttid
- osäkerheter
- eventuell koppling till uppgift, delproblem eller nytt block på tavlan

---

## 6. Arkitekturpåverkan

## 6.1 Nuvarande läge
Projektet har redan:
- GUI och kameraflöde
- keystone, zoom och pan
- grundstruktur för AI-pipeline
- konfiguration med profiler
- exportväg till ChatGPT-underlag
- promptgenerering
- metadata och tidslinje

Det betyder att produktens grund inte bara är AI-bearbetning, utan också en faktisk live-applikation för att visa och förbättra whiteboardinnehåll i realtid.

## 6.2 Nya eller förstärkta komponenter
För att nå målbilden behöver följande byggas eller stärkas:

### Konfigurationslager
- tydlig profilmodell: quick / recommended / full_local
- recommended ska vara standard
- recommended ska använda faster-whisper small

### Transkriptionslager
- robust lokal körning via faster-whisper
- tydlig hantering av språk, fel och progress

### Exportlager
- stabil sessionsstruktur
- generering av manifest, timeline och prompt
- robust filnamngivning och versionshantering

### Board state-lager
- representation av tavlans tillstånd över tid
- stöd för delta per region
- stöd för stabilisering och wipe-detektion

### Händelselager
- semantiska events för start, stabilisering, wipe och ny sektion
- koppling mellan taveltillstånd och transkriptsegment

### Anteckningslager
- bygg block som liknar elevanteckningar
- synka tavelinnehåll med lärarens förklaring
- skapa tydliga sektioner

### GUI-lager
- kameravisning och kameraval
- tydlig hantering av keystone
- tydlig hantering av zoom och pan
- val av profil
- knapp eller meny för export till ChatGPT
- tydlig återkoppling om vad som exporterats

### Testlager
- manuella testfall
- verifiering av exportstruktur
- verifiering av promptinnehåll
- verifiering av att recommended verkligen använder faster-whisper small
- verifiering av livefunktioner som kamera, zoom, pan och keystone
- verifiering av sektionering och wipe-detektion i senare steg

---

## 7. Icke-funktionella krav

### 7.1 Förutsägbarhet
Exporten ska alltid ge samma struktur så att användaren lär sig flödet.

### 7.2 Felrobusthet
Om en del av lokal analys inte lyckas ska export ändå kunna skapas med det material som finns.

### 7.3 Transparens
Användaren ska kunna se vilken profil som användes och vad som faktiskt exporterades.

### 7.4 Utbyggbarhet
Designen ska göra det enkelt att senare lägga till:
- bättre OCR-backend
- förbättrad board state
- fler exportmål
- djupare lokal analys

### 7.5 Låg hårdvarutröskel
Standardläget ska vara realistiskt att använda på en MacBook Air.

### 7.6 Meningsfull synk framför rå precision
Systemet ska prioritera att rätt tal kopplas till rätt tavelsektion, även om råtranskriptionen inte alltid är perfekt ord för ord.

---

## 8. Avgränsning

Detta steg omfattar inte:
- fullständig automatisk integration mot ChatGPT API
- perfekt handskriftsigenkänning
- full matematikparser
- avancerad multimodal molnpipeline

Detta steg omfattar:
- kärnflödet för live whiteboardvisning
- zoom, pan och keystone som del av produktens grundfunktion
- faster-whisper small som lokal standardväg
- export av välstrukturerat AI-underlag
- tydlig promptgenerering
- ett användarvänligt flöde för lokal bearbetning och frivillig ChatGPT-efterbearbetning
- nästa steg mot board state, wipe-detektion och synkade anteckningsblock

---

## 9. Definition of done för denna fas

Den nuvarande fasen är klar när följande stämmer:

1. Appen har en tydlig standardprofil som använder faster-whisper small.
2. Användaren kan använda live whiteboardvisning med kamera, zoom, pan och keystone.
3. Användaren kan exportera ett komplett ChatGPT-underlag från GUI:t.
4. Exporten innehåller rätt filer enligt specificerad struktur.
5. Prompten genereras automatiskt och är användbar direkt.
6. Det finns testbara kontrollpunkter för varje del.
7. Flödet kan demonstreras från live-användning eller inspelning till export utan manuella specialsteg.

## 9.2 Definition of done för nästa fas
Nästa fas är klar när systemet kan:
1. identifiera stabila tavelsektioner
2. upptäcka när tavlan suddas eller en ny uppgift börjar
3. koppla transkriptsegment till rätt tavelsektion
4. exportera anteckningsblock som tydligt motsvarar separata delar av lektionen

---

## 10. Rekommenderad fortsättning efter denna fas

Nästa fokus ska vara:
1. board-state-logik över tid
2. wipe-detektion
3. stable section detection
4. note units som synkar tavla och tal
5. därefter förbättrad OCR/vision-backend
6. därefter bättre lokal sammanställning före ChatGPT-export

Detta ger bäst progression från fungerande produktgrund till verkligt användbara föreläsningsanteckningar.

