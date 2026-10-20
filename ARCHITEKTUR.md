# Architektur und Datenflüsse — 3.0.0

Ein gemeinsamer Python-Kern; zwei eigenständige native Hosts und zwei getrennte HTML-Ansichten.

| Schicht | Mac | Windows |
|---|---|---|
| Fenster, Menü, Dateidialog | AppKit/PyObjC | WinForms/.NET 4.8 |
| Inhalt | WKWebView + ui/mac.html | WebView2 + ui/windows.html |
| Schlüssel | Security/Keychain | DPAPI |
| Engine | gemeinsame engine/*.py | dieselben Dateien |

## Datenfluss
Native Host → überwachte Python-Unterinstanz → Loopback-HTTP mit Sitzungstoken → Handler → workflows.
Maestro wird über maestro-script/MCP gelesen: connect → API-Schema → describe_api → read_only-Skript → workspace-Snapshot. Dieser enthält die gesamte Partitur, Auswahlkennungen und einen unveränderlichen Vergleichsstand (guard).
Auftrag + Snapshot → Anbieteradapter → KI-Antwort → score_response → composition/expression beziehungsweise replacement/workspace → validierter Vorschlag → atomare JSON-Sicherung.
Anwendung: Original sichern → festen Lua-Schreiber erzeugen → Maestro-Probelauf (read_only) → derselbe Code als Transaktion → Bestätigung → Ergebnisstatus sichern. Modelltext wird niemals als ausführbares Skript benutzt.

## Modulabhängigkeiten
- maestro_analyse: lokaler HTTP-Router, Anbieter, Modelllisten, MCP, atomare Ergebnisspeicherung.
- workflows: fünf Arbeitsbereiche und Snapshot-/Vorschlagsverwaltung.
- composition → expression: Taktfüllung, Tonhöhen, Stimmen, Bögen, Ausdruck und N-tolen.
- workspace → composition/expression: vollständiger Lesestand, Auswahländerung und feste Lua-Schreiber.
- replacement → workspace/composition/expression: vollständige ausgewählte Taktstimmen, Schutz unveränderter Musik.
- transition → replacement/workspace/composition: begrenzter Schlussersatz mit Fortsetzung.
- review → workflows/replacement: Analyse als Grundlage eines getrennten Revisionsvorschlags.
- history → workflows: lokale Ergebnisse, geprüfter Import, keine KI-Anfrage beim Öffnen.
- preferences → mac_keys oder DPAPI; diagnostics entfernt Schlüssel aus Fehlermeldungen.
Zyklische fachliche Bezüge werden erst innerhalb der aufgerufenen Funktionen importiert; es gibt keine zweite Plattform-Engine.

## Funktionsgleichheit
Beide Oberflächen bieten Neu komponieren, Analyse ganz/Auswahl, Fortsetzung, optionalen Übergang, Instrumentergänzung, gezielte Notenänderung, Taktstimmenersatz, Revision aus Analyse, Verlauf, Import/Export von Arbeitsständen, dynamische Modelllisten für vier Anbieter und Diagnosen. Beide zeigen Strukturkorrekturhinweise. Native Tastenkürzel und Dateidialoge bleiben plattformspezifisch.

## Erhaltene Grenzen
Keine Live-Maestro-Instanz in CI. Lua-Modelltests sind Simulationen. Übergangsersatz ist bei nicht sicher zuordenbaren Bögen, Strukturzeichen und bestimmten N-tolen/Vorschlägen bewusst gesperrt. Reines Anhängen oder gezielte Notenbearbeitung bleibt möglich. Keine neue musikalische Funktion wurde ergänzt.
