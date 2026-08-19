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

`ExpressionCue` bleibt ein nicht ausführbares Metadatum. Das lokale Modul
`brain/expression_actions.py` bildet den Cue kontrolliert auf eine feste
Vorschlags-ID ab und lässt das Ziel erneut durch `ToolProposalReviewer` gegen
die aktuelle Registry prüfen.

## Kontrollierte Ausdruckszuordnung

Die Zuordnung verwendet ausschließlich feste, bereits geprüfte Profile:

| Ausdruckshinweis | lokaler Vorschlag | Wirkung |
|---|---|---|
| `neutral` oder Intensität 0 | kein Vorschlag | keine Aktion |
| `attentive` | `vector.eyes_only` | nur geprüfter Vorschlag |
| `supportive` | `vector.eyes_only` | nur geprüfter Vorschlag |
| `reflective` | `vector.reflective_expression` | feste Kopf-Augen-Kopf-Sequenz |

Freie Kopfparameter, Begrüßung, Lift und Fahrbewegungen werden nicht aus einer
simulierten Gesprächshaltung abgeleitet. Das reflektierte Profil darf nur den
festen 18-Grad-Kopfwinkel, die Augenanimation und die Rückkehr auf 0 Grad
verwenden. Das Ergebnis enthält weder Nutzersatz noch
Zustandsgrund, erzeugt keine Berechtigung und ruft kein Tool auf. Fehlt das Ziel
in der Registry oder erfüllt es die Sicherheitsregeln nicht mehr, wird der
Vorschlag lokal blockiert. Die produktive Aktivierung, eine separate
Benutzerbestätigung und die tatsächliche Roboterausführung bleiben getrennt.
`application/expression_delivery.py` stellt den sicheren sequenziellen Ablauf
bereit: zuerst die vollständig abgeschlossene feste Ausdruckssequenz, danach
TTS. `vector/speech_prosody.py` ordnet jedem Cue ausschließlich ein festes,
lokales SSML-Profil zu. Das normale Gesprächsprofil behält die physisch
bestätigte Satzmelodie. `supportive` spricht etwas ruhiger und sanfter,
`attentive` markiert Grenzen mit geringfügig längeren Pausen und `reflective`
behält das bereits abgestimmte Reflexionsprofil. Die dynamische Prosodie gilt
auch für normale Antworten; Bewegungen bleiben weiterhin ausschließlich nach
`Mit Ausdruck ...` und einer separaten Bestätigung möglich.

| Ausdruckshinweis | Sprachprofil | begrenzte Wirkung |
|---|---|---|
| `neutral` | `CONVERSATIONAL` | bestätigte natürliche Gesprächsprosodie |
| `supportive` | `SUPPORTIVE` | etwas ruhigeres Tempo und sanftere Gesamtlage |
| `attentive` | `CAUTIOUS` | ruhige Grenzmarkierung mit kurzen Zusatzpausen |
| `reflective` | `REFLECTIVE` | leicht reduziertes Tempo für Reflexion |

Die Zuordnung verändert weder Antworttext noch Gesprächstyp und behauptet keine
echten Gefühle. Unbekannte oder fehlende Zustände fallen auf das bestätigte
Gesprächsprofil zurück.

Jeder vollständige Satz bleibt innerhalb eines einzigen Prosodieblocks. Es gibt
keine getrennten Lautstärke- oder Tonhöhenblöcke für Satzanfang, Satzmitte und
Satzende mehr. Dadurch kann OneCore die deutsche Aussprache und Satzmelodie
durchgehend formen; nur zwischen vollständigen Sätzen liegt eine kurze,
profilabhängige Pause.

