/* Encrypted, account-scoped pending input only: never an offline farm database. */
(async () => {
  const account = document.body.dataset.account;
  if (!account || !window.crypto?.subtle) return;
  sessionStorage.setItem('stocklog.activeAccount',account);
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/recovery-worker.js').catch(()=>{});
  const scope = 'stocklog.pending.' + location.origin + '.' + account;
  const keyName = scope + '.sessionkey';
  const encode = b => btoa(String.fromCharCode(...new Uint8Array(b)));
  const decode = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  let keyText = sessionStorage.getItem(keyName);
  if (!keyText) { keyText = encode(crypto.getRandomValues(new Uint8Array(32))); sessionStorage.setItem(keyName, keyText); }
  const key = crypto.subtle.importKey('raw', decode(keyText), 'AES-GCM', false, ['encrypt', 'decrypt']);
  async function retain(form) {
    const values = [...new FormData(form)].filter(([k]) => !['csrfmiddlewaretoken', 'password'].includes(k));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt({name:'AES-GCM',iv}, await key, new TextEncoder().encode(JSON.stringify({path:location.pathname,values})));
    localStorage.setItem(scope, JSON.stringify({iv:encode(iv),data:encode(encrypted)}));
  }
  async function pending() {
    const saved = JSON.parse(localStorage.getItem(scope) || 'null');
    if (!saved) return null;
    return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:decode(saved.iv)},await key,decode(saved.data))));
  }
  const clear = () => localStorage.removeItem(scope);
  document.querySelector('[data-logout]')?.addEventListener('submit', () => {clear();sessionStorage.removeItem(keyName);sessionStorage.removeItem('stocklog.activeAccount');});
  if (document.querySelector('#confirmed-result')) clear();
  const panel = document.querySelector('#recovery');
  async function send(path, values) {
    const body = new FormData(); values.forEach(([k,v]) => body.append(k,v));
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || document.cookie.split('; ').find(v=>v.startsWith('csrftoken='))?.split('=')[1];
    if (csrf) body.set('csrfmiddlewaretoken',csrf);
    const response = await fetch(path,{method:'POST',body,credentials:'same-origin'});
    if (!response.ok) throw new Error('Server did not confirm this submission.');
    const html = await response.text();
    window.stocklogRecoveryReady=false;document.open();document.write(html);document.close();
  }
  async function show() {
    let saved;
    try { saved = await pending(); }
    catch (_) { panel.hidden=false;panel.textContent='A previous encrypted pending entry cannot be recovered in this browser session. It is not proof that a server event was saved. Check History before re-entering.';return; }
    if (!saved) return;
    panel.hidden=false;panel.replaceChildren();
    const message=document.createElement('p');message.textContent='Not confirmed: pending input is stored in this browser session. Review, retry, download or discard it. Discard never reverses a server event. Closing/clearing browser storage can lose recovery input.';panel.append(message);
    const review=document.createElement('pre');review.textContent=saved.values.find(([k])=>k==='readable_input')?.[1] || saved.values.filter(([k])=>!['confirmed_payload','submission_key'].includes(k)).map(([k,v])=>`${k}: ${v}`).join('\n');panel.append(review);
    for (const [label,handler] of [
      ['Retry same submission',async()=>{try{await send(saved.path,saved.values);}catch(e){message.textContent='Not confirmed. '+e.message;}}],
      ['Download readable input',()=>{const blob=new Blob([review.textContent+'\nPath: '+saved.path+'\nSubmission: '+(saved.values.find(([k])=>k==='submission_key')?.[1]||'import batch')],{type:'text/plain'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='StockLOG-pending.txt';a.click();URL.revokeObjectURL(a.href);}],
      ['Discard local input',()=>{clear();panel.hidden=true;}]
    ]) {const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',handler);panel.append(b);}
  }
  document.querySelectorAll('form[data-recovery]').forEach(form=>form.addEventListener('submit',async event=>{
    event.preventDefault();
    try {await retain(form);await send(location.pathname,[...new FormData(form)].filter(([k])=>k!=='csrfmiddlewaretoken'));}
    catch(e){await show();panel.hidden=false;}
  }));
  window.stocklogRecoveryReady=true;
  await show();
})();
