# PostNL for Home Assistant

Home Assistant-port van **PostNL for Homey**, met Mijn Post, Mijn Pakketten en PostNL-dashboardkaarten.

## Functies

- PostNL-accountkoppeling via PKCE.
- Mijn Post inclusief poststukscans.
- Mijn Pakketten met Track & Trace-verrijking.
- Sensors voor aantallen, status, bezorgdatum, bezorgvenster, afzender, ontvanger, tracking en laatste update.
- Binary sensors voor post verwacht, pakket bezorgd en verbinding.
- Handmatige **Vernieuwen**-knop en `postnl_lrvdlinden.refresh`-actie.
- Home Assistant-events voor nieuwe post, nieuwe pakketten, statuswijzigingen, bezorgvenster, synchronisatiefouten en verlopen login.
- Vier ingebouwde Lovelace-kaarten:
  - **Mijn Post**
  - **Laatste poststuk**
  - **Mijn Pakketten**
  - **Mijn Bezorging**

De poststukscans worden niet als grote base64-attributen in de recorder opgeslagen. De kaarten halen de afbeelding via een geauthenticeerde Home Assistant WebSocket-opdracht op.

## Installeren via HACS

1. Voeg `LRvdLinden/nl.lrvdlinden.postnl-ha` toe als aangepaste HACS-repository van het type **Integration**.
2. Installeer **PostNL for Home Assistant**.
3. Herstart Home Assistant.
4. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen → PostNL**.

De Lovelace-module wordt door de integratie zelf geserveerd en geregistreerd. Een losse `/config/www/postnl` map of handmatige dashboard-resource is niet nodig.

## Handmatig installeren

Kopieer alleen:

```text
custom_components/postnl_lrvdlinden
```

naar:

```text
/config/custom_components/postnl_lrvdlinden
```

Herstart Home Assistant en voeg daarna de PostNL-integratie toe via de UI.

## PostNL aanmelden

Tijdens het koppelen toont Home Assistant een PostNL-aanmeldlink. Na het aanmelden probeert de browser een URL te openen die begint met:

```text
postnl://login?code=...
```

Kopieer de volledige callback-URL en plak die terug in de Home Assistant-configuratiestap.

## Lovelace-kaarten

De kaarten worden automatisch geladen en verschijnen in de kaartkiezer. YAML kan ook:

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

## Compatibiliteit

Minimale Home Assistant-versie: **2026.6.0**.

De gebruikte PostNL-interfaces zijn niet publiek gedocumenteerd en kunnen door PostNL wijzigen.
