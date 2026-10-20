"""Validated musical expression and irregular groups, shared by all writers.

Only fixed editor commands are emitted. Model text is always Lua-quoted.
Endpoints refer to generated entries, never guessed raw Maestro model fields.
"""
from fractions import Fraction
import copy

LINES={'pedal','crescendo','diminuendo','textLine','glissando','wavyGlissando',
       'octaveUp','octaveDown','twoOctavesUp','twoOctavesDown'}
POINTS={'text','tempo','arpeggio','breathMark','caesura','harmonic'}
CATEGORIES={'expression','technique','tempo'}

PROMPT='''
Musikalischer Ausdruck ist Teil der Komposition: Verwende passende Artikulation,
Dynamik, Phrasierung, Pedalwechsel, Spielanweisungen und bei musikalischer
Begründung Tempoverläufe. Erfinde keine Zeichen nur zur Demonstration.
Zusätzlich zu slurs kann JEDES System directions enthalten. Eine Position
[Takt,Stimme,Eintragsnummer] zählt ab 1 und bezieht sich auf die erzeugten
Noten/Pausen (auch innerhalb eines Takts, auch über Taktgrenzen):
{"kind":"pedal","from":[1,1,1],"to":[2,1,4]}
{"kind":"crescendo","from":[1,1,1],"to":[2,1,4]}
Weitere Linien: diminuendo,glissando,wavyGlissando,octaveUp,octaveDown,
twoOctavesUp,twoOctavesDown. Linien enden am Ende des Zieleintrags;
direkt benachbarte Pedallinien bilden einen Pedalwechsel.
{"kind":"textLine","from":[3,1,1],"to":[4,1,4],"text":"rit."}
Textlinien können rit.,rall.,accel.,cresc.,dim. tragen. Ein genaues Zieltempo
als tempo am folgenden Eintrag angeben; keine garantierte lineare BPM-Kurve
behaupten, Maestro interpretiert die Textlinie.
{"kind":"tempo","from":[5,1,1],"bpm":88,"text":"Andante"}
{"kind":"text","from":[1,1,1],"text":"dolce cantabile","category":"expression"}
category: expression,technique,tempo. Instrumenttechniken z.B. pizz.,arco,
con sord.,senza sord. als technique. a tempo/Tempo I als tempo oder konkretes
tempo mit bpm. Tempo gilt für alle Stimmen: nur einmal im obersten System
ausgeben. Pedal beim Klavier nur einmal, vorzugsweise im unteren System.
arpeggio,breathMark,caesura,harmonic sind directions nur mit kind und from.
Pedal und Bögen dürfen auf derselben Note beginnen/enden, andere Linien
brauchen einen längeren Bereich. Anker sind genaue Notenpositionen, keine
Takttexte ohne Zeitbezug. Allgemeine Ausdruckswörter sind Notationsangaben;
nicht jedes freie Wort hat eine automatische Wiedergabewirkung.

Unregelmäßige Gruppen: optional je Takt tuplets:[{"voice":1,"start":1,
"count":3,"ratio":[3,2]}]. Das sind z.B. drei normal notierte Achtel statt
zwei; events bleiben im bisherigen Format. start/count zählen Einträge,
ratio=geschriebene zu normalen Werten. Gemischte Werte sind möglich.
Gruppen dürfen nicht überlappen, verschachtelt sein oder die Taktgrenze
überschreiten. Berechne die Taktfüllung mit dem Faktor normal/geschrieben.
Nur Gruppen verwenden, deren einzelne effektive Dauern im Raster
Viertel=960 ganzzahlig sind (z.B. Triolen und Quintolen).
'''

def fail(message):
    from composition import ScoreError
    raise ScoreError(message)

def integer(value,lo,hi,name):
    if type(value)!=int or not lo<=value<=hi:fail(name+' ist ungültig.')
    return value

