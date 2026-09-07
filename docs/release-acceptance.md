# Systemabnahme und Release-Kandidat

Die zentrale Abnahme trennt bewusst lokale Qualitätsprüfungen, Live-Provider
und physische Robotertests. Der Standardbefehl verursacht weder API-Kosten
noch eine Bewegung oder Sprachausgabe von Vector.

## Automatischer Kern

```powershell
.venv\Scripts\python.exe -m diagnostics.release_acceptance `
  --report data/acceptance/core.json
```

Dieser Lauf führt die vollständige Unit-Test-Suite, `compileall`, den strikten
MkDocs-Build und `git diff --check` aus. Die Unit-Tests prüfen unter anderem:

- OpenAI-, Ollama- und Fallback-Komposition,
- Sprach-, Memory-, Bibliotheks- und Tool-Grenzen,
- kontrollierte Robot-Aktionen ohne Hardwarezugriff,
- Datenschutz, Prompt-Injection-Schutz und Secret-Redaktion,
- eine reale lokale SQLite-Sicherung mit anschließender Wiederherstellung.

Bei einer Fehlerkorrektur kann der neue Regressionstest vor diesen Kernprüfungen
verbindlich vorgeschaltet werden:

```powershell
.venv\Scripts\python.exe -m diagnostics.release_acceptance `
  --regression-test tests.test_modul.TestKlasse.test_fehlerfall
```

Der vollständige Ablauf einschließlich des nachgewiesenen Fehlschlags vor der
Korrektur ist in [`docs/testing.md`](testing.md) beschrieben.

Der optionale JSON-Bericht enthält nur Prüfname, Kategorie, Status,
Rückgabecode und Dauer. Kommandos, Prozessausgaben, Dokumenttexte, Vektoren und
Secrets werden nicht aufgenommen. `data/` bleibt von Git ausgeschlossen.

## Live-Test mit Ollama

```powershell
.venv\Scripts\python.exe -m diagnostics.release_acceptance `
  --live-ollama `
  --report data/acceptance/ollama.json
```

Zusätzlich werden lokale Embeddings, hybride Wissenssuche und die drei festen
Persönlichkeitsbeispiele mit dem konfigurierten Ollama-Modell ausgeführt.

## Live-Test mit OpenAI

```powershell
.venv\Scripts\python.exe -m diagnostics.release_acceptance `
  --live-openai `
  --report data/acceptance/openai.json
```

Dieser Modus sendet genau eine minimale Erreichbarkeitsanfrage an das
konfigurierte OpenAI-Modell und kann API-Kosten verursachen. Der Schlüssel und
die Modellantwort werden nicht ausgegeben oder im Bericht gespeichert.

## Physischer Vector-Test

```powershell
.venv\Scripts\python.exe -m diagnostics.release_acceptance `
  --physical-vector `
  --confirm-physical `
  --report data/acceptance/vector.json
