# Tool Registry und Berechtigungen

Die Tool Registry ist die einzige vorgesehene Ausführungsgrenze für spätere
Büro-, Datei-, Recherche- und Robot-Aktionen. Ein Sprachmodell darf weder
Python-Funktionen direkt aufrufen noch Toolnamen oder Berechtigungen selbst
freischalten.

## Sicherheitsgrundsatz

Jeder Aufruf durchläuft dieselbe Reihenfolge:

1. Toolname in der zentralen Registry nachschlagen.
2. Parameter gegen das deklarierte Schema prüfen.
3. Berechtigungsstufe aus der registrierten Definition lesen.
4. explizite Benutzerfreigabe und gegebenenfalls Bestätigung prüfen.
5. Tool innerhalb einer abgefangenen Fehlergrenze ausführen.
6. strukturiertes Ergebnis an den Agenten zurückgeben.
7. optional ein ausschließlich bereinigtes Audit-Ereignis erzeugen.

Nicht registrierte Tools werden immer mit `tool_not_registered` blockiert.
Unbekannte, fehlende oder typfalsche Parameter erreichen die Tool-Implementierung
nicht.

## Einheitliche Tool-Schnittstelle

Jedes Tool stellt eine unveränderliche `ToolDefinition` mit folgenden Angaben
bereit:

- sicherer, eindeutiger Name,
- kurze Beschreibung,
- Berechtigungsstufe,
- Parametername, Beschreibung, Datentyp und Pflichtstatus,
- Kennzeichen für sensible Parameter.

Die erste Version unterstützt bewusst nur flache Werte vom Typ String, Integer,
Number und Boolean. Ergebnisse werden als `ToolExecutionResult` mit Status,
sicherer Meldung, Fehlercode und flachen strukturierten Ausgabefeldern
zurückgegeben. Beliebige Objekte oder ungeprüfte Exceptions gelangen nicht an
den Agenten.

## Berechtigungsstufen

| Stufe | Bedeutung | notwendige Autorisierung |
|---|---|---|
| `READ_ONLY` | liest oder berechnet ohne externen Zustand zu verändern | standardmäßig erlaubt |
| `MUTATING` | verändert kontrollierten Zustand | `allow_mutation=True` aus einer expliziten Benutzeraktion |
| `DANGEROUS` | kann schwer rückgängig zu machende Auswirkungen haben | Mutationsfreigabe und zusätzliche Bestätigung dieses Aufrufs |

Eine Modellantwort darf niemals selbst ein `ToolAuthorization`-Objekt erzeugen.
Die spätere Oberfläche muss Freigaben aus einer eindeutigen Benutzerinteraktion
ableiten. Eine Bestätigung gilt nur für den konkreten Aufruf und wird nicht als
globale Dauerfreigabe behandelt.

## Audit und sensible Parameter

Audit-Ausgaben sind optional und erhalten nur registrierte Parameternamen.
Parameter mit `sensitive=True` werden durch `[REDACTED]` ersetzt. Bei einem
unbekannten Tool werden grundsätzlich keine übergebenen Argumente in das
Audit-Ereignis übernommen. Tool-Exceptions werden auf den neutralen Fehlercode
`tool_execution_failed` reduziert.

Ein Audit-Ziel darf den Toolablauf nicht unterbrechen. Auch Fehler des
Audit-Sinks werden deshalb an dieser Grenze abgefangen.

## Nebenwirkungsfreier Test

`tools/test_tools.py` enthält `EchoTestTool`. Es besitzt ausschließlich
`READ_ONLY`, gibt einen öffentlichen Testtext strukturiert zurück, ignoriert
den optionalen sensiblen Testparameter und greift weder auf Netzwerk,
Dateisystem, Datenbank noch Vector zu. Es wird nicht automatisch in der
Produktiv-Runtime registriert.

