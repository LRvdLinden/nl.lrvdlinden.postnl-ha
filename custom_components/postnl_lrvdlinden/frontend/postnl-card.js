const POSTNL_DOMAIN = "postnl_lrvdlinden";
const POSTNL_ICON = "/postnl_lrvdlinden_static/postnl-icon.svg";
const POSTNL_VAN = "/postnl_lrvdlinden_static/postnl-van.svg";
const imageCache = new Map();

function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));}
function findEntity(hass, role, configured){
  if(configured && hass.states[configured]) return configured;
  return Object.keys(hass.states).find(id=>hass.states[id]?.attributes?.postnl_role===role) || null;
}
function localLang(hass){return String(hass?.language||navigator.language||"nl").toLowerCase().startsWith("nl")?"nl":"en";}
function dateLabel(value, lang="nl"){
  if(!value) return "—"; const d=new Date(value); if(Number.isNaN(d.getTime())) return String(value);
  try{return new Intl.DateTimeFormat(lang==="nl"?"nl-NL":"en-GB",{day:"numeric",month:"short"}).format(d)}catch(_){return String(value)}
}
function fmtDate(value, lang="nl"){
  if(!value)return "—"; const d=new Date(value); if(Number.isNaN(d.getTime()))return String(value);
  try{return new Intl.DateTimeFormat(lang==="nl"?"nl-NL":"en-GB",{day:"2-digit",month:"2-digit",year:"numeric"}).format(d)}catch(_){return String(value)}
}
function literalParts(raw){
  const s=String(raw||""); const m=s.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/); if(!m)return null;
  return {date:`${m[1]}-${m[2]}-${m[3]}`,mins:+m[4]*60 + +m[5],time:`${m[4]}:${m[5]}`};
}
function nowParts(){const d=new Date();return {date:`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`,mins:d.getHours()*60+d.getMinutes(),secs:d.getHours()*3600+d.getMinutes()*60+d.getSeconds()};}
function addDay(key,n){const [y,m,d]=key.split("-").map(Number),x=new Date(y,m-1,d+n);return `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,"0")}-${String(x.getDate()).padStart(2,"0")}`;}
function dmy(k){if(!k)return"";const[y,m,d]=k.split("-");return `${d}-${m}-${y}`;}
function hhmm(total){const mins=((Math.round(total)%1440)+1440)%1440;return `${String(Math.floor(mins/60)).padStart(2,"0")}:${String(mins%60).padStart(2,"0")}`;}

async function mailImage(hass, entryId, mailId){
  const key=`${entryId}:${mailId}`; if(imageCache.has(key)) return imageCache.get(key);
  const promise=hass.connection.sendMessagePromise({type:`${POSTNL_DOMAIN}/get_mail_image`,entry_id:entryId,mail_id:String(mailId)})
    .then(resp=>{const r=resp?.result||resp; if(!r?.content)return null; return `data:${r.content_type||"image/jpeg"};base64,${r.content}`;})
    .catch(()=>null);
  imageCache.set(key,promise); return promise;
}

const commonCss=`
:host{display:block}*{box-sizing:border-box}.root{color:var(--primary-text-color);font:14px/1.28 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.card{overflow:hidden;border-radius:var(--ha-card-border-radius,17px);background:var(--card-background-color,var(--ha-card-background,#fff));box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002)}
header{height:52px;display:flex;align-items:center;padding:0 18px;border-bottom:1px solid var(--divider-color,#dedee0);background:color-mix(in srgb,var(--card-background-color,#fff) 94%,var(--primary-text-color,#000) 6%)}
header img{width:36px;height:36px;object-fit:contain}header h1{margin:0 0 0 auto;color:var(--secondary-text-color,#777);font-size:18px;font-weight:600}.state{display:grid;place-items:center;min-height:160px;padding:20px;color:var(--secondary-text-color);text-align:center}
`;

class PostNLMailCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._config={};this._signature="";}
  setConfig(c){this._config=c||{};}
  set hass(h){this._hass=h;this.render();}
  getCardSize(){return 5;}
  static getStubConfig(){return{};}
  async render(){
    const h=this._hass;if(!h)return;const id=findEntity(h,"mail",this._config.entity);const s=id?h.states[id]:null;const lang=localLang(h);const a=s?.attributes||{};const items=a.items||[];
    this.shadowRoot.innerHTML=`<style>${commonCss}.content{padding:12px 14px;overflow-x:auto}.track{display:flex;gap:12px;min-height:176px}.mail{flex:0 0 146px;display:grid;grid-template-rows:132px 31px;gap:7px;cursor:pointer}.scan{display:grid;place-items:center;padding:7px;border-radius:9px;background:color-mix(in srgb,var(--primary-text-color) 10%,transparent);overflow:hidden}.scan img{width:100%;height:100%;object-fit:contain;border-radius:3px;background:#fff;box-shadow:0 1px 4px #0003}.date{justify-self:center;padding:4px 13px 5px;border-radius:999px;background:color-mix(in srgb,var(--primary-text-color) 12%,transparent);font-size:15px;font-weight:800}.modal{position:fixed;inset:0;z-index:9999;display:none;place-items:center;padding:18px;background:#000c}.modal.open{display:grid}.modal img{max-width:95vw;max-height:92vh;border-radius:10px;background:#fff}.close{position:absolute;right:16px;top:16px;border:0;border-radius:50%;width:38px;height:38px;background:#222d;color:white;font-size:25px}</style><div class="root card"><header><img src="${POSTNL_ICON}"><h1>${lang==="nl"?"Mijn Post":"My Post"}</h1></header><div class="content">${!s?`<div class="state">${lang==="nl"?"PostNL-entiteit niet gevonden":"PostNL entity not found"}</div>`:!items.length?`<div class="state">${a.mail_api_status==="temporarily_unavailable"?(lang==="nl"?"Mijn Post is tijdelijk niet beschikbaar.":"My Post is temporarily unavailable."):(lang==="nl"?"Er wordt momenteel geen post verwacht.":"No mail is currently expected.")}</div>`:`<div class="track">${items.map((x,i)=>`<article class="mail" data-i="${i}"><div class="scan"><span>✉</span></div><div class="date">${esc(dateLabel(x.delivery_date,lang))}</div></article>`).join("")}</div>`}</div><div class="modal"><button class="close">×</button><img></div></div>`;
    const modal=this.shadowRoot.querySelector('.modal'),modalImg=modal?.querySelector('img');this.shadowRoot.querySelector('.close')?.addEventListener('click',()=>modal.classList.remove('open'));modal?.addEventListener('click',e=>{if(e.target===modal)modal.classList.remove('open')});
    if(!s)return; await Promise.all(items.map(async(x,i)=>{if(!x.image_available)return;const src=await mailImage(h,a.entry_id,x.id);const art=this.shadowRoot.querySelector(`.mail[data-i="${i}"]`),scan=art?.querySelector('.scan');if(src&&scan){scan.innerHTML=`<img src="${src}" alt="PostNL poststuk">`;art.addEventListener('click',()=>{modalImg.src=src;modal.classList.add('open')});}}));
  }
}
customElements.define("postnl-mail-card",PostNLMailCard);

class PostNLLatestMailCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._config={};}
  setConfig(c){this._config=c||{};}
  set hass(h){this._hass=h;this.render();}
  getCardSize(){return 6;}
  static getStubConfig(){return{};}
  async render(){const h=this._hass;if(!h)return;const id=findEntity(h,"mail",this._config.entity),s=id?h.states[id]:null,a=s?.attributes||{},items=a.items||[],item=items[0],lang=localLang(h);
    this.shadowRoot.innerHTML=`<style>${commonCss}.body{padding:14px;display:grid;place-items:center;min-height:240px}.body img{display:block;max-width:100%;max-height:420px;object-fit:contain;border-radius:8px;background:#fff;box-shadow:0 2px 10px #0002}.placeholder{box-shadow:none!important;background:transparent!important;max-width:360px!important}.caption{margin-top:10px;font-weight:700;color:var(--secondary-text-color)}</style><div class="root card"><header><img src="${POSTNL_ICON}"><h1>${lang==="nl"?"Laatste poststuk":"Latest mail item"}</h1></header><div class="body">${item?`<div class="state">${lang==="nl"?"Afbeelding laden…":"Loading image…"}</div>`:`<img class="placeholder" src="/postnl_lrvdlinden_static/no-mail-${lang}.svg" alt="No mail">`}</div></div>`;
    const body=this.shadowRoot.querySelector('.body');if(item?.image_available){const src=await mailImage(h,a.entry_id,item.id);if(src)body.innerHTML=`<div><img src="${src}" alt="PostNL poststuk"><div class="caption">${esc(dateLabel(item.delivery_date,lang))}</div></div>`;else body.innerHTML=`<div class="state">✉<br>${esc(dateLabel(item.delivery_date,lang))}</div>`;}else if(item){body.innerHTML=`<div class="state">✉<br>${esc(dateLabel(item.delivery_date,lang))}</div>`;}
  }
}
customElements.define("postnl-latest-mail-card",PostNLLatestMailCard);

class PostNLPackagesCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._config={};}
  setConfig(c){this._config=c||{};}
  set hass(h){this._hass=h;this.render();}
  getCardSize(){return 7;}
  static getStubConfig(){return{};}
  render(){const h=this._hass;if(!h)return;const id=findEntity(h,"packages",this._config.entity),s=id?h.states[id]:null,a=s?.attributes||{},items=(a.items||[]).slice(0,5),lang=localLang(h);
    this.shadowRoot.innerHTML=`<style>${commonCss}.list{display:grid;gap:8px;padding:10px 12px;max-height:420px;overflow:auto}.p{display:grid;grid-template-columns:54px minmax(0,1fr) minmax(90px,135px);gap:10px;align-items:center;padding:9px 10px;border:1px solid var(--divider-color);border-radius:11px;background:color-mix(in srgb,var(--card-background-color,#fff) 97%,var(--primary-color,#03a9f4) 3%);cursor:pointer}.carrier{display:grid;place-items:center;width:54px;height:42px;border-radius:9px;background:#fff4ec}.carrier img{max-width:42px;max-height:30px}.sender{font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.detail{color:var(--secondary-text-color);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.badge{padding:6px 8px;border-radius:14px;background:#fff0e6;color:#9a3f00;font-size:10px;font-weight:800;text-align:center}.modal{position:fixed;inset:0;z-index:9999;display:none;place-items:center;padding:18px;background:#000c}.modal.open{display:grid}.dialog{width:min(390px,95vw);max-height:85vh;overflow:auto;border-radius:24px;background:var(--card-background-color,#fff);padding:22px;box-shadow:0 18px 50px #0006}.x{float:right;border:0;background:transparent;color:var(--primary-text-color);font-size:26px}.hero{display:flex;gap:12px;align-items:center}.hero img{width:52px}.hero b{font-size:18px}.grid{display:grid;grid-template-columns:120px 1fr;gap:9px 10px;margin-top:18px}.k{color:var(--secondary-text-color)}@media(max-width:420px){.p{grid-template-columns:48px minmax(0,1fr);}.badge{grid-column:2}}</style><div class="root card"><header><img src="${POSTNL_ICON}"><h1>${lang==="nl"?"Mijn Pakketten":"My Packages"}</h1></header>${!items.length?`<div class="state">${lang==="nl"?"Er zijn geen pakketten onderweg.":"There are no parcels on the way."}</div>`:`<div class="list">${items.map((p,i)=>`<div class="p" data-i="${i}"><div class="carrier"><img src="${POSTNL_ICON}"></div><div><div class="sender">${esc(p.sender||"PostNL")}</div><div class="detail">${esc(p.tracking||"")}</div><div class="detail">${esc(p.delivery_window||fmtDate(p.delivery_date,lang))}</div></div><div class="badge">${esc(p.status||"—")}</div></div>`).join("")}</div>`}<div class="modal"><div class="dialog"></div></div></div>`;
    const modal=this.shadowRoot.querySelector('.modal'),dialog=this.shadowRoot.querySelector('.dialog');modal.addEventListener('click',e=>{if(e.target===modal)modal.classList.remove('open')});this.shadowRoot.querySelectorAll('.p').forEach(el=>el.addEventListener('click',()=>{const p=items[+el.dataset.i];dialog.innerHTML=`<button class="x">×</button><div class="hero"><img src="${POSTNL_ICON}"><div><b>${esc(p.sender||"PostNL")}</b><div>${esc(p.status||"—")}</div></div></div><div class="grid"><div class="k">${lang==="nl"?"Tracking":"Tracking"}</div><div>${esc(p.tracking||"—")}</div><div class="k">${lang==="nl"?"Bezorgdatum":"Delivery date"}</div><div>${esc(fmtDate(p.delivery_date,lang))}</div><div class="k">${lang==="nl"?"Bezorgvenster":"Delivery window"}</div><div>${esc(p.delivery_window||"—")}</div><div class="k">${lang==="nl"?"Laatste event":"Latest event"}</div><div>${esc(p.event||"—")}</div><div class="k">${lang==="nl"?"Ontvanger":"Receiver"}</div><div>${esc(p.receiver||"—")}</div><div class="k">${lang==="nl"?"Type zending":"Shipment type"}</div><div>${esc(p.shipment_type||"—")}</div></div>`;dialog.querySelector('.x').onclick=()=>modal.classList.remove('open');modal.classList.add('open');}));
  }
}
customElements.define("postnl-packages-card",PostNLPackagesCard);

class PostNLDeliveryCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._config={};this._timer=null;}
  connectedCallback(){if(!this._timer)this._timer=setInterval(()=>this.updateProgress(),1000)}
  disconnectedCallback(){clearInterval(this._timer);this._timer=null}
  setConfig(c){this._config=c||{};}
  set hass(h){this._hass=h;this.render();}
  getCardSize(){return 7;}
  static getStubConfig(){return{};}
  render(){const h=this._hass;if(!h)return;const id=findEntity(h,"packages",this._config.entity),s=id?h.states[id]:null,a=s?.attributes||{},p=a.active_package,lang=localLang(h);this._parcel=p;
    if(!p){this.shadowRoot.innerHTML=`<style>${commonCss}.empty{display:grid;place-items:center;gap:12px;padding:24px;min-height:290px;text-align:center}.empty img{max-width:280px;width:82%}.empty b{font-size:17px}</style><div class="root card"><header><img src="${POSTNL_ICON}"><h1>${lang==="nl"?"Mijn Bezorging":"My Delivery"}</h1></header><div class="empty"><img src="${POSTNL_VAN}"><b>${lang==="nl"?"Er is geen pakket onderweg":"There is currently no parcel on the way"}</b></div></div>`;return;}
    const from=literalParts(p.delivery_window_from),to=literalParts(p.delivery_window_to),n=nowParts();let headline=p.status||"";if(from&&to){headline=from.date===n.date?(lang==="nl"?`Vandaag tussen ${from.time} en ${to.time}`:`Today between ${from.time} and ${to.time}`):from.date===addDay(n.date,1)?(lang==="nl"?`Morgen tussen ${from.time} en ${to.time}`:`Tomorrow between ${from.time} and ${to.time}`):(lang==="nl"?`${dmy(from.date)} tussen ${from.time} en ${to.time}`:`${dmy(from.date)} between ${from.time} and ${to.time}`)}
    this.shadowRoot.innerHTML=`<style>${commonCss}.pkg{padding:13px 14px 11px}.top{display:flex;gap:10px;align-items:center}.top img{width:42px;height:42px}.sender{font-weight:800;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status{max-width:40%;font-size:11px;color:var(--secondary-text-color);text-align:right}.headline{font-size:14px;font-weight:700;margin-top:10px}.tracking{font-size:11px;color:var(--secondary-text-color);margin-top:2px}.vanwrap{display:grid;place-items:center;min-height:125px;padding:5px}.van{max-width:260px;width:72%;max-height:155px;object-fit:contain}.timeline{position:relative;height:62px;margin:0 2px}.track,.elapsed{position:absolute;left:0;right:0;top:20px;height:3px;background:#777b9c}.elapsed{right:auto;width:0;background:#FB6200}.dot{position:absolute;top:12px;width:18px;height:18px;margin-left:-9px;border:4px solid #FB6200;border-radius:50%;background:var(--card-background-color,#fff)}.tick{position:absolute;top:13px;width:3px;height:18px;background:#cfcfd5}.times{position:absolute;left:0;right:0;top:36px;display:grid;grid-template-columns:1fr 1fr 1fr;color:var(--secondary-text-color);font-size:10px}.times span:nth-child(2){text-align:center}.times span:nth-child(3){text-align:right}.hidden{display:none}</style><div class="root card"><header><img src="${POSTNL_ICON}"><h1>${lang==="nl"?"Mijn Bezorging":"My Delivery"}</h1></header><div class="pkg"><div class="top"><img src="${POSTNL_ICON}"><div class="sender">${esc(p.sender||"PostNL")}</div><div class="status">${esc(p.status||"")}</div></div><div class="headline">${esc(headline)}</div><div class="tracking">${p.tracking?`${lang==="nl"?"Tracking":"Tracking"}: ${esc(p.tracking)}`:""}</div><div class="vanwrap"><img class="van" src="${POSTNL_VAN}"></div><div class="timeline ${from&&to?"":"hidden"}"><div class="track"></div><div class="elapsed"></div><div class="dot"></div><i class="tick start"></i><i class="tick end"></i><div class="times"><span></span><span></span><span></span></div></div></div></div>`;this.updateProgress();
  }
  updateProgress(){const p=this._parcel;if(!p||!this.shadowRoot)return;const a=literalParts(p.delivery_window_from),b=literalParts(p.delivery_window_to),n=nowParts();if(!a||!b)return;const ds=a.mins-60,de=b.mins+60,span=Math.max(1,(de-ds)*60);let pct=n.date>a.date?100:n.date<a.date?0:Math.max(0,Math.min(100,(n.secs-ds*60)/span*100));const q=s=>this.shadowRoot.querySelector(s);if(q('.elapsed'))q('.elapsed').style.width=pct+'%';if(q('.dot'))q('.dot').style.left=pct+'%';const sp=(a.mins-ds)/(de-ds)*100,ep=(b.mins-ds)/(de-ds)*100;if(q('.start'))q('.start').style.left=sp+'%';if(q('.end'))q('.end').style.left=ep+'%';const t=this.shadowRoot.querySelectorAll('.times span');if(t.length===3){t[0].textContent=hhmm(ds);t[1].textContent=hhmm(Math.round((ds+de)/2));t[2].textContent=hhmm(de)}}
}
customElements.define("postnl-delivery-card",PostNLDeliveryCard);

