"""A bounded ending rewrite and new measures, committed in one Maestro script."""
from __future__ import annotations
import copy
import composition as c
import replacement as r
import workspace as w

PROMPT='''
Die Option Schluss fuer den Uebergang ueberarbeiten ist aktiviert. Gestalte die freigegebenen letzten Bestandstakte und die neuen Takte als EINEN musikalischen Zusammenhang. Oeffne bei Bedarf die bisherige Schlusskadenz, entwickle das Motiv weiter und fuehre ueberzeugend in die Verlaengerung. Vor dem freigegebenen Bereich darf nichts geaendert werden.
Gib im normalen Kompositions-JSON zuerst genau die freigegebenen Schlusstakte als Ersatz aus und danach genau die verlangten NEUEN Takte. Taktzahl ist die Gesamtzahl der auszugebenden Takte. Gleiche Systeme und Reihenfolge. Phrasierung und Spielanweisungen koennen den Uebergang von Ersatz zu neuen Takten ueberspannen. Positionen in bars/slurs/directions beginnen im Ersatzbereich bei 1. Alte Dynamik und Spielanweisungen im Ersatzbereich werden entfernt: gib dort die fuer den Zusammenhang benoetigten Angaben neu aus. Vorhandene Taktlaengen und Taktarten im Ersatzbereich exakt erhalten; neue Takte behalten die letzte vorhandene Taktart. Keine neuen globalen Tempoangaben und keine Tonart-/Taktartwechsel. Den Anschluss an den unveraenderten Vortakt beachten, einschliesslich eingehender Halteboegen. Kein Lua-Code.
'''
SPAN_FIELDS=('hairpins','octaves','pedals','textLines')
CLEAR_FIELDS=('dynamics','texts',*SPAN_FIELDS)

def count(value):
    if type(value)!=int or value not in (0,2,3,4):raise c.ScoreError('Für den Übergang bitte 2, 3 oder 4 Schlusstakte wählen.')
    return value

def timed_span(item,bar_number,bars):
    """Maestro stores measure-anchored lines as tick + duration in ticks.

    Evidence: https://maestroscore.app/esempi/canone-pachelbel.maestro,
    hairpins in measure 11: {kind: crescendo, tick: 0, ticks: 6720}.
    Convert against actual measure lengths, including meter changes/pickups.
    """
    def valid(value):return type(value) in (int,float) and value>=0 and value%1==0
    error='Eine bestehende Ausdruckslinie lässt sich am Übergang nicht sicher abgrenzen. Bitte reines Anhängen verwenden.'
    if not isinstance(item,dict) or not valid(item.get('tick')) or any(k in item for k in ('endMeasure','endBar','from','to','start','end','first','last')):raise c.ScoreError(error)
    tick=item['tick'];bar=bars[bar_number-1]
    if tick>bar['ticks']:raise c.ScoreError(error)
    if 'ticks' in item:
        length=item['ticks']
        if not valid(length):raise c.ScoreError(error)
        end=tick+length
        if 'endTick' in item and (not valid(item['endTick']) or item['endTick']!=end):raise c.ScoreError(error)
    else:
        # Retain support for the previously accepted local endTick form.
        end=item.get('endTick')
        if not valid(end) or not tick<=end<=bar['ticks']:raise c.ScoreError(error)
    origin=sum(b['ticks'] for b in bars[:bar_number-1])
    if origin+end>sum(b['ticks'] for b in bars):raise c.ScoreError(error)
    return origin+tick,origin+end

