# Changelog

## 1.0.0 — 2026-11-06

- First stable release: configurable `full` and `partial` fingerprint
  authorization, persistent Home Assistant registry, managed enrollment and
  revocation, dashboard and administrator-only services.
- Add runtime integration tests on the genuine **Home Assistant 2026.11.0**
  framework using the new official `pytest-homeassistant` fixtures. Cover
  full/partial script selection, unknown ID rejection, 1.5-second cooldown,
  persistence, and restarting a long-running sequence across profiles.
- Harden the unload path so delayed scan/action tasks cannot restart an
  already-unloaded manager.
- Disarm the enrollment timeout once a matching completion is accepted, before
  awaiting persistence; disk latency no longer causes a contradictory timeout
  during an otherwise successful enrollment.
- Retain the RC5 `Template` condition fix and 1.5-second matching cooldown,
  with the 5-second post-enrollment safety holdoff unchanged.
- Preserve the existing fingerprint register and carefully update only our own
  Lovelace resource URL to `?v=100`.
- Refresh documentation for the already implemented administrator card,
  installation, migration, tests and physical safety caveats.

This is **not** certified access-control equipment. The Home Assistant event
bus is not a cryptographically authenticated biometric assertion. Back up your
configuration and verify behavior on your own physical actuators.


## 1.0.0rc5 — 2026-11-06

- Fix a real Home Assistant action failure from RC4: template conditions in
  the shared restart-mode action script must use a Home Assistant `Template`
  object, not a bare string. RC4 raised
  `AttributeError: 'str' object has no attribute 'async_render_to_info'`
  before it could call the gate script.
- Reduce the global per-reader matching cooldown from 2.5 seconds to
  **1.5 seconds**, as requested.
- Add regression tests for template condition compatibility and the new
  cooldown boundary.
- Preserve authorization checks, the 5-second post-enrollment holdoff, and
  the restart-mode action runner. No change to ESPHome, the user's gate script,
  stored fingerprints, or unrelated Lovelace resources.
- Update manifest, card cache version and documentation for RC5.
- A real-reader test is still required before promoting this release to stable.


## 1.0.0rc4 — 2026-11-06

- Remove the action-duration lock that blocked new scans during 90-second
  light-off timers. Preserve the 2.5-second global cooldown.
- Reuse one Home Assistant Script in restart mode across full and partial
  profiles: new authorized fingerprints interrupt the prior sequence.
- Start sequences asynchronously, show a prompt action-started status,
  suppress stale completion reports and stop actions on integration unload.
- Document that external scripts such as script.cancello3q must also use
  mode: restart rather than parallel for correct timer reset.
- Behavioral regression tests cover 90-second actions, cooldown, replacement
  across different access profiles and unloading.
- Lovelace auto-registration stays unchanged except the cache key.


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
