# Changelog

Alle wesentlichen Änderungen an Vector Office AI Core werden in dieser Datei
dokumentiert. Das Projekt verwendet semantische Versionsnummern; Vorabstände
werden ausdrücklich als Release-Kandidaten gekennzeichnet.

## [Unreleased]

- feste, registrygebundene Tool-Auswahl im Gespräch ergänzt
- Ja/Nein-Bestätigung für Bewegungen und sofortigen Notfallstopp ergänzt
- inaktive strukturierte Modellvorschläge mit lokaler Registry-Prüfung ergänzt
- lokale redigierte Tool-Audits mit begrenzter Aufbewahrung ergänzt
- grenznahe Registry- und Embedding-Module verhaltensneutral aufgeteilt
- Ausdruckshinweise auf eine geprüfte, noch nicht ausführbare Animation abgebildet
- bestätigte Ausdrucksanimation und TTS sicher nacheinander koordiniert
- expliziten Zwei-Turn-Ausdrucksdialog für Konsole und WirePod ergänzt
- verworfene vorbereitete Antworten sicher aus dem Sitzungskontext zurückgerollt
- festes reflektiertes Kopf-Augen-Profil ohne Räder oder Lift ergänzt
- zusammengesetztes Profil mit dem bestehenden Timeout pro SDK-Einzelaktion abgesichert
- reflektiertes OneCore-SSML-Profil mit ruhigerem Tempo und Denkpausen ergänzt
- Satzmelodie durch weniger Bremsung, kürzere Pausen und native Tonhöhe verfeinert
- Sprachregeln gegen Manuskriptton, Nominalketten und abstrakte Aufzählungen ergänzt
- kurze reflektierte Sätze und greifbare Einstiege statt Lexikondefinitionen vorgegeben
- drei gleichgewichtete lokale Reflexionseinleitungen mit unabhängiger Auswahl ergänzt
- unnatürlich ausgesprochene Varianten `Hmmm` und `Mmmm` nach Hörprobe entfernt
- physisch ausgewählten IPA-Summton mit 1,5 Sekunden Denkpause übernommen
- IPA-Summton nach A/B-Hörprobe um rund eine halbe Sekunde verlängert
- doppelte WirePod-Transkripte innerhalb eines kurzen lokalen Fensters unterdrückt
- Voice-Wiedererkennung auf begrenzte SHA-256-Fingerabdrücke beschränkt
- WirePod-Initialisierung und laufende Erkennung begrenzt wiederholbar gemacht
- normalisierte Voice-Abbruchsignale und sichere Sitzungsbereinigung ergänzt
- im Hardwaretest beobachtete Vosk-Varianten gezielt in bestehende Allowlists aufgenommen
- Voice-Cloud-Hinweis auf die tatsächliche Anwendungsgrenze präzisiert
- parallele englische WirePod-Stimme durch deaktivierten Intent-Graph- und
  Konversationspfad beseitigt und den lokalen Transkriptpfad physisch bestätigt
- neutrale deutsche TTS moderat beschleunigt und eine präsente, nicht
  verlangsamte Satzöffnung mit leise fallendem Satzende ergänzt
