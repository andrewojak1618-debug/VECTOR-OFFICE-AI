# Kontrollierte Robot-Aktionen

Vector darf nur fest definierte, lokal geprüfte Aktionen ausführen. Freie
SDK-Befehle, beliebige Winkel, beliebige Animationsnamen und Fahrbewegungen
werden nicht an den Agenten oder die Tool Registry weitergereicht.

## Aktionsliste

| Aktionsname | Wirkung | feste Begrenzung |
|---|---|---|
| `head_up` | Kopf anheben | 25 Grad |
| `head_level` | Kopf neutral stellen | 0 Grad |
| `lift_up` | Lift anheben | 70 Prozent |
| `lift_down` | Lift absenken | 0 Prozent |
| `greeting` | kurze Begrüßungsanimation | `ReactToGreeting`, ein Durchlauf |
| `eyes_only` | kurze Augenanimation | `ObservingIdleEyesOnly`, ein Durchlauf |
| `reflective_expression` | reflektierte Kopf- und Augenbewegung | 18 Grad, Augenanimation, zurück auf 0 Grad |

`DRIVE_ACTIONS_ENABLED` bleibt `False`. Alle Animationen werden zusätzlich mit
`ignore_body_track=True` ausgeführt. Dadurch können sie keine enthaltene
Radspur übernehmen.

Jeder der drei primitiven Schritte des reflektierten Profils erhält den
konfigurierten Einzelaktions-Timeout. Der erste Hardwaretest zeigte, dass eine
Aufteilung des Timeouts auf drei Schritte die zulässige Augenanimation zu früh
abbrach; der Notfallstopp reagierte dabei wie vorgesehen. Die korrigierte
Fassung verlängert keinen einzelnen SDK-Aufruf über die allgemeine Grenze.

## Zentrale BehaviorControl

`vector/behavior_control.py` besitzt die einzige Laufzeitsperre für Sprache und
Aktionen. Eine zweite Operation wartet nicht unbemerkt, sondern wird sofort als
Konflikt abgewiesen. Der gleiche `BehaviorControl` wird in der Runtime an
`VectorSDKClient`, deutsche TTS und `VectorActions` weitergegeben.

Die SDK-Verbindung verwendet ausschließlich `DEFAULT_PRIORITY`. Die gefährliche
Override-Priorität wird nicht eingesetzt; Vectors verpflichtende physische
Schutzreaktionen bleiben damit über der Anwendung.

## Sequenzielle Ausdrucks- und Sprachausgabe

`application/expression_delivery.py` koordiniert eine zuvor geprüfte
Ausdrucksempfehlung und die deutsche Antwortausgabe. Die Animation wird niemals
parallel zur Sprache gestartet. Der Ablauf lautet:

1. nur die cuegebundenen Profile `vector.eyes_only` und
   `vector.reflective_expression` als Ausdrucksvorschlag akzeptieren,
2. eine explizite, auf diesen Aufruf begrenzte Bestätigung verlangen,
3. die Animation vollständig durch Tool Registry und `BehaviorControl` führen,
4. erst nach ihrem Abschluss die deutsche TTS-Ausgabe beginnen,
5. nur bei reflektierten Antworten das begrenzte SSML-Sprechprofil verwenden.

Ohne vollständige Bestätigung wird keine Animation ausgeführt und die Antwort
nur gesprochen; eine ausdrücklich reflektierte Antwort behält dabei ihre ruhige
Prosodie. Schlägt die Animation fehl, versucht die Koordination ebenfalls
die Sprachausgabe, ohne eine andere Bewegung als Ersatz zu starten. Schlägt TTS
fehl, enthält das Ergebnis nur einen neutralen Fehlercode und niemals den
gesprochenen Text. Die produktive Gesprächsschleife aktiviert diesen
Koordinator ausschließlich nach der eindeutigen Eingabe `Mit Ausdruck ...` und
einem anschließenden separaten Ja. Normale Antworten bleiben vollständig
bewegungslos.

`application/expression_conversation.py` hält dafür höchstens eine vorbereitete
Antwort im Arbeitsspeicher. `Nein` spricht sie ohne Animation, `Abbrechen`
verwirft sie vollständig. Ein Notfallstopp oder ein behandelter Konsolenbefehl
löscht den offenen Vorschlag ebenfalls. Die Freigabe gilt nur für diesen einen
Ablauf und wird unmittelbar danach vergessen. Ein interner
`ConversationCheckpoint` stellt bei einem vollständigen Verwerfen zusätzlich
den vorherigen Sitzungskontext wieder her; eine nie ausgegebene Antwort bleibt
damit nicht unsichtbar als bereits gesprochen im Modellverlauf stehen.

## Timeouts und Notfallstopp

`ROBOT_ACTION_TIMEOUT` begrenzt Aktionen standardmäßig auf acht Sekunden und
kann nur zwischen einer und 30 Sekunden konfiguriert werden. Bei Überschreitung
wird die aktive SDK-Future abgebrochen, `stop_all_motors` gesendet und der
Notfallzustand verriegelt. Neue Sprache und Aktionen bleiben danach gesperrt,
bis die Situation geprüft und die Sperre bewusst zurückgesetzt oder die
Anwendung neu gestartet wurde.

`vector.emergency_stop` ist zusätzlich als mutierendes Registry-Tool vorhanden.
Es verlangt wie jede physische Aktion eine explizite Benutzerfreigabe. Der
direkte Diagnosebefehl lautet:

```powershell
.venv\Scripts\python.exe -m diagnostics.vector_actions emergency_stop
```

## Tool Registry

Die produktive Runtime registriert ausschließlich:

- `vector.perform_action` mit einem Namen aus der festen Allowlist,
- `vector.emergency_stop` ohne Aktionsparameter.

Beide Tools besitzen `MUTATING` und benötigen `allow_mutation=True` aus einer
eindeutigen Benutzerinteraktion. Das Sprachmodell wählt oder autorisiert diese
Tools noch nicht automatisch. Nicht freigegebene Namen wie `drive_forward`
werden vor jedem SDK-Aufruf blockiert.

## Wiederholbare physische Prüfung

Jede Aktion wird einzeln gestartet:

```powershell
.venv\Scripts\python.exe -m diagnostics.vector_actions head_up
.venv\Scripts\python.exe -m diagnostics.vector_actions head_level
.venv\Scripts\python.exe -m diagnostics.vector_actions lift_up
.venv\Scripts\python.exe -m diagnostics.vector_actions lift_down
.venv\Scripts\python.exe -m diagnostics.vector_actions greeting
.venv\Scripts\python.exe -m diagnostics.vector_actions eyes_only
.venv\Scripts\python.exe -m diagnostics.vector_actions reflective_expression
```

Am 14. August 2026 wurden die damaligen sechs Befehle nacheinander über den physischen
Vector erfolgreich abgeschlossen. `head_level` und `lift_down` stellten danach
die neutrale Position wieder her. Der Notfallstopp wurde anschließend im
Leerlauf ebenfalls erfolgreich bestätigt. Das neue reflektierte Profil wurde am
17. August 2026 nach einer sicheren Timeout-Korrektur ebenfalls vollständig am
physischen Vector ausgeführt. Der Benutzer bewertete Bewegung und Sprachwirkung
als besser als die Vorstufe; weitere Feinabstimmung bleibt ausdrücklich möglich.
