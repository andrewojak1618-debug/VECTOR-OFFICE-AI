# Roadmap

## Release-Stabilisierung

- ✅ zentrale mehrstufige Systemabnahme implementieren
- ✅ lokale SQLite-Sicherung und Wiederherstellung automatisiert prüfen
- ✅ automatischen Kern vollständig abnehmen
- ✅ eingesetzte Ollama- und OpenAI-Provider live prüfen
- ✅ physischen Wissens- und Aktionspfad subjektiv bestätigen
- ✅ Versionsnummer und Changelog für `0.2.0-rc.1` festlegen
- ✅ ersten geprüften Git-Tag `v0.2.0-rc.1` historisch setzen

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

## Voice Input

- ✅ mehrturnigen physischen Voice-Dialog stabilisieren
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
