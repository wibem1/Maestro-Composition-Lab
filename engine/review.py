"""Turn an existing text analysis into a separate, validated revision proposal."""
import copy,uuid
import composition as c
import workspace as w
import replacement as replacement

def create(api,request,analysis):
    if not isinstance(analysis,dict) or analysis.get('mode')!='analysis':
        raise c.ScoreError('Bitte zuerst eine Analyse erstellen oder laden.')
    text=analysis.get('answer') or analysis.get('raw_response')
    if not isinstance(text,str) or not text.strip() or analysis.get('validation_error'):
        raise c.ScoreError('Die Analyse enthält keine verwendbaren Vorschläge.')
    if not analysis.get('source'):
        raise c.ScoreError('Der Analyse fehlt die zugehörige Partitur. Bitte das Stück erneut analysieren.')
    source=copy.deepcopy(analysis['source']);w.validate_source(source)
    if not source.get('selected_ids'):raise c.ScoreError('Der analysierte Bereich enthält keine Einträge.')
    # An all-score analysis already includes all entry IDs. A selected analysis
    # keeps precisely its original IDs, even if selection/focus later changes.
    original_scope=source['scope'];source['scope']='selection';source['id']=uuid.uuid4().hex
    try:
        replacement.targets(source);kind='replace';reason='Vollständige Taktstimmen können neu gestaltet werden.'
    except c.ScoreError:
        kind='patch';reason='Die analysierte Auswahl wird mit gezielten Notenänderungen überarbeitet.'
    from workflows import run
    body={k:request[k] for k in ('provider','key','model') if k in request}
    body.update(mode='revise',revise_kind=kind,path=request.get('path',''),
        limit=request.get('limit',32768),
        task='Überarbeite den analysierten Bereich auf Grundlage der beigefügten Analyse. '
             'Prüfe ihre Vorschläge kritisch anhand der Partitur und setze die musikalisch '
             'begründeten Verbesserungen um. Erhalte die tragende Idee und den Charakter. '
             'Nicht jeder Vorschlag muss übernommen werden. Begründe die konkreten Änderungen.',
        review_context={'analysis':text,'analysis_task':analysis.get('task',''),
                        'analysed_scope':original_scope})
    record=run(api,body,source)
    record['review_origin']={'id':analysis.get('id'),'answer':text,'task':analysis.get('task',''),
        'provider':analysis.get('provider'),'model':analysis.get('model'),'scope':original_scope}
    record['review_kind_reason']=reason
    record['saved_path']=api.save_composition(record)
    return record
