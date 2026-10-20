-- Entfernt ausschliesslich Takte nach der letzten Note. Ein Undo-Schritt.
assert(score, "Keine Zielpartitur")
local before=score.measureCount
local last=0
for _,staff in ipairs(score.staves) do
  for index,measure in ipairs(staff.measures) do
    for entry in measure:entries() do
      if entry.isNote and index>last then last=index end
    end
  end
end
assert(last>0, "Die Partitur enthaelt keine Noten. Es wurde nichts geloescht.")
if before>last then score:deleteMeasures(last+1,before) end
assert(score.measureCount==last, "Maestro hat die Takte nicht wie erwartet entfernt. Aenderung wird verworfen.")
for _,staff in ipairs(score.staves) do
  assert(#staff.measures==last, "Taktzahlen der Systeme stimmen nicht ueberein. Aenderung wird verworfen.")
end
print("MAESTRO_TRIM:"..before..":"..last)
