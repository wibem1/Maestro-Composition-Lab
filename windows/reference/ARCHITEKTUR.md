# Maestro Composition Lab 2.5.1 / 19.10.2026

## Datenfluss

KI-Auftrag + vollstaendiger Kontext -> JSON -> composition.validate /
workspace.patches / replacement.validate -> fester Lua-Schreiber ->
Maestro read_only-Probelauf -> identischer Commit -> ein Undo-Schritt.

expression.py kapselt die Ausdrucksarten, deren Anker, Texte, Tempowerte und
N-tolengruppen. Keine vom Modell gelieferten Programme werden ausgefuehrt.
Die bestehenden Formate sind rueckwaertskompatibel; neue optionale Felder:

- System directions: kind, from:[Takt,Stimme,Eintrag], optional to,text,category,bpm.
- Takt tuplets: voice,start,count,ratio:[geschrieben,normal].
- Patch directions: from/to sind vorhandene, ausgewaehlte Eintrags-IDs.
- Ersatz directions: from/to=[System,Takt,Stimme,neuer_Eintrag].
- Ersatz cell tuplets: voice=1 fuer die einzelne freigegebene Taktstimme.

Validierung prueft Anker, Auswahlgrenzen, Textarten, BPM, unbekannte Felder,
N-tolenueberlappung, Raster und effektive Taktlaengen. Einmal normalisierte
Daten sind erneut validierbar. JSON bleibt menschenlesbar und gespeichert.
Die Probelauf/Commit-Skripte pruefen die tatsaechlichen Notenpositionen und
N-tolendauern; fehlende Texte/Tempowerte und entfernte statt ergaenzte Linien
werden abgewiesen. Maestros Command-API fuehrt ihre eigene Validierung aus.

workspace.read_lua liest Artikulationen, Dynamik, lokale Taktzeichen, Pedal,
Gabeln, Texte, Textlinien, globale systemTexts (inklusive Tempo), Boegen und
Rohdetails. ai_context uebermittelt den gesamten musikalischen Zusammenhang.
Der Guard verwendet das ganze Original. Der Legacy-Schreiber delegiert jetzt
an denselben Schreiber, statt ein zweites schmaleres Format zu pflegen.
Fortsetzungen verwenden einen Taktoffset, neue Instrumente eigene Systeme.
Vorhandene Musik wird weiterhin geprueft; Tempoanweisungen bei blossen
Instrumentergaenzungen werden vor der Uebergabe abgewiesen.

Bei Uebertragungsfehlern speichert workflows.apply Phase und Fehlermeldung im
Arbeitsstand. Die Verbindungsdiagnose kann editor.commands() und Maestro-
Schemas read_only ausgeben; damit sind konkrete native Optionen nachpruefbar.

## Pruefung

python3 -m unittest discover -s engine -p '*test*.py'
node engine/ui_selftest.js
python3 Quellcode/browser_test.py <Chrome-Headless-Shell>
dotnet build Quellcode/desktop/MaestroDesktop.csproj -c Release -o build
dotnet run --project Quellcode/desktop-tests -- <engine> <python>

Die Tests pruefen die App in Python, echtem Lua 5.4, Chromium und mit dem
originalen C#-BackendSession-Code. Maestro/KI werden in diesen Tests simuliert.
Ein Test der tatsaechlichen Klangumsetzung im echten Maestro ist offen.

## Analyseanzeige 2.5.1

analysis_text.readable wandelt gaengiges LaTeX in Unicode-Klartext um.
workflows.run/load und der alte Analyse-Endpunkt benutzen denselben Aufbereiter.
raw_response bleibt unveraendert erhalten, answer ist fuer die Anzeige gedacht.
Die Darstellung erfolgt weiterhin ueber textContent, ohne Modell-HTML auszufuehren.

## Analyse -> Revision ab 2.5.1

