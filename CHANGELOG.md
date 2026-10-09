# Changelog

## 1.1.0

Brought in line with PostNL for Homey 1.2.8.

- **Direct login**: sign in with your PostNL e-mail address and password, no Chrome extension required. The Chrome Login Helper stays available as a fallback option, both during setup and when re-authenticating. The password is never stored.
- **New Lovelace card – Reis van je pakket** (`custom:postnl-journey-card`): the complete Track & Trace timeline of the active parcel with locations, weight, dimensions and PostNL Point.
- **More parcel data** from PostNL Track & Trace: weight (kg), dimensions (cm, converted from PostNL millimetres), full status history, observation codes, a normalised package phase and PostNL Point / pick-up information.
- New sensors: package phase (enum), weight, dimensions, length/width/height, PostNL status code and PostNL Point. New binary sensor: PostNL Point delivery.
- **Mijn Pakketten** popup now shows weight, dimensions, PostNL Point, shipment type, delivery address type, direction, shared-from account, status code and a Track & Trace link.
- New events: `postnl_package_delivered`, `postnl_delivery_window_changed`, `postnl_package_event_changed`, `postnl_package_weight_known` and `postnl_package_dimensions_known`. All parcel events carry the new data fields.
- Fixed old delivered parcels that re-appear in the PostNL account feed triggering "new parcel" events. Parcels are now matched on the stable tracking number instead of PostNL's changing internal key.
- A parcel that disappears from the account feed right after delivery is re-checked once via Track & Trace so the final "delivered" event is not missed.
- Fixed a status such as "Je pakket wordt vandaag bezorgd" being treated as delivered.
- Large card attributes (`items`, `active_package`, `journey_package`, `status_history`) are excluded from the recorder database.
- The integration now uses whichever schema library the running Home Assistant core uses (voluptuous or probatio).
- Bumped the Lovelace bundle to `postnl-card-v105.js`.

## 1.0.4

- Updated **Mijn Bezorging** to use the same Home Assistant card background as **Mijn Post** and **Mijn Pakketten**.
- The delivery header, empty-state area and active-delivery panel now follow the current Home Assistant theme instead of using a separate fixed grey background.
- Dark mode now follows Home Assistant theme colors as well.
- Bumped the Lovelace frontend bundle to `postnl-card-v104.js` to avoid stale browser caching.

## 1.0.3

- Fixed **Mijn Bezorging** staying on the last delivered parcel.
- Once the active parcel is marked as delivered and no other active parcel exists, the card now immediately returns to the **Er is geen pakket onderweg** fallback with the static PostNL van image.
- The delivery card now prefers the backend-provided `active_package` and never falls back to an already delivered package.
- Bumped the Lovelace bundle to `postnl-card-v103.js` to avoid stale browser caching.

## 1.0.2

- Rebuilt **Mijn Bezorging** to match the original PostNL delivery widget layout, spacing, typography, package header and delivery timeline.
- Reworked the animated PostNL delivery van to match the original widget concept: a stationary PostNL van with the scenery moving behind it.
- Delivery-window calculations use the Home Assistant time zone so the progress line and time markers stay aligned with the displayed delivery window.
- Removed the **Laatste poststuk** Lovelace card from the dashboard card picker.
- Removed the **Mijn Bezorging image** Lovelace card from the dashboard card picker.
- The integration now exposes exactly three built-in dashboard cards: **Mijn Post**, **Mijn Pakketten** and **Mijn Bezorging**.

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
- Setup instructions explain how to load the Chrome extension, sign in to PostNL, copy the captured callback and finish setup in Home Assistant.
- Added built-in Lovelace cards for PostNL mail, parcels and delivery.
- Added PostNL post-item scans through the authenticated Home Assistant WebSocket API.
- Added package detail popups and delivery-window visualization.
- HACS and Hassfest repository validation included.

## 0.1.0

- Initial Home Assistant release.
- PostNL PKCE account connection.
- Mijn Post and Mijn Pakketten data.
- PostNL sensors, binary sensors, events and manual refresh.
- Initial Lovelace cards for mail, packages and delivery.
