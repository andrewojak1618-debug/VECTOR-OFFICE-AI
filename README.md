# 🤖 VECTOR OFFICE AI CORE

![Vector Office AI illustration](assets/Vevtor_illustration_README.png)

> **Ein persönlicher deutschsprachiger KI-, Büro- und Entwicklungsassistent auf Basis eines physischen Vector-2.0-Roboters.**

## 💡 Projektidee

**VECTOR OFFICE AI CORE** verbindet einen physischen Vector 2.0 mit einem
eigenen Python-Core, modernen Sprachmodellen, lokalem Kontext, deutscher
Sprachausgabe und später einem kontrollierten Tool- und Memory-System.

Vector soll nicht nur vorgefertigte Kommandos ausführen. Er soll als greifbare
Schnittstelle zu einem persönlichen Assistenten dienen, Fragen verstehen,
Zusammenhänge behalten, bei Büro- und Entwicklungsaufgaben helfen und Antworten
mit natürlicher deutscher Aussprache sprechen.

Die langfristige Architektur:

```text
Benutzer
   ↓
Vector 2.0
   ↓
Vector Office AI Core
   ↓
Brain / LLM / Memory / Tools
   ↓
Antwort oder kontrollierte Aktion
   ↓
Vector 2.0
```

## 🎯 Ziele

Vector soll schrittweise zu einem persönlichen Assistenten ausgebaut werden,
der:

- natürlich auf Deutsch kommuniziert
- Fragen beantwortet und Gesprächskontext behält
- zwischen Cloud- und lokalen Sprachmodellen wechseln kann
- Erinnerungen und langfristigen Kontext verwaltet
- bei Programmierung, Recherche und Büroarbeit unterstützt
- Tools nur innerhalb klarer Berechtigungsregeln verwendet
- Bewegungen, Animationen und weitere Robot-Aktionen ausführt
- langfristig auch Spracheingaben über Vector entgegennimmt

## ✨ Aktuell umgesetzt

Der aktuelle Prototyp unterstützt bereits:

- direkte Verbindung zum physischen Vector über das Python SDK
- Verbindungstest zu einem lokalen WirePod-Server
- Auslesen der Batteriespannung
- erfolgreiche Anforderung von `BehaviorControl`
- direkte Vector-Sprachausgabe über `say_text()` als Fallback
- natürliche deutsche TTS-Ausgabe mit Microsoft Stefan
- Wiedergabe eigener WAV-Dateien über Vectors externen Audiostream
- automatische Konvertierung auf 16 kHz, 16 Bit und Mono
- Loudness-Normalisierung und Sprachkompression ohne digitales Clipping
- konfigurierbare TTS-Stimme und Lautstärke
- providerunabhängigen Agent- und Conversation-Core
- OpenAI-Adapter über die Responses API
- lokal getesteten Ollama-Adapter mit automatischem Offline-Fallback
- mehrere Gesprächsrunden mit erhaltenem Kontext
- kontrolliertes SQLite-Langzeitgedächtnis für beide Provider
- `/remember`, `/memories` und `/forget` zur Memory-Verwaltung
- `/clear` zum Löschen des aktuellen Gesprächskontexts
- `/exit` zum sauberen Beenden einer Sitzung
- automatisierte Tests für Agent, Kontext, Provider und Gesprächsschleife

## 🗣️ Deutsche Sprachausgabe

Vectors interne `say_text()`-Funktion verwendet die aktuell eingestellte
Robot-Stimme. Deutscher Text wird dadurch bei englischer Locale mit englischer
Aussprache gesprochen.

Die im verwendeten SDK enthaltene Methode `say_localized_text()` ist in der
aktuellen Konfiguration nicht nutzbar, weil sie intern den nicht verfügbaren
gRPC-Aufruf `UpdateSettings` erwartet.

VECTOR OFFICE AI CORE verwendet deshalb einen unabhängigen Audiopfad:

