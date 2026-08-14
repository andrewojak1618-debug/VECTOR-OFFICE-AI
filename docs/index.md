# Vector Office AI Core

Vector Office AI Core verbindet einen physischen Vector 2.0 mit deutscher
Spracheingabe, natürlicher Sprachausgabe, Cloud- und lokalen Sprachmodellen
sowie einem kontrollierten Langzeitgedächtnis.

Diese Dokumentation ergänzt die README. Sie hält technische Entscheidungen,
erfolgreiche Tests, offene Grenzen und die weitere Entwicklung nachvollziehbar
fest.

## Aktueller Stand

- WirePod und Vector-SDK sind mit dem physischen Roboter verbunden.
- WirePod transkribiert deutsche Sprache lokal mit Vosk.
- Windows OneCore erzeugt die Stimme „Microsoft Stefan“.
- FFmpeg normalisiert und komprimiert die Sprache für Vector.
- OpenAI ist als Cloud-Provider vorbereitet.
- Ollama mit `llama3.2:3b` arbeitet als lokaler Provider und Fallback.
- SQLite speichert ausschließlich ausdrücklich bestätigte Erinnerungen.
- Spracheingaben bleiben standardmäßig lokal.
- 69 automatisierte Tests sichern Funktion und Codequalität ab.

## Schnellstart

```powershell
.venv\Scripts\python.exe main.py
```

Die lokale `.env` bestimmt, ob Eingaben über die Konsole oder WirePod erfolgen.
Secrets und die lokale Memory-Datenbank gehören niemals in Git.

## Dokumentation lokal anzeigen

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-docs.txt
.venv\Scripts\python.exe -m mkdocs serve
```

MkDocs stellt die Seite anschließend standardmäßig unter
`http://127.0.0.1:8000` bereit.
