"""Small diagnostic records without credentials or entire score payloads."""
import datetime

FIELDS=('mode','task','provider','model','bars','transition_bars','revise_kind','source_id','score_id','id')

def context(route,request):
    request=request if isinstance(request,dict) else {}
    result={'date':datetime.datetime.now().astimezone().isoformat(),'route':route}
    for key in FIELDS:
        if key in request and isinstance(request[key],(str,int,float,bool)):
            result[key]=request[key][:1500] if isinstance(request[key],str) else request[key]
    return result

def record_error(server,route,request,error):
    data=context(route,request);message=str(error)
    secret=request.get('key') if isinstance(request,dict) else None
    if isinstance(secret,str) and secret:
        message=message.replace(secret,'[entfernt]')
        for key,value in data.items():
            if isinstance(value,str):data[key]=value.replace(secret,'[entfernt]')
    data.update(message=message[:6000],error_type=type(error).__name__)
    server.last_error=data
    return data

def report_ui(server,request):
    message=str(request.get('message') or '')[:6000]
    previous=getattr(server,'last_error',None)
    if previous and previous.get('message')==message:
        previous['ui_mode']=str(request.get('mode') or '')[:100]
    else:record_error(server,'ui',request,message)
    return {'ok':True}