```text
Deutscher Text
   ↓
Windows OneCore TTS – Microsoft Stefan
   ↓
FFmpeg-Konvertierung und Sprachkompression
   ↓
PCM-WAV – 16 kHz / 16 Bit / Mono
   ↓
Vector SDK ExternalAudioStreamPlayback
   ↓
Vector-Lautsprecher
```

Dieser Weg wurde erfolgreich mit einem physischen Vector 2.0 getestet.

## 🧠 Brain und Sprachmodelle

Der Brain-Core ist bewusst unabhängig von einem einzelnen Anbieter aufgebaut.
Alle Provider implementieren dieselbe `LanguageModel`-Schnittstelle.

Aktuell vorgesehen:

- **OpenAI:** Cloud-Modell über die Responses API; live getestet
- **Ollama:** lokales `llama3.2:3b` über `/api/chat`; live mit Vector getestet

Der aktive Provider wird über `.env` ausgewählt:

```env
LLM_PROVIDER=openai
```

oder:

```env
LLM_PROVIDER=ollama
```

Dadurch kann das Projekt später Qualität, Datenschutz, Offline-Fähigkeit und
Kosten flexibel gegeneinander abwägen.

## 💬 Gesprächsablauf

Der aktuelle Konsolenablauf:

```text
Benutzereingabe
   ↓
ConversationContext
   ↓
Agent
   ↓
OpenAIProvider oder OllamaProvider
   ↓
deutsche Modellantwort
   ↓
VectorSpeech
   ↓
Vector spricht
```

Innerhalb einer Sitzung bleibt der Gesprächskontext erhalten. Ein praktischer
Test wurde erfolgreich durchgeführt:

```text
Benutzer: Merke dir für dieses Gespräch die Zahl 27.
Vector:   Ich merke mir für dieses Gespräch die Zahl 27.

Benutzer: Welche Zahl solltest du dir merken?
Vector:   27
```

## 🛠️ Technik

- **Python 3.12:** zentraler Application Core
- **WirePod:** lokaler Voice- und Robot-Server
- **wirepod-vector-sdk 0.8.1:** direkte Robot-Kommunikation
- **OpenAI Responses API:** Cloud-basierte KI-Antworten
- **Ollama API:** vorbereitete lokale LLM-Alternative
- **Windows OneCore TTS:** natürliche deutsche Spracherzeugung
- **FFmpeg:** Audioformatierung, Normalisierung und Kompression
- **httpx:** WirePod- und Ollama-HTTP-Kommunikation
- **python-dotenv:** lokale Konfiguration und Secret-Verwaltung
- **uv:** Paketverwaltung der virtuellen Umgebung
- **unittest:** automatisierte Tests ohne zusätzliche Testabhängigkeit

## 📂 Projektstruktur

```text
VECTOR OFFICE AI CORE/
├── assets/
│   └── Vevtor_illustration_README.png
├── brain/
│   ├── agent.py
│   ├── context.py
│   ├── personality.py
│   └── providers.py
├── config/
│   └── settings.py
├── data/
├── memory/
│   ├── database.py
│   └── models.py
├── tests/
│   ├── test_agent.py
│   ├── test_main.py
│   └── test_providers.py
├── tools/
│   ├── permissions.py
│   └── registry.py
├── vector/
│   ├── actions.py
│   ├── client.py
│   ├── sdk_client.py
│   └── speech.py
├── .env.example
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

Die aktuell noch leeren Module in `tools/` und `vector/actions.py` sind bewusst
als nächste Architekturbereiche vorbereitet. `memory/` enthält inzwischen das
lokale SQLite-Langzeitgedächtnis.

## ⚙️ Installation

### Voraussetzungen

- Windows 10 oder Windows 11
- Python 3.12
- `uv`
- FFmpeg im `PATH`
- lokaler WirePod-Server
- eingerichtete Vector-SDK-Konfiguration unter `.anki_vector`
- physischer Vector 2.0 im selben Netzwerk
- gültiger OpenAI-API-Key oder eine lokale Ollama-Installation

### Repository klonen

```powershell
git clone https://github.com/andrewojak1618-debug/VECTOR-OFFICE-AI.git
cd VECTOR-OFFICE-AI
```

### Virtuelle Umgebung und Pakete

```powershell
uv venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

