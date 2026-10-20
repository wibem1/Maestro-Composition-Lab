"""Score snapshots, scoped patches and fixed writers for the five workflows."""
from __future__ import annotations
import copy,json,re
import composition as c
import expression as x

LUA_JSON=r'''
local function quote(s)
 return '"'..tostring(s):gsub('[%z\1-\31\\"]',function(x)
  local escapes={['"']='\\"',['\\']='\\\\',['\n']='\\n',['\r']='\\r',['\t']='\\t'}
  return escapes[x] or string.format('\\u%04x',string.byte(x))
 end)..'"'
end
local function json(v,seen)
 local t=type(v)
 if t=='nil' then return 'null' end
 if t=='boolean' then return v and 'true' or 'false' end
 if t=='number' then assert(v==v and v~=math.huge and v~=-math.huge,'Ungueltige Zahl');return tostring(v) end
 if t=='string' then return quote(v) end
 assert(t=='table','Rohdaten sind nicht serialisierbar: '..t)
 seen=seen or {};assert(not seen[v],'Zyklische Rohdaten');seen[v]=true
 local count,arr=0,true
 for k in pairs(v) do count=count+1;if type(k)~='number' or k<1 or k%1~=0 then arr=false end end
 arr=arr and count==#v
 local out={}
 if arr then for i=1,#v do out[#out+1]=json(v[i],seen) end
 else local keys={};for k in pairs(v) do keys[#keys+1]=k end;table.sort(keys,function(a,b)return tostring(a)<tostring(b)end)
  for _,k in ipairs(keys) do out[#out+1]=quote(k)..':'..json(v[k],seen) end
 end
 seen[v]=nil;return (arr and '[' or '{')..table.concat(out,',')..(arr and ']' or '}')
end
local function safe(obj,key)
 local ok,v=pcall(function()return obj[key]end);if not ok then return nil end
 if type(v)=='table' or type(v)=='string' or type(v)=='number' or type(v)=='boolean' or v==nil then return v end
 local ok2,raw=pcall(function()return v:raw()end);if ok2 then return raw end
 return nil
end
local function items(list)
 local result={};if list then for _,v in ipairs(list) do result[#result+1]=v:raw() end end;return result
end
'''

def lua(value):
    if value is None:return 'nil'
    if value is True:return 'true'
    if value is False:return 'false'
    if isinstance(value,(int,float)):return str(value)
    if isinstance(value,str):return c.lua_quote(value)
    if isinstance(value,list):return '{'+','.join(lua(x) for x in value)+'}'
    if isinstance(value,dict):return '{'+','.join('['+c.lua_quote(k)+']='+lua(v) for k,v in value.items())+'}'
    raise c.ScoreError('Unbekannter Datentyp.')

