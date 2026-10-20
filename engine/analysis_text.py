"""Readable analysis text for a plain-text UI; raw model output stays separate."""
import re

SYMBOLS={
    'rightarrow':'→','longrightarrow':'→','to':'→','Rightarrow':'⇒',
    'leftarrow':'←','longleftarrow':'←','Leftarrow':'⇐',
    'leftrightarrow':'↔','Leftrightarrow':'⇔','uparrow':'↑','downarrow':'↓',
    'sharp':'♯','flat':'♭','natural':'♮','times':'×','cdot':'·',
    'approx':'≈','neq':'≠','leq':'≤','geq':'≥','pm':'±',
    'parallel':'∥','infty':'∞','ldots':'…','dots':'…',
}

def readable(value):
    text=str(value or '')
    text=re.sub(r'\\(?:text|textrm|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}',r'\1',text)
    text=re.sub(r'\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}',r'\1/\2',text)
    text=re.sub(r'\\([A-Za-z]+)\b',lambda m:SYMBOLS.get(m[1],m[0]),text)
    text=re.sub(r'\\\((.*?)\\\)',r'\1',text,flags=re.S)
    text=re.sub(r'\\\[(.*?)\\\]',r'\1',text,flags=re.S)
    text=re.sub(r'(?<!\\)\$\$(.*?)\$\$',r'\1',text,flags=re.S)
    text=re.sub(r'(?<!\\)\$([^\n$]+?)(?<!\\)\$',r'\1',text)
    text=re.sub(r'\\([#$%&_{}])',r'\1',text)
    # The UI deliberately uses textContent, not untrusted model HTML.
    text=re.sub(r'^\s{0,3}#{1,6}\s+', '',text,flags=re.M)
    text=re.sub(r'\*\*([^*\n]+)\*\*',r'\1',text)
    return text
