(() => {
  "use strict";

  const VERSION = "1.0.1";
  const DOMAIN = "postnl_lrvdlinden";
  const BASE = `/${DOMAIN}_static`;
  const ICON = `${BASE}/icon.svg`;
  const VAN = `${BASE}/postnl-van.gif`;
  const VAN_STATIC = `${BASE}/van-1.svg`;
  const imageCache = new Map();

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));

  const language = (hass) => String(hass?.language || navigator.language || "nl")
    .toLowerCase()
    .startsWith("nl") ? "nl" : "en";

  const findRoleEntity = (hass, role, configuredEntity) => {
    if (!hass?.states) return null;
    if (configuredEntity && hass.states[configuredEntity]) return hass.states[configuredEntity];
    return Object.values(hass.states).find((state) => state?.attributes?.postnl_role === role) || null;
  };

  const formatDate = (value, lang) => {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    try {
      return new Intl.DateTimeFormat(lang === "nl" ? "nl-NL" : "en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(parsed);
    } catch (_error) {
      return String(value);
    }
  };

  const getMailImage = async (hass, entryId, mailId) => {
    if (!hass?.connection || !entryId || !mailId) return null;
    const key = `${entryId}:${mailId}`;
    if (!imageCache.has(key)) {
      imageCache.set(
        key,
        hass.connection.sendMessagePromise({
          type: `${DOMAIN}/get_mail_image`,
          entry_id: entryId,
          mail_id: String(mailId),
        }).then((response) => {
          const result = response?.result || response;
          if (!result?.content) return null;
          return `data:${result.content_type || "image/jpeg"};base64,${result.content}`;
        }).catch(() => null),
      );
    }
    return imageCache.get(key);
  };

  const commonCss = `
    :host{display:block}
    *{box-sizing:border-box}
    .card{overflow:hidden;border-radius:var(--ha-card-border-radius,17px);background:var(--card-background-color,var(--ha-card-background,#fff));color:var(--primary-text-color);box-shadow:var(--ha-card-box-shadow,0 2px 6px #0002);font:14px/1.3 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    header{height:52px;display:flex;align-items:center;padding:0 17px;border-bottom:1px solid var(--divider-color,#ddd)}
    header img{width:36px;height:36px;object-fit:contain}
    header b{margin-left:auto;color:var(--secondary-text-color);font-size:18px}
    .empty{min-height:180px;display:grid;place-items:center;text-align:center;padding:24px;color:var(--secondary-text-color)}
    .orange{color:#fb6200}
  `;

  class PostNLCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = config || {};
      this.render();
    }

    set hass(hass) {
      this._hass = hass;
      this.render();
    }

    render() {
      const lang = language(this._hass);
      this.innerHTML = `<div style="padding:16px;color:var(--secondary-text-color);line-height:1.45">${lang === "nl" ? "Deze PostNL-kaart gebruikt automatisch de gegevens van je gekoppelde PostNL-integratie. Er zijn geen extra instellingen nodig." : "This PostNL card automatically uses data from your linked PostNL integration. No extra settings are required."}</div>`;
    }
  }

  if (!customElements.get("postnl-card-editor")) {
    customElements.define("postnl-card-editor", PostNLCardEditor);
  }

  class PostNLBaseCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._hass = null;
    }

    setConfig(config) {
      this._config = config || {};
    }

    set hass(hass) {
      this._hass = hass;
      this.render();
    }

    getCardSize() {
      return 6;
    }

    static getStubConfig() {
      return {};
    }

    static getConfigElement() {
      return document.createElement("postnl-card-editor");
    }
  }

  class PostNLMailCard extends PostNLBaseCard {
    async render() {
      const hass = this._hass;
      if (!hass) return;
      const lang = language(hass);
      const state = findRoleEntity(hass, "mail", this._config.entity);
      const attrs = state?.attributes || {};
      const items = Array.isArray(attrs.items) ? attrs.items : [];

      this.shadowRoot.innerHTML = `
        <style>${commonCss}
          .list{display:flex;gap:12px;padding:13px;overflow-x:auto}
          .mail{flex:0 0 146px;cursor:pointer}
          .scan{height:132px;padding:7px;display:grid;place-items:center;border-radius:9px;background:color-mix(in srgb,var(--primary-text-color) 10%,transparent);overflow:hidden}
          .scan img{width:100%;height:100%;object-fit:contain;background:#fff;border-radius:4px}
          .date{text-align:center;margin:7px auto 0;padding:4px 10px;width:max-content;border-radius:20px;background:color-mix(in srgb,var(--primary-text-color) 12%,transparent);font-weight:800}
          .modal{display:none;position:fixed;inset:0;z-index:9999;background:#000c;place-items:center;padding:18px}
          .modal.open{display:grid}
          .modal img{max-width:94vw;max-height:90vh;background:#fff;border-radius:10px}
        </style>
        <div class="card">
          <header><img src="${ICON}" alt="PostNL"><b>${lang === "nl" ? "Mijn Post" : "My Mail"}</b></header>
          ${items.length ? `<div class="list">${items.map((item, index) => `
            <div class="mail" data-index="${index}">
              <div class="scan">✉</div>
              <div class="date">${escapeHtml(formatDate(item.delivery_date, lang))}</div>
            </div>`).join("")}</div>` : `<div class="empty">${lang === "nl" ? "Er wordt momenteel geen post verwacht." : "No mail is currently expected."}</div>`}
          <div class="modal"><img alt="PostNL poststuk"></div>
        </div>`;

      const modal = this.shadowRoot.querySelector(".modal");
      if (modal) modal.addEventListener("click", () => modal.classList.remove("open"));

      await Promise.all(items.map(async (item, index) => {
        if (!item?.image_available) return;
        const source = await getMailImage(hass, attrs.entry_id, item.id);
        const card = this.shadowRoot.querySelector(`.mail[data-index="${index}"]`);
        const scan = card?.querySelector(".scan");
        if (!source || !card || !scan || !modal) return;
        scan.innerHTML = `<img src="${source}" alt="PostNL poststuk">`;
        card.addEventListener("click", (event) => {
          event.stopPropagation();
          const image = modal.querySelector("img");
          if (image) image.src = source;
          modal.classList.add("open");
        });
      }));
    }
  }

  class PostNLLatestMailCard extends PostNLBaseCard {
    async render() {
      const hass = this._hass;
      if (!hass) return;
      const lang = language(hass);
      const state = findRoleEntity(hass, "mail", this._config.entity);
      const attrs = state?.attributes || {};
      const item = Array.isArray(attrs.items) ? attrs.items[0] : null;

      this.shadowRoot.innerHTML = `
        <style>${commonCss}
          .body{min-height:260px;padding:14px;display:grid;place-items:center;text-align:center;color:var(--secondary-text-color)}
          .body img{max-width:100%;max-height:430px;object-fit:contain;background:#fff;border-radius:8px}
        </style>
        <div class="card">
          <header><img src="${ICON}" alt="PostNL"><b>${lang === "nl" ? "Laatste poststuk" : "Latest mail item"}</b></header>
          <div class="body">${item ? (lang === "nl" ? "Afbeelding laden…" : "Loading image…") : (lang === "nl" ? "Geen poststuk beschikbaar" : "No mail item available")}</div>
        </div>`;

      if (!item?.image_available) return;
      const source = await getMailImage(hass, attrs.entry_id, item.id);
      const body = this.shadowRoot.querySelector(".body");
      if (source && body) body.innerHTML = `<img src="${source}" alt="PostNL poststuk">`;
    }
  }

  class PostNLPackagesCard extends PostNLBaseCard {
    render() {
      const hass = this._hass;
      if (!hass) return;
      const lang = language(hass);
      const state = findRoleEntity(hass, "packages", this._config.entity);
      const items = (Array.isArray(state?.attributes?.items) ? state.attributes.items : []).slice(0, 5);

      this.shadowRoot.innerHTML = `
        <style>${commonCss}
          .list{padding:10px;display:grid;gap:8px}
          .package{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px;border:1px solid var(--divider-color,#ddd);border-radius:12px;cursor:pointer}
          .package>img{width:42px;height:42px;object-fit:contain}
          .sender{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
          .small{font-size:11px;color:var(--secondary-text-color);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
          .badge{font-size:10px;font-weight:800;color:#9a3f00;background:#fff0e6;padding:6px 8px;border-radius:20px;max-width:145px;text-align:center;white-space:normal}
          .modal{display:none;position:fixed;inset:0;z-index:9999;background:#000c;place-items:center;padding:18px}
          .modal.open{display:grid}
          .dialog{width:min(410px,94vw);max-height:86vh;overflow:auto;padding:22px;border-radius:22px;background:var(--card-background-color,#fff)}
          .grid{display:grid;grid-template-columns:120px 1fr;gap:9px;margin-top:18px}
          .key{color:var(--secondary-text-color)}
          @media(max-width:430px){.package{grid-template-columns:44px minmax(0,1fr)}.badge{grid-column:2;justify-self:start}}
        </style>
        <div class="card">
          <header><img src="${ICON}" alt="PostNL"><b>${lang === "nl" ? "Mijn Pakketten" : "My Packages"}</b></header>
          ${items.length ? `<div class="list">${items.map((pkg, index) => `
            <div class="package" data-index="${index}">
              <img src="${ICON}" alt="PostNL">
              <div>
                <div class="sender">${escapeHtml(pkg.sender || "PostNL")}</div>
                <div class="small">${escapeHtml(pkg.tracking || "")}</div>
                <div class="small">${escapeHtml(pkg.delivery_window || formatDate(pkg.delivery_date, lang))}</div>
              </div>
              <span class="badge">${escapeHtml(pkg.status || "—")}</span>
            </div>`).join("")}</div>` : `<div class="empty">${lang === "nl" ? "Er zijn geen pakketten onderweg." : "There are no parcels on the way."}</div>`}
          <div class="modal"><div class="dialog"></div></div>
        </div>`;

      const modal = this.shadowRoot.querySelector(".modal");
      const dialog = this.shadowRoot.querySelector(".dialog");
      if (!modal || !dialog) return;
      modal.addEventListener("click", (event) => {
        if (event.target === modal) modal.classList.remove("open");
      });
      this.shadowRoot.querySelectorAll(".package").forEach((element) => {
        element.addEventListener("click", () => {
          const pkg = items[Number(element.dataset.index)];
          if (!pkg) return;
          dialog.innerHTML = `
            <h2>${escapeHtml(pkg.sender || "PostNL")}</h2>
            <strong class="orange">${escapeHtml(pkg.status || "—")}</strong>
            <div class="grid">
              <span class="key">Tracking</span><span>${escapeHtml(pkg.tracking || "—")}</span>
              <span class="key">${lang === "nl" ? "Bezorgdatum" : "Delivery date"}</span><span>${escapeHtml(formatDate(pkg.delivery_date, lang))}</span>
              <span class="key">${lang === "nl" ? "Bezorgvenster" : "Delivery window"}</span><span>${escapeHtml(pkg.delivery_window || "—")}</span>
              <span class="key">${lang === "nl" ? "Laatste event" : "Latest event"}</span><span>${escapeHtml(pkg.event || "—")}</span>
              <span class="key">${lang === "nl" ? "Ontvanger" : "Receiver"}</span><span>${escapeHtml(pkg.receiver || "—")}</span>
              <span class="key">${lang === "nl" ? "Type zending" : "Shipment type"}</span><span>${escapeHtml(pkg.shipment_type || "—")}</span>
            </div>`;
          modal.classList.add("open");
        });
      });
    }
  }

  const deliveryMarkup = (pkg, lang, square = false) => {
    if (!pkg) {
      return `<div class="empty"><img style="max-width:260px;width:82%" src="${VAN_STATIC}" alt="PostNL"><b>${lang === "nl" ? "Er is geen pakket onderweg" : "There is no parcel on the way"}</b></div>`;
    }
    return `
      <div class="delivery ${square ? "square" : ""}">
        <div class="top">
          <img src="${ICON}" alt="PostNL">
          <div><strong>${escapeHtml(pkg.sender || "PostNL")}</strong><small>${escapeHtml(pkg.status || "")}</small></div>
        </div>
        <h2>${escapeHtml(pkg.delivery_window || formatDate(pkg.delivery_date, lang))}</h2>
        <div class="van"><img src="${VAN}" data-fallback="${VAN_STATIC}" alt="PostNL bezorgbus"></div>
        ${pkg.tracking ? `<div class="tracking">${escapeHtml(pkg.tracking)}</div>` : ""}
      </div>`;
  };

  const deliveryCss = `${commonCss}
    .delivery{padding:15px}
    .top{display:flex;gap:11px;align-items:center}
    .top>img{width:44px;height:44px;object-fit:contain}
    .top div{display:grid}
    .top small,.tracking{color:var(--secondary-text-color)}
    h2{font-size:16px;margin:15px 0 6px}
    .van{height:150px;display:grid;place-items:center;overflow:hidden}
    .van img{max-width:290px;max-height:145px;object-fit:contain}
    .tracking{text-align:center;font-size:11px}
    .square{aspect-ratio:1/1;display:flex;flex-direction:column;justify-content:center}
    .square .van{height:190px}
    .square .van img{max-width:78%;max-height:180px}
  `;

  const attachVanFallback = (root) => {
    const image = root?.querySelector(".van img");
    if (!image) return;
    image.addEventListener("error", () => {
      const fallback = image.dataset.fallback;
      if (fallback && image.src !== fallback) image.src = fallback;
    }, { once: true });
  };

  class PostNLDeliveryCard extends PostNLBaseCard {
    render() {
      const hass = this._hass;
      if (!hass) return;
      const lang = language(hass);
      const state = findRoleEntity(hass, "packages", this._config.entity);
      const pkg = state?.attributes?.active_package || null;
      this.shadowRoot.innerHTML = `<style>${deliveryCss}</style><div class="card"><header><img src="${ICON}" alt="PostNL"><b>${lang === "nl" ? "Mijn Bezorging" : "My Delivery"}</b></header>${deliveryMarkup(pkg, lang)}</div>`;
      attachVanFallback(this.shadowRoot);
    }
  }

  class PostNLDeliveryImageCard extends PostNLBaseCard {
    getCardSize() {
      return 8;
    }

    render() {
      const hass = this._hass;
      if (!hass) return;
      const lang = language(hass);
      const state = findRoleEntity(hass, "packages", this._config.entity);
      const pkg = state?.attributes?.active_package || null;
      this.shadowRoot.innerHTML = `<style>${deliveryCss}.card{aspect-ratio:1/1}</style><div class="card">${deliveryMarkup(pkg, lang, true)}</div>`;
      attachVanFallback(this.shadowRoot);
    }
  }

  const definitions = [
    ["postnl-mail-card", PostNLMailCard],
    ["postnl-latest-mail-card", PostNLLatestMailCard],
    ["postnl-packages-card", PostNLPackagesCard],
    ["postnl-delivery-card", PostNLDeliveryCard],
    ["postnl-delivery-image-card", PostNLDeliveryImageCard],
  ];

  definitions.forEach(([name, klass]) => {
    if (!customElements.get(name)) customElements.define(name, klass);
  });

  window.customCards = window.customCards || [];
  const cards = [
    { type: "postnl-mail-card", name: "PostNL – Mijn Post", description: "Poststukken inclusief scans" },
    { type: "postnl-latest-mail-card", name: "PostNL – Laatste poststuk", description: "Laatste poststukscan" },
    { type: "postnl-packages-card", name: "PostNL – Mijn Pakketten", description: "Pakketten met details" },
    { type: "postnl-delivery-card", name: "PostNL – Mijn Bezorging", description: "Actuele bezorging" },
    { type: "postnl-delivery-image-card", name: "PostNL – Mijn Bezorging image", description: "Vierkante bezorgweergave" },
  ];

  for (const card of cards) {
    const definition = {
      ...card,
      preview: false,
      documentationURL: "https://github.com/LRvdLinden/nl.lrvdlinden.postnl-ha#lovelace-cards",
    };
    const existing = window.customCards.find((item) => item.type === card.type);
    if (existing) Object.assign(existing, definition);
    else window.customCards.push(definition);
  }

  console.info(`%c POSTNL %c Lovelace cards v${VERSION} `, "background:#fb6200;color:#fff;font-weight:700", "background:#fff;color:#fb6200;font-weight:700");
})();
