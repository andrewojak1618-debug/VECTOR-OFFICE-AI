# Teststrategie und Regressionen

Diese Teststrategie macht gefundene Fehler reproduzierbar und trennt sichere lokale
Prüfungen von Provider- und Hardwarezugriffen. Sie gilt für jede Fehlerkorrektur im
Vector Office AI Core.

## Verbindlicher Fehlerablauf

1. **Fehler reproduzieren:** Eingabe, Ausgangszustand und beobachtbares Fehlverhalten
   so klein und inhaltsarm wie möglich beschreiben.
2. **Regressionstest erstellen:** Den Fehler auf der niedrigsten geeigneten Ebene als
   deterministischen Unit- oder Integrationstest abbilden.
3. **Fehlschlag vor der Korrektur prüfen:** Den neuen Einzeltest gegen den
   fehlerhaften Stand ausführen. Er muss aus dem erwarteten fachlichen Grund
   fehlschlagen.
4. **Ursache gezielt beheben:** Nur die verantwortliche Logik ändern und bestehendes
   Verhalten außerhalb des Fehlers erhalten.
5. **Einzeltest wiederholen:** Zuerst den neuen Regressionstest grün ausführen.
6. **Vollständige Abnahme ausführen:** Alle Unit-Tests, Python-Kompilierung,
   Dokumentationsbau und Git-Diff-Prüfung müssen bestehen.
7. **Live oder physisch prüfen:** Nur wenn das korrigierte Verhalten von einem Dienst
   oder Vector-Hardware abhängt, folgt die getrennte manuelle Abnahme.

Kurzform:

> Fehler reproduzieren → Regressionstest → Ursache beheben → Einzeltest → vollständige Testsuite → Live- oder Vector-Test

Der Vorher-Fehlschlag wird im Arbeitsbefund bestätigt. Es werden keine Fehlerlogs mit
Benutzerfragen, Antworten, Dokumentinhalten, API-Schlüsseln oder anderen privaten
Laufzeitdaten versioniert.

## Einzeltest und vollständige Abnahme

Ein einzelner Test wird als vollständig qualifizierter `unittest`-Name ausgeführt:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_modul.TestKlasse.test_fehlerfall -v
```

Alternativ führt die zentrale Abnahme den Einzeltest garantiert vor der kompletten
Suite aus:

```powershell
.venv\Scripts\python.exe -m diagnostics.release_acceptance `
  --regression-test tests.test_modul.TestKlasse.test_fehlerfall
```

Der Zielname muss mit `tests.` beginnen. Dateipfade, Shell-Befehle und freie
Programmargumente werden nicht akzeptiert.

Die vollständige lokale Qualitätsabnahme lautet:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q .
.venv\Scripts\python.exe -m mkdocs build --strict
git diff --check
git status --short
```

`git status --short` ist eine abschließende Sichtkontrolle. Beabsichtigte Änderungen
dürfen sichtbar sein; unbekannte Laufzeit-, Secret- oder Datendateien dürfen nicht in
die Versionsverwaltung gelangen.

## Trennung der Testebenen

### Reproduzierbare Tests

Unit- und lokale Integrationstests laufen ohne Internet, kostenpflichtige API-Anfrage,
Sprachausgabe, Bewegung oder angeschlossene Hardware. Sie sind die verpflichtende
Grundlage jeder Korrektur und jeder Freigabe.

### Provider-Live-Tests

Live-Tests ersetzen niemals einen Regressionstest. Sie prüfen erst nach der lokalen
Abnahme die tatsächliche Erreichbarkeit oder das Laufzeitverhalten von Ollama,
OpenAI, ElevenLabs oder WirePod. Kostenpflichtige Cloud-Anfragen werden nur nach
einer bewussten Freigabe ausgeführt und bleiben außerhalb der Unit-Test-Suite.

### Physische Vector-Tests

Physische Tests können Sprache, Animationen oder Robot-Aktionen auslösen. Sie werden
nur nach der ausdrücklichen Bestätigung des Nutzers ausgeführt. Die zentrale Abnahme
verlangt dafür weiterhin gemeinsam `--physical-vector` und `--confirm-physical`.
Ein physischer Erfolg ersetzt weder den Vorher-Fehlschlag noch den automatisierten
Regressionstest.

## Abnahmekriterien einer Fehlerkorrektur

Eine Korrektur gilt erst als abgesichert, wenn:

- der Fehler vor der Korrektur reproduziert wurde,
- der neue Test vor der Korrektur aus dem erwarteten Grund fehlschlug,
- der fokussierte Test nach der Korrektur besteht,
- die vollständige lokale Qualitätsabnahme grün ist,
- erforderliche Live- oder Vector-Tests getrennt und ausdrücklich freigegeben wurden,
- keine privaten Inhalte, Secrets oder lokalen Testartefakte committed werden.