def read_lua(scope):
    if scope not in ('all','selection'):raise c.ScoreError('Unbekannter Lesebereich.')
    return LUA_JSON+'\nlocal scope='+lua(scope)+r'''
assert(score,'Partitur oeffnen')
local selected={}
if scope=='selection' then assert(selection,'Bitte Noten oder Takte markieren');for e in eachentry(selection) do selected[e.id]=true end end
local result={format='maestro-workspace-1',title=score.title,composer=score.composer,tempo=score.tempo,
 time=safe(score,'time'),key=safe(score,'key'),quarter_ticks=960,measure_count=score.measureCount,scope=scope,
 staves={},selected_ids={},selected_entries={},slurs=items(score.slurs),glissandos=items(score.glissandos),system_texts=items(score.systemTexts),measure_marks=items(score.measureMarks),last_note_bar=0}
local raw=score:raw();result.guard=json(raw);result.header={};for k,v in pairs(raw) do local key=tostring(k):lower();if key:find('time') or key:find('meter') or key:find('key') or key:find('tempo') or key:find('measure') or key:find('pickup') then result.header[k]=v end end
for si,staff in ipairs(score.staves) do
 local st={index=si,id=staff.id,name=staff.name,clef=staff.clef,transposition=safe(staff,'transposition'),measures={}}
 for bi,m in ipairs(staff.measures) do
  local cell={index=bi,number=m.number,ticks=m.ticks,time=safe(score.measures[bi],'time'),key=safe(score.measures[bi],'key'),entries={},
   dynamics=items(m.dynamics),hairpins=items(m.hairpins),texts=items(m.texts),chords=items(m.chords),octaves=items(m.octaves),pedals=items(m.pedals),textLines=items(m.textLines)}
  cell.details={};for k,v in pairs(m:raw()) do if k~='entries' and k~='layers' and k~='id' and k~='dynamics' and k~='hairpins' and k~='texts' and k~='chords' and k~='octaves' and k~='pedals' and k~='textLines' then cell.details[k]=v end end
  for e in m:entries() do
   local pitches,arts={},{}
   for _,n in ipairs(e.notes) do pitches[#pitches+1]=n.name end
   for _,art in ipairs(e.articulations) do arts[#arts+1]=art end
   local x={id=e.id,staff=si,bar=bi,layer=e.layer,tick=e.tick,ticks=e.ticks,duration=e.duration,pitches=pitches,articulations=arts,tied=e.tied,is_grace=e.isGrace,raw=e:raw()}
   cell.entries[#cell.entries+1]=x
   if e.isNote then result.last_note_bar=math.max(result.last_note_bar,bi) end
   if scope=='all' or selected[e.id] then result.selected_ids[#result.selected_ids+1]=e.id;result.selected_entries[#result.selected_entries+1]=x end
  end
  st.measures[#st.measures+1]=cell
 end
 result.staves[#result.staves+1]=st
end
assert(#result.selected_ids>0,scope=='selection' and 'Keine Eintraege markiert. Bitte in Maestro Noten oder Takte markieren.' or 'Die Partitur hat noch keine Noten oder Pausen.')
print('BEGIN_MAESTRO_WORKSPACE');print(json(result));print('END_MAESTRO_WORKSPACE')
'''

def parse_tool_result(result):
    strings=[]
    def walk(v):
        if isinstance(v,dict):
            if v.get('format')=='maestro-workspace-1':return v
            for k,x in v.items():
                if k in ('type','mimeType','name'):continue
                found=walk(x)
                if found:return found
        elif isinstance(v,list):
            for x in v:
                found=walk(x)
                if found:return found
        elif isinstance(v,str):
            strings.append(v)
            try:j=json.loads(v)
            except ValueError:return None
            if not isinstance(j,str):return walk(j)
        return None
    found=walk(result)
    if found:return validate_source(found)
    text='\n'.join(strings)
    match=re.search(r'BEGIN_MAESTRO_WORKSPACE\s*(.*?)\s*END_MAESTRO_WORKSPACE',text,re.S)
    if not match:raise c.ScoreError('Maestro hat keine vollständigen Partiturdaten zurückgegeben.')
    return validate_source(json.loads(match[1]))

def validate_source(s):
    if not isinstance(s,dict) or s.get('format')!='maestro-workspace-1':raise c.ScoreError('Keine gültige Partituraufnahme.')
    if not isinstance(s.get('guard'),str) or not s['guard']:raise c.ScoreError('Prüfstand der Partitur fehlt.')
    if not isinstance(s.get('staves'),list) or not s['staves'] or not isinstance(s.get('selected_ids'),list):raise c.ScoreError('Systeme oder Auswahl fehlen.')
    all_entries=entries(s);ids=[e.get('id') for e in all_entries]
    if any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids):raise c.ScoreError('Notenkennungen sind nicht eindeutig.')
    if not set(s['selected_ids'])<=set(ids):raise c.ScoreError('Auswahl passt nicht zur Partitur.')
    for si,st in enumerate(s['staves'],1):
        if len(st.get('measures',[]))!=s['measure_count']:raise c.ScoreError('Abweichende Taktzahlen im Lesestand.')
        for bi,bar in enumerate(st['measures'],1):
            for e in bar['entries']:
                if (e.get('staff'),e.get('bar'))!=(si,bi):raise c.ScoreError('Ungültige Notenposition.')
    return s

def entries(source):return [e for st in source['staves'] for bar in st['measures'] for e in bar['entries']]

def music_entry(entry):
    out={k:v for k,v in entry.items() if k!='raw'}
    raw=entry.get('raw',{})
    if isinstance(raw,dict):
        extra={k:v for k,v in raw.items() if k not in {'id','duration','pitches','articulations','tied','layer','tick','ticks'}}
        notes=raw.get('pitches',[])
        details=[{k:v for k,v in note.items() if k not in {'name','step','alter','octave','midi'}} if isinstance(note,dict) else {} for note in notes] if isinstance(notes,list) else []
        if any(details):extra['note_details']=details
        if extra:out['details']=extra
    return out

