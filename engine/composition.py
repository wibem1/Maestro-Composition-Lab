"""Validated score data -> fixed Maestro Lua writer. Never executes model code."""
import copy
from fractions import Fraction
import json, math, re
import expression as expression

PROMPT='''Komponiere das vom Nutzer beauftragte vollständige Stück. Gib nur ein JSON-Objekt aus, keinen Entwurf und keinen Lua-Code.
Technisches Austauschformat (keine Vorgabe für den musikalischen Stil):
{"title":"Titel","composer":"","time":[4,4],"key":[0,"major"],"tempo":100,"staves":[{"name":"Pianoforte","clef":"treble","bars":[{"voices":[[["q",["C4","E4"],["accent"]],["h",["D4"]],["q",null]]],"dynamics":[[0,"p"]]}],"slurs":[]}]}
Erklärung: staves = Notensysteme, Klavier hat zwei (treble und bass). bars enthält ALLE Takte jedes Systems. Bei Taktwechseln erhält der einzelne Takt ein Feld time:[Zaehler,Nenner]. program je System ist optional, GM-Klang 0 bis 127.
voices enthält 1 bis 4 Stimmen. Jede nichtleere Stimme füllt ihren Takt exakt. Eine Stimme besteht aus Einträgen [Dauer, Töne, optionale Artikulationen, optionaler Haltebogen_zum_nächsten_Eintrag].
Dauern: breve,w,h,q,8,16,32,64; bis zu zwei Punkte, z.B. q. oder 8.. . Töne sind eine Liste wie ["C4","Eb4","G4"], null oder [] = Pause. C4 ist mittleres C, B = deutsches H, Bb = deutsches B.
Haltebogen ist boolean true und nur zwischen gleichen vollständigen Akkorden möglich. Artikulationen: accent,staccato,tenuto,staccatissimo,marcato,fermata,trill,upperMordent,lowerMordent,turn,invertedTurn.
Mehrstimmigkeit: voices ist eine Liste getrennter Stimmen, NICHT eine Stimme mit
angehängter Unterstimme. Beispiel für einen vollständigen 3/4-Takt:
{"voices":[[["h",["A4"]],["q",["C5"]]],[["q",null],["h",["F4","C4"]]]],"dynamics":[[0,"p"]]}
Jede nichtleere Stimme füllt unabhängig den ganzen Takt. Prüfe sämtliche
Listenschlüsse und gib ausschließlich syntaktisch gültiges JSON aus.
slurs je System: [Starttakt,Stimme,Eintragsindex,Endtakt,Stimme,Eintragsindex], alles ab 1.
dynamics je Takt: [Tick,"p"], Viertel=960 Ticks. Möglich: ppp,pp,p,mp,mf,f,ff,fff,sf,sfz,fp.
time = Zähler/Nenner. key = Anzahl Vorzeichen (-7 bis 7), major/minor. tempo = Viertel pro Minute.
Alle Systeme haben gleich viele Takte. Dynamik kann taktintern wechseln. Nicht stillschweigend Takte auslassen. Keine Kommentare oder Markdown.''' + expression.PROMPT

class ScoreError(ValueError): pass
BASE={'breve':Fraction(8),'w':Fraction(4),'h':Fraction(2),'q':Fraction(1),'8':Fraction(1,2),'16':Fraction(1,4),'32':Fraction(1,8),'64':Fraction(1,16)}
ART={'accent','staccato','tenuto','staccatissimo','marcato','fermata','trill','upperMordent','lowerMordent','turn','invertedTurn','breathMark','caesura','harmonic'}
DYN={'ppp','pp','p','mp','mf','f','ff','fff','sf','sfz','fp','pppp','ffff','sffz','sfp','fz','rfz'}
CLEFS={'treble','bass','alto','tenor','soprano','mezzoSoprano','baritone','percussion','trebleOctaveDown'}

def duration_ticks(value):
    if not isinstance(value,str):raise ScoreError('Notendauer muss Text sein.')
    dots=len(value)-len(value.rstrip('.'));base=value.rstrip('.')
    if base not in BASE or dots>2:raise ScoreError('Nicht unterstützte Notendauer: '+value)
    length=BASE[base]*sum((Fraction(1,2**i) for i in range(dots+1)),Fraction(0))*960
    if length.denominator!=1:raise ScoreError('Dauer ist im Tickraster nicht darstellbar.')
    return int(length)

def integer(v,lo,hi,label):
    if type(v)!=int or not lo<=v<=hi:raise ScoreError(label+' muss zwischen '+str(lo)+' und '+str(hi)+' liegen.')
    return v

def parse_composition(text):
    text=text.strip()
    if text.startswith('```'):
        lines=text.splitlines()
        if lines[-1].strip()=='```':text='\n'.join(lines[1:-1])
    try:value=json.loads(text)
    except ValueError as e:raise ScoreError('Antwort ist kein vollständiges JSON: '+str(e)) from None
    return validate(value)