### Lokale Konfiguration

Kopiere `.env.example` nach `.env` und trage nur deine lokalen Werte ein:

```env
VECTOR_NAME=Vector
VECTOR_SERIAL=deine_vector_seriennummer
WIREPOD_HOST=http://127.0.0.1:8080

TTS_VOICE=Microsoft Stefan
TTS_VOLUME=90

INPUT_MODE=console
VOICE_LISTEN_TIMEOUT=120
VOICE_ALLOW_CLOUD=false

LLM_PROVIDER=openai
LLM_FALLBACK_PROVIDER=ollama
OPENAI_API_KEY=dein_api_key
OPENAI_MODEL=gpt-5.6-luna

OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EXECUTABLE=

MEMORY_DB_PATH=data/vector_memory.db
MEMORY_CONTEXT_LIMIT=5
```

OpenAI bleibt damit der bevorzugte Anbieter. Ist OpenAI nicht erreichbar,
erhält das lokale Ollama-Modell automatisch denselben Gesprächskontext und
übernimmt die Antwort. Mit `LLM_FALLBACK_PROVIDER=none` lässt sich der Fallback
abschalten.

Wenn Ollama als Anbieter oder Fallback konfiguriert ist, prüft das Programm den
lokalen Dienst beim Start und startet ihn bei Bedarf unsichtbar. Die ausführbare
Datei wird über den `PATH` und die üblichen Windows-Installationsordner gesucht.
Nur bei einer abweichenden Installation muss `OLLAMA_EXECUTABLE` als absoluter
Pfad gesetzt werden.

### Programm starten

```powershell
.venv\Scripts\python.exe main.py
```

Kommandos während einer Sitzung:

- `/remember TEXT` – eine bestätigte Erinnerung lokal speichern
- `/memories` – gespeicherte Erinnerungen mit IDs anzeigen
- `/forget ID` – eine bestimmte Erinnerung dauerhaft löschen
- `/clear` – aktuellen Gesprächskontext löschen
- `/exit` – Programm sauber beenden

Nur explizit mit `/remember` bestätigte Inhalte werden dauerhaft gespeichert.
Passende Erinnerungen werden OpenAI und Ollama über denselben Agent-Kontext zur
Verfügung gestellt. Die lokale Datenbank unter `data/` wird nicht eingecheckt.

### Tests ausführen

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### WirePod-Spracheingabe diagnostizieren

Der erste Voice-Input-Baustein wartet auf ein neues deutsches Transkript aus
WirePods lokaler Log-Schnittstelle:

```powershell
.venv\Scripts\python.exe -m voice.wirepod_input --timeout 60
```

Nach dem Start innerhalb des Zeitfensters einen normalen Befehl mit
„Hey Vector“ sprechen. Der Diagnosemodus liest nur das nächste erkannte
Transkript und führt noch keine KI-Antwort oder Robot-Aktion aus.

Für die vollständige Sprachpipeline kann anschließend in `.env`
`INPUT_MODE=wirepod` gesetzt werden. Dann läuft jede erkannte Äußerung durch
Agent, gemeinsames Memory, Provider-Fallback und deutsche Vector-TTS. Der
Konsolenmodus bleibt mit `INPUT_MODE=console` verfügbar.

Sprachtranskripte bleiben mit `VOICE_ALLOW_CLOUD=false` vollständig lokal und
werden direkt mit Ollama verarbeitet. Erst `VOICE_ALLOW_CLOUD=true` erlaubt im
WirePod-Modus die Übergabe erkannter Sprache an den konfigurierten
Cloud-Provider.

