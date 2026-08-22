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
| `NETWORK` | liest eine fest registrierte externe Quelle | `allow_network=True` und separate Bestätigung dieses Aufrufs |
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
Formulierungen registrierten Tools zu. `tools/selection_matching.py` kapselt
dabei ausschließlich die parameterlose kanonische Erkennung. Beide verwenden
weder OpenAI noch Ollama und
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
| Projektstatus | „Projekt Status“ | automatisch, lokal und rein lesend |
| Projekttests | „Projekt Test“ | feste lokale Suite, separates Ja erforderlich |
| Systemstatus | „System Status“ | feste lokale Dienste, rein lesend |
| Bibliotheksstatus | „Bibliothek Status“ | ausschließlich lokale Bestandszähler |
| Gedächtnisstatus | „Gedächtnis Status“ | ausschließlich bestätigte lokale Zähler |
| Nächster Projektpunkt | „Was ist der nächste Projektpunkt?“ | erster offener Eintrag aus dem festen Roadmap-Abschnitt |
| Dokumentationsstatus | „Dokumentation Status“ | ausschließlich Zähler für sechs feste Kerndokumente |
| Codequalitätsstatus | „Codequalität Status“ | feste Python-Regeln, ausschließlich begrenzte Zähler |
| Letzte Projektänderung | „Projekt Änderung“ | erster sicherer Eintrag aus dem festen lokalen Changelog |
| Recherchequelle | „Recherchequelle prüfen“ | feste Python.org-Quelle, separates Ja erforderlich |
| Python-Version | „Python Version“ | nur neueste stabile Versionsnummer von Python.org, separates Ja erforderlich |
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

## Lokaler Projektstatus

`tools/project_status.py` registriert `development.project_status` mit
`READ_ONLY` und ohne Parameter. Das Tool ist auf den eigenen Projektordner
festgelegt. Es führt ausschließlich drei intern definierte Git-Leseabfragen mit
kurzem Timeout und ohne Shell aus. Weder Nutzer noch Modell können einen Pfad,
einen Git-Unterbefehl oder weitere Prozessargumente angeben.

Die Ausgabe ist auf den validierten Branchnamen, einen kurzen hexadezimalen
Commit-Hash, die Anzahl offener Git-Einträge und den Status des festen lokalen
Kernabnahmeberichts begrenzt. `git status` wird intern nur gezählt; Dateinamen,
Diffs, Committexte, Datei- oder Reportinhalte verlassen das Tool nicht. Der
Sprechtext wird lokal aus diesen geprüften Metadaten aufgebaut und benötigt
weder OpenAI noch Ollama.

Reale Vosk-Transkriptionen trennen das Kompositum oder verlieren einzelne
Fragewörter. Enthält eine Eingabe sowohl `projekt` als auch `status`, wird sie
deshalb unabhängig von Artikel, Pronomen und Fragewort auf genau dieses
argumentlose Read-only-Tool kanonisiert. Die beobachtete Verkürzung `wie ist das
projekt` ist zusätzlich als exakte Phrase freigegeben. Dabei entstehen weder
freie Parameter noch eine Modellklassifikation. Ein Sprachmodell darf deshalb
weder fehlenden Projektzugriff behaupten noch Projektmetadaten erfinden.
Der kurze Befehl `Projekt Status` wurde am physischen Vector als zuverlässige
bevorzugte WirePod-Form bestätigt.

## Kontrollierter lokaler Projekt-Testlauf

`tools/project_checks.py` registriert `development.run_core_tests` mit
`MUTATING` und ohne Parameter. Die Einstufung erzwingt ein separates `Ja`, weil
ein lokaler Prozess gestartet wird. Das Tool führt ausschließlich den fest
definierten Aufruf `python -m unittest discover -s tests` im eigenen
Projektordner aus. Weder Nutzer noch Modell können Interpreter, Arbeitsordner,
Testziel, Prozessargumente oder eine Shell bestimmen.

Der Prozess besitzt ein festes Zeitlimit. Standardausgabe und Fehlerausgabe
werden nur intern zur Ermittlung von Ergebnis und Testanzahl gelesen und danach
verworfen. Die Registry-Ausgabe enthält ausschließlich einen Wahrheitswert,
die begrenzte Testanzahl, die Laufzeit und einen lokal erzeugten Sprechtext.
Damit gelangen weder Testprotokolle noch Dateiinhalte oder Secrets in den
Gesprächskontext. Fehlschläge werden transparent gemeldet, führen aber nicht
zu einer freien Fehlerausgabe.

