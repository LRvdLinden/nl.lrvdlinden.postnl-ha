<p align="center">
  <img src="custom_components/postnl_lrvdlinden/brand/logo.png" alt="PostNL" width="180">
</p>

<h1 align="center">PostNL for Home Assistant</h1>

<p align="center">
  Bring <strong>Mijn Post</strong>, <strong>Mijn Pakketten</strong> and <strong>Mijn Bezorging</strong> into Home Assistant, including scanned mail items and dedicated PostNL Lovelace cards.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.0.4-blue">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2026.6%2B-41BDF5">
  <img alt="HACS" src="https://img.shields.io/badge/HACS-Custom%20Integration-41BDF5">
</p>

---

## Features

- PostNL account linking using PKCE.
- **Mijn Post** with scanned mail-item images.
- **Mijn Pakketten** with Track & Trace enrichment.
- Sensors for counts, package status, delivery date, delivery window, sender, receiver, tracking information and last update.
- Binary sensors for expected mail, delivered parcels and connection status.
- Manual **Refresh** button and `postnl_lrvdlinden.refresh` action.
- Home Assistant events for new mail, new parcels, status changes, delivery windows, sync errors and expired login sessions.
- Three built-in Lovelace cards:
  - **Mijn Post**
  - **Mijn Pakketten**
  - **Mijn Bezorging**
- Local PostNL branding for the Home Assistant integration picker and device/service UI.
- **Mijn Bezorging** follows the original PostNL widget layout, delivery timeline and animated delivery van concept.

Mail-item scans are not stored in the recorder as large base64 attributes. The Lovelace cards retrieve them through an authenticated Home Assistant WebSocket command.

## Installing via HACS

1. Open **HACS → Integrations**.
2. Add `LRvdLinden/nl.lrvdlinden.postnl-ha` as a custom repository of type **Integration**.
3. Install **PostNL for Home Assistant**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration → PostNL**.

The Lovelace module is served and registered automatically by the integration. A separate `/config/www/postnl` folder or manually configured dashboard resource is not required.

## Linking your PostNL account

The recommended method is the included **PostNL Home Assistant Login Helper** for Google Chrome.

1. [**Download the PostNL Home Assistant Login Helper**](https://github.com/LRvdLinden/nl.lrvdlinden.postnl-ha/raw/main/tools/PostNL-Home-Assistant-Login-Helper.zip) and extract the ZIP file.
2. Open `chrome://extensions`, enable **Developer mode**, and select **Load unpacked**.
3. Select the extracted helper folder.
4. In Home Assistant, go to **Settings → Devices & services → Add integration → PostNL**.
5. Open the PostNL sign-in URL shown by Home Assistant and sign in to your PostNL account.
6. The helper captures the `postnl://login?...` callback automatically. Click the extension icon and choose **Copy callback**.
7. Return to Home Assistant, paste the callback into the PostNL setup form and complete the sign-in process.

The callback, authorization code and tokens are not written to Home Assistant logs.

## Lovelace cards

The cards are loaded automatically and appear in the dashboard card picker. YAML configuration is also supported.

### Mijn Post

```yaml
type: custom:postnl-mail-card
```

### Mijn Pakketten

```yaml
type: custom:postnl-packages-card
```

### Mijn Bezorging

```yaml
type: custom:postnl-delivery-card
```

## Manual installation

Copy `custom_components/postnl_lrvdlinden` to `/config/custom_components/postnl_lrvdlinden`, restart Home Assistant and add **PostNL** from **Settings → Devices & services**.

## Compatibility

Minimum Home Assistant version: **2026.6.0**.

The PostNL interfaces used by this integration are not publicly documented and may be changed by PostNL at any time.

---

## Contribution

If you appreciate this integration, you can support future development via [PayPal, iDEAL or Bunq.me](https://lrvdlinden.app/donate.html). Your support helps keep development moving. ✨🚀