def ai_context(source):
    staves=[]
    for st in source['staves']:
        bars=[]
        for bar in st['measures']:
            bars.append({**{k:v for k,v in bar.items() if k!='entries'},'entries':[music_entry(e) for e in bar['entries']]})
        if bars:staves.append({k:v for k,v in st.items() if k!='measures'}|{'measures':bars})
    return {k:source.get(k) for k in ('title','composer','tempo','time','key','scope','measure_count','last_note_bar','quarter_ticks','selected_ids','slurs','glissandos','system_texts','measure_marks','header')}|{'context_scope':'whole_score','edit_scope':source['scope'],'staves':staves}

def ensemble(value):
    if not isinstance(value,list) or not value:raise c.ScoreError('Bitte mindestens ein Instrument hinzufügen.')
    out=[]
    for st in value:
        name=str(st.get('name','')).strip();clef=st.get('clef','treble');program=st.get('program',0)
        if not name or len(name)>120 or clef not in c.CLEFS:raise c.ScoreError('Instrumentenname oder Schlüssel ungültig.')
        c.integer(program,0,127,'Klang');out.append({'name':name,'clef':clef,'program':program})
    return out

def parse_json(text):
    text=text.strip()
    if text.startswith('```') and text.splitlines()[-1].strip()=='```':text='\n'.join(text.splitlines()[1:-1])
    return json.loads(text)

def patches(value,source):
    if not isinstance(value,dict) or set(value)-{'changes','directions','explanation'} or not isinstance(value.get('changes'),list):raise c.ScoreError('Überarbeitung muss changes und optional explanation enthalten.')
    original={e['id']:e for e in entries(source)};selected=set(source['selected_ids']);result=[];seen=set();future=copy.deepcopy(original)
    for patch in value['changes']:
        if not isinstance(patch,dict) or set(patch)-{'id','pitches','duration','articulations','tied','dynamic'}:raise c.ScoreError('Unbekannte Änderung.')
        eid=patch.get('id')
        if eid not in selected or eid in seen:raise c.ScoreError('Änderung außerhalb der Auswahl oder doppelte Notenkennung.')
        seen.add(eid);before=original[eid];after=copy.deepcopy(before)
        if 'pitches' in patch:
            if not isinstance(patch['pitches'],list):raise c.ScoreError('Tonhöhen müssen als Liste vorliegen.')
            # Reuse the independent pitch and articulation validator with a one-beat cell.
            probe={'title':'Prüfung','time':[1,4],'key':[0,'major'],'tempo':100,'staves':[{'name':'Prüfung','clef':'treble','bars':[{'voices':[[['q',patch['pitches']]]]}]}]}
            after['pitches']=c.validate(probe)['staves'][0]['bars'][0]['voices'][0][0][1]
        if 'articulations' in patch:
            arts=patch['articulations']
            if not isinstance(arts,list) or any(not isinstance(a,str) or a not in c.ART for a in arts):raise c.ScoreError('Unbekannte Artikulation.')
            after['articulations']=arts
        if 'tied' in patch:
            if type(patch['tied'])!=bool:raise c.ScoreError('Haltebogen muss true oder false sein.')
            after['tied']=patch['tied']
        if not after['pitches'] and (after['articulations'] or after['tied']):raise c.ScoreError('Pause darf keine Artikulation oder Haltebogen haben.')
        if 'duration' in patch and patch['duration']!=before['duration']:
            if before.get('is_grace') or c.duration_ticks(before['duration'])!=before['ticks']:raise c.ScoreError('Rhythmusänderung an N-tolen/Vorschlägen ist noch nicht möglich; Tonhöhen sind bearbeitbar.')
            layer=[e for e in original.values() if (e['staff'],e['bar'],e['layer'])==(before['staff'],before['bar'],before['layer'])]
            if any(e['id'] not in selected for e in layer):raise c.ScoreError('Für Rhythmusänderungen bitte die gesamte Stimme des betroffenen Takts markieren.')
            after['duration']=patch['duration'];after['ticks']=c.duration_ticks(patch['duration'])
        if 'dynamic' in patch and patch['dynamic'] not in c.DYN:raise c.ScoreError('Unbekannte Dynamik.')
        future[eid]=after
        normalized={k:v for k,v in patch.items()}
        for field in ('pitches','duration','articulations','tied'):
            if field in normalized and normalized[field]==before[field]:normalized.pop(field)
        result.append(normalized)
    groups={}
    for e in original.values():groups.setdefault((e['staff'],e['bar'],e['layer']),[]).append(e)
    for layer in groups.values():
        if sum(e['ticks'] for e in layer)!=sum(future[e['id']]['ticks'] for e in layer):raise c.ScoreError('Geänderte Stimme hat eine andere Gesamtdauer. Rhythmusänderungen müssen sich im Takt ausgleichen.')
    voice_groups={}
    for e in original.values():voice_groups.setdefault((e['staff'],e['layer']),[]).append(e)
    for voice in voice_groups.values():
        voice.sort(key=lambda e:(e['bar'],e['tick']))
        for i,e in enumerate(voice):
            f=future[e['id']]
            if f['tied'] and (e['id'] in seen or (i+1<len(voice) and voice[i+1]['id'] in seen)):
                if i+1>=len(voice) or set(f['pitches'])!=set(future[voice[i+1]['id']]['pitches']):raise c.ScoreError('Änderung würde einen Haltebogen mit unterschiedlichen Tönen erzeugen.')
    return {'changes':result,'directions':x.patch_directions(value.get('directions',[]),source),'explanation':str(value.get('explanation',''))[:12000]}

