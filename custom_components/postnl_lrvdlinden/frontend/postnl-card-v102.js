(() => {
  "use strict";

  const VERSION = "1.0.2";
  const DOMAIN = "postnl_lrvdlinden";
  const BASE = `/${DOMAIN}_static`;
  const ICON = `${BASE}/icon.svg`;
  const VAN = `${BASE}/postnl-van.gif`;
  const VAN_STATIC = `${BASE}/van-1.svg`;
  const PACKAGE = `${BASE}/package.svg`;
  const imageCache = new Map();

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
  const lang = hass => String(hass?.language || navigator.language || "nl").toLowerCase().startsWith("nl") ? "nl" : "en";
  const entity = (hass, role, configured) => configured && hass?.states?.[configured] ? hass.states[configured] : Object.values(hass?.states || {}).find(s => s?.attributes?.postnl_role === role) || null;
  const dateText = (v, l) => { if (!v) return "—"; const d = new Date(v); if (Number.isNaN(d.getTime())) return String(v); try { return new Intl.DateTimeFormat(l === "nl" ? "nl-NL" : "en-GB", {day:"2-digit",month:"2-digit",year:"numeric"}).format(d); } catch (_) { return String(v); } };
  const getMailImage = async (hass, entryId, mailId) => {
    if (!hass || !entryId || !mailId) return null;
    const key = `${entryId}:${mailId}`;
    if (!imageCache.has(key)) {
      const call = hass.callWS ? hass.callWS.bind(hass) : (msg => hass.connection.sendMessagePromise(msg).then(r => r?.result || r));
      imageCache.set(key, call({type:`${DOMAIN}/get_mail_image`,entry_id:entryId,mail_id:String(mailId)}).then(r => r?.content ? `data:${r.content_type || "image/jpeg"};base64,${r.content}` : null).catch(() => null));
    }
    return imageCache.get(key);
  };

  const common = `
    :host{display:block}*{box-sizing:border-box}.card{overflow:hidden;border-radius:var(--ha-card-border-radius,17px);background:var(--card-background-color,var(--ha-card-background,#fff));color:var(--primary-text-color);box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002);font:14px/1.3 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{height:52px;display:flex;align-items:center;padding:0 17px;border-bottom:1px solid var(--divider-color,#ddd)}header img{width:36px;height:36px;object-fit:contain}header b{margin-left:auto;color:var(--secondary-text-color);font-size:18px}.empty{min-height:180px;display:grid;place-items:center;text-align:center;padding:24px;color:var(--secondary-text-color)}.orange{color:#fb6200}`;

  class Editor extends HTMLElement {
    setConfig(c){this._config=c||{};this.render();} set hass(h){this._hass=h;this.render();}
    render(){this.innerHTML=`<div style="padding:16px;color:var(--secondary-text-color);line-height:1.45">${lang(this._hass)==="nl"?"Deze PostNL-kaart gebruikt automatisch de gegevens van je gekoppelde PostNL-integratie. Er zijn geen extra instellingen nodig.":"This PostNL card automatically uses data from your linked PostNL integration. No extra settings are required."}</div>`;}
  }
  if(!customElements.get("postnl-card-editor")) customElements.define("postnl-card-editor",Editor);

  class Base extends HTMLElement {
    constructor(){super();this.attachShadow({mode:"open"});this._config={};this._hass=null;}
    setConfig(c){this._config=c||{};} set hass(h){this._hass=h;this.render();} getCardSize(){return 6;}
    static getStubConfig(){return {};} static getConfigElement(){return document.createElement("postnl-card-editor");}
  }

  class MailCard extends Base {
    async render(){
      const hass=this._hass;if(!hass)return;const l=lang(hass),state=entity(hass,"mail",this._config.entity),a=state?.attributes||{},items=Array.isArray(a.items)?a.items:[];
      this.shadowRoot.innerHTML=`<style>${common}.list{display:flex;gap:12px;padding:13px;overflow-x:auto}.mail{flex:0 0 146px;cursor:pointer}.scan{height:132px;padding:7px;display:grid;place-items:center;border-radius:9px;background:color-mix(in srgb,var(--primary-text-color) 10%,transparent);overflow:hidden}.scan img{width:100%;height:100%;object-fit:contain;background:#fff;border-radius:4px}.date{text-align:center;margin:7px auto 0;padding:4px 10px;width:max-content;border-radius:20px;background:color-mix(in srgb,var(--primary-text-color) 12%,transparent);font-weight:800}.modal{display:none;position:fixed;inset:0;z-index:9999;background:#000c;place-items:center;padding:18px}.modal.open{display:grid}.modal img{max-width:94vw;max-height:90vh;background:#fff;border-radius:10px}</style><div class="card"><header><img src="${ICON}" alt="PostNL"><b>${l==="nl"?"Mijn Post":"My Mail"}</b></header>${items.length?`<div class="list">${items.map((it,i)=>`<div class="mail" data-i="${i}"><div class="scan">✉</div><div class="date">${esc(dateText(it.delivery_date,l))}</div></div>`).join("")}</div>`:`<div class="empty">${l==="nl"?"Er wordt momenteel geen post verwacht.":"No mail is currently expected."}</div>`}<div class="modal"><img alt="PostNL poststuk"></div></div>`;
      const modal=this.shadowRoot.querySelector(".modal");if(modal)modal.addEventListener("click",()=>modal.classList.remove("open"));
      await Promise.all(items.map(async(it,i)=>{if(!it?.image_available)return;const src=await getMailImage(hass,a.entry_id,it.id),card=this.shadowRoot.querySelector(`.mail[data-i="${i}"]`),scan=card?.querySelector(".scan");if(!src||!card||!scan||!modal)return;scan.innerHTML=`<img src="${src}" alt="PostNL poststuk">`;card.onclick=e=>{e.stopPropagation();modal.querySelector("img").src=src;modal.classList.add("open");};}));
    }
  }

  class PackagesCard extends Base {
    render(){
      const hass=this._hass;if(!hass)return;const l=lang(hass),s=entity(hass,"packages",this._config.entity),items=(Array.isArray(s?.attributes?.items)?s.attributes.items:[]).slice(0,5);
      this.shadowRoot.innerHTML=`<style>${common}.list{padding:10px;display:grid;gap:8px}.package{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px;border:1px solid var(--divider-color,#ddd);border-radius:12px;cursor:pointer}.package>img{width:42px;height:42px;object-fit:contain}.sender{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.small{font-size:11px;color:var(--secondary-text-color);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.badge{font-size:10px;font-weight:800;color:#9a3f00;background:#fff0e6;padding:6px 8px;border-radius:20px;max-width:145px;text-align:center;white-space:normal}.modal{display:none;position:fixed;inset:0;z-index:9999;background:#000c;place-items:center;padding:18px}.modal.open{display:grid}.dialog{width:min(410px,94vw);max-height:86vh;overflow:auto;padding:22px;border-radius:22px;background:var(--card-background-color,#fff)}.grid{display:grid;grid-template-columns:120px 1fr;gap:9px;margin-top:18px}.key{color:var(--secondary-text-color)}@media(max-width:430px){.package{grid-template-columns:44px minmax(0,1fr)}.badge{grid-column:2;justify-self:start}}</style><div class="card"><header><img src="${ICON}" alt="PostNL"><b>${l==="nl"?"Mijn Pakketten":"My Packages"}</b></header>${items.length?`<div class="list">${items.map((p,i)=>`<div class="package" data-i="${i}"><img src="${ICON}" alt="PostNL"><div><div class="sender">${esc(p.sender||"PostNL")}</div><div class="small">${esc(p.tracking||"")}</div><div class="small">${esc(p.delivery_window||dateText(p.delivery_date,l))}</div></div><span class="badge">${esc(p.status||"—")}</span></div>`).join("")}</div>`:`<div class="empty">${l==="nl"?"Er zijn geen pakketten onderweg.":"There are no parcels on the way."}</div>`}<div class="modal"><div class="dialog"></div></div>`;
      const modal=this.shadowRoot.querySelector(".modal"),dialog=this.shadowRoot.querySelector(".dialog");if(!modal||!dialog)return;modal.onclick=e=>{if(e.target===modal)modal.classList.remove("open");};this.shadowRoot.querySelectorAll(".package").forEach(el=>el.onclick=()=>{const p=items[Number(el.dataset.i)];if(!p)return;dialog.innerHTML=`<h2>${esc(p.sender||"PostNL")}</h2><strong class="orange">${esc(p.status||"—")}</strong><div class="grid"><span class="key">Tracking</span><span>${esc(p.tracking||"—")}</span><span class="key">${l==="nl"?"Bezorgdatum":"Delivery date"}</span><span>${esc(dateText(p.delivery_date,l))}</span><span class="key">${l==="nl"?"Bezorgvenster":"Delivery window"}</span><span>${esc(p.delivery_window||"—")}</span><span class="key">${l==="nl"?"Laatste event":"Latest event"}</span><span>${esc(p.event||"—")}</span><span class="key">${l==="nl"?"Ontvanger":"Receiver"}</span><span>${esc(p.receiver||"—")}</span></div>`;modal.classList.add("open");});
    }
  }

  const pad=n=>String(n).padStart(2,"0");
  const clock=d=>`${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const zoned=s=>/([zZ]|[+\-]\d\d:?\d\d)$/.test(String(s||""));
  const parseLocal=s=>{if(!s)return null;const d=zoned(s)?new Date(s):new Date(String(s).replace(" ","T"));return Number.isNaN(d.getTime())?null:d;};
  const windowParts=p=>{
    let start=parseLocal(p.delivery_start||p.deliveryStart||p.window_start),end=parseLocal(p.delivery_end||p.deliveryEnd||p.window_end);
    if((!start||!end)&&p.delivery_window){const m=String(p.delivery_window).match(/(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})/);if(m){const base=parseLocal(p.delivery_date)||new Date();start=new Date(base);start.setHours(+m[1],+m[2],0,0);end=new Date(base);end.setHours(+m[3],+m[4],0,0);}}
    return {start,end};
  };
  const deliveryLabel=(p,l,start,end)=>{
    if(start&&end){const now=new Date(),same=now.toDateString()===start.toDateString(),tom=new Date(now);tom.setDate(tom.getDate()+1);const when=same?(l==="nl"?"Vandaag":"Today"):(tom.toDateString()===start.toDateString()?(l==="nl"?"Morgen":"Tomorrow"):dateText(start,l));return `${when} ${clock(start)} - ${clock(end)}`;}
    return p.delivery_window||p.status||(l==="nl"?"Bezorging":"Delivery");
  };

  const deliveryCss=`
    :host{display:block;color-scheme:light dark;--orange:#FB6200;--primary:#232323;--secondary:#747378;--muted:#97969b;--card:#f4f4f5;--header:#fafafa;--border:#dedee0;--panel:#fff;--line:#777b9c}*{box-sizing:border-box}.card{display:grid;grid-template-rows:52px minmax(0,1fr);width:100%;height:100%;min-height:276px;overflow:hidden;border-radius:17px;background:var(--card);color:var(--primary);font:14px/1.28 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002)}header{display:flex;align-items:center;padding:0 18px;border-bottom:1px solid var(--border);background:var(--header)}.app-icon{display:block;width:36px;height:36px;object-fit:contain}h1{margin:0 0 0 auto;color:#77767b;font-size:18px;font-weight:600;white-space:nowrap}#content{min-width:0;min-height:0;padding:10px 12px;overflow:hidden}.package{height:100%;min-height:0;overflow:hidden;border-radius:12px;background:var(--panel);padding:12px 12px 10px;display:flex;flex-direction:column}.package-top{display:flex;align-items:center;gap:9px;min-height:28px}.mini-logo{width:38px;height:38px;object-fit:contain;flex:0 0 auto}.sender{font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}.status{color:var(--secondary);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:40%}.headline{font-size:13px;font-weight:650;margin:9px 0 1px;min-height:17px}.tracking{color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-height:13px}.vanwrap{flex:1;min-height:82px;display:grid;place-items:center;padding:4px 0}.van{display:block;max-width:260px;max-height:145px;object-fit:contain}.van.animated-van{width:240px;height:auto;max-width:100%;max-height:none;object-fit:contain}.timeline{position:relative;height:58px;margin-top:0}.track{position:absolute;left:0;right:0;top:20px;height:3px;background:var(--line)}.elapsed{position:absolute;left:0;top:20px;height:3px;background:var(--orange);width:0}.dot{position:absolute;top:12px;width:18px;height:18px;margin-left:-9px;border:4px solid var(--orange);border-radius:50%;background:var(--panel);left:0}.tick{position:absolute;top:15px;width:1px;height:13px;background:#9d9fac}.actual-start,.actual-end{position:absolute;top:11px;width:3px;height:21px;background:#cfcfd5;border-radius:2px}.times{position:absolute;left:0;right:0;top:33px;display:grid;grid-template-columns:1fr 1fr 1fr;color:var(--muted);font-size:10px}.times span:nth-child(2){text-align:center}.times span:nth-child(3){text-align:right}.hidden{display:none!important}.state{display:grid;place-items:center;height:100%;padding:16px;text-align:center;color:var(--primary)}.state-inner{display:grid;place-items:center;gap:12px}.state .van{width:min(88%,290px);max-height:170px}.state p{margin:0;font-size:17px;font-weight:700}@media(prefers-color-scheme:dark){:host{--primary:#f4f4f5;--secondary:#c4c3c7;--muted:#aaa9ad;--card:#202022;--header:#29292b;--border:#424244;--panel:#343436;--line:#71748e}h1{color:#aaa9ad}.dot{background:var(--panel)}.state{color:#aaa9ad}}`;

  class DeliveryCard extends Base {
    constructor(){super();this._timer=null;}
    connectedCallback(){if(!this._timer)this._timer=setInterval(()=>this.render(),30000);}
    disconnectedCallback(){if(this._timer){clearInterval(this._timer);this._timer=null;}}
    render(){
      const hass=this._hass;if(!hass)return;const l=lang(hass),s=entity(hass,"packages",this._config.entity),items=Array.isArray(s?.attributes?.items)?s.attributes.items:[],p=items.find(x=>!x.delivered)||items[0]||null;
      this.shadowRoot.innerHTML=`<style>${deliveryCss}</style><main class="card"><header><img class="app-icon" src="${ICON}" alt="PostNL"><h1>${l==="nl"?"Mijn Bezorging":"My Delivery"}</h1></header><section id="content"></section></main>`;
      const content=this.shadowRoot.querySelector("#content");
      if(!p){content.innerHTML=`<div class="state"><div class="state-inner"><img class="van" src="${VAN_STATIC}" alt="PostNL"><p>${l==="nl"?"Er is geen pakket onderweg":"There is no parcel on the way"}</p></div></div>`;return;}
      const {start,end}=windowParts(p),sender=p.sender||p.title||p.sourceDisplayName||"PostNL",headline=deliveryLabel(p,l,start,end),tracking=p.tracking?`${l==="nl"?"Tracking":"Tracking"}: ${p.tracking}`:"";
      content.innerHTML=`<section class="package"><div class="package-top"><img class="mini-logo" src="${PACKAGE}" alt="Package"><div class="sender">${esc(sender)}</div><div class="status">${esc(p.status||"")}</div></div><div class="headline">${esc(headline)}</div><div class="tracking">${esc(tracking)}</div><div class="vanwrap"><img class="van animated-van" src="${VAN}" alt="PostNL" onerror="this.onerror=null;this.src='${VAN_STATIC}'"></div><div class="timeline ${start&&end?"":"hidden"}"><div class="track"></div><div class="elapsed"></div><div class="dot"></div><i class="actual-start"></i><i class="actual-end"></i><div class="times"><span></span><span></span><span></span></div></div></section>`;
      if(start&&end){const displayStart=new Date(start.getTime()-3600000),displayEnd=new Date(end.getTime()+3600000),span=displayEnd-displayStart,now=Date.now(),pct=Math.max(0,Math.min(1,(now-displayStart)/span))*100,startPct=((start-displayStart)/span)*100,endPct=((end-displayStart)/span)*100,mid=new Date((displayStart.getTime()+displayEnd.getTime())/2),tl=content.querySelector(".timeline");tl.querySelector(".elapsed").style.width=`${pct}%`;tl.querySelector(".dot").style.left=`${pct}%`;tl.querySelector(".actual-start").style.left=`calc(${startPct}% - 1px)`;tl.querySelector(".actual-end").style.left=`calc(${endPct}% - 1px)`;const ts=tl.querySelectorAll(".times span");ts[0].textContent=clock(displayStart);ts[1].textContent=clock(mid);ts[2].textContent=clock(displayEnd);}
    }
  }

  const defs=[["postnl-mail-card",MailCard],["postnl-packages-card",PackagesCard],["postnl-delivery-card",DeliveryCard]];
  defs.forEach(([n,c])=>{if(!customElements.get(n))customElements.define(n,c);});
  window.customCards=window.customCards||[];
  window.customCards=window.customCards.filter(c=>!["postnl-mail-card","postnl-packages-card","postnl-delivery-card","postnl-latest-mail-card","postnl-delivery-image-card"].includes(c.type));
  [
    {type:"postnl-mail-card",name:"PostNL – Mijn Post",description:"PostNL poststukken",preview:false},
    {type:"postnl-packages-card",name:"PostNL – Mijn Pakketten",description:"PostNL pakketten",preview:false},
    {type:"postnl-delivery-card",name:"PostNL – Mijn Bezorging",description:"Actieve PostNL bezorging",preview:false}
  ].forEach(c=>window.customCards.push(c));
  console.info(`%c PostNL cards ${VERSION} `,"background:#FB6200;color:#fff;font-weight:bold;padding:3px 6px;border-radius:4px");
})();
