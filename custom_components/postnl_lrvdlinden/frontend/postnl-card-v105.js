(() => {
  "use strict";

  const VERSION = "1.0.5";
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
  const fmtNum = (v, d, l) => { const n = Number(v); if (!Number.isFinite(n)) return ""; return new Intl.NumberFormat(l === "nl" ? "nl-NL" : "en-GB", {maximumFractionDigits:d}).format(n); };
  const shipmentLabel = (v, l) => (l === "nl" && /^parcel$/i.test(String(v || ""))) ? "Pakket" : String(v || "");
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
      this.shadowRoot.innerHTML=`<style>${common}.list{padding:10px;display:grid;gap:8px}.package{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px;border:1px solid var(--divider-color,#ddd);border-radius:12px;cursor:pointer}.package>img{width:42px;height:42px;object-fit:contain}.sender{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.small{font-size:11px;color:var(--secondary-text-color);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.badge{font-size:10px;font-weight:800;color:#9a3f00;background:#fff0e6;padding:6px 8px;border-radius:20px;max-width:145px;text-align:center;white-space:normal}.modal{display:none;position:fixed;inset:0;z-index:9999;background:#000c;place-items:center;padding:18px}.modal.open{display:grid}.dialog{width:min(410px,94vw);max-height:86vh;overflow:auto;padding:22px;border-radius:22px;background:var(--card-background-color,#fff)}.grid{display:grid;grid-template-columns:120px 1fr;gap:9px;margin-top:18px}.key{color:var(--secondary-text-color)}@media(max-width:430px){.package{grid-template-columns:44px minmax(0,1fr)}.badge{grid-column:2;justify-self:start}}</style><div class="card"><header><img src="${ICON}" alt="PostNL"><b>${l==="nl"?"Mijn Pakketten":"My Packages"}</b></header>${items.length?`<div class="list">${items.map((p,i)=>`<div class="package" data-i="${i}"><img src="${ICON}" alt="PostNL"><div><div class="sender">${esc(p.sender||"PostNL")}</div><div class="small">${esc(p.tracking||"")}</div><div class="small">${esc(p.delivery_window||dateText(p.delivery_date,l))}${p.weight_kg!=null?` · ${esc(fmtNum(p.weight_kg,2,l))} kg`:""}</div></div><span class="badge">${esc(p.status||"—")}</span></div>`).join("")}</div>`:`<div class="empty">${l==="nl"?"Er zijn geen pakketten onderweg.":"There are no parcels on the way."}</div>`}<div class="modal"><div class="dialog"></div></div>`;
      const modal=this.shadowRoot.querySelector(".modal"),dialog=this.shadowRoot.querySelector(".dialog");if(!modal||!dialog)return;modal.onclick=e=>{if(e.target===modal)modal.classList.remove("open");};this.shadowRoot.querySelectorAll(".package").forEach(el=>el.onclick=()=>{const p=items[Number(el.dataset.i)];if(!p)return;const nl=l==="nl",rows=[["Tracking",p.tracking],[nl?"Bezorgdatum":"Delivery date",p.delivery_date?dateText(p.delivery_date,l):""],[nl?"Bezorgvenster":"Delivery window",p.delivery_window],[nl?"Laatste gebeurtenis":"Latest event",p.event],[nl?"Afzender":"Sender",p.sender],[nl?"Ontvanger":"Receiver",p.receiver],[nl?"Gewicht":"Weight",p.weight_kg!=null?`${fmtNum(p.weight_kg,2,l)} kg`:p.weight],[nl?"Afmetingen":"Dimensions",p.dimensions],[nl?"PostNL-punt":"PostNL Point",p.pickup_point||(p.pickup?(nl?"Ja":"Yes"):"")],[nl?"Type zending":"Shipment type",shipmentLabel(p.shipment_type,l)],[nl?"Type bezorgadres":"Delivery address type",p.delivery_address_type],[nl?"Richting":"Direction",p.direction==="outgoing"?(nl?"Verzonden":"Sent"):(nl?"Ontvangen":"Received")],[nl?"Gedeeld via":"Shared from",p.shared_from],[nl?"Statuscode":"Status code",p.observation_code]].filter(([,v])=>v!==undefined&&v!==null&&String(v).trim()!=="");dialog.innerHTML=`<h2>${esc(p.sender||"PostNL")}</h2><strong class="orange">${esc(p.status||"—")}</strong><div class="grid">${rows.map(([k,v])=>`<span class="key">${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>${p.details_url?`<p><a class="orange" href="${esc(p.details_url)}" target="_blank" rel="noopener">${nl?"Open in PostNL Track & Trace":"Open in PostNL Track & Trace"}</a></p>`:""}`;modal.classList.add("open");});
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
    :host{display:block;color-scheme:light dark;--orange:#FB6200;--primary:var(--primary-text-color,#232323);--secondary:var(--secondary-text-color,#747378);--muted:var(--secondary-text-color,#97969b);--card:var(--card-background-color,var(--ha-card-background,#fff));--header:var(--card-background-color,var(--ha-card-background,#fff));--border:var(--divider-color,#dedee0);--panel:var(--card-background-color,var(--ha-card-background,#fff));--line:#777b9c}*{box-sizing:border-box}.card{display:grid;grid-template-rows:52px minmax(0,1fr);width:100%;height:100%;min-height:276px;overflow:hidden;border-radius:17px;background:var(--card);color:var(--primary);font:14px/1.28 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002)}header{display:flex;align-items:center;padding:0 18px;border-bottom:1px solid var(--border);background:var(--header)}.app-icon{display:block;width:36px;height:36px;object-fit:contain}h1{margin:0 0 0 auto;color:#77767b;font-size:18px;font-weight:600;white-space:nowrap}#content{min-width:0;min-height:0;padding:10px 12px;overflow:hidden}.package{height:100%;min-height:0;overflow:hidden;border-radius:12px;background:var(--panel);padding:12px 12px 10px;display:flex;flex-direction:column}.package-top{display:flex;align-items:center;gap:9px;min-height:28px}.mini-logo{width:38px;height:38px;object-fit:contain;flex:0 0 auto}.sender{font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}.status{color:var(--secondary);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:40%}.headline{font-size:13px;font-weight:650;margin:9px 0 1px;min-height:17px}.tracking{color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-height:13px}.vanwrap{flex:1;min-height:82px;display:grid;place-items:center;padding:4px 0}.van{display:block;max-width:260px;max-height:145px;object-fit:contain}.van.animated-van{width:240px;height:auto;max-width:100%;max-height:none;object-fit:contain}.timeline{position:relative;height:58px;margin-top:0}.track{position:absolute;left:0;right:0;top:20px;height:3px;background:var(--line)}.elapsed{position:absolute;left:0;top:20px;height:3px;background:var(--orange);width:0}.dot{position:absolute;top:12px;width:18px;height:18px;margin-left:-9px;border:4px solid var(--orange);border-radius:50%;background:var(--panel);left:0}.tick{position:absolute;top:15px;width:1px;height:13px;background:#9d9fac}.actual-start,.actual-end{position:absolute;top:11px;width:3px;height:21px;background:#cfcfd5;border-radius:2px}.times{position:absolute;left:0;right:0;top:33px;display:grid;grid-template-columns:1fr 1fr 1fr;color:var(--muted);font-size:10px}.times span:nth-child(2){text-align:center}.times span:nth-child(3){text-align:right}.hidden{display:none!important}.state{display:grid;place-items:center;height:100%;padding:16px;text-align:center;color:var(--primary)}.state-inner{display:grid;place-items:center;gap:12px}.state .van{width:min(88%,290px);max-height:170px}.state p{margin:0;font-size:17px;font-weight:700}@media(prefers-color-scheme:dark){:host{--line:#71748e}h1{color:var(--secondary-text-color,#aaa9ad)}.dot{background:var(--panel)}.state{color:var(--primary-text-color,#f4f4f5)}}`;

  class DeliveryCard extends Base {
    constructor(){super();this._timer=null;}
    connectedCallback(){if(!this._timer)this._timer=setInterval(()=>this.render(),30000);}
    disconnectedCallback(){if(this._timer){clearInterval(this._timer);this._timer=null;}}
    render(){
      const hass=this._hass;if(!hass)return;const l=lang(hass),s=entity(hass,"packages",this._config.entity),items=Array.isArray(s?.attributes?.items)?s.attributes.items:[],active=s?.attributes?.active_package||null,p=(active&&!active.delivered?active:null)||items.find(x=>!x.delivered)||null;
      this.shadowRoot.innerHTML=`<style>${deliveryCss}</style><main class="card"><header><img class="app-icon" src="${ICON}" alt="PostNL"><h1>${l==="nl"?"Mijn Bezorging":"My Delivery"}</h1></header><section id="content"></section></main>`;
      const content=this.shadowRoot.querySelector("#content");
      if(!p){content.innerHTML=`<div class="state"><div class="state-inner"><img class="van" src="${VAN_STATIC}" alt="PostNL"><p>${l==="nl"?"Er is geen pakket onderweg":"There is no parcel on the way"}</p></div></div>`;return;}
      const {start,end}=windowParts(p),sender=p.sender||p.title||p.sourceDisplayName||"PostNL",headline=deliveryLabel(p,l,start,end),tracking=p.tracking?`${l==="nl"?"Tracking":"Tracking"}: ${p.tracking}`:"";
      content.innerHTML=`<section class="package"><div class="package-top"><img class="mini-logo" src="${PACKAGE}" alt="Package"><div class="sender">${esc(sender)}</div><div class="status">${esc(p.status||"")}</div></div><div class="headline">${esc(headline)}</div><div class="tracking">${esc(tracking)}</div><div class="vanwrap"><img class="van animated-van" src="${VAN}" alt="PostNL" onerror="this.onerror=null;this.src='${VAN_STATIC}'"></div><div class="timeline ${start&&end?"":"hidden"}"><div class="track"></div><div class="elapsed"></div><div class="dot"></div><i class="actual-start"></i><i class="actual-end"></i><div class="times"><span></span><span></span><span></span></div></div></section>`;
      if(start&&end){const displayStart=new Date(start.getTime()-3600000),displayEnd=new Date(end.getTime()+3600000),span=displayEnd-displayStart,now=Date.now(),pct=Math.max(0,Math.min(1,(now-displayStart)/span))*100,startPct=((start-displayStart)/span)*100,endPct=((end-displayStart)/span)*100,mid=new Date((displayStart.getTime()+displayEnd.getTime())/2),tl=content.querySelector(".timeline");tl.querySelector(".elapsed").style.width=`${pct}%`;tl.querySelector(".dot").style.left=`${pct}%`;tl.querySelector(".actual-start").style.left=`calc(${startPct}% - 1px)`;tl.querySelector(".actual-end").style.left=`calc(${endPct}% - 1px)`;const ts=tl.querySelectorAll(".times span");ts[0].textContent=clock(displayStart);ts[1].textContent=clock(mid);ts[2].textContent=clock(displayEnd);}
    }
  }


  const journeyCss=`
    .body{max-height:var(--postnl-journey-height,420px);overflow-y:auto;padding:15px 16px 18px;overscroll-behavior-y:contain}.summary{padding:0 2px 13px;border-bottom:1px solid var(--divider-color,#dedee0)}.sender{font-size:16px;font-weight:800}.tracking,.physical{color:var(--secondary-text-color);font-size:11px;margin-top:3px}.status{display:flex;align-items:flex-start;gap:9px;font-size:18px;font-weight:850;margin-top:8px;overflow-wrap:anywhere}.current{flex:none;width:27px;height:27px;border-radius:50%;display:grid;place-items:center;background:#FB6200;color:#fff;font-size:14px}.journey{position:relative;padding:13px 0 0 42px}.journey:before{content:"";position:absolute;left:17px;top:24px;bottom:18px;width:3px;background:#FB6200}.event{position:relative;padding:0 0 18px;min-height:55px}.dot{position:absolute;left:-39px;top:2px;width:27px;height:27px;border-radius:50%;display:grid;place-items:center;background:#FB6200;color:#fff;font-size:17px;font-weight:900}.when{font-weight:750;font-size:12px}.msg{font-size:14px;margin-top:4px;overflow-wrap:anywhere}.location{font-size:11px;color:var(--secondary-text-color);margin-top:3px}.state{min-height:240px;display:grid;place-items:center;text-align:center;padding:25px;color:var(--secondary-text-color)}.state img{width:min(88%,290px);max-height:170px;margin-bottom:14px}.state strong{display:block;font-size:17px;color:var(--primary-text-color);font-weight:700}`;
  const eventTime=(v,l,tz)=>{const d=new Date(v);if(Number.isNaN(d.getTime()))return String(v||"");try{return new Intl.DateTimeFormat(l==="nl"?"nl-NL":"en-GB",{timeZone:tz||undefined,day:"2-digit",month:"long",hour:"2-digit",minute:"2-digit"}).format(d);}catch(_){return String(v||"");}};

  class JourneyCard extends Base {
    getCardSize(){return 8;}
    render(){
      const hass=this._hass;if(!hass)return;const l=lang(hass),nl=l==="nl",s=entity(hass,"packages",this._config.entity),a=s?.attributes||{},p=a.journey_package||null,tz=a.time_zone||hass.config?.time_zone,title=nl?"Reis van je pakket":"Parcel Journey";
      const height=Number(this._config.height)>0?`--postnl-journey-height:${Number(this._config.height)}px;`:"";
      let body;
      if(!s){body=`<div class="state">${nl?"Koppel eerst je PostNL-account.":"Connect your PostNL account first."}</div>`;}
      else if(!p){body=`<div class="state"><div><img src="${VAN_STATIC}" alt="PostNL"><strong>${nl?"Er is momenteel geen pakketreis.":"There is currently no parcel journey."}</strong></div></div>`;}
      else{
        const physical=[p.weight_kg!=null?`${nl?"Gewicht":"Weight"}: ${fmtNum(p.weight_kg,2,l)} kg`:(p.weight?`${nl?"Gewicht":"Weight"}: ${p.weight}`:""),p.dimensions?`${nl?"Afmetingen":"Dimensions"}: ${p.dimensions}`:"",p.pickup_point?`${nl?"PostNL-punt":"PostNL Point"}: ${p.pickup_point}`:""].filter(Boolean).join(" · ");
        let events=[...(p.events||[])].sort((x,y)=>(Date.parse(y.timestamp||"")||0)-(Date.parse(x.timestamp||"")||0));
        const current=String(p.status||"").trim().toLowerCase();
        if(events.length&&current&&String(events[0].description||"").trim().toLowerCase()===current)events=events.slice(1);
        body=`<div class="body"><section class="summary"><div class="sender">${esc(p.sender||"PostNL")}</div><div class="tracking">Tracking: ${esc(p.tracking||"")}</div>${physical?`<div class="physical">${esc(physical)}</div>`:""}<div class="status"><span class="current">▣</span><span>${esc(p.status||"")}</span></div></section><div class="journey">${events.map(e=>`<article class="event"><span class="dot">✓</span><div class="when">${esc(eventTime(e.timestamp,l,tz))}</div><div class="msg">${esc(e.description||"")}</div>${e.location?`<div class="location">${esc(e.location)}</div>`:""}</article>`).join("")}</div></div>`;
      }
      const key=JSON.stringify([l,p,height,!!s]);if(key===this._lastKey)return;this._lastKey=key;
      const prevScroll=this.shadowRoot.querySelector(".body")?.scrollTop||0;
      this.shadowRoot.innerHTML=`<style>${common}${journeyCss}</style><div class="card" style="${height}"><header><img src="${ICON}" alt="PostNL"><b>${title}</b></header>${body}</div>`;
      const b=this.shadowRoot.querySelector(".body");if(b)b.scrollTop=prevScroll;
    }
  }

  const defs=[["postnl-mail-card",MailCard],["postnl-packages-card",PackagesCard],["postnl-delivery-card",DeliveryCard],["postnl-journey-card",JourneyCard]];
  defs.forEach(([n,c])=>{if(!customElements.get(n))customElements.define(n,c);});
  window.customCards=window.customCards||[];
  window.customCards=window.customCards.filter(c=>!["postnl-mail-card","postnl-packages-card","postnl-delivery-card","postnl-journey-card","postnl-latest-mail-card","postnl-delivery-image-card"].includes(c.type));
  [
    {type:"postnl-mail-card",name:"PostNL – Mijn Post",description:"PostNL poststukken",preview:false},
    {type:"postnl-packages-card",name:"PostNL – Mijn Pakketten",description:"PostNL pakketten",preview:false},
    {type:"postnl-delivery-card",name:"PostNL – Mijn Bezorging",description:"Actieve PostNL bezorging",preview:false},
    {type:"postnl-journey-card",name:"PostNL – Reis van je pakket",description:"Volledige Track & Trace-tijdlijn van je actieve pakket",preview:false}
  ].forEach(c=>window.customCards.push(c));
  console.info(`%c PostNL cards ${VERSION} `,"background:#FB6200;color:#fff;font-weight:bold;padding:3px 6px;border-radius:4px");
})();