Vor jeder modellgestützten Antwort wählt die lokale TTS-Schicht unabhängig und mit
gleicher Chance genau eine feste Gesprächseinleitung: einen synthetischen
IPA-Summton, `Ich schätze` oder `Lass mich überlegen`. Die Auswahl besitzt
keinen Sitzungszustand;
Wiederholungen sind daher möglich. Die Einleitung stammt niemals vom
Sprachmodell, verändert die gespeicherte Antwort nicht und wird nicht als
tatsächliches menschliches Empfinden oder Bewusstsein dargestellt.
Der physisch ausgewählte IPA-Summton wird intern mit minus 32 Prozent Tempo
erzeugt und dauert lokal gemessen rund 1,54 Sekunden. Anschließend folgen 1.500
Millisekunden Pause. `Lass mich überlegen` erhält 2.000 Millisekunden und
`Ich schätze` bleibt bei 320 Millisekunden. Geschriebene Varianten wie `Hmmm`
oder `Mmmm` wurden entfernt, weil OneCore sie unnatürlich aussprach.

Die Antwortberechnung beginnt unmittelbar nach der erkannten Frage in einem
einzelnen Hintergrundarbeiter. Währenddessen wird die gewählte Einleitung lokal
gesprochen. Nach fertiger Modellantwort werden TTS und FFmpeg im selben
Hintergrundpfad vorbereitet. Die bereits fertige WAV-Datei wartet auf das Ende
der Einleitung, sodass keine Audios gleichzeitig laufen und danach keine zweite
TTS-Wartephase nötig ist. Direkte Befehle, Sicherheitsaktionen und Bestätigungen
erhalten keine künstliche Denkphase.

## Optionale Reflexionsschicht

`brain/reflection.py` aktiviert die Reflexion nur bei eindeutig passenden
Themen wie Ethik, Freiheit, Gerechtigkeit, Bewusstsein oder Lebenssinn.
`REFLECTION_ENABLED=false` schaltet diese Zusatzführung vollständig ab.

Eine reflektierte Antwort soll:

- Tatsachen nicht mit Interpretation vermischen,
- eine Perspektive als mögliche Sichtweise kennzeichnen,
- relevante Unsicherheit offen benennen,
- verständlich und unaufdringlich bleiben,
- aktive Verben statt abstrakter Aufzählungen und Nominalketten verwenden,
- wie gesprochene Reflexion und nicht wie ein Manuskript klingen,
- mit einem greifbaren Kerngedanken statt einer Lexikondefinition beginnen,
- gesprochene Sätze möglichst unter 18 Wörtern halten,
- standardmäßig höchstens zwei Sätze enthalten.

Alle direkten und reflektierten Antworten sollen außerdem aus vollständigen,
idiomatischen deutschen Sätzen bestehen. Ein Satz enthält ein erkennbares
Subjekt und ein finites Verb. Telegrammstil und alleinstehende Fragmente wie
`Funktioniert gut` werden nicht als natürliche Gesprächsantwort akzeptiert.

Fordert der Benutzer ausdrücklich eine ausführliche oder detaillierte Antwort,
wird ausschließlich die Satzgrenze kontrolliert auf maximal acht Sätze
erweitert.

## Verbindliche Antwortprüfung

Ein Prompt allein garantiert keine Regelbefolgung. Deshalb prüft
`ResponseQualityPolicy` jede interne Modellantwort vor Speicherung und TTS auf:

- Behauptungen eigener Gefühle,
- Formeln falscher absoluter Gewissheit,
- deutlich belehrende Formulierungen,
- typische alleinstehende Prädikatsfragmente,
- Überschreitung der erlaubten Satzanzahl.

Bei einem Verstoß erhält derselbe Provider genau einen Korrekturversuch mit
neutralen Fehlercodes, niemals mit protokolliertem Antwortinhalt. Verstößt auch
die zweite Antwort gegen eine Inhaltsregel, wird sie verworfen und nicht
gesprochen. Bleibt ausschließlich die Satzgrenze verletzt, werden vollständige
führende Sätze bis zum erlaubten Maximum übernommen und erneut validiert.

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
