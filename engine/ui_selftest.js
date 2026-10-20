// Independent DOM and service test model. No paid calls and no live Maestro.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync(__dirname+'/ui/'+(process.argv[2]||'windows')+'.html','utf8').split('<script>')[1].split('</script>')[0];
const makeSource=scope=>({id:'src-'+scope,score_id:'original',format:'maestro-workspace-1',guard:'snapshot',title:'Original',measure_count:2,last_note_bar:2,scope,selected_ids:scope==='all'?['a','b']:['a'],staves:[{name:'Piano',clef:'treble',measures:[{entries:[{id:'a',staff:1,bar:1,layer:1,duration:'q',pitches:['C4']},{id:'b',staff:1,bar:1,layer:1,duration:'q',pitches:['D4']}]}]}]});
const makeComposition=(staffs,bars=1)=>({title:'Vorschlag',tempo:116,staves:Array.from({length:staffs},(_,i)=>({name:'Instrument '+i,clef:'treble',bars:Array.from({length:bars},()=>({voices:[]}))}))});
function create(){
 const nodes={};function node(id){return nodes[id]??newElement(id)}
 function newElement(id){const n={value:'',textContent:'',disabled:false,hidden:false,children:[],files:[],classList:{toggle(){},add(){}},append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=xs;this.value=''},setAttribute(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false},click(){}};Object.defineProperty(n,'options',{get(){return this.children}});if(id)nodes[id]=n;return n}
 let calls=[],read=null,failApply=false,invalid=false,scoreList=[{score_id:'original',title:'Original'}],native=null;
 const context={window:{chrome:{webview:{addEventListener:(name,fn)=>native=fn}}},document:{getElementById:node,createElement:()=>newElement()},navigator:{clipboard:{writeText:async()=>{}}},setTimeout,clearTimeout,Blob,URL,fetch:async(route,req)=>{
  const b=JSON.parse(req.body);calls.push([route,b]);let data={},ok=true;
  if(route==='/preferences/load')data={provider:'Google',profiles:{Google:{key:'key',model:'remembered',remember:true}},can_protect:true};
  if(route==='/workspace/history'){const all=[{id:'one.json',title:'Historisches Stück',mode:'compose',kind:'Komposition',task:'Heiter',provider:'Google',model:'Argon',status:'Vorschlag',updated_at:'2026-10-19T08:00:00Z'},{id:'two.json',title:'Analyse vom Vortag',mode:'analysis',kind:'Analyse',task:'Stimmführung',provider:'Test',model:'Kritiker',status:'Analyse',updated_at:'2026-10-18T08:00:00Z'}];const items=all.filter(x=>(!b.query||x.title.includes(b.query))&&(b.mode==='all'||b.mode===x.mode));data={items,total:items.length,all_count:2,next_offset:null};}
  if(route==='/workspace/history/open'){data={id:'historical-record',mode:'compose',task:'Heiter',composition:{...makeComposition(2,16),title:'Historisches Stück'},provider:'Google',model:'Argon',saved_path:'saved'};}
  if(route==='/workspace/catalog')data={sounds:[{program:0,name:'Piano'},{program:73,name:'Flöte'}],presets:[{name:'Klavier',program:0,clefs:['treble','bass']},{name:'Flöte',program:73,clefs:['treble']}]};
  if(route==='/models')data={models:[{id:'one',name:'Modell eins'},{id:'two',name:'Modell zwei'}]};
  if(route==='/targets')data={scores:[{score_id:'blank',title:'Leer',empty:true},{score_id:'original',title:'Original',empty:false}]};
  if(route==='/workspace/scores')data={scores:scoreList};
  if(route==='/workspace/read'){read=makeSource(b.scope);read.score_id=b.score_id;data=read;}
  if(route==='/workspace/run'){
   data={id:'record-'+b.mode,mode:b.mode,task:b.task,source:read,provider:b.provider,model:b.model,usage:{total:100},transition_bars:b.transition_bars||0,bars:b.bars,saved_path:'saved',validation_error:invalid?'Takt zu lang':null};
   if(b.mode==='analysis')data.answer='Beurteilung';else if(b.mode==='revise'&&b.revise_kind==='replace'){data.revise_kind='replace';data.replacement={explanation:'Neue rhythmische Gestalt',cells:[{staff:1,bar:1,layer:1,events:[['h',['E4']]]}],slurs:[],removed_curves:0};}else if(b.mode==='revise')data.patches={explanation:'Stimmführung verbessert',changes:[{id:'a',pitches:['C#4']}]};else data.composition=makeComposition(b.mode==='continue'?1:b.ensemble.length,b.mode==='instruments'?2:b.bars+(b.transition_bars||0));
  }
  if(route==='/workspace/review')data={id:'review-record',mode:'revise',task:'Vorschläge umsetzen',source:read,revise_kind:'patch',patches:{changes:[{id:'a',articulations:['tenuto']}],explanation:'Verbesserung aus der Analyse'},review_origin:{id:b.id}};
  if(route==='/workspace/apply'){if(failApply){ok=false;data={error:'Partitur wurde seit dem Einlesen verändert'}}else data={ok:true,score_id:b.score_id||'original'};}
  if(route==='/workspace/load')data={id:'loaded',mode:'compose',task:'Geladen',composition:makeComposition(2,16),provider:'Import',model:'m',saved_path:'saved'};
  if(route==='/trim')data={removed:16,after:16};
  return {ok,json:async()=>data};
 }};
 vm.createContext(context);vm.runInContext(script,context);
 return {node,calls,context,initialized:async()=>{await new Promise(r=>setImmediate(r))},setFailApply:v=>failApply=v,setInvalid:v=>invalid=v,setScores:s=>scoreList=s,native:()=>native};
}
(async()=>{
 const h=create(),n=h.node;await h.initialized();assert.equal(n('model').value,'remembered');assert.equal(n('ensembleRows').children.length,2);
 // Model controls work inside the settings dialog as well as in the header.
 await n('settingsModels').onclick();assert(n('settingsModelList').children.some(o=>o.value==='two'));n('settingsModelList').value='two';n('settingsModelList').onchange();assert.equal(n('model').value,'two');
 // More than 16 systems can be assembled; the exact ensemble is sent.
 n('preset').value='1';for(let i=0;i<19;i++)n('addInstrument').onclick();assert.equal(n('ensembleRows').children.length,21);
 n('task').value='Heiteres Ensemble';n('bars').value='8';await n('run').onclick();assert(h.calls.some(([r,b])=>r==='/workspace/run'&&b.ensemble.length===21));assert(h.calls.some(([r])=>r==='/workspace/apply'));assert(n('apply').disabled);
 // Task/bars survive mode switches. Whole-piece and selection analysis stay read-only.
 n('tab-analysis').onclick();assert(n('ensemblePanel').hidden);await n('run').onclick();assert(h.calls.some(([r,b])=>r==='/workspace/read'&&b.scope==='all'));assert(n('resultText').textContent.includes('Beurteilung'));assert(n('apply').hidden);assert(n('apply').disabled);assert(!n('review').disabled);const writesBeforeReview=h.calls.filter(([r])=>r==='/workspace/apply').length;await n('review').onclick();assert(h.calls.some(([r,b])=>r==='/workspace/review'&&b.id==='record-analysis'));assert.equal(h.calls.filter(([r])=>r==='/workspace/apply').length,writesBeforeReview);assert(!n('apply').disabled);assert(n('resultSummary').textContent.includes('gezielte Änderungen'));n('tab-analysis').onclick();assert(n('resultText').textContent.includes('Beurteilung'));
 n('scope').value='selection';n('scope').onchange();await n('read').onclick();await n('run').onclick();assert(h.calls.some(([r,b])=>r==='/workspace/read'&&b.scope==='selection'));
 n('tab-compose').onclick();assert.equal(n('task').value,'Heiteres Ensemble');assert.equal(n('bars').value,'8');
 // Continuation is a proposal first; explicit application is separate.
 n('tab-continue').onclick();const before=h.calls.filter(([r])=>r==='/workspace/apply').length;await n('run').onclick();assert.equal(h.calls.filter(([r])=>r==='/workspace/apply').length,before);assert(!n('apply').disabled);await n('apply').onclick();assert(n('apply').disabled);
 // Ending rewrite remains optional and creates a proposal with an explicit boundary.
 assert.equal(h.calls.filter(([r])=>r==='/workspace/run').at(-1)[1].transition_bars,0);
 assert(!n('transitionPanel').hidden);n('transitionEnabled').checked=true;n('transitionEnabled').onchange();assert(!n('transitionBars').disabled);
 for(const tail of [2,3,4]){n('transitionBars').value=String(tail);n('transitionBars').onchange();const count=h.calls.filter(([r])=>r==='/workspace/apply').length;await n('run').onclick();assert.equal(h.calls.filter(([r,b])=>r==='/workspace/run').at(-1)[1].transition_bars,tail);assert.equal(h.calls.filter(([r])=>r==='/workspace/apply').length,count);assert(n('resultSummary').textContent.includes(tail+' Schlusstakte überarbeitet'));assert(n('apply').textContent.includes('Übergang'));}
 n('tab-analysis').onclick();assert(n('transitionPanel').hidden);n('tab-continue').onclick();assert(n('transitionEnabled').checked);assert.equal(n('transitionBars').value,'4');
 await vm.runInContext('savePreferences()',h.context);let optionPrefs=h.calls.filter(([r])=>r==='/preferences/save').at(-1)[1];assert(optionPrefs.workspace.transitionEnabled);assert.equal(optionPrefs.workspace.transitionBars,4);
 vm.runInContext('showRecord('+JSON.stringify({id:'loaded-cont',mode:'continue',transition_bars:3,bars:7,task:'Mit Übergang',source:makeSource('all'),composition:makeComposition(1,10)})+')',h.context);
 assert.equal(n('transitionBars').value,'3');assert.equal(n('bars').value,'7');assert(n('transitionEnabled').checked);assert(n('resultText').textContent.includes('Alles davor bleibt erhalten'));
 n('transitionEnabled').checked=false;n('transitionEnabled').onchange();assert(n('transitionBars').disabled);assert.equal(n('run').textContent,'Fortsetzung erstellen');
 // Adding instruments and revising marked entries use separate modes and show a diff.
 n('tab-instruments').onclick();assert(!n('ensemblePanel').hidden);assert.equal(n('ensembleRows').children.length,1);await n('run').onclick();await n('apply').onclick();
 n('tab-revise').onclick();await n('run').onclick();assert(!n('changePanel').hidden);assert.equal(n('changes').children.length,1);
 h.setFailApply(true);await n('apply').onclick();assert(n('status').textContent.includes('verändert'));assert(!n('apply').disabled);h.setFailApply(false);await n('apply').onclick();assert(n('apply').disabled);
 n('reviseKind').value='replace';n('reviseKind').onchange();await n('read').onclick();await n('run').onclick();assert.equal(n('changes').children.length,1);assert(n('resultSummary').textContent.includes('neu gestaltete'));assert(!n('apply').disabled);await n('apply').onclick();assert(h.calls.some(([route,b])=>route==='/workspace/run'&&b.revise_kind==='replace'));
 // Invalid answers remain savable; no automatic destructive apply.
 n('tab-continue').onclick();h.setInvalid(true);const count=h.calls.filter(([r])=>r==='/workspace/apply').length;await n('run').onclick();assert.equal(h.calls.filter(([r])=>r==='/workspace/apply').length,count);assert(n('apply').disabled);assert(!n('save').disabled);
 // Native file-open bridge imports old saved compositions without a paid generation call.
 const generations=h.calls.filter(([r])=>r==='/workspace/run').length;await h.native()({data:{type:'open-composition',text:'old file'}});assert.equal(h.calls.filter(([r])=>r==='/workspace/run').length,generations);assert.equal(n('task').value,'Geladen');
 await vm.runInContext('savePreferences()',h.context);
 const stored=h.calls.filter(([r])=>r==='/preferences/save').at(-1)[1];assert(stored.workspace.ensembles.compose.length>=2);assert(stored.workspace.tasks.continue);
 const paidBeforeHistory=h.calls.filter(([r])=>r==='/workspace/run'||r==='/workspace/review').length;const appliedBeforeHistory=h.calls.filter(([r])=>r==='/workspace/apply').length;await n('historyOpen').onclick();assert(n('history').open);assert.equal(n('historyList').children.length,2);n('historyQuery').value='Analyse';await n('historyRefresh').onclick();assert.equal(n('historyList').children.length,1);n('historyQuery').value='';await n('historyRefresh').onclick();await n('historyList').children[0].onclick();assert(!n('history').open);assert(n('resultSummary').textContent.includes('Historisches Stück'));assert.equal(h.calls.filter(([r])=>r==='/workspace/run'||r==='/workspace/review').length,paidBeforeHistory);assert.equal(h.calls.filter(([r])=>r==='/workspace/apply').length,appliedBeforeHistory);
 console.log('UI passed: 5 modes; 21-system ensemble; whole/selection analysis; proposal-before-apply; source conflict; selected-entry diff; invalid answer retention; native JSON import; model selection; per-mode task/bar persistence.');
})().catch(e=>{console.error(e);process.exit(1)});
