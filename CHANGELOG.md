# Changelog

Alle wesentlichen Änderungen an Vector Office AI Core werden in dieser Datei
dokumentiert. Das Projekt verwendet semantische Versionsnummern; Vorabstände
werden ausdrücklich als Release-Kandidaten gekennzeichnet.

## [Unreleased]

- feste, registrygebundene Tool-Auswahl im Gespräch ergänzt
- Ja/Nein-Bestätigung für Bewegungen und sofortigen Notfallstopp ergänzt
- inaktive strukturierte Modellvorschläge mit lokaler Registry-Prüfung ergänzt
- Persönlichkeit mit freigegebenen Robot-Aktionen verbinden
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