Der feste Sprachbefehl `Projekt Test` erzeugt zunächst nur den offenen
Registry-Vorschlag. Erst ein nachfolgendes `Ja` erteilt einmalig die nötige
Mutationsfreigabe; anschließend wird sie verworfen. Der Testlauf verwendet
weder OpenAI noch Ollama. Die im physischen Test beobachtete Vosk-Lautvariante
`projekte ist` ist zusätzlich als exakte Phrase freigegeben. Ihre Zuordnung
bleibt argumentlos und führt weiterhin nur zur ausdrücklichen Bestätigungsfrage.

## Lokaler Systemstatus

`tools/service_status.py` registriert `system.local_service_status` mit
`READ_ONLY` und ohne Parameter. Die Runtime verbindet das Tool ausschließlich
mit den bereits fest konfigurierten lokalen WirePod- und Ollama-Healthchecks.
Nutzer und Modell können weder Hosts noch URLs, Ports, Pfade oder zusätzliche
Prüfziele angeben.

Die strukturierte Ausgabe enthält nur boolesche Verfügbarkeitswerte und einen
lokal erzeugten Sprechtext. Transportfehler werden an dieser Grenze als
`nicht erreichbar` behandelt; URLs und Exception-Texte verlassen das Tool
nicht. Da bereits der laufende Gesprächspfad antwortet, darf das Tool Vector
Office AI selbst als aktiv kennzeichnen. Es behauptet bewusst keinen Status für
Internet, OpenAI, ElevenLabs, Akku oder die allgemeine Roboterhardware.

Die feste Formulierung `System Status` wird ohne Modellaufruf und ohne
Bestätigung ausgeführt. Weitere beobachtete Vosk-Varianten werden nur nach
einem realen Test einzeln ergänzt.

## Lokaler Bibliotheksstatus

`tools/library_status.py` registriert `knowledge.library_status` mit
`READ_ONLY` und ohne Parameter. Es verwendet dieselbe bereits zusammengesetzte
`IndexedKnowledgeLibrary` wie der Agent. Dadurch entsteht weder eine zweite
Datenquelle noch ein frei wählbarer Datenbank- oder Dateipfad.

Das Tool reduziert die internen Dokumentstatus vor der Registry-Ausgabe auf
vier begrenzte Ganzzahlen: Dokumente, Abschnitte, aktuelle Vektoren und
veraltete Vektoren. Titel, Quellenpfade, Prüfsummen, Importzeiten, Modellnamen,
Vektordimensionen und Dokumenttexte werden verworfen und erscheinen weder im
Sprechtext noch im Audit. Ist die lokale Bibliothek leer, wird ausschließlich
dieser Zustand genannt.

Der feste Sprachbefehl `Bibliothek Status` läuft ohne OpenAI oder Ollama als
Antwortgenerator und benötigt keine Bestätigung. Die bestehende lokale
Embedding-Grenze darf für die interne Statusklassifikation das konfigurierte
Ollama-Modell prüfen; ist es nicht verfügbar, verwendet die Bibliothek ihre
bereits gespeicherten Metadaten. Es gibt keinen Cloud-Fallback.

## Lokaler Gedächtnisstatus

`tools/memory_status.py` registriert `memory.local_status` mit `READ_ONLY` und
ohne Parameter. Agent und Tool verwenden dieselbe `SQLiteMemoryStore`-Instanz.
Die Datenbankschicht zählt in einer einzelnen lokalen Abfrage getrennt normale
bestätigte Erinnerungen und bestätigte Einträge der Kategorie `feedback`, ohne
deren Text zu laden.

Die Registry-Ausgabe enthält ausschließlich Erinnerungs-, Feedback- und
Gesamtzahl sowie einen lokal aufgebauten deutschen Sprechtext. Inhalte,
Kategorien, Quellen, Zeitpunkte und IDs bleiben außerhalb von Registry,
Gesprächskontext, TTS und Audit. Leere Memory-Daten werden transparent genannt;
es werden keine persönlichen Erinnerungen abgeleitet oder erfunden.

Der feste Sprachbefehl `Gedächtnis Status` läuft ohne OpenAI, Ollama oder andere
Netzwerkzugriffe und benötigt keine Bestätigung. Nutzer und Modell können weder
Suchtext noch Memory-ID, Datenbankpfad oder Kategorie ergänzen.

## Lokaler Roadmapstatus

`tools/roadmap_status.py` registriert `development.next_roadmap_item` mit
`READ_ONLY` und ohne Parameter. Der Projektordner, die Datei
`docs/roadmap.md` und der Abschnitt `Tools und Sicherheit` sind fest im Code
vorgegeben. Nutzer und Modell können weder Dateipfad noch Abschnitt, Suchtext
oder Ausgabeformat bestimmen.