def plan(source,tail):
    tail=count(tail);w.validate_source(source)
    if not tail or source['scope']!='all':raise c.ScoreError('Für den Übergang bitte das ganze Stück einlesen.')
    if tail>source['measure_count']:raise c.ScoreError('Das Stück enthält weniger Takte als für den Übergang freigegeben.')
    first=source['measure_count']-tail+1
    selected=copy.deepcopy(source);selected['scope']='selection'
    selected['selected_entries']=[e for e in w.entries(selected) if e['bar']>=first]
    selected['selected_ids']=[e['id'] for e in selected['selected_entries']]
    # Reuse the existing boundary, rhythm, tie and curve checks.
    rhythm_source=copy.deepcopy(selected)
    for st in rhythm_source['staves']:
        for bar in st['measures']:
            for kind in CLEAR_FIELDS:bar[kind]=[]
    r.targets(rhythm_source)
    chosen=set(selected['selected_ids']);ids={e['id'] for e in w.entries(source)}
    removed=r.curve_plan(selected)
    marks=[]
    for si,st in enumerate(source['staves'],1):
        for bi,bar in enumerate(st['measures'],1):
            if bi>=first and bar.get('chords'):raise c.ScoreError('Akkordsymbole im Schlussbereich können noch nicht neu gestaltet werden. Bitte reines Anhängen verwenden.')
            for kind in SPAN_FIELDS:
                for item in bar.get(kind,[]):
                    linked=r.refs(item,ids)
                    if linked:
                        if linked & chosen and linked-chosen:raise c.ScoreError('Eine bestehende Ausdruckslinie reicht über die Übergangsgrenze. Bitte mehr Schlusstakte wählen oder reines Anhängen verwenden.')
                        delete=bool(linked & chosen)
                    else:
                        start,end=timed_span(item,bi,st['measures'])
                        boundary=sum(bar['ticks'] for bar in st['measures'][:first-1])
                        if start<boundary<end:
                            raise c.ScoreError('Eine bestehende Ausdruckslinie reicht über die Übergangsgrenze. Bitte mehr Schlusstakte wählen oder reines Anhängen verwenden.')
                        delete=start>=boundary
                        if delete and bi<first:
                            raise c.ScoreError('Eine Ausdruckslinie beginnt an der Übergangsgrenze, ist aber im vorherigen Takt verankert. Bitte mehr Schlusstakte wählen.')
                    if delete:marks.append({'staff':si,'bar':bi,'kind':kind,'raw':item})
            if bi>=first:
                for kind in ('dynamics','texts'):
                    marks.extend({'staff':si,'bar':bi,'kind':kind,'raw':item} for item in bar.get(kind,[]))
    systems=[]
    for item in source.get('system_texts',[]):
        if not isinstance(item,dict) or type(item.get('measure'))!=int:raise c.ScoreError('Ein Systemtext lässt sich für die Übergangsoption nicht sicher zuordnen. Bitte reines Anhängen verwenden.')
        if item['measure']>=first:systems.append(item)
    # Repeat signs and other structural marks require their own score-wide model.
    if source.get('measure_marks') or source.get('header',{}).get('measureMarks'):
        raise c.ScoreError('Bei vorhandenen Wiederholungs- oder Strukturzeichen bitte vorerst reines Anhängen verwenden.')
    return {'first':first,'tail':tail,'removed_curves':removed,'marks':marks,'system_texts':systems}

def meter(bar):
    time=bar.get('time')
    if isinstance(time,dict):return [time.get('beats'),time.get('beatType')]
    if isinstance(time,list) and len(time)==2:return time
    from fractions import Fraction
    ratio=Fraction(int(bar['ticks']),3840)
    return [ratio.numerator,ratio.denominator]

def validate(data,source,tail,new_bars):
    p=plan(source,tail);data=c.validate(data)
    if type(new_bars)!=int or not 1<=new_bars<=1024-tail:raise c.ScoreError('Übergang und neue Takte dürfen zusammen höchstens 1024 Takte umfassen.')
    if len(data['staves'])!=len(source['staves']) or any(len(st['bars'])!=tail+new_bars for st in data['staves']):raise c.ScoreError('Die Antwort muss die freigegebenen Schlusstakte UND alle neuen Takte enthalten.')
    for si,st in enumerate(data['staves']):
        for i,bar in enumerate(st['bars']):
            old=source['staves'][si]['measures'][p['first']-1+i] if i<tail else source['staves'][si]['measures'][-1]
            if bar.get('time',data['time'])!=meter(old):raise c.ScoreError('Die Taktarten im Übergang und in der Fortsetzung müssen erhalten bleiben.')
        for d in st.get('directions',[]):
            if d['kind']=='tempo' or (d['kind']=='text' and d.get('category')=='tempo') or (d['kind']=='textLine' and d.get('text','').lower().startswith(('rit','rall','accel','allarg'))):
                raise c.ScoreError('Globale Tempoänderungen sind bei der Übergangsoption noch nicht möglich.')
    # An unchanged incoming tie constrains the first new chord of that voice.
    for si,old_st in enumerate(source['staves']):
        if p['first']==1:continue
        groups={}
        for e in old_st['measures'][p['first']-2]['entries']:groups.setdefault(e['layer'],[]).append(e)
        for layer,es in groups.items():
            last=max(es,key=lambda e:e['tick'])
            if last.get('tied'):
                voices=data['staves'][si]['bars'][0]['voices']
                if layer>len(voices) or not voices[layer-1] or set(voices[layer-1][0][1])!=set(last['pitches']):raise c.ScoreError('Der eingehende Haltebogen passt nicht zum überarbeiteten Schluss.')
    return data

