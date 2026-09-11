'use strict';
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(value);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = {data:null, selected:'TX-1042', details:{}, analyzed:new Set(), explanations:{}, decisions:{}, errors:{}, busy:null};


// One coherent set of local, vector icons. No remote icon font or image service.
const iconPaths = {
  basket:'<path d="M4 9h16l-2 11H6L4 9ZM8 9l4-6 4 6M9 13v3m6-3v3"/>',
  fuel:'<path d="M4 21V4h10v17M2 21h14M7 7h4v5H7M14 10h3v7a2 2 0 0 0 4 0V8l-3-3"/>',
  screen:'<rect x="3" y="4" width="18" height="13" rx="1"/><path d="M8 21h8m-4-4v4M7 8h5"/>',
  bolt:'<path d="m14 2-9 12h7l-2 8 9-12h-7l2-8Z"/>',
  shield:'<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.shield}</svg>`;
const signalLabels = {amount_anomaly:'Un monto fuera de lo habitual',unusual_time:'Una hora poco frecuente',unusual_country:'Otro país de origen',new_merchant:'Un comercio nuevo para ti',high_velocity:'Varias compras en pocos minutos'};

async function api(path, body) {
  const options = body ? {method:'POST',headers:{'Content-Type':'application/json','X-BankGuard':'local'},body:JSON.stringify(body)} : {};
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la solicitud.');
  return result;
}

function renderList() {
  $('transaction-list').innerHTML = state.data.transactions.map(tx => {
    const icons = {SUPERMERCADO:'basket',GASOLINERA:'fuel','TECH STORE':'screen','ELECTRO WORLD':'bolt'};
    const detail = state.details[tx.id];
    const flag = detail && detail.risk.risk_score >= 60;
    const country = {PA:'Panamá',CO:'Colombia',US:'Estados Unidos'}[tx.country] || tx.country;
    return `<button class="transaction ${tx.id===state.selected?'selected':''} ${flag?'needs-review':'normal'}" data-id="${esc(tx.id)}" aria-pressed="${tx.id===state.selected}"><span class="merchant-icon" aria-hidden="true">${icon(icons[tx.merchant])}</span><span class="merchant-info"><b>${esc(tx.merchant)}</b><small>${esc(tx.timestamp.slice(8,10))} sep · ${esc(tx.timestamp.slice(11,16))} · ${esc(country)}</small></span><span class="amount">−${money(tx.amount)}<small>${flag?'Requiere revisión':'✓ Actividad habitual'}</small></span></button>`;
  }).join('');
  $('transaction-list').querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
    state.selected = button.dataset.id;
    renderList(); renderDetail();
  }));
}

