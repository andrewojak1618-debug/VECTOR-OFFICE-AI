# Fehler und Lösungen

Diese Seite sammelt bestätigte technische Störungen und ihre sicheren
Lösungswege. Diagnoseausgaben bleiben inhaltsfrei: Fragen, Antworten,
Dokumente, Zugangsdaten und Robot-Zertifikate gehören nicht in Fehlerberichte.

## Deutsche Windows-Folgeaufnahme startet nicht

**Beobachtet am:** 28. August 2026
**Betroffene Funktion:** firmwarefreie lokale Folgeaufnahme aus Karte 39

### Symptome

- Vector beantwortet die erste, über das Wakeword gestellte Frage.
- Das anschließende fünfsekündige Mikrofonfenster nimmt kurze Antworten wie
  „Danke“ oder „Vielen Dank“ nicht an.
- Die Anwendung fällt anschließend kontrolliert in den normalen
  Wakeword-Betrieb zurück.
- Ein isolierter Aufruf von `WindowsSpeechFollowUpCapture.prepare()` liefert
  `False`, bevor überhaupt eine Mikrofonaufnahme beginnt.

### Bestätigter technischer Befund

Die deutsche Windows-Spracherkennung war als
`Language.Speech~~~de-DE~0.0.1.0` registriert, konnte aber nicht geladen
werden. Der `System.Speech`-Konstruktor meldete, dass kein Erkennungsmodul mit
der erforderlichen ID gefunden wurde. Der alternative WinRT-Erkenner brach mit
dem internen Sprachfehler `0x800455A0` ab.

Mikrofonfreigabe, Windows-Audiodienste und das deutsche Sprachpaket waren
vorhanden. WirePod und Vector SDK waren nicht die Ursache. Der Rechner läuft
auf ARM64, während Python und Windows PowerShell in der geprüften Umgebung als
AMD64-Prozesse ausgeführt wurden. Diese Architekturgrenze ist ein möglicher
Kompatibilitätsfaktor; sie ist nicht als alleinige Ursache bewiesen.

### Kontrollierte Lösung

1. Vector Office AI vollständig stoppen.
2. Als Administrator ausschließlich
   `Language.Speech~~~de-DE~0.0.1.0` entfernen.
3. Dieselbe Capability unmittelbar wieder über Windows installieren.
4. Einen von Windows geforderten Neustart durchführen.
5. Isoliert prüfen, ob `WindowsSpeechFollowUpCapture.prepare()` nun `True`
   liefert.
6. Erst danach Vector Office AI starten und das fünfsekündige Folgefenster
   physisch testen.

Die Reparatur darf weder `Language.Basic~~~de-DE~0.0.1.0` noch
`Language.TextToSpeech~~~de-DE~0.0.1.0` entfernen. WirePod, Zertifikate,
Firmware und TTS-Konfiguration bleiben unverändert.

### Ergebnis der Reparatur vom 28. August 2026

Die Capability wurde erfolgreich entfernt und anschließend vollständig über
Windows Update neu installiert. CBS beendete die Komponentenwartung mit
`S_OK`; ein Neustart war nicht erforderlich. Der unmittelbar folgende
isolierte Test lieferte dennoch wieder `PREPARE=False`.

Die Neuinstallation ist damit als Reparaturversuch abgeschlossen, hat den
Fehler auf diesem Rechner aber nicht behoben. Eine bloß beschädigte
Speech-Capability ist als alleinige Ursache unwahrscheinlich. Die
ARM64-/AMD64-Kompatibilitätsgrenze des registrierten alten
`System.Speech`-Erkenners bleibt der wichtigste technische Verdacht. Diese
Neuinstallation soll nicht wiederholt werden, solange keine neue Windows- oder
Architekturdiagnose einen konkreten Grund dafür liefert.

Auch nach einem anschließend vollständig ausgeführten Windows-Neustart blieb
der isolierte Befund unverändert bei `PREPARE=False`. Ein bloßes erneutes
Starten, Ab- und Anmelden oder Wiederholen derselben Komponenteninstallation
ist deshalb kein begründeter nächster Reparaturschritt.

### Sicherer Rückfall

Der unbrauchbare Windows-Erkenner wurde mit
`VOICE_FOLLOWUP_PROVIDER=vosk` durch einen firmwarefreien lokalen Vosk-Adapter
ersetzt. Das offizielle Modell `vosk-model-small-de-0.15` liegt außerhalb von
Git unter `F:\Vosk\models`; der isolierte Starttest liefert damit
`PREPARE=True`. Audio bleibt flüchtig im Arbeitsspeicher. Bestätigungen
verwenden weiterhin eine feste Grammatik, freie Erkennung bleibt auf das
fünfsekündige Inhaltsfenster begrenzt.

Der anschließende physische End-to-End-Test wurde erfolgreich abgeschlossen:
Nach einer normalen Wakeword-Frage erkannte Vosk das ohne erneutes Wakeword
gesprochene „Danke“ im Folgefenster und Vector antwortete unmittelbar mit
„Gern.“. Der Vosk-Pfad ist damit die bestätigte Lösung auf diesem Rechner.

Falls auch Vosk nicht vorbereitet werden kann, deaktiviert
`VOICE_FOLLOWUP_LOCAL=false` die lokale Folgeaufnahme. Der normale
Wakeword-Dialog bleibt dadurch verfügbar. Firmware und Berechtigungsgrenzen
werden dafür nicht verändert.

### Vorbeugung

- Vor Änderungen an Grammatik, Konfidenzwerten oder Dialoglogik immer zuerst
  den isolierten `prepare()`-Test ausführen.
- Ein fehlgeschlagenes `prepare()` ist ein Windows-Engine-Problem und kein
  Beleg für eine falsch erkannte Formulierung.
- Sprach-Capabilities nur einzeln und mit ihrem vollständigen Namen ändern.
- Nach einer Reparatur erst die isolierte Erkennung, dann die Anwendung und
  zuletzt den physischen Vector-Dialog prüfen.
