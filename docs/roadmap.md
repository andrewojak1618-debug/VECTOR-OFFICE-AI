# Roadmap

## Aktueller Stand – RC2 abgeschlossen

- ✅ historischen Tag `v0.2.0-rc.1` unverändert erhalten
- ✅ alle vorgesehenen Änderungen seit `v0.2.0-rc.1` integriert
- ✅ README und kanonische Roadmap auf den tatsächlichen Stand synchronisiert
- ✅ Windows-Autostart nach Neustart technisch geprüft
- ✅ lokale Sprachfrage nach Kaltstart korrekt und verständlich beantwortet
- ✅ letzter vollständiger Qualitätslauf mit 635 automatisierten Tests bestanden
- ✅ vollständige RC2-Kernabnahme mit 4/4 Prüfungen bestanden
- ✅ lokale Ollama-Abnahme mit 7/7 Prüfungen bestanden
- ✅ OpenAI-Live-Abnahme mit 5/5 Prüfungen bestanden
- ✅ genau eine ElevenLabs-Erzeugung validiert und über Vector hörgeprüft
- ✅ physischen Vector-Pfad mit 6/6 Prüfungen technisch bestanden
- ✅ Aussprache, Lautstärke, Wissensantwort und Animation subjektiv bestätigt
- ✅ Changelog und Versionsstand für `0.2.0-rc.2` festgelegt
- ✅ geprüften annotierten Tag `v0.2.0-rc.2` gesetzt

## RC3 – Natürlicher und kontrollierter Alltagsdialog

- ✅ Karte 39: begrenzte inhaltliche Folgefragen ohne erneutes Wakeword implementieren
- ✅ Karte 39: defekten Windows-Erkenner durch lokalen Vosk-Adapter ersetzen
- ✅ Karte 39: mehrturnigen Vosk-Folgepfad am physischen Vector abnehmen
- ✅ Karte 40: Intent-Erkennung und beobachtete Sprachvarianten absichern
- ✅ Karte 41: freigegebene Projektdokumente lokal zusammenfassen
- ✅ Karte 44: Antwortlatenz und TTS-Übergänge inhaltsfrei messen
- ✅ Karte 42: kontrollierte lokale Erinnerungen vorbereiten
- ⏳ Karte 43: ehrliches persönliches Gesprächsprofil erweitern
- ⏳ Karte 45: sichere lokale Statusübersicht planen
- ⏳ Karte 46: RC3 vollständig abnehmen und `v0.2.0-rc.3` setzen

## Release-Stabilisierung

- ✅ zentrale mehrstufige Systemabnahme implementieren
- ✅ lokale SQLite-Sicherung und Wiederherstellung automatisiert prüfen
- ✅ automatischen Kern vollständig abnehmen
- ✅ eingesetzte Ollama- und OpenAI-Provider live prüfen
- ✅ physischen Wissens- und Aktionspfad subjektiv bestätigen
- ✅ Versionsnummer und Changelog für `0.2.0-rc.1` festlegen
- ✅ ersten geprüften Git-Tag `v0.2.0-rc.1` historisch setzen
- ✅ Versionsnummer und Changelog für `0.2.0-rc.2` festlegen
- ✅ zweiten geprüften Git-Tag `v0.2.0-rc.2` setzen

## Conversation Foundation

- ✅ Retry- und Timeout-Verhalten weiter vereinheitlichen
- ✅ strukturierte Logs und Diagnoseausgaben ergänzen
- ✅ Providerwechsel in längeren Sitzungen testen
- ✅ zentralen ConnectionSupervisor mit begrenzter Wiederverbindung ergänzen
- ✅ einmalige lokale Offline-Ansage bei Cloud-Ausfall ergänzen
- ✅ einmalige lokale Wiederherstellungsansage nach WirePod-Ausfall ergänzen
- ✅ lokalen Windows-Autostart und Host-Watchdog implementieren
- ✅ vollständigen Windows-Kaltstart und Bereitschaftsstatus praktisch abnehmen
- ✅ lokale Ollama-Antwortlatenz für den Voice-Modus begrenzen und praktisch messen
- ✅ WirePod-SDK-Zugriff vor dem Start prüfen und veraltete Zuordnung einmal neu laden

## Provider-Zuverlässigkeit

- ✅ Architekturprinzipien und bewusst ausgeschlossene Großumbauten dokumentieren
- ✅ zentrale Zustandsübersicht für Vector SDK, WirePod, Ollama, OpenAI und ElevenLabs ergänzen
- ✅ ungefährlichen Provider-Statusbefehl ohne kostenpflichtige Cloud-Anfrage bereitstellen
- ✅ providerbezogene Timeouts zentral benennen und validieren
- ✅ OpenAI-/Ollama- und ElevenLabs-/lokale-TTS-Fallbacks absichern
- ✅ Ausfall, begrenzte Wiederholung und einmalige Wiederherstellung behandeln
- ✅ strukturierte Providerereignisse ohne Fragen, Antworten, Dokumente oder Secrets ergänzen
- ✅ externe Ergebnisse vor der Sprachausgabe validieren
- ✅ verbindlichen Regressionstest-Ablauf in die Qualitätsregeln aufnehmen
- ✅ Windows-, Homeserver- und spätere Docker-Grenzen dokumentieren

## Voice Input

- ✅ mehrturnigen physischen Voice-Dialog stabilisieren
- ✅ firmwarefreie lokale Folgeaufnahme über den deutschen Windows-Erkenner implementieren
- ✅ lokale Folgeaufnahme am physischen Gesprächsfluss bestätigt
- ✅ Erkennungsfehler und Abbruchsignale behandeln
- ✅ doppelte WirePod-Reaktionen verhindern
- ✅ optionalen ElevenLabs-TTS-Pfad mit lokaler Freigabe und Fallback implementieren
- ✅ „Felix Serenitas“ mit Flash v2.5 physisch abnehmen
- ⏳ Multilingual v2 nur bei späterem Qualitätsbedarf gegen Flash vergleichen