function renderDetail() {
  const id = state.selected;
  const detail = state.details[id];
  if (!detail) return;
  const {transaction:tx,risk,context} = detail;
  const analyzed = state.analyzed.has(id);
  const result = state.explanations[id];
  const decision = state.decisions[id];
  const low = risk.risk_score < 30;
  const busy = state.busy === id;
  const country = {PA:'Panamá',CO:'Colombia',US:'Estados Unidos'}[tx.country] || tx.country;
  $('detail-content').innerHTML = `
    <div class="detail-header"><div><div class="eyebrow">EXPEDIENTE LOCAL / ${esc(id)}</div><h2>${esc(tx.merchant)}</h2><p>${esc(country)} · ${esc(tx.timestamp.slice(11,16))} · Tarjeta simulada</p></div><div class="detail-amount">${money(tx.amount)}</div></div>
    <div class="detail-body">
    ${!analyzed ? `<div class="empty"><span class="empty-mark">${icon('shield')}</span><h3>Antes de decidir,<br>mira las señales.</h3><p>Comparamos esta compra con tu historial.<br>Todo ocurre en este dispositivo.</p></div><button id="analyze" class="primary">Revisar este movimiento →</button><p class="button-hint">Reglas explicables · No necesita un modelo de IA</p>` : `
      <div class="risk-overview"><div class="score ${low?'low':''}"><strong>${risk.risk_score}</strong><span>/ 100</span></div><div class="risk-text"><span class="badge ${low?'low':''}">RIESGO ${esc(risk.risk_level.toUpperCase())}</span><h3>${low?'Dentro de tu comportamiento habitual':'Esta operación merece tu atención'}</h3><p>Score determinístico. No es una probabilidad de fraude.</p></div></div><meter class="risk-meter ${low?'low':''}" min="0" max="100" value="${risk.risk_score}" aria-label="Score de riesgo"></meter>
      <ul class="signals">${context.evidence.map((reason,index)=>`<li><span class="signal-number">0${index+1}</span><div><b>${esc(signalLabels[risk.signals[index]] || 'Señal detectada')}</b><span>${esc(reason)}</span></div></li>`).join('') || '<li class="normal-note">No se activaron señales. Esto no garantiza ausencia de fraude.</li>'}</ul>
      ${state.errors[id]?`<div class="error" role="alert">${esc(state.errors[id])}</div>`:''}
      <button id="explain" class="primary" ${state.busy?'disabled':''}>${busy?'<span class="spinner"></span>QVAC está analizando en tu dispositivo…':result?'Generar una nueva explicación local ↻':'Entender estas señales con QVAC →'}</button>
      <p class="button-hint">${busy?'Puede tardar hasta 45 s al iniciar. Puedes seguir revisando otras operaciones.':'Llama 3.2 · Modelo en disco · Contexto compacto'}</p>
      ${result?`<section class="explanation"><div class="eyebrow">LECTURA LOCAL / QVAC</div><h3>Interpretación de las señales.</h3><p>${esc(result.summary)}</p>${result.explanation?`<p>${esc(result.explanation)}</p>`:''}<p><b>${esc(result.recommended_action)}</b></p><small>QVAC local · ${esc(result.seconds)} s · Explicación generada desde señales determinísticas<br>Última generación de esta sesión. El botón ejecuta una inferencia nueva.</small></section>`:''}
      <section class="decision"><h3>¿Reconoces esta compra?</h3><div class="decision-buttons"><button class="secondary" id="recognize">Sí, la reconozco</button><button class="secondary danger" id="report">No la reconozco</button></div>${decision?`<div class="decision-result" role="status">${decision.choice==='reported'?`<b>SIMULACIÓN · Caso #${esc(decision.case)}</b><br>✓ Tarjeta bloqueada temporalmente<br>✓ Transacción reportada<br><small>No se envió un reporte ni se bloqueó una tarjeta real.</small>`:'<b>SIMULACIÓN · Compra reconocida</b><br>El perfil de referencia permanece fijo durante la demo.'}</div>`:''}</section>
      <details class="audit"><summary>Ver evidencia y contexto enviado a QVAC</summary><pre>${esc(JSON.stringify(context,null,2))}</pre></details>
    `}</div>`;
  $('analyze')?.addEventListener('click', () => {state.analyzed.add(id);renderDetail();});
  $('explain')?.addEventListener('click', () => generate(id));
  $('recognize')?.addEventListener('click', () => decide(id,'recognized'));
  $('report')?.addEventListener('click', () => decide(id,'reported'));
}

async function generate(id) {
  if (state.busy) return;
  state.busy = id;
  delete state.errors[id];
  delete state.explanations[id];
  $('reset').disabled = true;
  $('rag-submit').disabled = true;
  renderDetail();
  try { state.explanations[id] = await api('/api/explain',{id}); }
  catch (error) { state.errors[id] = error.message || 'Sin respuesta del servidor local. Revisa que siga ejecutándose.'; }
  finally {state.busy=null; $('reset').disabled=false; $('rag-submit').disabled=false; renderDetail();}
}

async function decide(id, choice) {
  try {state.decisions[id]=await api('/api/decision',{id,choice});}
  catch(error) {state.errors[id]=error.message;}
  if (state.selected===id) renderDetail();
}

$('reset').addEventListener('click', () => {
  if (state.busy) return;
  state.analyzed.clear(); state.explanations={}; state.decisions={}; state.errors={}; state.selected='TX-1042';
  $('rag-result').replaceChildren(); $('rag-question').value='';
  renderList();renderDetail();
});

async function start() {
  try {
    state.data = await api('/api/status');
    const details = await Promise.all(state.data.transactions.map(tx=>api(`/api/analysis?id=${encodeURIComponent(tx.id)}`)));
    details.forEach(detail=>{state.details[detail.transaction.id]=detail;});
    const {runtime,profile,baseline} = state.data;
    $('runtime-title').textContent = runtime.ready ? 'Protección local activa' : 'Protección local no disponible';
    $('runtime-sub').textContent = runtime.ready ? 'QVAC · Inferencia en dispositivo · Sin envío de datos externos' : runtime.error;
    $('average').textContent=money(profile.average_amount);
    const attentionCount=details.filter(d=>d.risk.risk_score>=60).length;
    $('review-count').textContent=attentionCount;
    $('protection-count').textContent=attentionCount;
    $('sidebar-alert-count').textContent=attentionCount;
    $('profile-details').textContent=`Referencia fija: ${profile.count} operaciones anteriores · Promedio ${money(profile.average_amount)} · Mediana ${money(profile.median_amount)} · Desviación ${money(profile.std_amount)} · Horario ${profile.usual_hours[0]}:00–${profile.usual_hours[1]}:59 · Países ${profile.frequent_countries.join(', ')}. Las operaciones evaluadas no se incorporan a este perfil.`;
    $('baseline-rows').innerHTML=baseline.map(tx=>`<tr><td>${esc(tx.timestamp.slice(0,10))}</td><td>${esc(tx.merchant)}</td><td>${money(tx.amount)}</td><td>${esc(tx.country)}</td></tr>`).join('');
    renderList();renderDetail();
  } catch(error) {
    $('global-error').hidden=false;
    $('global-error').textContent='No se pudo conectar con BankGuard. Ejecuta run-web.ps1 y vuelve a cargar esta página. '+error.message;
    $('runtime-title').textContent='Servidor no disponible';
    $('runtime-sub').textContent='Reintenta al iniciar el servidor local';
  }
}
start();

$('rag-example').addEventListener('click',()=>{$('rag-question').value='Me llegó un correo pidiendo confirmar mi contraseña. ¿Qué hago?';$('rag-question').focus();});
$('rag-form').addEventListener('submit',async event=>{
  event.preventDefault();
  if(state.busy) return;
  const question=$('rag-question').value.trim();
  if(question.length<5) return;
  state.busy='rag';$('reset').disabled=true;$('rag-submit').disabled=true;$('rag-question').disabled=true;$('rag-example').disabled=true;
  $('rag-result').replaceChildren();
  $('rag-progress').textContent='QVAC genera el embedding de tu pregunta, busca fragmentos y después carga el LLM. La primera consulta también crea el índice local; puede tardar varios minutos.';
  renderDetail();
  try {
    const result=await api('/api/ask',{question});
    $('rag-result').innerHTML=`<section class="explanation"><h3>${result.supported?'Respuesta con respaldo documental':'Información insuficiente'}</h3><p>${esc(result.answer)}</p><small>${esc(result.mode)} · ${esc(result.seconds)} s · Índice ${result.index_cached?'reutilizado':'creado'}<br>Selección extractiva de un fragmento; no es una política bancaria oficial.</small></section>${result.sources.map(source=>`<details class="audit" open><summary>Fuente: ${esc(source.title)} · ${esc(source.heading)}</summary><p>${esc(source.document)} · ${esc(source.id)}</p><blockquote>${esc(source.text)}</blockquote></details>`).join('')}<details class="audit"><summary>Auditar fragmentos recuperados</summary>${result.retrieved.map(source=>`<p><b>${esc(source.title)} / ${esc(source.heading)}</b><br>Score de búsqueda: ${esc(source.score)} (no es confianza de la respuesta)</p><blockquote>${esc(source.text)}</blockquote>`).join('')}</details>`;
    $('rag-progress').textContent='Consulta terminada. Los modelos se liberaron después del procesamiento.';
  } catch(error) {
    $('rag-result').innerHTML=`<div class="error" role="alert">${esc(error.message)}</div>`;
    $('rag-progress').textContent='No se completó la consulta. Puedes reintentar; el análisis de transacciones sigue disponible.';
  } finally {
    state.busy=null;$('reset').disabled=false;$('rag-submit').disabled=false;$('rag-question').disabled=false;$('rag-example').disabled=false;renderDetail();
  }
});
api('/api/documents').then(result=>{
  $('rag-doc-count').textContent=`${new Set(result.chunks.map(c=>c.document)).size} documentos ficticios · ${result.chunks.length} secciones · QVAC local`;
  $('rag-documents').innerHTML=result.chunks.map(chunk=>`<details class="audit"><summary>${esc(chunk.title)} · ${esc(chunk.heading)}</summary><blockquote>${esc(chunk.text)}</blockquote><small>${esc(chunk.document)} · Material 100% sintético</small></details>`).join('');
}).catch(()=>{$('rag-documents').textContent='No se pudo cargar la lista de documentos. Comprueba el servidor local.';});

// Navigation follows the section the user visits, including the collapsed ledger.
document.querySelectorAll('.nav').forEach(link => link.addEventListener('click', () => {
  document.querySelectorAll('.nav').forEach(item=>item.classList.remove('active'));
  link.classList.add('active');
  if (link.getAttribute('href')==='#history') $('history').open=true;
}));
