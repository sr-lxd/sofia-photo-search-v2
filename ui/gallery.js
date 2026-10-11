'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const api = '/api/v1';
  const initial = {mode:'library',photo_goal:'face',time_basis:'photo',recent_days:30,date_from:null,date_to:null,face_eq:null,face_min:null,face_max:null,directory:'',filename:'',center_lat:null,center_lon:null,radius_km:5,place_name:'',description:'',reference_ids:[],face_mode:'or',min_match_faces:null,sort:'date_desc'};
  const state = {query:{...initial},files:[],draftFiles:[],draftIds:[],draftMode:'library',rows:[],selected:new Set(),cursor:null,searchId:null,batch:1,hasMore:false,range:null,sequence:0,controller:null,history:[],places:[],policy:'',busy:false,downloading:false,selectMode:false,viewIndex:0,zoom:1,rotation:0,panX:0,panY:0};
  const objectUrls = new Map();
  let conditionFocus = null;
  let elapsedTimer = null;
  let started = 0;
  const media = window.matchMedia('(max-width:800px)');

  function storageGet(key, fallback) { try { const value=localStorage.getItem(key); return value===null ? fallback : JSON.parse(value); } catch { return fallback; } }
  function storageSet(key, value) { try { localStorage.setItem(key,JSON.stringify(value)); } catch { /* memory-only operation remains available */ } }
  function key(name) { return `photo_search_v2_${state.policy}_${name}`; }
  function text(id, value) { $(id).textContent=value; }
  function error(value) { text('error',value || ''); $('error').hidden=!value; }
  function message(value) { text('message',value || ''); }
  function filename(path) { return String(path || '').split(/[\\/]/).pop(); }
  function button(label, action, ariaLabel) { const node=document.createElement('button'); node.type='button'; node.textContent=label; if(ariaLabel)node.setAttribute('aria-label',ariaLabel);node.addEventListener('click',action);return node; }
  async function request(path, options={}) {
    const response=await fetch(api+path,{credentials:'same-origin',...options});
    if(response.status===401){state.selected.clear();location.assign('/login');throw new Error('登录已过期');}
    let result;
    try{result=await response.json();}catch{throw new Error('服务器返回了无法读取的结果');}
    if(!response.ok){const detail=result.detail || result.message || result.error;const err=new Error(typeof detail==='string'?detail:detail?.message || '操作失败，请稍后重试');err.code=detail?.code;err.status=response.status;throw err;}
    return result;
  }
  function jsonOptions(data) {return{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)};}
  function nullableNumber(id) {const value=$(id).value.trim();return value===''?null:Number(value);}

  function collect() {
    const q={...initial,mode:state.draftMode,photo_goal:$('photoGoal').value,time_basis:$('timeBasis').value,directory:$('directory').value,filename:$('filename').value.trim(),description:$('description').value.trim(),reference_ids:[...state.draftIds],face_mode:$('faceMode').value,min_match_faces:nullableNumber('minMatch'),sort:$('sort').value};
    const period=$('recentDays').value;
    if(period==='custom'){q.date_from=$('dateFrom').value || null;q.date_to=$('dateTo').value || null;}else if(period!=='all')q.recent_days=Number(period);
    const count=$('faceCount').value;
    if(count==='3-5'){q.face_min=3;q.face_max=5;}else if(count==='6+')q.face_min=6;else if(count==='custom'){q.face_min=nullableNumber('faceMin');q.face_max=nullableNumber('faceMax');}else if(count!=='all')q.face_eq=Number(count);
    if($('placeSelect').value){q.center_lat=nullableNumber('latitude');q.center_lon=nullableNumber('longitude');q.radius_km=Number($('radius').value);q.place_name=$('placeName').value.trim();if(q.center_lat===null||q.center_lon===null)throw new Error('请填写完整的地点坐标');}
    if(q.date_from&&q.date_to&&q.date_from>q.date_to)throw new Error('起始日期不能晚于结束日期');
    if(q.face_min&&q.face_max&&q.face_min>q.face_max)throw new Error('人数下限不能大于上限');
    if(q.mode==='photo'&&!q.reference_ids.length&&!state.draftFiles.length)throw new Error('请添加本次参考照片');
    if(q.mode==='description'&&!q.description)throw new Error('请描述要找的画面');
    return q;
  }
  function hydrate(q, files=state.files) {
    state.draftMode=q.mode;state.draftIds=[...q.reference_ids];state.draftFiles=[...files];
    $('photoGoal').value=q.photo_goal;$('timeBasis').value=q.time_basis;$('recentDays').value=q.recent_days ? String(q.recent_days) : (q.date_from||q.date_to?'custom':'all');
    $('dateFrom').value=q.date_from || '';$('dateTo').value=q.date_to || '';$('description').value=q.description;$('filename').value=q.filename;$('sort').value=q.sort;
    if(q.directory&&!Array.from($('directory').options).some(o=>o.value===q.directory)){$('directory').add(new Option(filename(q.directory),q.directory));}
    $('directory').value=q.directory;$('faceMode').value=q.face_mode;$('minMatch').value=q.min_match_faces || '';
    $('faceCount').value=q.face_eq&&[1,2].includes(q.face_eq)?String(q.face_eq):q.face_min===3&&q.face_max===5?'3-5':q.face_min===6&&!q.face_max?'6+':q.face_eq||q.face_min||q.face_max?'custom':'all';
    $('faceMin').value=q.face_eq || q.face_min || '';$('faceMax').value=q.face_eq || q.face_max || '';
    $('latitude').value=q.center_lat ?? '';$('longitude').value=q.center_lon ?? '';$('radius').value=q.radius_km;$('placeName').value=q.place_name;
    $('placeSelect').value=q.center_lat===null?'':'manual';sections();references();
  }
  function sections() {
    $('photoSection').hidden=state.draftMode!=='photo';$('descriptionSection').hidden=state.draftMode!=='description';
    $('dateFields').hidden=$('recentDays').value!=='custom';$('faceFields').hidden=$('faceCount').value!=='custom';$('gpsFields').hidden=!$('placeSelect').value;
    document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===state.draftMode)));
  }
  function openConditions() {
    conditionFocus=document.activeElement;$('conditionPanel').classList.add('is-open');
    if(media.matches){$('shade').hidden=false;document.body.style.overflow='hidden';$('conditionPanel').setAttribute('role','dialog');$('conditionPanel').setAttribute('aria-modal','true');}
    $('conditionPanel').querySelector(state.draftMode==='description'?'textarea':state.draftMode==='photo'?'select':'#recentDays')?.focus();
  }
  function closeConditions(cancel=false) {
    if(cancel)hydrate(state.query,state.files);
    $('conditionPanel').classList.remove('is-open');$('shade').hidden=true;document.body.style.overflow='';$('conditionPanel').removeAttribute('role');$('conditionPanel').removeAttribute('aria-modal');conditionFocus?.focus();
  }
  function setBusy(value) {
    state.busy=value;$('apply').disabled=value;$('loadMore').disabled=value;
    if(value){started=performance.now();clearInterval(elapsedTimer);elapsedTimer=setInterval(()=>text('elapsed',` · 已等待${Math.floor((performance.now()-started)/1000)}秒`),1000);}else{clearInterval(elapsedTimer);text('elapsed',` · 用时${((performance.now()-started)/1000).toFixed(1)}秒`);}
  }
  async function run(q, {append=false,record=true,files=state.files}={}) {
    state.controller?.abort();const controller=new AbortController();state.controller=controller;const seq=++state.sequence;
    error('');setBusy(true);message(append?'正在加载下一批…':q.mode==='library'?'正在读取照片库…':'正在检索。首次使用模型会稍慢。');
    try {
      let data;
      if(q.mode==='library') {
        const params=new URLSearchParams({config:JSON.stringify(q),limit:'55'});if(append&&state.cursor)params.set('cursor',state.cursor);
        data=await request('/photos/browse?'+params,{signal:controller.signal});
      }else if(append){data=await request('/search/batch?'+new URLSearchParams({search_id:state.searchId,batch:String(state.batch+1)}),{signal:controller.signal});}
      else{const form=new FormData();form.append('config',JSON.stringify(q));files.forEach(file=>form.append('files',file));data=await request('/search/query',{method:'POST',body:form,signal:controller.signal});}
      if(seq!==state.sequence)return;
      if(!append&&record&&state.rows.length){state.history.push({query:structuredClone(state.query),files:[...state.files]});if(state.history.length>20)state.history.shift();}
      const incoming=data.items || data.results || [];
      const previous=append?state.rows:[];const map=new Map(previous.map(row=>[row.photo_id,row]));incoming.forEach(row=>map.set(row.photo_id,row));state.rows=[...map.values()];
      state.query=structuredClone(q);state.files=[...files];state.cursor=data.next_cursor || null;state.searchId=q.mode==='library'?null:data.search_id;state.batch=data.batch || 1;state.hasMore=q.mode==='library'?Boolean(data.has_more):Boolean(data.has_next);if(data.resolved_range)state.range=data.resolved_range;
    state.total=data.total ?? null;hydrate(q,files);render();closeConditions();
      message(q.mode==='description'?'画面描述结果是按相关程度找出的候选，请结合缩略图判断。':state.selected.size?'原有选择已保留，可继续选择或下载。':'');
      if(!append){window.scrollTo({top:0,behavior:'auto'});facets(seq);}
      storageSet(key('recent'),{recent_days:q.recent_days,time_basis:q.time_basis});
    }catch(err){if(err.name==='AbortError'||seq!==state.sequence)return;error(err.message+(state.rows.length?'。已保留上一次结果和选择。':''));if(err.status===404&&q.mode!=='library'||err.code==='library_changed'){message('可点击“应用条件”重新检索，已选照片ID继续保留。');}else message('');}
    finally{if(seq===state.sequence)setBusy(false);}
  }
  function patch(patchValues) {const q={...state.query,...patchValues};hydrate(q,state.files);run(q);}
  function chip(label, values) {$('activeFilters').append(button(label+' ×',()=>patch(values),'移除条件：'+label));}
  function render() {
    const q=state.query;$('activeFilters').replaceChildren();
    if(q.recent_days)chip(`最近${q.recent_days}天`,{recent_days:null});else if(q.date_from||q.date_to)chip(`${q.date_from||'不限'}—${q.date_to||'不限'}`,{date_from:null,date_to:null});
    if(q.time_basis==='added')chip('按入库时间',{time_basis:'photo'});
    if(q.face_eq)chip(`检测人脸${q.face_eq}个`,{face_eq:null});else if(q.face_min||q.face_max)chip(`检测人脸${q.face_min||1}—${q.face_max||'不限'}个`,{face_min:null,face_max:null});
    if(q.directory)chip('目录：'+filename(q.directory),{directory:''});if(q.filename)chip('文件名：'+q.filename,{filename:''});
    if(q.center_lat!==null)chip(`${q.place_name||'指定位置'}附近${q.radius_km}公里`,{center_lat:null,center_lon:null,place_name:''});
    if(q.mode==='photo')chip(`${q.photo_goal==='face'?'参考人脸':'相似画面'} · ${state.files.length+q.reference_ids.length}张`,{mode:'library',reference_ids:[],sort:'date_desc'});
    if(q.mode==='description')chip('描述：'+q.description,{mode:'library',description:'',sort:'date_desc'});
    document.querySelectorAll('[data-recent]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.recent==='all'?!q.recent_days&&!q.date_from&&!q.date_to:Number(b.dataset.recent)===q.recent_days)));
    document.querySelectorAll('[data-basis]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.basis===q.time_basis)));
    text('recentTitle',q.recent_days?'近期照片':'照片库');text('rangeLabel',state.range&&(state.range[0]||state.range[1])?`${q.time_basis==='added'?'入库时间':'照片日期'}：${state.range[0]||'不限'}—${state.range[1]||'不限'}，包含结束日。`:'全部时间。照片日期可能来自EXIF、目录推断或文件时间。');
    text('resultCount',state.total===null?`已加载${state.rows.length}张`:`${state.total}张候选 · 已加载${state.rows.length}张`);$('undo').disabled=!state.history.length;$('loadMore').hidden=!state.hasMore;$('empty').hidden=state.rows.length!==0;
    $('photoGrid').replaceChildren();state.rows.forEach((row,index)=>{
      const card=document.createElement('article');card.className='photo-card';card.dataset.id=row.photo_id;
      const open=button('',()=>preview(index),'预览：'+filename(row.file_path));open.className='photo-open';const image=document.createElement('img');image.src=`${api}/photos/${row.photo_id}/thumb?size=384`;image.alt=filename(row.file_path) || '照片';image.loading='lazy';image.decoding='async';image.onerror=()=>{image.alt='缩略图无法加载，点按查看照片';};open.append(image);
      const pick=document.createElement('label');pick.className='photo-select';const check=document.createElement('input');check.type='checkbox';check.checked=state.selected.has(row.photo_id);check.setAttribute('aria-label','选择照片：'+filename(row.file_path));check.onchange=()=>{if(check.checked)state.selected.add(row.photo_id);else state.selected.delete(row.photo_id);selection();};pick.append(check);
      const caption=document.createElement('div');caption.className='photo-caption';const date=document.createElement('span');date.textContent=String(q.time_basis==='added'?row.created_at||row.exif_datetime||'':row.exif_datetime||'').slice(0,10)||'日期未知';caption.append(date,button('详情',()=>preview(index)));card.append(open,pick,caption);$('photoGrid').append(card);
    });selection();
  }
  function selection() {
    const loaded=new Set(state.rows.map(row=>row.photo_id));const elsewhere=[...state.selected].filter(id=>!loaded.has(id)).length;
    text('selectionCount',`已选${state.selected.size}张${elsewhere?`，另有${elsewhere}张不在当前已加载结果中`:''}`);$('selectionBar').hidden=!state.selected.size&&!state.selectMode;document.body.classList.toggle('has-selection',!$('selectionBar').hidden);
    document.querySelectorAll('.photo-card').forEach(card=>{const selected=state.selected.has(Number(card.dataset.id));card.classList.toggle('is-selected',selected);card.querySelector('input').checked=selected;});
    $('toggleSelect').setAttribute('aria-pressed',String(state.selectMode));$('mobileSelect').textContent=state.selectMode?'结束选择':'选择照片';$('downloadSelected').disabled=!state.selected.size||state.downloading;
  }
  async function facets(seq) {
    $('suggestionPanel').hidden=true;
    try {
      const requestId=String(seq);const data=await request('/search/suggestions',jsonOptions({config:state.query,search_id:state.searchId,request_id:requestId,resolved_range:state.range}));
      if(seq!==state.sequence||data.request_id!==requestId)return;$('suggestionList').replaceChildren();data.suggestions.forEach(item=>$('suggestionList').append(button(`${item.label} · ${item.count}张`,()=>patch(item.patch))));
      if(!state.rows.length&&state.query.recent_days)$('suggestionList').append(button('扩大到全部时间',()=>patch({recent_days:null,date_from:null,date_to:null})));
      text('suggestionScope',data.scope==='current_candidates'?`当前${data.total_candidates}张候选`:`当前条件内${data.total_candidates}张照片`);text('gpsSummary',`${data.no_gps_count}张没有GPS。${state.query.center_lat===null?'选择地点后，无GPS照片不参与附近查询。':'当前已按GPS附近范围筛选。'}`);$('suggestionPanel').hidden=false;
    }catch(err){if(seq===state.sequence)message('照片已显示，筛选提示暂时不可用。');}
  }
  function references() {
    $('referenceList').replaceChildren();
    state.draftFiles.forEach((file,index)=>{if(!objectUrls.has(file))objectUrls.set(file,URL.createObjectURL(file));referenceItem(objectUrls.get(file),file.name,()=>{state.draftFiles.splice(index,1);references();});});
    state.draftIds.forEach(id=>referenceItem(`${api}/photos/${id}/thumb?size=128`,`照片 ${id}`,()=>{state.draftIds=state.draftIds.filter(value=>value!==id);references();}));
  }
  function referenceItem(src,label,remove) {const node=document.createElement('div');node.className='ref-item';const image=document.createElement('img');image.src=src;image.alt=label;const name=document.createElement('span');name.textContent=label;node.append(image,name,button('×',remove,'移除参考图：'+label));$('referenceList').append(node);}
  function places() {
    const current=$('placeSelect').value;$('placeSelect').replaceChildren(new Option('不限',''),new Option('手动指定坐标','manual'));
    state.places.forEach((place,index)=>$('placeSelect').add(new Option(place.name,String(index))));$('placeSelect').value=current;
  }
  function placeChanged() {const value=$('placeSelect').value;if(value&&value!=='manual'){const place=state.places[Number(value)];if(place){$('latitude').value=place.lat;$('longitude').value=place.lon;$('radius').value=place.radius;$('placeName').value=place.name;}}sections();}
  function savePlace() {const lat=nullableNumber('latitude'),lon=nullableNumber('longitude'),radius=Number($('radius').value),name=$('placeName').value.trim();if(!name||lat===null||lon===null||lat< -90||lat>90||lon< -180||lon>180||!Number.isFinite(radius)||radius<.1||radius>1000){error('请填写有效坐标、范围和地点名称');return;}const item={name,lat,lon,radius};const index=state.places.findIndex(place=>place.name===name);if(index>=0)state.places[index]=item;else state.places.push(item);storageSet(key('places'),state.places);places();message('常用地点已保存。');}
  async function pool() {try{const data=await request('/standard');$('poolList').replaceChildren();for(const row of data.items){const b=button('',()=>{if(!state.draftIds.includes(row.photo_id))state.draftIds.push(row.photo_id);references();b.setAttribute('aria-pressed','true');});b.setAttribute('aria-pressed',String(state.draftIds.includes(row.photo_id)));const image=document.createElement('img');image.src=`${api}/photos/${row.photo_id}/thumb?size=128`;image.alt=filename(row.file_path);const label=document.createElement('span');label.textContent=filename(row.file_path);b.append(image,label);$('poolList').append(b);}if(!data.items.length)text('poolList','尚未保存常用参考图，可以从大图预览中保存。');$('poolDialog').showModal();}catch(err){error(err.message);}}
  function transform() {$('largeImage').style.transform=`translate(${state.panX}px,${state.panY}px) rotate(${state.rotation}deg) scale(${state.zoom})`;}
  function resetImage() {state.zoom=1;state.rotation=0;state.panX=0;state.panY=0;transform();}
  function preview(index) {state.viewIndex=Math.max(0,Math.min(index,state.rows.length-1));const row=state.rows[state.viewIndex];if(!row)return;resetImage();$('largeImage').src=`${api}/photos/${row.photo_id}/thumb?size=1024`;$('largeImage').alt=filename(row.file_path);text('viewerPosition',`${state.viewIndex+1} / ${state.rows.length}`);$('prevPhoto').disabled=state.viewIndex===0;$('nextPhoto').disabled=state.viewIndex===state.rows.length-1;$('originalLink').href=`${api}/photos/${row.photo_id}/file`;$('nearbyPhoto').disabled=row.gps_lat==null||row.gps_lon==null;$('photoInfo').replaceChildren();for(const [name,value] of [['文件',row.file_path],['照片日期',row.exif_datetime],['入库时间',row.created_at],['检测人脸',row.face_count],['GPS',row.gps_lat==null?'无GPS':`${row.gps_lat}, ${row.gps_lon}`],['原始相关分数',row.score]]){if(value==null)continue;const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=String(value);$('photoInfo').append(dt,dd);}if(!$('viewer').open)$('viewer').showModal();}
  function usePhoto(goal) {const row=state.rows[state.viewIndex];$('viewer').close();hydrate({...state.query,mode:'photo',photo_goal:goal,reference_ids:[row.photo_id],sort:'relevance'},[]);openConditions();message('已将这张照片加入本次参考。日期、人数等筛选继续保留。');}
  function nearby() {const row=state.rows[state.viewIndex];$('viewer').close();hydrate({...state.query,center_lat:Number(row.gps_lat),center_lon:Number(row.gps_lon),place_name:'照片位置'},state.files);openConditions();}
  async function saveReference() {const row=state.rows[state.viewIndex];try{await request('/standard',jsonOptions({photo_id:row.photo_id}));$('saveReference').textContent='已保存';setTimeout(()=>text('saveReference','保存常用参考图'),1800);}catch(err){error(err.message);}}
  async function download() {if(state.downloading||!state.selected.size)return;state.downloading=true;selection();error('');try{const job=await request('/photos/download_zip_prepare',jsonOptions({photo_ids:[...state.selected]}));const deadline=Date.now()+15*60*1000;let ready;while(Date.now()<deadline){const info=await request('/photos/download_zip_status?'+new URLSearchParams({task_id:job.task_id}));message(info.message || '正在打包所选照片…');if(info.status==='ready'){ready=info;break;}if(info.status==='error')throw new Error(info.message || '打包失败');await new Promise(resolve=>setTimeout(resolve,1000));}if(!ready)throw new Error('打包仍在进行，请稍后重试');const anchor=document.createElement('a');anchor.href=api+'/photos/download_zip_file?'+new URLSearchParams({task_id:job.task_id});anchor.download=ready.zip_name || 'photos.zip';document.body.append(anchor);anchor.click();anchor.remove();message('已开始下载所选照片。');}catch(err){error(err.message);}finally{state.downloading=false;selection();}}

  $('conditions').addEventListener('submit',event=>{event.preventDefault();try{run(collect(),{files:[...state.draftFiles]});}catch(err){error(err.message);}});
  document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{if(b.dataset.mode==='library'){patch({mode:'library',sort:'date_desc'});return;}state.draftMode=b.dataset.mode;$('sort').value='relevance';sections();openConditions();message('设置本次搜索后点击“应用条件”。当前结果暂时保留。');});
  document.querySelectorAll('[data-recent]').forEach(b=>b.onclick=()=>patch({recent_days:b.dataset.recent==='all'?null:Number(b.dataset.recent),date_from:null,date_to:null}));
  document.querySelectorAll('[data-basis]').forEach(b=>b.onclick=()=>patch({time_basis:b.dataset.basis}));
  document.querySelectorAll('[data-scene]').forEach(b=>b.onclick=()=>{$('description').value=b.dataset.scene;$('description').focus();});
  ['recentDays','faceCount'].forEach(id=>$(id).onchange=sections);$('placeSelect').onchange=placeChanged;$('customDate').onclick=()=>{$('recentDays').value='custom';sections();openConditions();};
  $('fileInput').onchange=()=>{for(const file of $('fileInput').files){if(!state.draftFiles.some(old=>old.name===file.name&&old.size===file.size&&old.lastModified===file.lastModified))state.draftFiles.push(file);}references();$('fileInput').value='';};
  $('choosePool').onclick=pool;$('closePool').onclick=()=>$('poolDialog').close();$('savePlace').onclick=savePlace;$('currentLocation').onclick=()=>{if(!navigator.geolocation){error('浏览器不支持定位，可手动输入坐标');return;}navigator.geolocation.getCurrentPosition(position=>{$('latitude').value=position.coords.latitude;$('longitude').value=position.coords.longitude;$('placeName').value='当前位置';},()=>error('未取得位置，可手动输入坐标或从照片选择位置'),{timeout:10000});};
  $('reset').onclick=()=>hydrate({...initial,recent_days:null},[]);$('closeConditions').onclick=()=>closeConditions(true);$('shade').onclick=()=>closeConditions(true);$('openConditions').onclick=openConditions;
  $('loadMore').onclick=()=>run(state.query,{append:true,record:false});$('sort').onchange=()=>patch({sort:$('sort').value});$('expandTime').onclick=()=>patch({recent_days:null,date_from:null,date_to:null});$('switchAdded').onclick=()=>patch({time_basis:'added',recent_days:30,date_from:null,date_to:null});
  $('undo').onclick=()=>{const previous=state.history.pop();if(previous){hydrate(previous.query,previous.files);run(previous.query,{record:false,files:previous.files});}};
  const toggleSelection=()=>{state.selectMode=!state.selectMode;selection();};$('toggleSelect').onclick=toggleSelection;$('mobileSelect').onclick=toggleSelection;$('clearSelection').onclick=()=>{state.selected.clear();state.selectMode=false;selection();};$('selectPage').onclick=()=>{state.rows.forEach(row=>state.selected.add(row.photo_id));selection();};$('downloadSelected').onclick=download;
  $('closeViewer').onclick=()=>$('viewer').close();$('prevPhoto').onclick=()=>preview(state.viewIndex-1);$('nextPhoto').onclick=()=>preview(state.viewIndex+1);$('zoomIn').onclick=()=>{state.zoom=Math.min(5,state.zoom+.5);transform();};$('zoomOut').onclick=()=>{state.zoom=Math.max(1,state.zoom-.5);transform();};$('rotate').onclick=()=>{state.rotation=(state.rotation+90)%360;transform();};$('resetZoom').onclick=resetImage;$('referencePerson').onclick=()=>usePhoto('face');$('referenceScene').onclick=()=>usePhoto('scene');$('nearbyPhoto').onclick=nearby;$('saveReference').onclick=saveReference;
  const pointers=new Map();let gesture=null;const distance=()=>{const pair=[...pointers.values()];return pair.length>=2?Math.hypot(pair[0].x-pair[1].x,pair[0].y-pair[1].y):0;};
  $('imageStage').onpointerdown=event=>{pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});$('imageStage').setPointerCapture(event.pointerId);gesture={x:event.clientX,y:event.clientY,panX:state.panX,panY:state.panY,zoom:state.zoom,distance:distance()};};
  $('imageStage').onpointermove=event=>{if(!pointers.has(event.pointerId)||!gesture)return;pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});if(pointers.size>=2&&gesture.distance){state.zoom=Math.max(1,Math.min(5,gesture.zoom*distance()/gesture.distance));transform();}else if(state.zoom>1){state.panX=gesture.panX+event.clientX-gesture.x;state.panY=gesture.panY+event.clientY-gesture.y;transform();}};
  function endPointer(event,swipe=true){if(gesture&&swipe&&pointers.size===1&&state.zoom===1){const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y;if(Math.abs(dx)>65&&Math.abs(dx)>Math.abs(dy)*1.5)preview(state.viewIndex+(dx<0?1:-1));}pointers.delete(event.pointerId);gesture=null;}
  $('imageStage').onpointerup=endPointer;$('imageStage').onpointercancel=event=>endPointer(event,false);
  document.addEventListener('keydown',event=>{if($('viewer').open){if(event.key==='ArrowLeft'){event.preventDefault();preview(state.viewIndex-1);}if(event.key==='ArrowRight'){event.preventDefault();preview(state.viewIndex+1);}return;}if(media.matches&&$('conditionPanel').classList.contains('is-open')){if(event.key==='Escape')closeConditions(true);if(event.key==='Tab'){const controls=[...$('conditionPanel').querySelectorAll('button,input,textarea,select,summary')].filter(node=>!node.disabled&&node.offsetParent!==null);const first=controls[0],last=controls[controls.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}}});
  $('logout').onclick=async()=>{state.controller?.abort();state.selected.clear();objectUrls.forEach(url=>URL.revokeObjectURL(url));await request('/auth/logout',{method:'POST'});location.assign('/login');};media.addEventListener('change',()=>closeConditions());
  async function start() {try{const auth=await request('/auth/status');if(!auth.authenticated){location.assign('/login');return;}state.policy=auth.policy_id;text('identity',auth.policy_name);state.places=storageGet(key('places'),[]).filter(place=>Number.isFinite(place.lat)&&Number.isFinite(place.lon));places();const recent=storageGet(key('recent'),null);const q={...initial};if(recent&&['photo','added'].includes(recent.time_basis)){q.time_basis=recent.time_basis;q.recent_days=[7,30,90,null].includes(recent.recent_days)?recent.recent_days:30;}hydrate(q,[]);await run(q,{record:false});request('/photos/directories').then(data=>{data.items.forEach(item=>$('directory').add(new Option(item.path,item.path)));$('directory').value=state.query.directory;}).catch(()=>{});request('/gallery/capabilities').then(data=>text('descriptionNote',data.description_note)).catch(()=>{});}catch(err){error(err.message);text('resultCount','暂时无法读取照片库');}}
  start();
})();