## Memory und Bibliothek

- ✅ lokale providerunabhängige Embedding-Grundlage ergänzen
- ✅ `embeddinggemma` lokal prüfen und Batch-Embeddings integrieren
- ✅ Embedding-Vektoren für Dokumentabschnitte in SQLite speichern
- ✅ Dokumente automatisch und differentiell indexieren
- ✅ Modellwechsel erkennen und `/reindex ID` anbieten
- ✅ hybride semantische und lexikalische Suche ergänzen
- ✅ Datenschutz und Prompt-Injection-Schutz für Dokumentkontext absichern
- ✅ semantische Suche mit direkten Fragen und Paraphrasen evaluieren
- ✅ vollständigen lokalen Wissenspfad bis zur Vector-Wiedergabe testen
- ✅ Markdown- und Textdokumente kontrolliert importieren
- ✅ Quellen und Inhaltsprüfsummen speichern
- ✅ Versionshistorie, Modell- und Vektorstatus ergänzen
- ✅ getrennten Metadaten- und Memory-Export anbieten
- ✅ vollständige Reindexierung und verifizierte Löschung ergänzen

## Tools und Sicherheit

- ✅ zentrale Tool Registry und einheitliche Schnittstelle implementieren
- ✅ Lese-, Änderungs- und Gefahrenstufen mit Bestätigung definieren
- ✅ sensible Audit-Parameter redigieren und Blockierungen testen
- ✅ erste produktive Robot-Tools mit expliziter Mutationsfreigabe anbinden
- ✅ Kopf, Lift, Kurzanimationen und Notfallstopp physisch prüfen
- ✅ deterministische Tool-Auswahl im Konsolen- und WirePod-Dialog ergänzen
- ✅ strukturierte Modellvorschläge ohne Ausführungs- oder Berechtigungsrecht prüfen
- ✅ kontextabhängige Ausdrucksvorschläge kontrolliert produktiv freigeben
- ✅ lokale Audit-Persistenz mit Aufbewahrungsregeln ergänzen
- ✅ erstes lokales Read-only-Bürotool für Datum und Uhrzeit ergänzen
- ✅ lokale Read-only-Projektstatus-Abfrage ohne freie Befehle ergänzen
- ✅ bestätigten lokalen Projekt-Testlauf ohne freie Befehle oder Rohlogs ergänzen
- ✅ lokalen Read-only-Systemstatus für WirePod und Ollama ergänzen
- ✅ lokalen count-only Bibliotheksstatus ohne Dokumentmetadaten ergänzen
- ✅ lokalen count-only Gedächtnisstatus ohne Erinnerungsinhalte ergänzen
- ✅ lokalen Read-only-Roadmapstatus für den nächsten sicheren Punkt ergänzen
- ✅ kontrollierten lokalen Dokumentationsstatus ohne freie Pfade ergänzen
- ✅ kontrollierte Recherchequelle mit explizitem Netzwerkrecht vorbereiten
- ✅ erste inhaltlich begrenzte Python-Versionsabfrage absichern
- ✅ kontrollierte letzte Projektänderung aus festem Changelog nennen
- ✅ lokalen count-only Codequalitätsstatus ohne freie Pfade ergänzen
- ✅ feste Übersicht freigegebener Projektdokumente ohne freie Pfade ergänzen
- ✅ kontrolliertes Öffnen genau eines freigegebenen Projektdokuments implementieren
- ✅ bestätigtes Öffnen eines Projektdokuments am Windows-Desktop physisch abgenommen
- ✅ kontrolliertes Öffnen des fest freigegebenen Dokumentationsordners implementieren
- ✅ bestätigtes Öffnen des Dokumentationsordners am Windows-Desktop physisch abgenommen
- ✅ lokalen Read-only-Status der letzten kontrollierten Tool-Aktion ergänzen
- ✅ Statusabfrage der letzten Tool-Aktion am physischen Vector abnehmen

## Codequalität und Dokumentation

- ✅ alle produktiven Funktionen und Methoden mit deutschen Docstrings erklären

## Robot Personality

- ✅ kontrolliertes emotionales Zustandsmodell implementieren
- ✅ philosophische Reflexionsschicht implementieren
- ✅ Deutsch auf C1-Niveau mit Beispieldialogen systematisch prüfen
- ✅ bestätigtes Stilfeedback providerunabhängig berücksichtigen
- ✅ Ausdruckshinweise kontrolliert auf freigegebene Animationen abbilden
- ✅ bestätigte Ausdrucksanimation und Vector-Sprache sequenziell synchronisieren
- ✅ expliziten Ausdrucksdialog für Konsole und WirePod kontrolliert aktivieren
- ✅ stärkeres festes Reflexionsprofil für Bewegung und Prosodie implementieren
- ✅ erstes reflektiertes Bewegungs- und Sprachprofil physisch verbessern und abnehmen
- ✅ natürliche Satzmelodie und eigenständiger wirkende Reflexion technisch fein abstimmen
- ✅ fein abgestimmte Satzmelodie am physischen Vector subjektiv abnehmen
- ✅ drei lokale zufällige Reflexionseinleitungen physisch auf Natürlichkeit prüfen
- ✅ Gesprächstypen auf feste unterstützende und vorsichtige TTS-Profile abbilden
- ✅ unterstützende und vorsichtige Prosodie am physischen Vector fein abgestimmt