## 🔐 Sicherheit und Secrets

Folgende Daten dürfen niemals committed oder veröffentlicht werden:

- `.env`
- OpenAI-API-Keys
- Vector-Seriennummern, Tokens und Zertifikate
- Inhalte aus `.anki_vector/`
- `sdk_config.ini`

Die lokale `.env` und `.venv` werden durch `.gitignore` ausgeschlossen. Das
Repository enthält ausschließlich `.env.example` ohne echte Zugangsdaten.

## 📈 Entwicklungsverlauf

### Phase 1 – Projektgrundlage

- Python-3.12-Projektstruktur aufgebaut
- lokale Konfiguration mit `.env` eingerichtet
- WirePod-Healthcheck implementiert
- direkte Vector-SDK-Verbindung hergestellt
- Batteriestatus und BehaviorControl erfolgreich getestet

### Phase 2 – Direkte Robot-Sprache

- `VectorSDKClient.say()` mit `robot.behavior.say_text()` implementiert
- physische Sprachausgabe erfolgreich bestätigt
- Ursache der englischen Aussprache bei deutschem Text analysiert
- inkompatiblen `say_localized_text()`-/`UpdateSettings`-Pfad dokumentiert

### Phase 3 – Natürliches deutsches TTS

- `VectorSDKClient.play_wav()` ergänzt
- externen WAV-Audiostream auf Vector 2.0 getestet
- Windows OneCore TTS mit Microsoft Stefan angebunden
- FFmpeg-Konvertierung auf das Vector-Audioformat implementiert
- Lautstärke normalisiert und Sprachkompression abgestimmt
- Stimme und Lautstärke über `.env` konfigurierbar gemacht

### Phase 4 – Providerunabhängiger Brain-Core

- `ChatMessage` und `ConversationContext` eingeführt
- System-Persönlichkeit für Vector Office AI definiert
- unabhängige `LanguageModel`-Schnittstelle aufgebaut
- Agent mit Kontextverwaltung und Eingabevalidierung implementiert
- OpenAI- und Ollama-Provider ergänzt
- Fehlerausgaben gegen Secret-Leaks gehärtet

### Phase 5 – KI spricht über Vector

- echten OpenAI-API-Aufruf erfolgreich getestet
- Modellantwort an die deutsche TTS-Schicht übergeben
- vollständigen Ablauf bis zum physischen Vector bestätigt
- mehrturnige Gesprächsschleife mit erhaltenem Kontext ergänzt
- `/clear` und `/exit` implementiert
- einunddreißig automatisierte Tests erfolgreich ausgeführt

## 🏷️ Versions- und Commit-Historie

| Stand | Commit | Inhalt |
|---|---|---|
| Repository-Basis | `c88c224` | Erster Git-Stand |
| Core-Grundlage | `cdaf906` | Projektstruktur, WirePod-/SDK-Tests und WAV-Wiedergabe |
| German TTS | `b85e5ed` | Konfigurierbare deutsche TTS-Pipeline |
| AI Conversation Core | `15ea79a` | Providerunabhängiger Agent, OpenAI/Ollama und Tests |
| Conversation Loop & README | `d4a3d5e` | Mehrturnige Gesprächsschleife und Projektdokumentation |
| Aktueller Arbeitsstand | noch nicht committed | Ollama-Fallback und kontrolliertes SQLite-Memory |

Die Anwendung befindet sich weiterhin in Version **0.1.0**. Die Historie wird
bewusst über kleine, überprüfbare Meilensteine aufgebaut.

## 🚧 Aktueller Projektstatus

### Aktuelle Phase

**Funktionaler KI-/Speech-Prototyp mit physischem Vector 2.0**

