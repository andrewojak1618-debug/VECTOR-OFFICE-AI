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

`tools/audit_store.py` persistiert diese bereits bereinigten Ereignisse additiv
in der lokalen, durch `.gitignore` geschützten SQLite-Datei aus
`MEMORY_DB_PATH`. Gespeichert werden nur Zeitpunkt, Toolname,
Berechtigungsstufe, redigierte flache Argumente, Ergebnisstatus und neutraler
Fehlercode. Tool-Ausgaben, Nutzersätze, Modellantworten, Dokumentinhalte,
Embeddings und interne Exceptions gehören nicht zur Audit-Tabelle.

Die lokale Persistenz ist standardmäßig aktiviert und doppelt begrenzt:

- `TOOL_AUDIT_RETENTION_DAYS=30` entfernt ältere Ereignisse,
- `TOOL_AUDIT_MAX_ENTRIES=1000` behält nur die neuesten Ereignisse,
- beide Regeln werden nach jedem neuen Eintrag und über einen manuellen
  Bereinigungsbefehl angewendet,
- `TOOL_AUDIT_ENABLED=false` deaktiviert die Persistenz vollständig.

Ein Fehler beim Initialisieren oder Schreiben des Audit-Ziels blockiert keine
Toolaktion. Die Runtime arbeitet dann mit einer neutralen Warnung ohne lokale
Persistenz weiter. Die additive Tabelle verändert oder löscht keine Memory-,
Dokument-, Versions- oder Embedding-Daten.

`diagnostics/tool_audit.py` bietet ausschließlich lokale Wartungsbefehle:

```powershell
.venv\Scripts\python.exe -m diagnostics.tool_audit list --limit 20
.venv\Scripts\python.exe -m diagnostics.tool_audit prune
.venv\Scripts\python.exe -m diagnostics.tool_audit clear --confirm DELETE
```

Das vollständige Löschen verlangt die exakte Bestätigung `DELETE` und betrifft
nur die Audit-Tabelle.

## Nebenwirkungsfreier Test

`tools/test_tools.py` enthält `EchoTestTool`. Es besitzt ausschließlich
`READ_ONLY`, gibt einen öffentlichen Testtext strukturiert zurück, ignoriert
den optionalen sensiblen Testparameter und greift weder auf Netzwerk,
Dateisystem, Datenbank noch Vector zu. Es wird nicht automatisch in der
Produktiv-Runtime registriert.

Der Agent besitzt mit `execute_tool(...)` einen expliziten Übergabepunkt. Die
Runtime registriert die kontrollierte Vector-Aktion, den Notfallstopp, die rein
lesende Anzeige der sicheren Aktionsnamen und das lokale Datums-/Uhrzeittool.
Bewegungen bleiben ohne eine explizite Mutationsfreigabe blockiert. Weitere
produktive Toolaufrufe sind standardmäßig nicht registriert.

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
| Datum/Uhrzeit | „Welcher Tag ist heute?“, „Wie spät ist es?“ | automatisch, lokal und rein lesend |
| Aktionen anzeigen | „Welche Aktionen kannst du?“ | automatisch, rein lesend |
| Kopf bewegen | „Schau nach oben“, „Kopf gerade“ | Bestätigung erforderlich |
| Lift bewegen | „Lift nach oben“, „Lift nach unten“ | Bestätigung erforderlich |
| Animation | „Begrüße mich“, „Zeige deine Augen“ | Bestätigung erforderlich |
| Sicherheit | „Notfallstopp“, „Stopp sofort“ | sofortiger Notfallstopp |

## Lokales Bürotool für Datum und Uhrzeit

`tools/office.py` registriert `office.local_datetime` mit `READ_ONLY`. Das Tool
greift nur auf die lokale Systemzeit zu und besitzt weder Netzwerk- noch
Dateizugriff. Die feste Absichtsauswahl liefert ausschließlich `mode=date` oder
`mode=time`; andere Werte werden innerhalb der Registry fehlerneutral
abgewiesen. Deutsche Wochentage und Monatsnamen sind lokal definiert und nicht
von einer installierten Betriebssystemsprache abhängig.

Beobachtete Vosk-Varianten wie `Welchen Tag haben wir heute?` sind ebenfalls
fest freigegeben. Eine erkennbare Datums- oder Uhrzeitfrage außerhalb dieser
Allowlist wird mit einer neutralen Wiederholungsbitte blockiert. Sie fällt
bewusst nicht an OpenAI oder Ollama durch, damit ein Modell kein aktuelles Datum
oder eine Uhrzeit erfinden kann. Im physischen Test erwies sich `Welcher Tag ist
heute?` als zuverlässige bevorzugte Formulierung.

Die strukturierte Ausgabe enthält nur ISO-Datum, lokale Uhrzeit, Zeitzonenname
und einen lokal aufgebauten deutschen Sprechsatz. Nutzereingaben, Modelltexte,
Dateiinhalte und Secrets werden weder benötigt noch als Toolausgabe erzeugt.

## Strukturierte Modellvorschläge

`tools/proposals.py` bildet die lokale Prüfgrenze für kontextabhängige
Vorschläge. OpenAI oder Ollama dürfen dort ausschließlich ein
kleines JSON-Objekt mit `schema_version` und einer abstrakten `proposal_id`
zurückgeben. Sie erhalten keine Toolnamen, Parameterwerte oder
`ToolAuthorization`-Objekte zur freien Erzeugung.

`application/model_tool_proposals.py` erstellt für beide Provider denselben
isolierten Klassifikationsprompt. Die Nutzeranfrage wird als unvertrauenswürdige
JSON-Dateneingabe übertragen. Der Modelltext wird anschließend lokal streng
geprüft:

