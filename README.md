<img width="1772" height="1102" alt="https___www metronieuws nl_wp-content_uploads_2020_08_POSTNL-01" src="https://github.com/user-attachments/assets/3b9957d2-a20d-4368-b96b-b0f60b1284cb" />


<h1 align="center">PostNL for Home Assistant</h1>

<p align="center">
  Bring <strong>Mijn Post</strong> and <strong>Mijn Pakketten</strong> into Home Assistant, including mail scans, parcel details, delivery windows, events and dedicated PostNL Lovelace cards.
</p>

<p align="center">
  <img alt="HACS Custom" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg">
  <img alt="Home Assistant 2026.6+" src="https://img.shields.io/badge/Home%20Assistant-2026.6%2B-18BCF2.svg">
  <img alt="Version 1.0.0" src="https://img.shields.io/badge/version-1.0.0-orange.svg">
  <img alt="GPL-3.0" src="https://img.shields.io/badge/license-GPL--3.0-blue.svg">
</p>

---

## Features

- 📬 **Mijn Post** with scanned mail-item images.
- 📦 **Mijn Pakketten** with Track & Trace enrichment.
- 🚚 Delivery date and delivery-window information.
- 🔎 Package status, sender, recipient, tracking code, shipment type and latest event.
- 🔔 Home Assistant events for new mail, new parcels, status changes, delivery windows, expired sessions and synchronization errors.
- 🔄 Manual **Refresh** button and `postnl_lrvdlinden.refresh` action.
- 🔐 PostNL account linking with PKCE and the dedicated Chrome login helper.
- 🖼️ Five built-in PostNL Lovelace cards.
- 🌗 Light and dark mode support.
- 🧡 Local PostNL branding for the Home Assistant integration UI.

Mail scans are retrieved through an authenticated Home Assistant WebSocket command instead of being stored as large base64 attributes in the recorder.

---

## Install with HACS

1. Open **HACS → Integrations**.
2. Open the menu in the top-right and choose **Custom repositories**.
3. Add `https://github.com/LRvdLinden/nl.lrvdlinden.postnl-ha` as type **Integration**.
4. Install **PostNL for Home Assistant**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration → PostNL**.

The Lovelace module is served and registered automatically by the integration. No separate `/config/www/postnl` folder and no manually configured dashboard resource are required.

---

## Linking your PostNL account

The PostNL callback is captured with the dedicated **PostNL Home Assistant Login Helper** for Google Chrome.

1. [**Download the PostNL Home Assistant Login Helper**](https://github.com/LRvdLinden/nl.lrvdlinden.postnl-ha/raw/main/tools/PostNL-Home-Assistant-Login-Helper.zip) and extract the ZIP file.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked** and select the extracted helper folder.
5. In Home Assistant, go to **Settings → Devices & services → Add integration → PostNL**.
6. Open the PostNL sign-in link shown by Home Assistant and sign in to your PostNL account.
7. The helper automatically captures the `postnl://login?...` callback.
8. Click the helper icon in Chrome and choose **Copy callback**.
9. Return to Home Assistant, paste the callback into the setup form and complete the sign-in process.

The callback, authorization code and tokens are not written to Home Assistant logs.

---

## Lovelace cards

All cards are registered automatically and appear in the dashboard card picker.

| Card | Lovelace type | Purpose |
|---|---|---|
| **Mijn Post** | `custom:postnl-mail-card` | Recent mail items with PostNL scan images |
| **Laatste poststuk** | `custom:postnl-latest-mail-card` | Large view of the newest mail scan |
| **Mijn Pakketten** | `custom:postnl-packages-card` | Recent parcels, status and parcel details |
| **Mijn Bezorging** | `custom:postnl-delivery-card` | Current delivery with delivery window and animated PostNL van |
| **Mijn Bezorging image** | `custom:postnl-delivery-image-card` | Square delivery image-style card |

### YAML examples

```yaml
type: custom:postnl-mail-card
```

```yaml
type: custom:postnl-latest-mail-card
```

```yaml
type: custom:postnl-packages-card
```

```yaml
type: custom:postnl-delivery-card
```

```yaml
type: custom:postnl-delivery-image-card
```

<p align="center">
  <img src="custom_components/postnl_lrvdlinden/frontend/postnl-van.gif" alt="PostNL delivery van" width="420">
</p>

The dashboard frontend also includes the supplied `icon.svg`, `van-1.svg`, package artwork and animated PostNL van GIF so the cards retain the PostNL visual style.

---

## Entities

The integration exposes Home Assistant entities for, among other things:

- mail item count;
- parcel count;
- expected mail;
- connection state;
- next delivery;
- delivery date;
- delivery window;
- parcel status;
- sender and recipient;
- tracking code;
- latest package event and status time;
- shipment type;
- last update;
- manual refresh.

These entities can be used directly in dashboards, scripts and automations alongside the included Lovelace cards.

---

## Manual installation

Copy:

```text
custom_components/postnl_lrvdlinden
```

to:

```text
/config/custom_components/postnl_lrvdlinden
```

Restart Home Assistant and add **PostNL** from **Settings → Devices & services**.

---

## Compatibility

- Minimum Home Assistant version: **2026.6.0**.
- The integration uses PostNL interfaces that are not publicly documented and may be changed by PostNL at any time.
- This project is not affiliated with or endorsed by PostNL.

---

## Contribution

If you appreciate this integration, you can support future development through [PayPal](https://lrvdlinden.app/donate.html), [iDEAL](https://lrvdlinden.app/donate.html) or [Bunq.me](https://lrvdlinden.app/donate.html). Your support helps keep development moving. ✨🚀
