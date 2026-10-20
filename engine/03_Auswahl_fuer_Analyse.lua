--[[ maestro
name = { de = "Composition Lab: Auswahl fuer Analyse", en = "Composition Lab: Export selection for review" }
needsSelection = true
]]
-- Version 0.4.0 / 18.10.2026. Ausschliesslich lesend.
local function quote(s)
  return '"' .. tostring(s):gsub('[%z\1-\31\\"]', function(c)
    local escapes = { ['"']='\\"', ['\\']='\\\\', ['\n']='\\n', ['\r']='\\r', ['\t']='\\t' }
    return escapes[c] or string.format('\\u%04x', string.byte(c))
  end) .. '"'
end
local function json(v, seen)
  local t = type(v)
  if t == 'nil' then return 'null' end
  if t == 'boolean' then return v and 'true' or 'false' end
  if t == 'number' then
    assert(v == v and v ~= math.huge and v ~= -math.huge, 'Ungueltige Zahl')
    return tostring(v)
  end
  if t == 'string' then return quote(v) end
  assert(t == 'table', 'Nicht serialisierbarer Datentyp: ' .. t)
  seen = seen or {}; assert(not seen[v], 'Zyklische Daten'); seen[v] = true
  local out, count, length, array = {}, 0, #v, true
  for k in pairs(v) do count = count + 1; if type(k) ~= 'number' or k < 1 or k % 1 ~= 0 then array = false end end
  array = array and count == length
  if array then
    for i=1,length do out[#out+1] = json(v[i], seen) end
  else
    for k,x in pairs(v) do out[#out+1] = quote(k) .. ':' .. json(x, seen) end
  end
  seen[v] = nil
  return (array and '[' or '{') .. table.concat(out, ',') .. (array and ']' or '}')
end
assert(score and selection, 'Partitur oeffnen und Passage markieren')
local warnings = {}
local function read(obj, field)
  local ok, value = pcall(function() return obj[field] end)
  if ok then return value end
  warnings[#warnings+1] = 'Feld nicht verfuegbar: ' .. field
end
local function raw(obj, label)
  local ok, value = pcall(function() return obj:raw() end)
  if ok and type(value) == 'table' then
    local valid = pcall(json, value)
    if valid then return value end
  end
  warnings[#warnings+1] = 'Rohdaten fehlen: ' .. label
end
local entries = {}
for e in eachentry(selection) do
  local item = { duration=e.duration, tick=e.tick, rest=e.isRest, pitches={} }
  item.ticks = read(e,'ticks')
  for _, n in ipairs(e.notes or {}) do
    item.pitches[#item.pitches+1] = { name=n.name, midi=n.midi }
  end
  item.raw = raw(e,'Noteneintrag')
  entries[#entries+1] = item
end
assert(#entries > 0, 'Keine Noten oder Pausen ausgewaehlt')
local attributes = {}
local function scalar_or_raw(value, label)
  if value == nil then return nil end
  if pcall(json, value) then return value end
  return raw(value, label)
end
local globals = read(score,'measures')
if globals then
  for i, m in ipairs(globals) do
    attributes[#attributes+1] = {
      measure_index=i,
      time=scalar_or_raw(read(m,'time'),'Taktart'),
      key=scalar_or_raw(read(m,'key'),'Tonart')
    }
  end
end
local cells = {}
for measure, staff in eachcell(selection) do
  cells[#cells+1] = {staff=staff.name, measure=measure.number, context=raw(measure,'Takt')}
end
local payload = {
  format='maestro-review-1', version='1.0.0', title=score.title,
  composer=read(score,'composer'), tempo=read(score,'tempo'),
  scope='Ausgewaehlte Eintraege; vollstaendige betroffene Takte nur als Kontext',
  quarter_ticks=960, measure_attributes=attributes, selected_entries=entries, context_cells=cells, warnings=warnings
}
print('BEGIN_MAESTRO_REVIEW')
print(json(payload))
print('END_MAESTRO_REVIEW')
print('Ausgelesen: ' .. #entries .. ' Eintraege. Partitur unveraendert.')