def groups(bar,duration):
    values=bar.get('tuplets',[])
    if not isinstance(values,list):fail('N-tolen müssen als Liste vorliegen.')
    scales={};out=[]
    for group in values:
        if not isinstance(group,dict) or set(group)!={'voice','start','count','ratio'}:fail('Ungültige N-tolengruppe.')
        vi=integer(group['voice'],1,len(bar['voices']),'N-tolenstimme')
        start=integer(group['start'],1,len(bar['voices'][vi-1]),'N-tolenbeginn')
        count=integer(group['count'],2,128,'N-tolenumfang')
        if start+count-1>len(bar['voices'][vi-1]):fail('N-tole überschreitet die Taktstimme.')
        ratio=group['ratio']
        if not isinstance(ratio,list) or len(ratio)!=2:fail('Ungültiges N-tolenverhältnis.')
        a,b=[integer(x,1,32,'N-tolenverhältnis') for x in ratio]
        if a==b:fail('N-tolenverhältnis darf nicht 1:1 sein.')
        for ei in range(start,start+count):
            if (vi,ei) in scales:fail('Überlappende oder verschachtelte N-tolen.')
            ticks=Fraction(duration(bar['voices'][vi-1][ei-1][0])*b,a)
            if ticks.denominator!=1:fail('N-tolendauer liegt nicht im ganzzahligen 960-Tick-Raster.')
            scales[vi,ei]=int(ticks)
        out.append(copy.deepcopy(group))
    return out,scales

def event_ticks(bar,voice,index,duration):
    _,scales=groups(bar,duration)
    return scales.get((voice,index),duration(bar['voices'][voice-1][index-1][0]))

def direction(value,resolve):
    if not isinstance(value,dict):fail('Ungültige Spielanweisung.')
    d=copy.deepcopy(value);kind=d.get('kind')
    if kind not in LINES|POINTS:fail('Unbekannte Spielanweisung: '+str(kind))
    allowed={'kind','from'}|({'to'} if kind in LINES else set())
    if kind=='text':allowed|={'text','category'}
    if kind=='textLine':allowed|={'text'}
    if kind=='tempo':allowed|={'text','bpm'}
    if set(d)-allowed:fail('Unbekannte Felder einer Spielanweisung.')
    a=resolve(d.get('from'))
    if kind in LINES:
        b=resolve(d.get('to'))
        if a[0]!=b[0] or a[1:]>b[1:] or (a==b and kind!='pedal'):fail('Linie muss vorwärts in derselben Stimme verlaufen.')
    # A tempo's numeric BPM is complete without a verbal label.
    if kind=='tempo' and (d.get('text') is None or isinstance(d.get('text'),str) and not d['text'].strip()):
        d.pop('text',None)
    if kind in {'text','textLine'} or 'text' in d:
        if not isinstance(d.get('text'),str) or not d['text'].strip() or len(d['text'])>1000:fail('Text einer Spielanweisung fehlt oder ist zu lang.')
    if kind=='text':
        d.setdefault('category','expression')
        if d['category'] not in CATEGORIES:fail('Unbekannte Textart.')
    if kind=='tempo':
        bpm=d.get('bpm')
        if type(bpm) not in (int,float) or not 20<=bpm<=300:fail('Lokales Tempo muss zwischen 20 und 300 liegen.')
    return d

def staff_directions(staff,warnings=None,staff_number=None):
    def resolve(p):
        if not isinstance(p,list) or len(p)!=3 or any(type(x)!=int or x<1 for x in p):fail('Ungültige Ausdrucksposition.')
        b,v,e=p
        try:staff['bars'][b-1]['voices'][v-1][e-1]
        except IndexError:fail('Spielanweisung verweist auf einen fehlenden Eintrag.')
        return (v,b,e)
    values=staff.get('directions',[])
    if not isinstance(values,list) or len(values)>10000:fail('Ungültige Liste von Spielanweisungen.')
    from composition import ScoreError
    result=[]
    for number,d in enumerate(values,1):
        kind=d.get('kind','unbekannt') if isinstance(d,dict) else 'unbekannt'
        location=(f'System {staff_number}, ' if staff_number is not None else '')+f'Spielanweisung {number} ({kind})'
        try:result.append(direction(d,resolve))
        except ScoreError as error:
            # Only unusable text annotations are optional. Invalid positions,
            # numeric tempo, line ranges and unknown commands still block.
            if warnings is not None and str(error)=='Text einer Spielanweisung fehlt oder ist zu lang.' and kind in {'text','textLine'}:
                warnings.append(location+' ausgelassen: '+str(error)+' Noten bleiben unverändert.')
            else:raise ScoreError(location+': '+str(error)) from error
    return result