def validate(c, warnings=None):
    if not isinstance(c,dict):raise ScoreError('Komposition muss ein JSON-Objekt sein.')
    if set(c)-{'title','composer','time','key','tempo','staves'}:raise ScoreError('Nicht unterstützte Kompositionsfelder: '+', '.join(sorted(set(c)-{'title','composer','time','key','tempo','staves'})))
    title=c.get('title','')
    if not isinstance(title,str) or not title.strip() or len(title)>300:raise ScoreError('Titel fehlt oder ist zu lang.')
    composer=c.get('composer','')
    if not isinstance(composer,str) or len(composer)>300:raise ScoreError('Ungültige Komponistenangabe.')
    meter=c.get('time');key=c.get('key')
    if not isinstance(meter,list) or len(meter)!=2:raise ScoreError('Taktart fehlt.')
    beats=integer(meter[0],1,32,'Taktzähler');denom=integer(meter[1],1,64,'Taktnenner')
    if denom not in (1,2,4,8,16,32,64):raise ScoreError('Taktnenner muss eine Zweierpotenz sein.')
    bar_ticks=int(Fraction(beats*4,denom)*960)
    if not isinstance(key,list) or len(key)!=2 or key[1] not in ('major','minor'):raise ScoreError('Tonart muss [Vorzeichenanzahl,major/minor] sein.')
    fifths=integer(key[0],-7,7,'Vorzeichenanzahl');tempo=c.get('tempo')
    if type(tempo) not in (int,float) or not math.isfinite(tempo) or not 20<=tempo<=300:raise ScoreError('Tempo muss zwischen 20 und 300 liegen.')
    staves=c.get('staves')
    if not isinstance(staves,list) or not staves:raise ScoreError('Mindestens ein Notensystem erforderlich.')
    result={'title':title,'composer':composer,'time':[beats,denom],'key':[fifths,key[1]],'tempo':tempo,'staves':[]}
    n_bars=None;total=0
    for si,staff in enumerate(staves,1):
        if not isinstance(staff,dict):raise ScoreError('Ungültiges System.')
        if set(staff)-{'name','clef','bars','slurs','program','directions'}:raise ScoreError('Nicht unterstützte Systemfelder.')
        name=staff.get('name');clef=staff.get('clef')
        if not isinstance(name,str) or not name.strip() or len(name)>120 or not isinstance(clef,str) or clef not in CLEFS:raise ScoreError('Name oder Schlüssel in System '+str(si)+' ungültig.')
        bars=staff.get('bars')
        if not isinstance(bars,list) or not 1<=len(bars)<=1024:raise ScoreError('1 bis 1024 Takte je System erforderlich.')
        if n_bars is None:n_bars=len(bars)
        if len(bars)!=n_bars:raise ScoreError('Die Systeme haben unterschiedliche Taktzahlen.')
        out={'name':name,'clef':clef,'bars':[],'slurs':[]};
        if 'program' in staff:out['program']=integer(staff['program'],0,127,'GM-Klang')
        flat={i:[] for i in range(1,5)}
        for bi,bar in enumerate(bars,1):
            if not isinstance(bar,dict):raise ScoreError('Ungültiger Takt.')
            if set(bar)-{'voices','dynamics','time','tuplets'}:raise ScoreError('Unbekannte Taktfelder. Spielanweisungen gehören in directions je System.')
            voices=bar.get('voices')
            if not isinstance(voices,list) or not 1<=len(voices)<=4 or not voices[0]:raise ScoreError('Takt '+str(bi)+': 1 bis 4 Stimmen erforderlich.')
            local_time=bar.get('time',meter)
            if not isinstance(local_time,list) or len(local_time)!=2:raise ScoreError('Ungültige lokale Taktart.')
            lb=integer(local_time[0],1,32,'Taktzähler');ld=integer(local_time[1],1,64,'Taktnenner')
            if ld not in (1,2,4,8,16,32,64):raise ScoreError('Ungültiger Taktnenner.')
            bar_ticks=int(Fraction(lb*4,ld)*960)
            newbar={'voices':[],'dynamics':[]}
            tuplets,effective=expression.groups(bar,duration_ticks)
            if tuplets:newbar['tuplets']=tuplets
            if 'time' in bar:newbar['time']=[lb,ld]
            for vi,voice in enumerate(voices,1):
                if not isinstance(voice,list) or len(voice)>512:raise ScoreError('Ungültige Stimme.')
                ticks=0;events=[]
                for ei,event in enumerate(voice,1):
                    if not isinstance(event,list) or not 2<=len(event)<=4:raise ScoreError('Ungültiger Noteneintrag.')
                    d,n=event[:2];ticks+=effective.get((vi,ei),duration_ticks(d))
                    if isinstance(n,str):n=[n]
                    if n is None:n=[]
                    if not isinstance(n,list) or len(n)>16:raise ScoreError('Ungültiger Akkord.')
                    for pitch in n:
                        if not isinstance(pitch,str) or not re.fullmatch(r'[A-G](?:bb|##|b|#|x)?[0-8]',pitch):raise ScoreError('Ungültige Tonhöhe: '+str(pitch))
                        match=re.fullmatch(r'([A-G])(bb|##|b|#|x)?([0-8])',pitch)
                        midi=(int(match[3])+1)*12+{'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[match[1]]+{None:0,'b':-1,'bb':-2,'#':1,'##':2,'x':2}[match[2]]
                        if not 0<=midi<=127:raise ScoreError('Tonhöhe außerhalb MIDI-Bereich.')
                    if len(set(n))!=len(n):raise ScoreError('Doppelter Ton im Akkord.')
                    arts=event[2] if len(event)>2 else []
                    tie=event[3] if len(event)>3 else False
                    if not isinstance(arts,list) or any(not isinstance(x,str) or x not in ART for x in arts):raise ScoreError('Unbekannte Artikulation.')
                    if type(tie)!=bool or (not n and (arts or tie)):raise ScoreError('Ungültiger Haltebogen/Artikulation auf Pause.')
                    events.append([d,n,arts,tie]);flat[vi].append((bi,ei,events[-1]));total+=1
                    if total>50000:raise ScoreError('Zu viele Noteneinträge.')
                if voice and ticks!=bar_ticks:raise ScoreError(f'System {si}, Takt {bi}, Stimme {vi}: {ticks}/960 Viertel statt {bar_ticks}/960. Antwort bleibt zur Korrektur erhalten.')
                newbar['voices'].append(events)
            dynamics=bar.get('dynamics',[])
            if not isinstance(dynamics,list):raise ScoreError('Ungültige Dynamikliste.')
            for item in dynamics:
                if not isinstance(item,list) or len(item)!=2 or not isinstance(item[1],str) or item[1] not in DYN:raise ScoreError('Ungültige Dynamik.')
                integer(item[0],0,bar_ticks-1,'Dynamikposition');newbar['dynamics'].append(item)
            out['bars'].append(newbar)
        for entries in flat.values():
            for i,(bar_number,_,event) in enumerate(entries):
                if event[3] and (i+1>=len(entries) or entries[i+1][0]>bar_number+1 or set(event[1])!=set(entries[i+1][2][1])):raise ScoreError('Haltebogen ohne gleiche nachfolgende Töne.')
        slurs=staff.get('slurs',[])
        if not isinstance(slurs,list):raise ScoreError('Ungültige Bogenliste.')
        for number,endpoints in enumerate(slurs,1):
            try:
                if not isinstance(endpoints,list) or len(endpoints)!=6:raise ScoreError('Ungültiger Phrasierungsbogen.')
                b1,v1,e1,b2,v2,e2=endpoints
                if any(type(x)!=int for x in endpoints) or v1!=v2 or (b1,e1)>=(b2,e2):raise ScoreError('Bogen muss vorwärts in derselben Stimme verlaufen.')
                for b,v,e in ((b1,v1,e1),(b2,v2,e2)):
                    try:
                        if min(b,v,e)<1 or not out['bars'][b-1]['voices'][v-1][e-1][1]:raise IndexError()
                    except IndexError:raise ScoreError('Bogenendpunkt verweist nicht auf eine Note.')
                out['slurs'].append(copy.deepcopy(endpoints))
            except ScoreError as error:
                if warnings is None:raise
                warnings.append(f'System {si}, Phrasierungsbogen {number} ausgelassen: {error} Noten bleiben unverändert.')
        if 'directions' in staff:out['directions']=expression.staff_directions({**out,'directions':staff['directions']},warnings=warnings,staff_number=si)
        result['staves'].append(out)
    for bi in range(n_bars):
        if len({tuple(st['bars'][bi].get('time',meter)) for st in result['staves']})!=1:raise ScoreError('Taktarten der Systeme stimmen nicht überein.')
    return result

def lua_quote(s):
    out='"'
    for ch in str(s):
        if ch in ('"','\\'):out+='\\'+ch
        elif ord(ch)<32:out+='\\'+str(ord(ch)).zfill(3)
        else:out+=ch
    return out+'"'

def lua_writer(data,provider='',model=''):
    # Keep old callers on the same expressive writer as the desktop workflows.
    from workspace import score_lua
    return score_lua(data,'compose',provider=provider,model=model)


def trim_empty_tail_lua():
    # Score chosen explicitly; preserve every bar containing any note in any staff.
    return r'''assert(score, "Keine Zielpartitur")
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
'''
