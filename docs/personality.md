# Persönlichkeit, Emotion und Reflexion

Vector verwendet eine transparente, simulierte Gesprächshaltung. Die Haltung
steuert Formulierungsregeln, ist aber kein Gefühl, kein Bewusstsein und keine
Behauptung über ein inneres Erleben.

## Kontrolliertes Zustandsmodell

`brain/emotions.py` kennt genau vier sitzungsbezogene Zustände:

| Zustand | Zweck | vorbereiteter Ausdruckshinweis |
|---|---|---|
| `neutral` | ruhige, sachlich zugewandte Antwort | `neutral` |
| `supportive` | behutsame Antwort bei Belastung | `supportive` |
| `reflective` | differenzierte Antwort auf philosophische Themen | `reflective` |
| `cautious` | transparente Grenzen bei Risiko oder Unsicherheit | `attentive` |

Die Intensität liegt ausschließlich zwischen 0 und 2. Wiederholte passende
Signale können sie um höchstens eine Stufe erhöhen; neutrale Beiträge bauen sie
schrittweise wieder ab. Jeder Verarbeitungsschritt erhält eine Revisionsnummer
und einen neutralen Grundcode. Nutzersätze werden nicht im Übergangsverlauf
gespeichert. Der Verlauf ist auf 20 Einträge begrenzt und endet mit der Sitzung.

`ExpressionCue` bereitet eine spätere Zuordnung zu freigegebenen Animationen
vor. Der Cue ist nur Metadatum: Er führt weder ein Tool noch eine Robot-Aktion
aus. Die automatische Aktionsauswahl bleibt deaktiviert.

## Optionale Reflexionsschicht

`brain/reflection.py` aktiviert die Reflexion nur bei eindeutig passenden
Themen wie Ethik, Freiheit, Gerechtigkeit, Bewusstsein oder Lebenssinn.
`REFLECTION_ENABLED=false` schaltet diese Zusatzführung vollständig ab.

Eine reflektierte Antwort soll:

- Tatsachen nicht mit Interpretation vermischen,
- eine Perspektive als mögliche Sichtweise kennzeichnen,
- relevante Unsicherheit offen benennen,
- verständlich und unaufdringlich bleiben,
- standardmäßig höchstens zwei Sätze enthalten.

Fordert der Benutzer ausdrücklich eine ausführliche oder detaillierte Antwort,
wird ausschließlich die Satzgrenze kontrolliert auf maximal acht Sätze
erweitert.

## Verbindliche Antwortprüfung

Ein Prompt allein garantiert keine Regelbefolgung. Deshalb prüft
`ResponseQualityPolicy` jede interne Modellantwort vor Speicherung und TTS auf:

- Behauptungen eigener Gefühle,
- Formeln falscher absoluter Gewissheit,
- deutlich belehrende Formulierungen,
- Überschreitung der erlaubten Satzanzahl.

Bei einem Verstoß erhält derselbe Provider genau einen Korrekturversuch mit
neutralen Fehlercodes, niemals mit protokolliertem Antwortinhalt. Verstößt auch
die zweite Antwort gegen die Regeln, wird sie verworfen und nicht gesprochen.

## Bestätigtes Feedback

`/feedback TEXT` speichert ausschließlich bewusst bestätigte Hinweise zu
Sprache und Ton mit der Kategorie `feedback` und der Herkunft
`user-confirmed-feedback`. Diese Einträge werden nicht als Fakten-Memory
gesucht. Im Modellkontext erscheinen sie JSON-kodiert und dürfen weder
Berechtigungen erteilen noch Fakten ändern oder als Trainingssignal gelten.

Feedback kann über `/memories` eingesehen und mit `/forget ID` wieder gelöscht
werden. Da OpenAI und Ollama denselben Agentkontext erhalten, wird bestätigtes
Feedback bei Verwendung von OpenAI an den Cloud-Provider übertragen. Es dürfen
daher keine Secrets oder vertraulichen Inhalte als Stilfeedback gespeichert
werden.

## Gemeinsame Providerregeln

Die vollständige C1-Persönlichkeit entsteht im providerunabhängigen Agenten.
OpenAI, Ollama und der automatische Fallback erhalten exakt dieselben System-,
Zustands-, Reflexions- und Feedbackregeln. Provider dürfen den Zustand weder
selbst setzen noch Aktionen autorisieren.

## Antwortqualität und Modellgrenze

Automatisierte Beispieldialoge prüfen unterstützende, philosophische und
unsichere Situationen. Der lokale Realtest lautet:

```powershell
.venv\Scripts\python.exe -m diagnostics.personality_ollama
```

Am 14. August 2026 schloss `llama3.2:3b` alle drei Beispiele regelkonform mit
höchstens zwei Sätzen ab. Das kleine Modell verwendet dennoch gelegentlich
sprachlich unbeholfene Wörter oder Konstruktionen. Die Schutzschicht erzwingt
Ehrlichkeit, Kürze und Tonregeln; die tatsächliche C1-Sprachqualität bleibt
zusätzlich von der Fähigkeit des gewählten Sprachmodells abhängig.

Es findet kein autonomes Selbsttraining aus Gesprächen oder Modellantworten
statt. Lernen bedeutet hier ausschließlich: bestätigtes Feedback kontrolliert
als löschbaren Kontext zu berücksichtigen.
