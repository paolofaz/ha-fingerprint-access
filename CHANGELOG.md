# Changelog

## 1.0.0rc3 — 2026-11-06

- Automatically register the Lovelace module resource **after HA startup**
  using the supported Home Assistant resource collection API.
- Create or update only the exact Fingerprint Access resource URL.
- Preserve all Marketplace/custom card entries; stop without changes if
  multiple Fingerprint Access resources exist.
- Keep YAML resource-mode configuration manual, since it is user-owned.
- Add behavioral regression tests covering preserved other resources,
  idempotency, updates, duplicates, and YAML mode.
- Reader and authorization behavior unchanged from RC2.


## 1.0.0rc2 — 2026-11-06

- Stop automatically editing Lovelace resources at integration startup.
- Serve the card as a JavaScript module for manual, explicit registration.
- Document recovery steps for unrelated custom cards and frontend caches.
- Access-control logic is unchanged from RC1.

## 1.0.0rc1 — 2026-11-06

- Full and Partial access continue to support independently customizable HA action sequences.
- Removed beta Test mode; a known fingerprint dispatches the configured actions.
- Added 2.5-second cooldown and 5-second post-enrollment holdoff.
- Serialized enrollment completion, failure, start and cancel operations.
- Keeps fail-closed behavior for unknown IDs and missing action sequences.
- More usable mobile Lovelace card, with live form-draft retention,
  compact status and recent diagnostic events.
- Original local integration brand icon.
- Updated migration and security guidance.

**Field testing remains necessary; do not treat this RC as a certified lock controller.**

## 0.2.0b4
- Timestamp and matched-event counter.

## 0.2.0b3
- Lovelace resource registration.

## 0.2.0b2
- Frontend loading updates.

## 0.2.0b1
- First Lovelace card.

## 0.1.0b2
- Editable ESPHome event prefix.

## 0.1.0b1
- First integration prototype.