- ✅ WirePod-Verbindung
- ✅ direkte Vector-SDK-Verbindung
- ✅ natürliche deutsche Sprachausgabe
- ✅ Lautheitsnormalisierung und Sprachkompression
- ✅ providerunabhängiger Brain-Core
- ✅ OpenAI-Live-Integration
- ✅ lokal getestetes Ollama-Modell `llama3.2:3b`
- ✅ automatischer Ollama-Fallback bei OpenAI-Ausfall
- ✅ mehrturniger Gesprächskontext
- ✅ kontrolliertes SQLite-Langzeitgedächtnis
- ✅ kontextbezogener Abruf für OpenAI und Ollama
- ✅ Anzeigen und Löschen gespeicherter Erinnerungen
- ✅ automatisierte Tests
- ✅ WirePod-Transcript-Listener für deutsche Spracheingabe
- 🧪 Spracheingabe mit Agent, Memory, Fallback und TTS verbunden
- ⏳ semantische Memory-Suche und Dokumentbibliothek
- ⏳ Tool Registry und Berechtigungsmodell
- ⏳ Robot-Aktionen und kontextabhängige Animationen

## 🗺️ Roadmap

### Version 0.2 – Conversation Foundation

- interaktive Gesprächsschleife weiter stabilisieren
- Timeout-, Retry- und Provider-Fallback-Verhalten ergänzen
- Ollama lokal installieren und mit geeignetem Modell testen
- Providerwechsel vollständig über Konfiguration absichern
- strukturierte Logs und Diagnoseausgaben einführen

### Version 0.3 – Voice Input

- Spracheingaben von Vector beziehungsweise WirePod empfangen
- Speech-to-Text-Ergebnisse an den Brain-Core übergeben
- Aktivierungs- und Abbruchlogik entwickeln
- vollständige sprachgesteuerte Unterhaltung ermöglichen

### Version 0.4 – Memory

- ✅ SQLite-basiertes Langzeitgedächtnis als Grundlage entwickelt
- ✅ bestätigte Benutzerpräferenzen und Erinnerungen speicherbar
- ✅ relevante Erinnerungen kontextbezogen abrufbar
- ✅ Erinnerungen können angezeigt und einzeln gelöscht werden
- semantische Suche und kontrollierten Dokumentimport ergänzen

### Version 0.5 – Tools und Sicherheit

- Tool Registry implementieren
- Berechtigungsstufen und Bestätigungen definieren
- Büro-, Datei-, Recherche- und Entwicklungswerkzeuge anbinden
- alle Aktionen nachvollziehbar protokollieren

### Version 0.6 – Robot Personality

- Bewegungen und Animationen passend zu Antworten auswählen
- Blickrichtung, Kopf, Lift und Fahrverhalten koordinieren
- Sprach- und Aktionsausgabe synchronisieren
- emotionale Reaktionen kontrolliert einsetzen

### Version 1.0 – Personal Office Assistant

- stabile sprachbasierte Kommunikation
- austauschbare Cloud- und lokale Modelle
- langfristiges Memory
- kontrollierte Tool-Nutzung
- ausgereifte Vector-Persönlichkeit
- dokumentierter, testbarer und sicherer Betrieb

## 🚀 Langfristige Vision

VECTOR OFFICE AI CORE soll zu einem persönlichen Assistenten werden, der nicht
nur in einem Browserfenster existiert, sondern als physischer Charakter am
Arbeitsplatz präsent ist.

Vector soll langfristig zuhören, verstehen, erinnern, erklären, bei der Arbeit
helfen und kontrollierte Aktionen ausführen – mit einer klaren deutschen
Stimme, einer konsistenten Persönlichkeit und einer Architektur, bei der der
Benutzer jederzeit die Kontrolle behält.

## © Hinweis

Dieses Projekt befindet sich in aktiver Entwicklung. Architektur, Funktionen,
Modelle und Robot-Verhalten können sich während der Entwicklung verändern oder
erweitert werden.
