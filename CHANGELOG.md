# Changelog

## 1.0.0

### New

- Added local PostNL brand assets for the Home Assistant integration UI.
- Added the **PostNL Home Assistant Login Helper** for Chrome and linked it directly from the setup flow.
- Added five built-in Lovelace cards: **Mijn Post**, **Laatste poststuk**, **Mijn Pakketten**, **Mijn Bezorging** and **Mijn Bezorging image**.
- Added authenticated WebSocket delivery of PostNL mail-item scans.
- Added package detail popups and delivery-window visualization.

### Improved

- Lovelace cards now use the supplied PostNL `icon.svg`, `van-1.svg` and animated PostNL delivery van.
- Setup instructions now guide users through loading the Chrome extension, signing in to PostNL and pasting the captured callback into Home Assistant.
- Added HACS and Hassfest validation for repository releases.
- Cleaned the integration, documentation and helper so all user-facing text is specific to Home Assistant.

## 0.1.0

- Initial Home Assistant release.
- PostNL PKCE account connection.
- Mijn Post and Mijn Pakketten data.
- PostNL sensors, binary sensors, events and manual refresh.
- Initial Lovelace cards for mail, packages and delivery.