```

Ohne `--confirm-physical` wird der Lauf vor jeder Hardwareaktion abgebrochen.
Nach der Bestätigung prüft er den vollständigen lokalen Wissenspfad bis zur
deutschen Sprachausgabe und genau eine freigegebene Begrüßungsanimation. Der
Nutzer bewertet anschließend Aussprache, Lautstärke, Antwortqualität und die
physische Ausführung.

## Freigabekriterien

Ein Release-Kandidat wird erst markiert, wenn:

1. der automatische Kern vollständig grün ist,
2. die tatsächlich eingesetzten Provider live erreichbar sind,
3. der physische Test erfolgreich und subjektiv bestätigt ist,
4. `git status --short` keine unbeabsichtigten Dateien zeigt,
5. kein `.env`-, Datenbank-, Export- oder Abnahmebericht versioniert ist.

Erst danach werden Versionsnummer, Changelog und Git-Tag gemeinsam festgelegt.

## Ergebnis des ersten Release-Kandidaten

Am 17. August 2026 bestanden der Kern 4/4, Ollama 7/7, OpenAI 5/5 und
der physische Vector-Pfad 6/6 Prüfschritte. Der Nutzer bestätigte Aussprache,
Lautstärke, die korrekte Wissensantwort `0,35` und die Begrüßungsbewegung.
Daraufhin wurde `0.2.0-rc.1` als erster Release-Kandidat vorbereitet. Die
lokalen JSON-Berichte bleiben unter `data/acceptance/` und werden nicht
versioniert.

## Ergebnis des zweiten Release-Kandidaten

Am 25. August 2026 bestand der finale RC2-Stand den automatischen Kern mit 4/4
Prüfungen und 635 automatisierten Tests. Die lokale Ollama-Abnahme erreichte
7/7 und die minimale OpenAI-Live-Abnahme 5/5 Prüfungen. Genau eine kurze
ElevenLabs-Erzeugung wurde als gültiges MP3 dekodiert und anschließend ohne
erneuten Cloud-Aufruf über Vector abgespielt.

Der physische Vector-Pfad bestand 6/6 Prüfungen: semantischer Dokumentabruf,
lokale Ollama-Antwort, deutsche Sprachausgabe und eine kontrollierte
Begrüßungsanimation wurden technisch abgeschlossen. Der Nutzer bestätigte
anschließend Aussprache, Lautstärke, Wissensantwort, ElevenLabs-Stimme und
Animation. Auch der vollständige Windows-Kaltstart mit WirePod, Ollama und
Vector SDK wurde vor der Freigabe praktisch bestätigt. Damit erfüllt
`0.2.0-rc.2` alle Freigabekriterien.

## Ergebnis des dritten Release-Kandidaten

Am 6. September 2026 bestand der vorbereitete RC3-Stand den gezielten
Status-Regressionstest und den vollständigen automatischen Kern mit 5/5
Prüfungen und 820 automatisierten Tests. Die lokale Ollama-Abnahme erreichte
8/8 Prüfungen. OpenAI blieb im privaten Sprachbetrieb mit
`VOICE_ALLOW_CLOUD=false` deaktiviert und wurde deshalb nicht durch eine
zusätzliche kostenpflichtige Live-Anfrage angesprochen.

Der semantische Wissenspfad bis zur deutschen Vector-TTS und die kontrollierte
Begrüßungsanimation wurden in getrennten physischen Läufen erfolgreich
abgeschlossen. Nach einer kontrollierten WirePod-Wiederherstellung bestätigte
der Nutzer die Wissensausgabe als klar und verständlich. Die natürliche Frage
„Wie ist dein Systemzustand?“ wurde anschließend ohne LLM-Aufruf in 15
Millisekunden lokal vorbereitet, über ElevenLabs ausgegeben und ebenfalls klar
verstanden. Damit sind die technischen und subjektiven RC3-Kriterien erfüllt
und der gemeinsame Release-Stand für Commit und annotierten Tag
`v0.2.0-rc.3` freigegeben.

## Ergebnis des vierten Release-Kandidaten

Am 7. September 2026 bestand der vorbereitete RC4-Stand den gezielten
Kaltstart-Regressionstest und den vollständigen automatischen Kern mit 5/5
Prüfungen und 834 automatisierten Tests. Der begrenzte lokale Stabilitätslauf
erreichte für Vector SDK, WirePod und Ollama jeweils zehn von zehn erfolgreiche
Messungen ohne Ausfall oder Zustandswechsel.

Ein zunächst blockierter WirePod-SDK-Zugriff ließ sich durch genau einen
kontrollierten Neustart wiederherstellen und wurde anschließend als dauerhafte,
einmalig begrenzte Startreparatur abgesichert. Der folgende echte
Windows-Kaltstart bestand zehn von zehn Prüfungen ohne notwendigen
Reparatureingriff. Watchdog, Anwendung und WirePod liefen jeweils genau einmal;
Vector SDK, WirePod und Ollama waren verfügbar. Der Nutzer bestätigte die
anschließende Systemstatusantwort als klar und verständlich. Damit ist Karte 50
abgenommen und `0.2.0-rc.4` für Release-Commit und annotierten Tag freigegeben.
