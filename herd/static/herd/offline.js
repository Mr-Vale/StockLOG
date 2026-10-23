document.body.dataset.account=sessionStorage.getItem('stocklog.activeAccount')||'';
const script=document.createElement('script');script.src='/static/herd/recovery.js';document.head.append(script);
