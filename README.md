# Maestro Composition Lab 3.0 — gemeinsamer Quellstand

Gemeinsame musikalische Engine `engine/*.py`; **getrennte plattformspezifische Oberflächen** unter `engine/ui/mac.html` und `engine/ui/windows.html`. Die Engine wählt zur Laufzeit anhand des Betriebssystems genau eine Oberfläche. Native Hosts bleiben unter `macos/mac_host/` und `windows/desktop/`.

## Herkunft

Windows-Referenz 2.5.1 (GitHub-Basispaket vom 19.10.2026). Mac-Referenz 2.6.9 (Mac-Intel-Paket vom 19.10.2026). Neuere Mac-Engine-Fixes wurden in die gemeinsame Engine übernommen; die Windows-Oberfläche wurde aus der ursprünglichen Windows-Referenz konserviert und nicht durch das Mac-Layout ersetzt.

## Qualität / Freigabe

Dies ist ein **zusammengeführter Quellstand, kein geprüftes Release für Maestro**. Unit-Tests sind auf Linux lauffähig. Native Windows-/Mac-Builds sowie Maestro-Integrationstests sind noch auf den Zielplattformen nötig. Die Mac-Buildroutine benötigt zudem ihre externen, gepinnten Laufzeit-Abhängigkeiten und ein Icon-Asset; der Basispaketstand enthält nicht alle hierfür notwendigen Dateien.

`python -m unittest discover -s engine -p 'test_*.py'`

Offener Prüfungspunkt: macOS- und Windows-KI-Schlüssel- und Einstellungs-Verhalten inklusive Eingabe über die jeweiligen nativen Oberflächen.