- neue deutsche Satzkontur am physischen Vector erfolgreich hörgeprüft
- gemeinsame konfigurierbare LLM-Zeitlimits und maximale Versuche eingeführt
- lokale Ollama-Wiederholung auf vorübergehende Transport- und Serverfehler begrenzt
- OpenAI-SDK-Retries explizit an dieselbe Versuchszahl gebunden
- lokale strukturierte JSONL-Diagnose mit stabilen Ereigniscodes ergänzt
- Diagnosefelder durch feste Metadaten-Allowlist gegen private Inhalte abgesichert
- begrenzte Dateirotation sowie Startup-, Service-, Retry- und Fallback-Ereignisse ergänzt
- mehrturnigen Wechsel vom Primäranbieter zu Ollama und zurück abgesichert
- gemeinsame Kontexterhaltung nach einer lokalen Fallback-Antwort nachgewiesen
- unbeantwortete Runde bei Ausfall beider Provider transaktional zurückgerollt
- zentralen ConnectionSupervisor mit begrenzter exponentieller Staffel ergänzt
- WirePod, Ollama und Vector-SDK an datenschutzsichere Zustandswechsel angebunden
- einmalige lokale Kollektiv-Offline-Ansage vor der Ollama-Antwort ergänzt
- separate ehrliche Meldung für den Ausfall von Cloud und lokalem Fallback ergänzt
- beide lokalen Offline-Meldungen am physischen Vector erfolgreich abgenommen
- aktive WirePod-Sprachsitzungen an die gemeinsame Wiederholungsstaffel angebunden
- einmalige deutsche Wiederherstellungsansage nach einem WirePod-Ausfall ergänzt
- Wiederherstellungsansage am physischen Vector verständlich hörgeprüft und bestätigt
- lokalen Windows-Autostart mit verzögerter Einzelinstanz-Aufgabe ergänzt
- Host-Watchdog für fehlenden WirePod-Prozess und begrenzte App-Neustarts ergänzt
- sauberen Prozessbaum-Stopp beim Beenden der Windows-Aufgabe abgesichert
- installierten Windows-Aufgabenstart und rückstandsfreien Stopp praktisch geprüft
- aktive WirePod-Wiederherstellung auf fünf Prüfungen und 18 Sekunden erweitert
- Voice-Recovery verhaltensneutral aus der allgemeinen Gesprächsschleife ausgelagert
- native Windows-Prozessprüfung mit expliziten 64-Bit-Signaturen abgesichert
- vollständigen VECTOR-PY-CLEANUP nach Karte 18 mit 366 Tests abgeschlossen
- Pause nach `Lass mich überlegen` auf zwei Sekunden abgestimmt
- `vektor beenden` und sauberen Abbruch der Voice-Schleife per `Ctrl+C` ergänzt
- reflektiertes Bewegungs- und Sprachprofil physisch erfolgreich als Verbesserung bewertet
- Bedienung und Systemdiagnose weiter vereinfachen

## [0.2.0-rc.1] – 2026-08-17

### Hinzugefügt

- OpenAI mit lokalem Ollama-Fallback und gemeinsamem Gesprächskontext
- kontrolliertes SQLite-Memory und lokale Dokumentbibliothek
- lokale `embeddinggemma`-Vektoren und hybride semantische Suche
- Dokumentversionen, Exporte, Reindexierung und verifizierte Löschung
- zentrale Tool Registry mit Berechtigungs- und Bestätigungssystem
- sichere Kopf-, Lift- und Animationsaktionen mit Notfallstopp
- transparentes Gesprächszustandsmodell und optionale Reflexionsschicht
- mehrstufige Release-Abnahme für Kern, Ollama, OpenAI und Vector

### Geändert

- deutsche TTS für Vector auf verständliche, komprimierte Ausgabe optimiert
- Ollama-Diagnosen für wiederholbare Abnahmen deterministisch konfiguriert
- Antwortprüfung begrenzt reine Längenverstöße sicher auf vollständige Sätze
- Python-Struktur durch automatische Funktions- und Unter-400-Zeilen-Regeln
  abgesichert

### Sicherheit

- Dokumentwissen bleibt standardmäßig lokal und für OpenAI gesperrt
- Prompt-Injection-Inhalte werden ausdrücklich als unvertrauenswürdige Daten
  behandelt
- Secrets, Dokumenttexte und Vektoren bleiben aus Logs und Abnahmeberichten
- physische Prüfungen benötigen eine ausdrückliche zweite Bestätigung

### Abnahme

- 227 automatisierte Tests bestanden
- Kernabnahme: 4/4
- Ollama-Abnahme: 7/7
- OpenAI-Abnahme: 5/5
- physische Vector-Abnahme: 6/6
- Aussprache, Lautstärke, Wissensantwort und Begrüßung subjektiv bestätigt