Das Tool liest höchstens eine begrenzte lokale Markdown-Datei und gibt nur den
ersten mit `⏳` markierten Eintrag des festen Abschnitts zurück. Die einzelne
Planzeile besitzt eine feste Längengrenze; URLs, Pfadtrenner, Steuerzeichen und
andere nicht freigegebene Zeichen werden abgewiesen. Dateiinhalt, weitere
Roadmapeinträge und interne Lesefehler gelangen nicht in Registry, Audit oder
Sprachausgabe.

Der Sprechtext entsteht rein lokal und verwendet weder OpenAI noch Ollama zur
Interpretation. Der feste Sprachbefehl `Was ist der nächste Projektpunkt?`
läuft ohne Bestätigung. Die eigentliche TTS-Ausgabe darf wie jede andere
Antwort dem konfigurierten Sprachprovider folgen; die freigegebene Zeile stammt
deshalb ausschließlich aus der versionierten, nicht privaten Projekt-Roadmap.

## Lokaler Dokumentationsstatus

`tools/documentation_status.py` registriert
`development.documentation_status` mit `READ_ONLY` und ohne Parameter. Die
Allowlist enthält ausschließlich `README.md`, `CHANGELOG.md`, Architektur,
Roadmap, Tool-Sicherheitskonzept und Qualitätsregeln. Nutzer und Modell können
weder Dateien, Verzeichnisse, Erweiterungen noch Prüfkriterien ergänzen.

Jedes feste Dokument wird lokal auf Projektzugehörigkeit, regulären Dateityp,
begrenzte Größe, UTF-8-Lesbarkeit und seine erwartete Hauptüberschrift geprüft.
Die Registry-Ausgabe enthält nur Gesamtzahl, gültige, fehlende und ungültige
Anzahlen, den Zustand `complete` oder `incomplete` und einen lokal aufgebauten
Sprechtext. Dateinamen, Pfade, Inhalte und interne Fehler werden nicht
ausgegeben oder auditiert.

Der feste Sprachbefehl `Dokumentation Status` benötigt keine Bestätigung und
keine Interpretation durch OpenAI oder Ollama. Eine konfigurierte Cloud-TTS
erhält höchstens die nicht sensible Zählerzusammenfassung, niemals gelesene
Dokumentinhalte.

## Lokaler Codequalitätsstatus

`tools/code_quality_status.py` registriert
`development.code_quality_status` mit `READ_ONLY` und ohne Parameter. Die
Prüfung ist auf `main.py` und die festen Produktivpakete aus
`docs/quality.md` beschränkt. Nutzer und Modell können weder Pfade,
Dateimuster, Regeln, Grenzwerte noch Ausgabeformat beeinflussen.

Die Python-Dateien werden lokal geparst. Geprüft werden fehlende Modul- und
Funktions-Docstrings, blockierte englische Standardformulierungen, Funktionen
oberhalb von 35 Zeilen und Module mit 400 oder mehr Zeilen. Ein fehlender fester
Produktivpfad, eine ungültige Python-Datei oder ein Lesefehler beendet den
Aufruf an der bereinigenden Registry-Grenze, statt einen unvollständigen
Erfolgsstatus zu melden.

Die Ausgabe enthält ausschließlich die Anzahl geprüfter Module und Funktionen,
fünf begrenzte Verstoßzähler, ihre Summe und einen lokal erzeugten Sprechtext.
Dateinamen, Pfade, Funktionsnamen, Docstrings, Quelltexte und interne Fehler
gelangen weder in Gesprächskontext noch Audit. `Codequalität Status` benötigt
keine Bestätigung und kein Sprachmodell; eine konfigurierte Cloud-TTS erhält
höchstens die nicht sensible Zählerzusammenfassung.

Für eine deutliche physische Ausgabe werden die begrenzten Zähler lokal in
deutsche Zahlwörter umgewandelt und in getrennten kurzen Sätzen gesprochen.
Dadurch entstehen klare Satzpausen, ohne die allgemeine ElevenLabs-Stimme oder
deren Geschwindigkeit für andere Antworten zu verändern.

WirePod hat den vollständigen Befehl im physischen Test als `qualität status`
verkürzt. Diese eine beobachtete Kurzform ist deshalb zusätzlich exakt auf
dasselbe argumentlose Tool abgebildet; allgemeinere Qualitätsfragen bleiben
weiterhin normaler Dialog und erzeugen keine freien Toolparameter.

## Letzte dokumentierte Projektänderung

`tools/changelog_status.py` registriert `development.latest_change` mit
`READ_ONLY` und ohne Parameter. Projektwurzel, `CHANGELOG.md` und der Abschnitt
`[Unreleased]` sind fest im Code vorgegeben. Das Tool liest ausschließlich den
ersten Aufzählungspunkt dieses Abschnitts. Nutzer und Modell können weder Pfad,
Dateiname, Abschnitt noch Suchtext beeinflussen.

