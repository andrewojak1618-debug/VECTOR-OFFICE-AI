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

`DRIVE_ACTIONS_ENABLED` bleibt `False`. Beide Animationen werden zusätzlich mit
`ignore_body_track=True` ausgeführt. Dadurch können sie keine enthaltene
Radspur übernehmen.

## Zentrale BehaviorControl

`vector/behavior_control.py` besitzt die einzige Laufzeitsperre für Sprache und
Aktionen. Eine zweite Operation wartet nicht unbemerkt, sondern wird sofort als
Konflikt abgewiesen. Der gleiche `BehaviorControl` wird in der Runtime an
`VectorSDKClient`, deutsche TTS und `VectorActions` weitergegeben.

Die SDK-Verbindung verwendet ausschließlich `DEFAULT_PRIORITY`. Die gefährliche
Override-Priorität wird nicht eingesetzt; Vectors verpflichtende physische
Schutzreaktionen bleiben damit über der Anwendung.

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
```

Am 14. August 2026 wurden alle sechs Befehle nacheinander über den physischen
Vector erfolgreich abgeschlossen. `head_level` und `lift_down` stellten danach
die neutrale Position wieder her. Der Notfallstopp wurde anschließend im
Leerlauf ebenfalls erfolgreich bestätigt.
