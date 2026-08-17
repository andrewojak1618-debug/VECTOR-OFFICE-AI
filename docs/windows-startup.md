# Windows-Autostart und Host-Watchdog

Der lokale Autostart macht Vector Office AI nach einer Windows-Anmeldung ohne
manuellen Konsolenstart verfügbar. Er schaltet den Roboter nicht elektrisch
ein. Vector muss geladen, eingeschaltet und im selben Netzwerk erreichbar sein.

## Aufbau

- `application/host_watchdog.py` hält genau eine lokale Supervisor-Instanz.
- `application/process_control.py` kapselt Dateisperre und Prozessbaumkontrolle.
- `scripts/start_vector_office.ps1` startet ausschließlich die Projekt-`.venv`.
- `scripts/install_windows_startup.ps1` registriert eine verzögerte Aufgabe.
- `scripts/uninstall_windows_startup.ps1` entfernt nur diese benannte Aufgabe.

Der Watchdog prüft WirePods lokalen Endpunkt alle 0,5 Sekunden. Ist der Endpunkt
nicht erreichbar und läuft kein `chipper.exe`-Prozess, wird ausschließlich die
konfigurierte WirePod-Datei mit `-d` gestartet. Ein bereits laufender Prozess
wird nicht dupliziert. Anschließend startet `main.py`; Ollama verwendet dabei
seinen bestehenden lokalen Startmechanismus.

Ein Anwendungsabsturz mit einem Fehlercode wird höchstens dreimal nach 2, 5 und
10 Sekunden neu gestartet. Ein bewusst und erfolgreich beendeter Dialog bleibt
beendet. Die geplante Aufgabe selbst darf höchstens einmal gleichzeitig laufen
und besitzt zusätzlich einen lokalen Dateisperrschutz unter `data/startup/`.
Der Starter übergibt außerdem seine Besitzer-PID. Wird die geplante Aufgabe
manuell gestoppt, erkennt der Watchdog das Ende der Aufgabenhülle und beendet
den zugehörigen Python-Anwendungsbaum, ohne fremde Prozesse anzufassen.

## Voraussetzungen

- `.venv` und alle Projektabhängigkeiten sind vollständig installiert.
- `.env` enthält `INPUT_MODE=wirepod` und die bestehende lokale Konfiguration.
- WirePod ist unter dem konfigurierten Pfad installiert.
- Der Windows-Benutzer besitzt Zugriff auf seine Vector-Zertifikate.

Der Hintergrundstart lehnt `INPUT_MODE=console` bewusst ab, weil eine versteckte
Konsolensitzung nicht bedienbar wäre.

## Optionale Einstellungen

```env
HOST_WATCHDOG_WIREPOD_EXECUTABLE=C:\Program Files\wire-pod\chipper\chipper.exe
HOST_WATCHDOG_POLL_INTERVAL=0.5
HOST_WATCHDOG_STARTUP_ATTEMPTS=5
HOST_WATCHDOG_APP_RESTART_ATTEMPTS=3
```

Alle Grenzwerte werden beim Laden validiert. Zugangsdaten, Seriennummern und
Inhalte aus `.env` erscheinen weder im Aufgabenbefehl noch im Watchdog-Log.

## Aufgabeninstallation prüfen

Der sichere Probelauf baut die vollständige Aufgabe, registriert sie aber nicht:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts\install_windows_startup.ps1 -WhatIf
```

## Aufgabe installieren

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts\install_windows_startup.ps1 -DelaySeconds 20
```

Die Aufgabe läuft nach der Benutzeranmeldung mit 20 Sekunden Verzögerung, mit
normalen Benutzerrechten und ohne parallele zweite Instanz. Sie darf auch im
Akkubetrieb weiterlaufen. Mit `-StartNow` kann sie nach der Registrierung direkt
gestartet werden.

Der registrierte Zustand lässt sich ohne Änderung prüfen:

```powershell
Get-ScheduledTask -TaskName "Vector Office AI"
Get-ScheduledTaskInfo -TaskName "Vector Office AI"
```

## Aufgabe entfernen

Die Entfernung verlangt eine ausdrückliche Bestätigung. `-WhatIf` bleibt auch
hier verfügbar.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts\uninstall_windows_startup.ps1 `
  -ConfirmRemoval -Confirm:$false
```

Lokale Datenbanken, `.env`, Zertifikate und WirePod selbst werden dabei nicht
gelöscht oder verändert.

## Wiederherstellungsgrenzen

Während eines laufenden Voice-Dialogs verwendet die Anwendung fünf begrenzte
WirePod-Prüfungen. Die Wartezeiten 1, 2, 5 und 10 Sekunden ergeben ein lokales
Wiederanlauffenster von bis zu 18 Sekunden. Nach erfolgreicher Verbindung wird
die einmalige deutsche Wiederherstellungsansage ausgegeben.

Kann der PC selbst nicht starten oder verliert Vector seine Strom- oder
Netzwerkverbindung, kann der Host-Watchdog keine Robot-Kommunikation herstellen.

## Lokale Abnahme

Am 17. August 2026 wurde die Aufgabe für den lokalen Benutzer mit 20 Sekunden
Anmeldeverzögerung registriert. Ein manueller Probelauf erreichte WirePod,
Ollama, Vector-SDK und den lokalen Voice-Modus. Der anschließende Aufgabenstopp
wechselte auf `Ready`, schrieb das sichere Besitzer-Stopp-Ereignis und hinterließ
keinen Watchdog- oder `main.py`-Prozess.