window.customCards = window.customCards || [];
window.customCards.push(
  {type:"postnl-mail-card",name:"PostNL – Mijn Post",description:"Live poststukken inclusief scans",preview:true,getEntitySuggestion:(h,id)=>h.states[id]?.attributes?.postnl_role==="mail"?{entity:id}:null},
  {type:"postnl-latest-mail-card",name:"PostNL – Laatste poststuk",description:"Lovelace-vervanger voor de image capability",preview:true,getEntitySuggestion:(h,id)=>h.states[id]?.attributes?.postnl_role==="mail"?{entity:id}:null},
  {type:"postnl-packages-card",name:"PostNL – Mijn Pakketten",description:"Actuele PostNL-pakketten met details",preview:true,getEntitySuggestion:(h,id)=>h.states[id]?.attributes?.postnl_role==="packages"?{entity:id}:null},
  {type:"postnl-delivery-card",name:"PostNL – Mijn Bezorging",description:"Live bezorgvenster met voortgang",preview:true,getEntitySuggestion:(h,id)=>h.states[id]?.attributes?.postnl_role==="packages"?{entity:id}:null}
);
console.info("%c POSTNL %c Lovelace cards v0.1.0 ","background:#FB6200;color:#fff;font-weight:700","background:#fff;color:#FB6200;font-weight:700");