FILL=x.LUA+r'''
local function fill(staff,offset,generated,defaultTime)
 local refs={}
 for bi,bar in ipairs(generated.bars) do
  local m=staff.measures[offset+bi];local time=bar.time or defaultTime
  local expected=time[1]*4/time[2]*960
  m:clear();refs[bi]={}
  for layer,events in ipairs(bar.voices) do
   refs[bi][layer]={}
   for ei,event in ipairs(events) do
    local notes=#event[2]>0 and event[2] or nil
    local e=m:append(event[1],notes,layer);refs[bi][layer][ei]=e
    for _,art in ipairs(event[3]) do e:add(art) end
    if event[4] then e.tied=true end
    -- Apply each group immediately, before appending following music.
    for _,g in ipairs(bar.tuplets or {}) do
     if g.voice==layer and ei==g.start+g.count-1 then writeTuplet(g,refs[bi]) end
    end
   end
   local position=0
   for ei,event in ipairs(events) do
    local e=refs[bi][layer][ei];local ticks=durations[event[1]]
    for _,g in ipairs(bar.tuplets or {}) do
     if g.voice==layer and ei>=g.start and ei<g.start+g.count then ticks=ticks*g.ratio[2]/g.ratio[1] end
    end
    assert(e.tick==position,'Notenposition nach N-tolen wurde unerwartet umgesetzt')
    assert(e.ticks==ticks,'Notendauer nach N-tolen wurde unerwartet umgesetzt')
    position=position+ticks
   end
   if #events>0 then assert(position==expected,'Stimme fuellt ihren Takt nicht exakt') end
  end
  assert(m.ticks==expected,'Taktart der erzeugten Musik passt nicht zu Takt '..(offset+bi))
  for _,d in ipairs(bar.dynamics) do m.dynamics:add({tick=d[1],marking=d[2]}) end
 end
 for _,s in ipairs(generated.slurs) do musicalCommand('slur',{refs[s[1]][s[2]][s[3]],refs[s[4]][s[5]][s[6]]}) end
 writeDirections(generated.directions,function(p)return refs[p[1]][p[2]][p[3]]end)
end
'''

