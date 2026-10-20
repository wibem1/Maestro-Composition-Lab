"""Bounded recovery of score container syntax; never invent musical values.

Only missing array closers in bar objects and a trailing nested voice can be
recovered. Tokens, order, event contents and all musical checks are preserved.
The caller must validate the complete candidate before displaying a proposal.
"""
import copy,json,re

def invalid_constant(value):
    raise ValueError('Ungültiger JSON-Zahlenwert: '+value)

TOKEN=re.compile(r'"(?:[^"\\]|\\.)*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null|[{}\[\],:]|\s+')

def close_bar_arrays(text):
    if len(text)>8_000_000:raise ValueError('Partiturantwort zu groß für lokale Strukturprüfung.')
    tokens=[];end=0
    for m in TOKEN.finditer(text):
        if m.start()!=end:raise ValueError('Unbekannte Zeichen in der Partiturantwort.')
        end=m.end()
        if not m.group().isspace():tokens.append(m.group())
    if end!=len(text):raise ValueError('Unvollständige Zeichenfolge in der Partiturantwort.')
    stack=[];out=[];added=0
    def close_arrays():
        nonlocal added
        owner=next((x for x in reversed(stack) if x['kind']=='{'),None)
        if owner is None or 'voices' not in owner['fields']:raise ValueError('Fehlende Klammer außerhalb eines Takts; keine automatische Korrektur.')
        while stack and stack[-1]['kind']=='[':
            stack.pop();out.append(']');added+=1
            if added>4096:raise ValueError('Zu viele fehlende Klammern.')
    for i,t in enumerate(tokens):
        is_key=t.startswith('"') and i+1<len(tokens) and tokens[i+1]==':'
        if is_key and stack and stack[-1]['kind']=='[':
            if json.loads(t) not in {'dynamics','time','tuplets'} or not out or out[-1]!=',':raise ValueError('Mehrdeutige Struktur; keine automatische Korrektur.')
            out.pop();close_arrays();out.append(',')
        if is_key and stack and stack[-1]['kind']=='{':stack[-1]['fields'].add(json.loads(t))
        if t in ('[','{'):stack.append({'kind':t,'fields':set()})
        elif t=='}':
            if stack and stack[-1]['kind']=='[':close_arrays()
            if not stack or stack.pop()['kind']!='{':raise ValueError('Nicht passende Objektklammer.')
        elif t==']':
            if not stack or stack.pop()['kind']!='[':raise ValueError('Nicht passende Listenklammer.')
        out.append(t)
    if stack or not added:raise ValueError('Antwort ist unvollständig oder nicht eindeutig korrigierbar.')
    return json.loads(''.join(out),parse_constant=invalid_constant),added

def decode(text,warnings):
    from composition import ScoreError
    text=text.strip()
    if text.startswith('```') and text.splitlines()[-1].strip()=='```':text='\n'.join(text.splitlines()[1:-1])
    added=0
    try:value=json.loads(text,parse_constant=invalid_constant)
    except json.JSONDecodeError as original:
        try:value,added=close_bar_arrays(text)
        except ValueError:raise ScoreError(f'KI-Antwort ist kein gültiges Partitur-JSON (Zeile {original.lineno}, Spalte {original.colno}). Rohantwort ist gespeichert; keine Musik wurde verändert.') from original
    value=copy.deepcopy(value);split=[]
    def event(x):return isinstance(x,list) and 2<=len(x)<=4 and isinstance(x[0],str)
    if isinstance(value,dict) and isinstance(value.get('staves'),list):
        for si,st in enumerate(value['staves'],1):
            if not isinstance(st,dict) or not isinstance(st.get('bars'),list):continue
            for bi,bar in enumerate(st['bars'],1):
                if not isinstance(bar,dict):continue
                vs=bar.get('voices')
                if not isinstance(vs,list) or len(vs)!=1 or not isinstance(vs[0],list) or len(vs[0])<2:continue
                first,tail=vs[0][:-1],vs[0][-1]
                if all(event(x) for x in first) and isinstance(tail,list) and tail and all(event(x) for x in tail):
                    bar['voices']=[first,tail];split.append(f'{si}/{bi}')
    if added or split:
        warnings.append('Lokale Strukturkorrektur: '+str(added)+' fehlende Listenschlüsse ergänzt; '+str(len(split))+' verschachtelte Taktstimmen getrennt'+(' (System/Takt: '+', '.join(split)+')' if split else '')+'. Tonhöhen, Dauern und Ausdrucksangaben bleiben unverändert; vollständige Partiturprüfung erforderlich.')
    return value
