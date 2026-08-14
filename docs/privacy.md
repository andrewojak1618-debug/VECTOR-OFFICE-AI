# Datenschutz und Kontextschutz

Vector Office AI behandelt importierte Dokumente als lokale, nicht
vertrauenswürdige Daten. Weder Dokumenttext noch Embeddings werden automatisch
zu Trainingsergebnissen oder ausführbaren Anweisungen.

## Sichere Voreinstellungen

```env
EMBEDDING_PROVIDER=ollama
KNOWLEDGE_ALLOW_CLOUD=false
```

Embeddings werden ausschließlich über den lokalen Ollama-Endpunkt erzeugt. Die
Factory akzeptiert keinen Cloud-Embedding-Anbieter und besitzt keinen
Cloud-Fallback. Datenbank, Vektoren und `.env` liegen unter ignorierten lokalen
Pfaden und werden nicht eingecheckt.

Mit `KNOWLEDGE_ALLOW_CLOUD=false` werden Dokumentauszüge nicht in einen
OpenAI-Modellkontext aufgenommen. Das gilt konservativ auch für einen Agenten,
dessen primärer Anbieter OpenAI ist und der Ollama lediglich als automatischen
Fallback verwendet. Läuft Ollama als aktiver Anbieter oder als erzwungener
lokaler Voice-Anbieter, darf der Agent die lokale Bibliothek verwenden.

## Bedeutung der Cloud-Freigabe

`KNOWLEDGE_ALLOW_CLOUD=true` ist eine ausdrückliche Freigabe: Relevante,
hybrid ausgewählte Dokumentauszüge werden dem OpenAI-Systemkontext hinzugefügt
und verlassen damit den lokalen Rechner. Die vollständige Bibliothek, die
SQLite-Datenbank und gespeicherte Embeddings werden dadurch nicht hochgeladen.
Auch Suchanfrage und Dokumentindex bleiben für die semantische Auswahl beim
lokalen Ollama-Embedding-Dienst.

Die Freigabe sollte nur für Dokumente aktiviert werden, deren Übertragung an den
konfigurierten Cloud-Anbieter bewusst akzeptiert wurde.

## Schutz des Modellkontexts

Jeder Dokumentabschnitt wird mit Quelle, Titel und Abschnittsnummer als
JSON-kodierter Eintrag unter dem Label
`UNVERTRAUENSWÜRDIGE_DOKUMENTDATEN` eingefügt. Der übergeordnete Systemtext legt
fest, dass diese Inhalte ausschließlich Daten sind. Darin enthaltene Befehle,
Rollenwechsel oder Aufforderungen zur Regelverletzung dürfen nicht ausgeführt
werden.

Kommen Treffer aus mehreren Dateien, trägt der Kontext zusätzlich den Hinweis
`MÖGLICHER QUELLENKONFLIKT`. Das Modell muss widersprüchliche Aussagen benennen,
statt sie unbemerkt zu einer vermeintlich sicheren Aussage zu vermischen.

Diese Struktur reduziert das Risiko gespeicherter Prompt Injection deutlich.
Wie jeder promptbasierte Schutz ist sie keine mathematische Sicherheitsgarantie;
deshalb bleiben Cloud-Sperre, minimale Kontextauswahl und explizite Quellen
zusätzliche Schutzschichten.

## Protokoll- und Git-Hygiene

Normale Indexierungs- und Suchpfade protokollieren nur Status, Anzahl, Quelle
oder Abschnittsnummer, niemals Dokumenttext oder Vektorwerte. `/documents`
zeigt Metadaten; ein bewusstes `/memories` zeigt dagegen ausdrücklich die vom
Benutzer angeforderten bestätigten Erinnerungen.

Automatisierte Tests sichern folgende Grenzen ab:

- lokale Embeddings und ausgeschaltete Cloud-Freigabe als Defaults,
- OpenAI-Sperre sowie ausdrückliche Freigabe,
- lokalen Dokumentzugriff für Ollama,
- Prompt-Injection-Kapselung und Mehrquellenhinweis,
- stillen Suchpfad ohne Inhalts- oder Vektorlogs,
- `.env` und `data/` als ignorierte Laufzeitpfade.