def patch_directions(values,source):
    from workspace import entries
    es={e['id']:e for e in entries(source)};chosen=set(source['selected_ids'])
    def resolve(eid):
        if not isinstance(eid,str) or eid not in chosen:fail('Spielanweisung liegt außerhalb der markierten Auswahl.')
        e=es[eid];return (e['staff']*10+e['layer'],e['bar'],e['tick'])
    if not isinstance(values,list) or len(values)>10000:fail('Ungültige Liste von Spielanweisungen.')
    for d in values:
        direction(d,resolve)
        if d.get('to'):
            a,b=es[d['from']],es[d['to']]
            if any(e['id'] not in chosen for e in es.values() if
                   (e['staff'],e['layer'])==(a['staff'],a['layer']) and
                   (a['bar'],a['tick'])<=(e['bar'],e['tick'])<=(b['bar'],b['tick'])):
                fail('Eine Spielanweisung überspannt nicht markierte Musik.')
    return [direction(d,resolve) for d in values]

LUA=r'''
local function musicalCommand(command,region,options)
 local changed,message=editor.perform(command,region,options)
 assert(changed~=false and (type(changed)~='number' or changed>0),
   'Maestro konnte '..command..' nicht anwenden: '..tostring(message))
end
local function writeDirections(directions,resolve)
 local function contains(value,wanted)
  if type(value)=='table' then for _,v in pairs(value) do if contains(v,wanted) then return true end end
  elseif type(wanted)=='number' and type(value)=='number' then return value==wanted
  elseif type(value)=='string' then return value:find(tostring(wanted),1,true)~=nil end
  return false
 end
 for _,d in ipairs(directions or {}) do
  local first=resolve(d.from);local region=first
  if d.to then region={first,(resolve(d.to))} end
  local command=d.kind;local options=nil
  local collection=({pedal='pedals',crescendo='hairpins',diminuendo='hairpins',
    textLine='textLines',octaveUp='octaves',octaveDown='octaves',
    twoOctavesUp='octaves',twoOctavesDown='octaves',text='texts'})[command]
  local function writtenItems()
   if command=='tempoMark' or (command=='text' and d.category=='tempo') then return items(score.systemTexts) end
   if command=='glissando' or command=='wavyGlissando' then return items(score.glissandos) end
   return collection and items(first.measure[collection]) or nil
  end
  if command=='text' then options={text=d.text,kind=d.category}
  elseif command=='tempo' then
   command='tempoMark';options={text=(d.text and (d.text..' ') or '')..'♩ = '..tostring(d.bpm)}
  elseif command=='textLine' then options={text=d.text} end
  local before=writtenItems()
  musicalCommand(command,region,options)
  local after=writtenItems()
  if after then
   assert(#after>=#before and #after>0,'Maestro hat eine Spielanweisung entfernt oder nicht geschrieben: '..command)
   if d.text then assert(contains(after,d.text),'Maestro hat den Anweisungstext nicht uebernommen: '..command) end
   if d.bpm then assert(contains(after,d.bpm),'Maestro hat das lokale Tempo nicht uebernommen') end
  end
 end
end
local function writeTuplet(group,refs)
 local ends={}
 for i=group.start,group.start+group.count-1 do ends[#ends+1]=refs[group.voice][i] end
 musicalCommand('tuplet',ends,{ratio=group.ratio[1]..':'..group.ratio[2]})
end
'''