review.create erhaelt den unveraenderten Analyse-Arbeitsstand und die aktuell
gewaehlten KI-Zugangsdaten. Das analysierte Original wird kopiert; dessen
IDs und score_id bleiben gebunden. scope=all wird fuer den bestehenden
Revision-Schreiber zu einer Auswahl aller bereits analysierten IDs. Eine
Auswahlanalyse behaelt nur die urspruenglichen IDs. Geeignete vollstaendige
Taktstimmen verwenden replacement, sonst werden gezielte patches erzeugt.
Vor einem bezahlten Modellaufruf wird der Original-Guard erneut geprueft.

/workspace/review speichert den separaten Vorschlag, die Analyseherkunft und
einen eigenen Lesestand. Die Analyse bleibt erhalten. Das UI zeigt in Analyse
den neuen Button Ueberarbeitung aus Analyse erstellen statt eines gesperrten
Anwenden-Buttons. Der neue Aufruf schreibt nicht; er wechselt zur Vorschau in
Auswahl ueberarbeiten. Erst /workspace/apply laeuft durch die bisherigen
Probelauf/Commit-Schranken. Kein neues Eingabefeld oder Chat.

## Verlauf und Diagnose ab 2.5.1

history.py liest die bestehenden Ergebnis-JSONs und erstellt kurze Metadaten.
Ein Cache ueber mtime_ns/Dateigroesse vermeidet wiederholtes Lesen unveraenderter
grosser Partituren. Suche, Typfilter und Pagination arbeiten auf allen Dateien.
/workspace/history/open validiert die Datei, registriert sie in der Sitzung und
benutzt workflows.load(save=False). Der Server erzeugt beim blossen Wiederlesen
keine weiteren Dateien. Erst eine neue Anwendung/Revision speichert einen neuen
Arbeitsstand. Fehlerhafte Modellantworten koennen ohne Anwendung gelesen werden.
Die JSON-Dateien bleiben der eigentliche Speicher; es gibt keine zweite Datenbank.

save_composition verwendet temporaere Dateien im selben Ordner und os.replace.
created bleibt erhalten, updated wird erneuert. Alte JSONs werden nicht migriert
oder ueberschrieben. Dateinamen aus der Verlaufsroute sind an den Ergebnisordner
gebunden, Symlinks und Pfadkomponenten werden nicht als Ladeziele akzeptiert.

diagnostics.py protokolliert die letzte Ausnahme und ausgewaehlte Auftragsdaten.
Handler erfasst auch technische Validierungsfehler und den letzten Workflow.
UI-Fehler werden ueber /desktop/report im lokalen Dienst hinterlegt.
/desktop/info liefert diese Angaben; die native Diagnose speichert service als
JSON-Objekt statt als in JSON verschachtelte Zeichenkette.

## Fortsetzung bei leeren Systemnamen (2.5.1)

workflows.prepare_score prueft Namen aus der Maestro-Quelle vor der Uebernahme.
Ein nur aus Whitespace bestehender Name erhaelt im generierten Fragment den
lokalen Ersatznamen System N. Der Quellsnapshot inklusive guard bleibt exakt
erhalten; der Fortsetzungswriter setzt keine Namen an vorhandenen Systemen.
workflows.load prueft fehlgeschlagene Fortsetzungen mit composition=null aus
der gespeicherten raw_response erneut, ohne KI-Aufruf. Alle musikalischen
Pruefungen gelten weiter. Die Wiederherstellung wird als recovery vermerkt.
history.open_record nutzt diese Pruefung; nicht reparierbare Antworten bleiben
als fehlgeschlagene, nicht anwendbare Arbeitsstaende einsehbar. Keine Datei
wird beim Oeffnen ueberschrieben. Die Anwendung behaelt ihre Bindungspruefung
und den Schutz bereits angewendeter Fortsetzungen.

## Uebergang und Fortsetzung (ab 2.5.0)

transition.py kapselt Planung, technische Validierung und den gemeinsamen
Lua-Writer. transition_bars=0 ist der bisherige reine Anhaengemodus. 2, 3 oder
4 gibt exakt diesen Schlussbereich zur Ersetzung frei. bars bleibt die Zahl
neuer Takte; composition enthaelt Ersatzbereich plus neue Takte.