def score_lua(data,mode,source=None,provider='',model=''):
    data=c.validate(data);n=len(data['staves'][0]['bars']);staff_count=len(data['staves']);lines=[LUA_JSON,'assert(score,"Keine Partitur")']
    if mode!='compose':
        validate_source(source);lines.append('assert(json(score:raw())=='+lua(source['guard'])+',"Partitur wurde seit dem Einlesen veraendert. Bitte erneut einlesen und den Auftrag neu ausfuehren.")')
        lines+=['local before={};for si,s in ipairs(score.staves) do before[si]={};for bi,m in ipairs(s.measures) do before[si][bi]=json(m:raw()) end end']
    lines+=['local generated='+lua(data),'local durations='+lua({e[0]:c.duration_ticks(e[0]) for st in data['staves'] for b in st['bars'] for v in b['voices'] for e in v}),FILL]
    if mode=='compose':
        lines+=['for e in score:entries() do assert(not e.isNote,"Zielpartitur enthaelt bereits Musik. Bitte eine leere Partitur waehlen.") end',
          # Add first, then remove old systems: no zero-staff intermediate state.
          '''local function pianoName(s)local name=s.name:lower();return name:find('piano',1,true) or name:find('klavier',1,true) or name:find('flügel',1,true)end
local keepPiano=#generated.staves==2 and generated.staves[1].clef=='treble' and generated.staves[2].clef=='bass' and #score.staves==2 and (generated.staves[1].program or 0)==0 and (generated.staves[2].program or 0)==0 and score.staves[1].clef=='treble' and score.staves[2].clef=='bass' and pianoName(score.staves[1]) and pianoName(score.staves[2])
if keepPiano then for si,st in ipairs(generated.staves) do score.staves[si].name=st.name end
else local oldCount=#score.staves;for _,st in ipairs(generated.staves) do score:addStaff({name=st.name,clef=st.clef,program=st.program or 0}) end;for i=oldCount,1,-1 do score.staves[i]:delete() end end''',
          f'assert(#score.staves=={staff_count},"Besetzung wurde nicht vollstaendig angelegt")',
          f'score:setTime({data["time"][0]},{data["time"][1]},1)',f'score:setKey({data["key"][0]},1,{lua(data["key"][1])})']
        prev=data['time']
        for bi,bar in enumerate(data['staves'][0]['bars'],1):
            meter=bar.get('time',data['time'])
            if meter!=prev:
                lines += [f'if score.measureCount<{bi} then score:appendMeasures({bi}-score.measureCount) end',f'score:setTime({meter[0]},{meter[1]},{bi})'];prev=meter
        lines += [f'if score.measureCount<{n} then score:appendMeasures({n}-score.measureCount) end',f'if score.measureCount>{n} then score:deleteMeasures({n+1},score.measureCount) end',f'assert(score.measureCount=={n},"Taktzahl stimmt nicht")',
         f'score.title={lua(data["title"])}',f'score.composer={lua(data["composer"])}',f'score.tempo={data["tempo"]}',f'score.copyright={lua("Verwendetes KI-Modell: "+provider+" / "+model)}',
         'for si,st in ipairs(generated.staves) do fill(score.staves[si],0,st,generated.time) end']
    elif mode=='continue':
        old=source['measure_count']
        if staff_count!=len(source['staves']):raise c.ScoreError('Fortsetzung muss dieselbe Besetzung haben.')
        lines += [f'assert(#score.staves=={staff_count},"Besetzung hat sich veraendert")',f'score:appendMeasures({n})',f'assert(score.measureCount=={old+n},"Fortsetzung konnte nicht angehaengt werden")',f'for si,st in ipairs(generated.staves) do fill(score.staves[si],{old},st,generated.time) end']
    elif mode=='instruments':
        old=len(source['staves'])
        if n!=source['measure_count']:raise c.ScoreError('Neue Instrumente müssen den gesamten vorhandenen Taktumfang abdecken.')
        lines += [f'assert(score.measureCount=={n},"Taktzahl hat sich veraendert")',f'assert(#score.staves=={old},"Besetzung hat sich veraendert")',
          'for _,st in ipairs(generated.staves) do local added=score:addStaff({name=st.name,clef=st.clef,program=st.program or 0});fill(added,0,st,generated.time) end',f'assert(#score.staves=={old+staff_count},"Neue Besetzung stimmt nicht")']
    else:raise c.ScoreError('Unbekannter Schreibmodus.')
    if mode!='compose':lines += ['for si,staff in ipairs(before) do for bi,raw in ipairs(staff) do assert(json(score.staves[si].measures[bi]:raw())==raw,"Vorhandene Musik wurde unerwartet veraendert. Gesamte Aenderung wird verworfen.") end end']
    note_count=sum(len(v) for st in data['staves'] for bar in st['bars'] for v in bar['voices'])+(len(entries(source)) if source else 0)
    lines += ['local entryCount=0;for e in score:entries() do entryCount=entryCount+1 end',f'assert(entryCount=={note_count},"Anzahl der Noteneintraege stimmt nicht")']
    if source:
        for si,st in enumerate(source['staves'],1):lines.append(f'assert(score.staves[{si}].id=={lua(st["id"])},"Vorhandenes Instrument wurde verschoben oder ersetzt")')
    expected=n+(source['measure_count'] if mode=='continue' else 0)
    lines += [f'assert(score.measureCount=={expected},"Abschliessende Taktzahl stimmt nicht")',f'for _,st in ipairs(score.staves) do assert(#st.measures=={expected},"Taktzahl eines Systems stimmt nicht") end','print("WORKSPACE_APPLIED")']
    return '\n'.join(lines)

