# Physischer Wissenspfad mit Ollama und Vector

Dieser Diagnosepfad prüft die vollständige Strecke von einem ungefährlichen
Projektdokument bis zur hörbaren deutschen Antwort des physischen Vector.
OpenAI ist an keiner Stelle beteiligt.

## Wiederholbarer Befehl

```powershell
.venv\Scripts\python.exe -m diagnostics.knowledge_vector
```

Der Ablauf verwendet ausschließlich temporäre Index- und Datenbankdateien. Als
kontrollierte Quelle dient `docs/paraphrase-evaluation.md`.

## Ablauf

1. lokalen Ollama-Dienst prüfen,
2. Projektdokument in eine temporäre Bibliothek importieren,
3. Dokumentabschnitte lokal mit `embeddinggemma` indexieren,
4. eine bewusst anders formulierte Frage lokal einbetten,
5. besten hybriden Treffer samt Quelle und Bewertung anzeigen,
6. Antwort ausschließlich mit `llama3.2:3b` erzeugen,
7. Ergebnis auf höchstens zwei Sätze begrenzen,
8. erwarteten Wissenswert automatisch validieren,
9. deutsche TTS mit Microsoft Stefan erzeugen,
10. WAV-Datei physisch über Vector wiedergeben.

## Erfolgreicher Lauf vom 14. August 2026

| Prüfschritt | Ergebnis |
|---|---|
| Projektdokument | `paraphrase-evaluation.md`, 3 Abschnitte |
| bester Treffer | Abschnitt 2 |
| kombinierter Trefferwert | `0,683` |
| semantische Ähnlichkeit | `0,423` |
| Antwortanbieter | ausschließlich lokales Ollama |
| erwarteter Wissenswert | `0,35` enthalten |
| Antwortlänge | 2 Sätze |
| Vector-Verbindung | erfolgreich, Batterie `4,04 V` |
| deutsche Stimme | Microsoft Stefan |
| konfigurierte Lautstärke | `90` |
| Audiostream | vollständig wiedergegeben |

Die technische Antwortqualität bestand: Der erwartete Wert war enthalten und
die Zwei-Satz-Grenze wurde eingehalten. Die SDK-Rückmeldung bestätigt die
vollständige Wiedergabe. Aussprache, subjektive Lautstärke und Natürlichkeit
müssen beim jeweiligen Lauf von einer hörenden Person bewertet werden.

## Datenschutz

Die Diagnose zeigt nur Quellname, Abschnittsnummer und numerische Bewertungen.
Dokumenttext, Frage und Vektorwerte werden nicht protokolliert. Temporäre
Bibliotheks- und Audiodateien werden nach dem Lauf automatisch entfernt.