Die Changelog-Datei besitzt eine feste Größenobergrenze. Die einzelne Ausgabe
wird zusätzlich in Länge und Zeichenvorrat begrenzt; URLs, Pfadtrenner,
Steuerzeichen und nicht unterstütztes Markup führen zu einer sicheren
Ablehnung. Markdown-Codezeichen werden lokal entfernt. Weitere Einträge,
Releasehistorie und interne Lesefehler gelangen nicht in Registry, Sprache oder
Audit.

Der Sprechtext entsteht lokal und wird nicht von OpenAI oder Ollama formuliert.
Der feste Befehl `Projekt Änderung` benötigt als rein lesender Aufruf keine
Bestätigung. Die Ausgabe stammt aus der öffentlichen versionierten
Projektdokumentation und enthält keine Diffs, Dateinamen oder Commitinhalte.

## Kontrollierte Recherchequelle

`PermissionLevel.NETWORK` trennt externe Lesezugriffe von lokalen
`READ_ONLY`-Tools und verändernden Aktionen. Ein Netzwerk-Tool bleibt blockiert,
bis ein einzelner Aufruf sowohl `allow_network=True` als auch eine konkrete
Bestätigung besitzt. Mutationsfreigaben berechtigen kein Netzwerk; die
Netzwerkfreigabe wird nach dem Aufruf verworfen und gilt nicht für andere Tools.

`tools/research_source.py` registriert `research.python_source_status` ohne
Parameter. Das Tool verwendet ausschließlich die intern festgelegte offizielle
Adresse `https://www.python.org/downloads/`, einen festen User-Agent, fünf
Sekunden Timeout und deaktivierte Weiterleitungen. Es sendet eine `HEAD`-Anfrage
und liest keinen Seiteninhalt. Nutzer und Modell können weder URL, Host,
Suchbegriff, Header noch Zeitlimit bestimmen.

Die strukturierte Ausgabe enthält nur die öffentliche Quellenbezeichnung,
einen Verfügbarkeitswert, einen festen Status und lokalen Sprechtext.
Transportfehler werden als `nicht erreichbar` behandelt; Zieladresse,
Antwortheader, Seiteninhalt und interne Fehlerdetails gelangen nicht in Sprache
oder Audit. Modellvorschläge dürfen Tools der Stufe `NETWORK` grundsätzlich
nicht auswählen.

Der bevorzugte kurze Sprachbefehl `Python Status` erzeugt zunächst nur die transparente
Bestätigungsfrage zum einmaligen Internetzugriff. Erst ein separates `Ja`
erzeugt die einmalige Netzwerkautorisierung. `Nein`, Abbruch oder ein anderer
Aufruf führen zu keiner externen Anfrage. Erkennbare, aber uneindeutige
Rechercheformulierungen werden mit einer Bitte um `Python Status` blockiert und
nicht an ein Sprachmodell weitergereicht.

`tools/python_release.py` registriert ergänzend
`research.python_latest_version`. Auch dieses Netzwerk-Tool ist argumentlos,
verwendet dieselbe feste Python.org-Adresse und benötigt für jeden Aufruf ein
separates `Ja`. Die Antwort wird gestreamt und nach höchstens 750.000 Bytes
abgebrochen. Weiterleitungen, andere Medientypen, ungültiges UTF-8 und andere
HTTP-Statuswerte werden nicht akzeptiert.

Der HTML-Text wird ausschließlich lokal nach finalen Versionsnummern im festen
Format `3.x.y` ausgewertet. Vorabkennzeichnungen wie Alpha, Beta oder Release
Candidate sind ausgeschlossen. Nur die numerisch höchste validierte Version,
die öffentliche Quellenbezeichnung und ein lokal erzeugter deutscher Sprechtext
erreichen die Registry-Ausgabe. Rohes HTML, Links, Seitentexte und mögliche
Anweisungen aus dem Dokument gelangen weder zu OpenAI noch zu Ollama, TTS oder
Audit. Kann keine eindeutige stabile Version bestimmt werden, erfindet das Tool
keinen Wert und meldet die Prüfung als nicht verfügbar.

Der bevorzugte Sprachbefehl lautet `Python Version`. Er löst zunächst nur die
transparente Netzwerkfrage aus; erst ein nachfolgendes `Ja` startet den festen
Abruf. `Python Status` bleibt davon getrennt und prüft weiterhin ausschließlich
die Erreichbarkeit ohne Seiteninhalt.

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
- Dateiänderungen, Shell-Kommandos oder freie beziehungsweise unbestätigte Internetzugriffe,
- Auswahl von Toolnamen, Parametern oder Autorisierungen durch ein Modell,
- Ausführung von Toolanweisungen aus importierten Dokumenten.

Jedes zukünftige produktive Tool benötigt eigene Parameter-, Berechtigungs-,
Fehler- und Regressionstests, bevor es registriert werden darf.
