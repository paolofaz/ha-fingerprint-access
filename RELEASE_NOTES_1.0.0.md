# Fingerprint Access 1.0.0

First stable release for Home Assistant 2026.11.

## Included

- Server-side authorization for ESPHome fingerprint readers.
- Configurable **Full** and **Partial** action sequences.
- Persistent ID/name/profile registry and guided registration/cancellation/deletion.
- Administrator-only services and a dedicated Lovelace management card.
- Per-reader **1.5-second match cooldown**, with **5 seconds** of holdoff after enrollment.
- Restart-mode action execution without waiting for long timers to finish.
- Automatic registration of only this integration's Lovelace resource.

## Reliability

- Fix the RC4 Home Assistant Script condition error by using a real `Template` object (included since RC5).
- New tests using the actual **Home Assistant 2026.11.0** runtime.
- Guard against action execution from late scans after integration unload.
- Avoid false enrollment timeout while saving a completed scan.
- Tested upgrade paths preserve the existing configuration-entry identity and registry design; always take a backup before updating.

## Upgrade

Update Fingerprint Access using Marketplace, restart Home Assistant and refresh the dashboard. Do **not** delete your existing integration or re-enroll existing fingerprints. The frontend resource cache key is now `?v=100`.

## Safety and limitations

This is a community integration and is **not certified** access-control equipment.
The Home Assistant event bus is not cryptographically authenticated to a live
fingerprint scan. Use a manual alternative for entry and test Full/Partial
behavior, revoked credentials, reloads and reader failure on your installation.
A light timer implemented with an external script `delay` may not complete if
Home Assistant is restarted during that delay.

See README and CHANGELOG for detailed requirements, migration and diagnostics.