Der Agent besitzt mit `execute_tool(...)` einen expliziten Übergabepunkt. Die
Runtime registriert ausschließlich die kontrollierte Vector-Aktion, den
Notfallstopp und die rein lesende Anzeige der sicheren Aktionsnamen. Bewegungen
bleiben ohne eine explizite Mutationsfreigabe blockiert. Weitere produktive
Toolaufrufe sind standardmäßig nicht registriert.

## Kontrollierte Auswahl im Gespräch

`tools/selection.py` ordnet eine kleine feste Liste eindeutiger deutscher
Formulierungen registrierten Tools zu. Es verwendet weder OpenAI noch Ollama und
ergänzt keine Parameter aus Vermutungen. Nur eine vollständige normalisierte
Übereinstimmung gilt als Auswahl; zusätzliche Anweisungen bleiben normale
Gesprächseingaben und lösen kein Tool aus.

`application/tool_conversation.py` hält höchstens einen offenen Vorschlag:

- `READ_ONLY` wird nach erfolgreicher Registry-Prüfung direkt ausgeführt,
- `MUTATING` wird zunächst nur vorgeschlagen und benötigt anschließend ein
  separates `Ja`, `Ja bitte`, `Bestätigen` oder `Ausführen`,
- `Nein`, `Abbrechen` oder `Nicht ausführen` verwirft den Vorschlag,
- andere Antworten halten die Aktion offen und erteilen keine Berechtigung,
- `DANGEROUS` wird in diesem Gesprächspfad grundsätzlich blockiert,
- ein exakter Notfallstopp unterbricht offene Vorschläge und wird sofort
  ausgeführt, weil Verzögerung die Schutzwirkung verschlechtern würde.

Die Bestätigung erzeugt genau ein `ToolAuthorization`-Objekt für diesen Aufruf
und wird danach vergessen. Das Sprachmodell sieht keine Tooldefinitionen,
wählt keinen Toolnamen und erzeugt weder Parameter noch Berechtigungen.

Der produktive Konsolentest wurde mit der Folge „Welche Aktionen kannst du?“,
„Begrüße mich“ und „Ja“ durchgeführt. Vector las die Allowlist ohne Bewegung
vor, stellte anschließend nur die Bestätigungsfrage und führte erst nach dem
separaten Ja genau eine Begrüßungsanimation aus. Die abschließende TTS-Ausgabe
erfolgte erst nach Ende der Animation.

### Freigegebene Formulierungen

| Absicht | Beispiele | Verhalten |
|---|---|---|
| Aktionen anzeigen | „Welche Aktionen kannst du?“ | automatisch, rein lesend |
| Kopf bewegen | „Schau nach oben“, „Kopf gerade“ | Bestätigung erforderlich |
| Lift bewegen | „Lift nach oben“, „Lift nach unten“ | Bestätigung erforderlich |
| Animation | „Begrüße mich“, „Zeige deine Augen“ | Bestätigung erforderlich |
| Sicherheit | „Notfallstopp“, „Stopp sofort“ | sofortiger Notfallstopp |

## Robot-Aktionen

`tools/vector_actions.py` stellt `vector.list_actions`,
`vector.perform_action` und `vector.emergency_stop` bereit. Der Aktionsname wird zusätzlich in
`vector/actions.py` gegen eine feste Allowlist geprüft. Freie Winkel,
Animationsnamen und Fahrbefehle erreichen die SDK-Grenze nicht. Die vollständige
Allowlist, Timeouts und Hardwaretests sind unter
[Kontrollierte Robot-Aktionen](robot-actions.md) dokumentiert.

## Noch nicht freigegeben

Folgende Funktionen sind bewusst nicht Teil dieser Karte:

- freie oder probabilistische Toolauswahl durch OpenAI oder Ollama,
- dauerhafte Berechtigungsfreigaben,
- Dateiänderungen, Shell-Kommandos oder Internetzugriffe,
- Auswahl oder Autorisierung von Robot-Aktionen durch ein Modell,
- Ausführung von Toolanweisungen aus importierten Dokumenten.

Jedes zukünftige produktive Tool benötigt eigene Parameter-, Berechtigungs-,
Fehler- und Regressionstests, bevor es registriert werden darf.