Datenfluss: Option -> workflows.run -> transition.plan vor KI-Aufruf ->
gesamter Partiturkontext mit expliziter Freigabe -> eine KI-Antwort ->
prepare_score/transition.validate -> Arbeitsstand mit unveraendertem Quellsnapshot
und Guard -> Vorschau -> workflows.apply -> Sicherung -> read_only-Probelauf
und ein schreibender run_script-Aufruf mit demselben Lua-Code.

Die Planung nutzt die Pruefungen fuer vollstaendige Taktstimmen und Boegen aus
replacement.py. Nur sichere, eindeutig zugeordnete Ausdrucksanker werden
entfernt. Grenzueberschreitende oder unbekannte Konstruktionen werden abgewiesen,
bevor Kosten fuer eine KI-Anfrage entstehen. Die Validierung prueft Gesamtlaenge,
Besetzung, bestehende Taktarten und eingehende Halteboegen. Alte Schlussdynamik
wird entfernt, damit sie nicht dem neu gestalteten Uebergang widerspricht.
Neue Boegen und Ausdruckslinien duerfen Ersatz- und Neutakte verbinden.

Der Writer prueft die exakte Ausgangspartitur, entfernt nur freigegebene
Bogen-/Ausdrucksobjekte, haengt ausschliesslich bars neue Takte an und fuellt
ab dem ersten freigegebenen Bestandstakt. Takte davor, Instrumentkennungen,
Namen, Schluessel, bestehende externe Boegen, Systemtexte ausserhalb der Freigabe
und Taktstruktur werden nachgeprueft. Eine Skriptausnahme verwirft laut Maestro-API
den gesamten Vorgang. Kein Lua-Code aus der Modellantwort wird ausgefuehrt.

load/history erhalten transition_bars und bars und validieren die Schreibgrenze
erneut. Der Schutz bereits angewendeter Arbeitsstaende bleibt erhalten.
preferences speichert die Option und validiert den Umfang auf 2/3/4. diagnostics
protokolliert transition_bars ohne Zugangsdaten.

## Zeitbasierte Ausdruckslinien (2.5.1)

transition.timed_span liest das native tick/ticks-Format. Beleg: offizielle
Maestro-Beispieldatei https://maestroscore.app/esempi/canone-pachelbel.maestro,
Crescendi ab Takt 11 mit tick=0, ticks=6720. Die Dauer kann mehrere Takte
umfassen und ist kein End-Tick innerhalb des Starttakts.

Start und Ende werden durch Summieren der realen Taktlaengen auf absolute
Positionen abgebildet. Ende <= Freigabestart bleibt erhalten; Start innerhalb
der Freigabe wird entfernt/neu gestaltet; ein echtes Ueberschreiten der Grenze
wird abgewiesen. Exakt an der Grenze endende Linien sind erlaubt. Bei am Ende
des vorigen Takts verankertem Linienstart wird vorab um groesseren Umfang
gebeten, damit keine Metadaten geschuetzter Takte nachtraeglich geloescht werden.

Der bisherige endTick-Fall und ID-basierte Anker bleiben unterstuetzt. Negative,
nicht endliche, inkonsistente, nicht ganzzahlige oder ausserhalb der Partitur
liegende Positionen werden nicht geraten. Keine unbekannten Anker werden
ignoriert. Die eigentliche Writer- und Sicherungslogik bleibt erhalten.

Regression Gaenseliesel: 32 Takte im 2/4, Crescendo vom Beginn Takt 21 bis Ende
Takt 22, native Darstellung tick=0/ticks=3840. Ein synthetisches Partiturmodell
mit genau dieser Laenge und diesen Linienpositionen prueft alle 2/3/4-Optionen
und den echten Lua-Writer. Die Nutzerkomposition wird nicht als Testbeispiel
mitverteilt.