def writer(data,source,tail,new_bars):
    data=validate(data,source,tail,new_bars);p=plan(source,tail);old=source['measure_count']
    durations={e[0]:c.duration_ticks(e[0]) for st in data['staves'] for b in st['bars'] for v in b['voices'] for e in v}
    protected={kind:[item for item in source.get(kind,[]) if item not in p['removed_curves'][kind]] for kind in ('slurs','glissandos')}
    lines=[w.LUA_JSON,'assert(score,"Keine Partitur")',
       'assert(json(score:raw())=='+w.lua(source['guard'])+',"Partitur wurde seit dem Einlesen veraendert. Bitte neu einlesen.")',
       'local generated='+w.lua(data),'local durations='+w.lua(durations),w.FILL,
       'local first='+str(p['first']),
       '''local before={};local names={};local tailMeta={}
local function metadata(m)local raw=m:raw();local out={};for k,v in pairs(raw) do if k~='entries' and k~='layers' and k~='dynamics' and k~='texts' and k~='hairpins' and k~='octaves' and k~='pedals' and k~='textLines' then out[k]=v end end;return json(out)end
for si,st in ipairs(score.staves) do
 names[si]={id=st.id,name=st.name,clef=st.clef};before[si]={};tailMeta[si]={}
 for bi,m in ipairs(st.measures) do if bi<first then before[si][bi]=json(m:raw()) else tailMeta[si][bi]=metadata(m) end end
end''',
       'local removed='+w.lua(p['removed_curves']),
       '''for kind,values in pairs(removed) do for _,raw in ipairs(values) do local list=score[kind];local found=false;for i=#list,1,-1 do if json(list[i]:raw())==json(raw) then list[i]:delete();found=true;break end end;assert(found,'Bestehender Bogen nicht gefunden') end end''',
       'local marks='+w.lua(p['marks']),
       '''for _,mark in ipairs(marks) do local list=score.staves[mark.staff].measures[mark.bar][mark.kind];local found=false;for i=#list,1,-1 do if json(list[i]:raw())==json(mark.raw) then list[i]:delete();found=true;break end end;assert(found,'Bestehende Spielanweisung nicht gefunden') end''',
       'local systems='+w.lua(p['system_texts']),
       '''for _,raw in ipairs(systems) do local list=score.systemTexts;local found=false;for i=#list,1,-1 do if json(list[i]:raw())==json(raw) then list[i]:delete();found=true;break end end;assert(found,'Systemtext nicht gefunden') end''',
       f'assert(score.measureCount=={old},"Taktzahl hat sich veraendert")',
       f'assert(#score.staves=={len(source["staves"])},"Besetzung hat sich veraendert")',
       f'score:appendMeasures({new_bars})',
       'for si,st in ipairs(generated.staves) do fill(score.staves[si],first-1,st,generated.time) end',
       'local protectedSystemTexts='+w.lua([item for item in source.get('system_texts',[]) if item not in p['system_texts']]),
       'assert(json(items(score.systemTexts))==json(protectedSystemTexts),"Systemtexte ausserhalb des Uebergangs wurden veraendert")',
       'local protectedCurves='+w.lua(protected),
       '''for kind,values in pairs(protectedCurves) do local actual=items(score[kind]);for _,raw in ipairs(values) do local found=false;for _,v in ipairs(actual) do if json(v)==json(raw) then found=true;break end end;assert(found,'Bestehender Bogen vor dem Uebergang wurde veraendert') end end
for si,st in ipairs(score.staves) do
 assert(st.id==names[si].id and st.name==names[si].name and st.clef==names[si].clef,'Bestehendes Instrument wurde veraendert')
 for bi,raw in pairs(before[si]) do assert(json(st.measures[bi]:raw())==raw,'Musik vor dem Uebergang wurde veraendert. Gesamte Aenderung wird verworfen.') end
 for bi,raw in pairs(tailMeta[si]) do assert(metadata(st.measures[bi])==raw,'Taktstruktur im Uebergang wurde veraendert') end
end''',
       f'assert(score.measureCount=={old+new_bars},"Taktzahl der Fortsetzung stimmt nicht")',
       'print("WORKSPACE_APPLIED")']
    return '\n'.join(lines)