def patch_lua(data,source):
    data=patches(data,source);ids=set(source['selected_ids']);lines=[LUA_JSON,x.LUA,'assert(score,"Keine Partitur")','assert(json(score:raw())=='+lua(source['guard'])+',"Partitur wurde seit dem Einlesen veraendert. Bitte erneut einlesen und den Auftrag neu ausfuehren.")',
      'local chosen='+lua(list(ids))+';local selected={};for _,id in ipairs(chosen) do selected[id]=true end',
      'local protected={};local lookup={};local count=0;for e in score:entries() do lookup[e.id]=e;count=count+1;if not selected[e.id] then protected[e.id]=json(e:raw()) end end',
      'local oldSlurs=items(score.slurs);local oldGlissandos=items(score.glissandos)',
      'local changes='+lua(data['changes']),
      'for _,p in ipairs(changes) do local e=assert(lookup[p.id],"Markierte Note fehlt");assert(selected[p.id],"Note liegt ausserhalb der Auswahl");if p.pitches~=nil then e:setNotes(p.pitches) end;if p.articulations~=nil then e.articulations=p.articulations end;if p.tied~=nil then e.tied=p.tied end end',
      'for _,p in ipairs(changes) do if p.duration~=nil then lookup[p.id].duration=p.duration end end',
      'for _,p in ipairs(changes) do if p.dynamic then local e=lookup[p.id];local m=e.measure;for i=#m.dynamics,1,-1 do if m.dynamics[i].tick==e.tick then m.dynamics[i]:delete() end end;m.dynamics:add({tick=e.tick,marking=p.dynamic}) end end',
      'writeDirections('+lua(data['directions'])+',function(id)return assert(lookup[id],"Ausdrucksanker fehlt")end)',
      'local after={};local afterCount=0;for e in score:entries() do after[e.id]=e;afterCount=afterCount+1 end;assert(afterCount==count,"Noteneintraege wurden unerwartet verschoben oder geteilt")',
      'for id,raw in pairs(protected) do assert(after[id] and json(after[id]:raw())==raw,"Nicht markierte Note wurde veraendert. Gesamte Aenderung wird verworfen.") end',
      '''local function preserveCurves(list,original)
 local found={};for _,v in ipairs(items(list)) do found[json(v)]=true end
 for _,v in ipairs(original) do assert(found[json(v)],'Bestehende Boegen wurden unerwartet veraendert') end
end
preserveCurves(score.slurs,oldSlurs);preserveCurves(score.glissandos,oldGlissandos)''',
      f'assert(score.measureCount=={source["measure_count"]},"Taktzahl wurde veraendert")',f'assert(#score.staves=={len(source["staves"])},"Besetzung wurde veraendert")']
    # Verify the actual resulting notes and durations, not only the unselected material.
    original={e['id']:e for e in entries(source)}
    for p in data['changes']:
        e=original[p['id']]
        if 'pitches' in p:lines.append('do local ns={};for _,n in ipairs(after['+lua(p['id'])+'].notes) do ns[#ns+1]=n.name end;assert(json(ns)=='+lua(json.dumps(p['pitches'],separators=(',',':')))+',"Tonhoehen wurden nicht wie erwartet umgesetzt") end')
        if 'duration' in p:lines.append('assert(after['+lua(p['id'])+'].ticks=='+str(c.duration_ticks(p['duration']))+',"Rhythmus wurde nicht wie erwartet umgesetzt")')
    lines.append('print("WORKSPACE_APPLIED")');return '\n'.join(lines)
