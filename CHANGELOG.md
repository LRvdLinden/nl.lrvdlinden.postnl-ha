# Changelog

## 1.0.2

- Rebuilt **Mijn Bezorging** to match the original PostNL delivery widget layout, spacing, typography, package header and delivery timeline.
- Bundled the original animated PostNL delivery van GIF unchanged, together with the matching `van-1.svg`, `package.svg` and `icon.svg` assets.
- Delivery-window calculations now use the Home Assistant time zone so the progress line and time markers stay aligned with the displayed delivery window.
- Removed the **Laatste poststuk** Lovelace card.
- Removed the **Mijn Bezorging image** Lovelace card.
- The integration now exposes exactly three built-in cards: **Mijn Post**, **Mijn Pakketten** and **Mijn Bezorging**.

## 1.0.1

- Fixed Lovelace card picker loading by disabling live card previews.
- Fixed Home Assistant 2026.6+ entity suggestions for all PostNL cards.
- Mail scan images now use the supported `hass.callWS` path with a compatibility fallback.
- Added repository and integration-local PostNL brand assets.
- Bumped the frontend cache version so browsers load the fixed card bundle immediately.
- Removed the asset rebuild workflow that could overwrite the bundled Lovelace frontend.

## 1.0.0

- First stable Home Assistant release.
- Added local PostNL brand assets for the Home Assistant integration picker and device/service UI.
- Added the PostNL Home Assistant Login Helper and linked it directly from the setup flow.
- Setup instructions now explain how to load the Chrome extension, sign in to PostNL, copy the captured callback and finish setup in Home Assistant.
- Added five built-in Lovelace cards: **Mijn Post**, **Mijn Pakketten**, **Mijn Bezorging**, **Laatste poststuk** and **Mijn Bezorging image**.
- Updated the Lovelace cards to use the supplied PostNL `icon.svg`, `van-1.svg`, package asset and the supplied animated PostNL van GIF.
- Added PostNL post-item scans through the authenticated Home Assistant WebSocket API.
- Added package detail popups and delivery-window visualization.
- Removed references to unrelated smart-home platforms from the integration, documentation and login helper.
- HACS and Hassfest repository validation included.

## 0.1.0

- Initial Home Assistant release.
- PostNL PKCE account connection.
- Mijn Post and Mijn Pakketten data.
- PostNL sensors, binary sensors, events and manual refresh.
- Initial Lovelace cards for mail, packages and delivery.