- exakt ein JSON-Objekt, kein Markdown und kein Begleittext,
- keine doppelten oder zusätzlichen Felder,
- nur lokale IDs aus `SAFE_VECTOR_PROPOSAL_OPTIONS`,
- feste lokale Abbildung von ID auf Toolname und Parameter,
- erneute Prüfung gegen die tatsächlich registrierte Tooldefinition,
- vollständiger Ausschluss gefährlicher und sensibler Tooldefinitionen,
- keine Registry-Ausführung, kein Audit-Ereignis und keine Berechtigung.

`tools/inspection.py` enthält dafür nur den unveränderlichen Prüfbefund. Die
eigentliche Namens- und Parameterprüfung bleibt in `tools/registry.py`. Der
Notfallstopp gehört ausdrücklich nicht zum Modellkatalog. Ein Ergebnis ist nur
ein `ToolProposal`-Datenobjekt; selbst ein gültiger Vorschlag bewirkt noch keine
Bewegung.

`application/contextual_tool_conversation.py` aktiviert diese Grenze nur nach
der eindeutigen Einleitung `Schlage eine passende Aktion vor: ...` oder
`Welche Aktion passt dazu: ...`. Gewöhnliche Gesprächsrunden erzeugen deshalb
weder einen zweiten Modellaufruf noch einen versteckten Aktionsvorschlag. Der
produktive Katalog ist gegenüber dem allgemeinen Prüfkatalog zusätzlich auf
das sichtbare feste Profil `vector.reflective_expression` eingeschränkt. Die
dezente Aktion `vector.eyes_only` bleibt explizit aufrufbar, wird aber nicht
mehr als kontextabhängiger Vorschlag verwendet.

Falls WirePod die Aufnahme nach `Welche Aktion passt dazu?` beendet, wird noch
kein Modell aufgerufen. Stattdessen kann genau die nächste Spracheingabe
innerhalb von 30 Sekunden den Kontext liefern. Abbruch, Ablauf und Sitzungsende
verwerfen dieses Kontextfenster ohne Vorschlag, Autorisierung oder Bewegung.

Ein akzeptierter Vorschlag wird höchstens 30 Sekunden und nur mit abstrakter
Vorschlags-ID sowie lokaler Bezeichnung gehalten. `Nein` oder `Abbrechen`
verwirft ihn. Erst ein separates exaktes `Ja` erzeugt eine einmalige
`ToolAuthorization`; unmittelbar davor wird die Vorschlags-ID erneut gegen die
aktuelle Registry geprüft. Fehler, unbekannte IDs, Schemaerweiterungen und
inzwischen nicht mehr verfügbare Ziele bleiben ohne Ausführung.

`brain/expression_actions.py` verwendet dieselbe lokale Prüfgrenze für
simulierte Ausdruckshinweise, jedoch ohne Modellaufruf. Nicht neutrale Cues
können ausschließlich `vector.eyes_only` oder das feste Profil
`vector.reflective_expression` vorschlagen. Letzteres besitzt lokal unveränderlich
die Parameter für 18 Grad Kopfneigung, eine Augenanimation und die Rückkehr auf
0 Grad. Auch dieser Pfad erzeugt keine Autorisierung, keine Registry-Ausführung
und kein Audit-Ereignis. Freie Kopfparameter, Begrüßung, Lift, Fahrbewegung und
Notfallstopp sind von dieser automatischen Zuordnung ausgeschlossen.

`application/expression_delivery.py` darf einen solchen Vorschlag nur mit einem
separaten `ToolAuthorization` ausführen, dessen Mutationsfreigabe und
Einzelbestätigung beide gesetzt sind. Die Autorisierung wird nicht gespeichert.
Nach der synchronen Registry-Rückgabe beginnt TTS; eine parallele Umgehung der
zentralen `BehaviorControl` findet nicht statt.

`application/expression_conversation.py` aktiviert diesen Pfad nur für die
deterministisch erkannte Form `Mit Ausdruck ...`. Zuerst wird die Antwort
vorbereitet, dann eine gesonderte Ja/Nein-Frage gestellt. Nur ein nachfolgendes
exaktes Ja erzeugt die einmalige Autorisierung. Nein liefert dieselbe Antwort
ohne Bewegung, behält bei reflektierten Fragen jedoch das begrenzte TTS-Profil;
Abbruch, Notfallstopp und behandelte Konsolenbefehle verwerfen den offenen
Ausdrucksvorschlag.

## Robot-Aktionen

`tools/vector_actions.py` stellt `vector.list_actions`,
`vector.perform_action` und `vector.emergency_stop` bereit. Der Aktionsname wird zusätzlich in
`vector/actions.py` gegen eine feste Allowlist geprüft. Freie Winkel,
Animationsnamen und Fahrbefehle erreichen die SDK-Grenze nicht. Die vollständige
Allowlist, Timeouts und Hardwaretests sind unter
[Kontrollierte Robot-Aktionen](robot-actions.md) dokumentiert.

## Noch nicht freigegeben

Folgende Funktionen sind weiterhin bewusst nicht freigegeben:

- automatische Modellvorschläge ohne ausdrückliche Aktivierungsform,
- automatische Ausführung von Ausdrucksvorschlägen,
- dauerhafte Berechtigungsfreigaben,
- Dateiänderungen, Shell-Kommandos oder Internetzugriffe,
- Auswahl von Toolnamen, Parametern oder Autorisierungen durch ein Modell,
- Ausführung von Toolanweisungen aus importierten Dokumenten.

Jedes zukünftige produktive Tool benötigt eigene Parameter-, Berechtigungs-,
Fehler- und Regressionstests, bevor es registriert werden darf.
