const PREFIX="postnl://login";
async function save(url){if(!url||!url.startsWith(PREFIX))return;await chrome.storage.local.set({postnlCallback:url,capturedAt:Date.now()});try{await chrome.action.setBadgeText({text:"✓"});await chrome.action.setBadgeBackgroundColor({color:"#FB6200"})}catch(_){}}
chrome.webRequest.onBeforeRedirect.addListener(d=>save(d.redirectUrl),{urls:["https://login.postnl.nl/*"]});
chrome.webRequest.onHeadersReceived.addListener(d=>{const h=(d.responseHeaders||[]).find(x=>String(x.name||"").toLowerCase()==="location");if(h?.value)save(h.value)},{urls:["https://login.postnl.nl/*"]},["responseHeaders"]);
chrome.runtime.onInstalled.addListener(()=>chrome.action.setBadgeText({text:""}));
