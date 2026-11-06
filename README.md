# Fingerprint Access for Home Assistant — 1.0.0rc5

A custom Home Assistant integration for **ESPHome fingerprint readers**. It keeps names
and access profiles in Home Assistant, processes **an event for each scan** and executes
your own Home Assistant action sequences.

> [!WARNING]
> **Release candidate — not yet validated on your physical locks.**
> Keep a manual way to enter. Before authorizing an ID, verify its Full/Partial
> action sequence and test the actuators safely. This is not certified security hardware.

## What it does

- Two user-configurable profiles: **Full access** and **Partial access**.
- Each profile has its **own Home Assistant action sequence** chosen in the integration's
  configuration screen. Actions may call a script, control a device, send a
  notification, or combine several steps.
- Names, IDs and profiles are stored in Home Assistant's `.storage` through its
  `Store` API, not in the ESP8266's flash or editable permission helpers.
- No test mode: a registered ID **immediately dispatches** the configured Full/Partial
  actions on a matching scan. An ID without an entry or without actions never opens.
- 1.5-second cooldown between dispatched actions; no queued delayed unlocks.
- 5-second holdoff after registration completion/cancellation to avoid an
  immediate unintended opening from a finger remaining on the reader.
- Short in-memory recent event history and a compact, responsive Lovelace card.
- Enrollment workflow: enter an available ID, person's name and profile; only
  save the authorization **after** ESPHome emits `_enrollment_done` for that ID.
- Refuse unknown IDs, invalid records, missing action sequences and concurrent
  access requests (no queued delayed unlocks).
- On removal: revoke access in Home Assistant **before** requesting hardware deletion.
- Read-only summary sensor with a dynamic list of people and their access profiles.
- Manage identities using the integration's **Configure** flow (no text-list helpers).
- Admin-only Home Assistant actions also available for advanced use.

## Installation

This repository is structured for HACS (custom repository, category **Integration**).
Alternatively copy `custom_components/fingerprint_access` into Home Assistant's
`/config/custom_components/` folder.

Restart Home Assistant. Under **Settings → Devices & services → Add integration**
search for **Fingerprint Access**. Enter the event prefix (default:
`esphome.impronte3q`).

**Need to rename the ESPHome reader later?** Under **Settings → Devices &
services → Fingerprint Access**, open the integration entry's three-dot menu
and choose **Reconfigure / Riconfigura**. Enter the new event prefix. The
integration reloads its event listeners while preserving the existing register
and action profiles. Avoid doing this during an enrollment; the reconfigure
flow refuses while enrollment is pending. Remember to update the event names
and ESPHome API action names in the ESPHome firmware consistently.

In the integration **Configure** menu:

1. **Configure access actions**: choose the sequences for *Full access* and
   *Partial access*. Verify both sequences before registering authorized IDs.
2. **Register new fingerprint**: type a previously verified empty slot, a name
   and one of the two profiles. Follow the reader's enrollment procedure.
3. **Manage fingerprints**: choose an existing person to edit name/profile or
   to revoke access and delete the template.
4. **Cancel enrollment**: stop an in-progress enrollment request.

**The RC has no Test mode switch.** For initial dry-run tests, temporarily
configure harmless actions (such as notifications) or leave sequences empty
while safely verifying ID recognition. When you configure actions that actuate
locks, a subsequent authorized scan can open them.

### Example: your existing `script.cancello3q`

In the **Full access** action editor, choose *Call a service/action* and enter:

```yaml
action: script.cancello3q
data:
  con_allarme_e_porta: true
```

In the **Partial access** action editor:

```yaml
action: script.cancello3q
data:
  con_allarme_e_porta: false
```

You are **not** required to use scripts. The editor accepts an entire native
Home Assistant sequence of actions. Action templates can use `finger_id`,
`person_name` and `profile`.

### Critical migration: disable the old automations

Disable the earlier YAML automations triggered by
`esphome.impronte3q_finger_matched` or changes to fingerprint state.
Otherwise **both systems might open the locks independently**. Keep any
scripts referenced by the configured actions **enabled** (e.g.
`script.cancello3q`).
This integration starts with an **empty authorization register**. Do not assume
existing templates on the physical reader are imported automatically.

## ESPHome: the essential event and action configuration

The reader still does the biometric matching itself. This integration needs
ESPHome to emit an event containing the **matched ID from that exact scan**
rather than exposing a changing `last_finger_id` sensor.

Insert / merge this into your ESPHome configuration. The example uses the
name `impronte3q`, so the event prefix in the integration is
`esphome.impronte3q`.

```yaml
fingerprint_grow:
  sensing_pin: D2

  on_finger_scan_matched:
    - homeassistant.event:
        event: esphome.impronte3q_finger_matched
        data:
          finger_id: !lambda 'return finger_id;'

    - fingerprint_grow.aura_led_control:
        state: BREATHING
        speed: 200
        color: GREEN
        count: 1

  on_finger_scan_unmatched:
    - fingerprint_grow.aura_led_control:
        state: FLASHING
        speed: 30
        color: RED
        count: 4

  on_enrollment_scan:
    - homeassistant.event:
        event: esphome.impronte3q_enrollment_scan
        data:
          finger_id: !lambda 'return finger_id;'
          scan_num: !lambda 'return scan_num;'

  on_enrollment_done:
    - homeassistant.event:
        event: esphome.impronte3q_enrollment_done
        data:
          finger_id: !lambda 'return finger_id;'

  on_enrollment_failed:
    - homeassistant.event:
        event: esphome.impronte3q_enrollment_failed
        data:
          finger_id: !lambda 'return finger_id;'

# Add these under the existing api: block (retain your encryption key):
api:
  encryption:
    key: !secret encryption_key
  actions:
    - action: enroll
      variables:
        finger_id: int
        num_scans: int
      then:
        - fingerprint_grow.enroll:
            finger_id: !lambda 'return finger_id;'
            num_scans: !lambda 'return num_scans;'

    - action: cancel_enroll
      then:
        - fingerprint_grow.cancel_enroll:

    - action: delete
      variables:
        finger_id: int
      then:
        - fingerprint_grow.delete:
            finger_id: !lambda 'return finger_id;'
```

This is an **excerpt**, not an entire ESPHome file. Keep the existing
`esphome:`, board, Wi-Fi, UART, OTA and logger settings. Do not add a second
`fingerprint_grow:` or `api:` block. LED effects are local to ESPHome.
The documented `fingerprint_grow` callbacks expose `finger_id` and
`scan_num` as shown:
https://esphome.io/components/fingerprint_grow/

**Required:** in the Home Assistant ESPHome integration, enable the permission
**Allow the device to perform Home Assistant actions**, so the firmware can
send `homeassistant.event` events.

For other ESPHome node names, change the common prefix consistently.
The integration derives ESPHome action service names from the prefix:
`esphome.impronte3q_enroll`,
`esphome.impronte3q_cancel_enroll`,
`esphome.impronte3q_delete`.

## Lovelace card (RC5: automatic registration after HA startup)

Fingerprint Access serves its own JavaScript card and **automatically registers
one Lovelace JavaScript module resource** in Home Assistant's resource storage
after Home Assistant finishes starting. No manual resource registration is
needed when Lovelace uses **storage mode** (the default).

Unlike the RC1 mechanism, this procedure runs **after startup**, when
Marketplace has already had the opportunity to migrate its resources. It uses
Home Assistant's supported collection API, checks only the exact Fingerprint
Access URL, and never iterates through other entries to rewrite or remove them.
An existing resource for this card is updated in place to
`/fingerprint_access/fingerprint-access-card.js?v=100rc5`. Other resources
belonging to Marketplace, uConnect, or other integrations are not edited.

Steps:

1. Update from the GitHub `main` branch to `1.0.0rc5`.
2. Restart Home Assistant, so the integration can register its static file
   and schedule resource registration after startup.
3. Refresh the browser or restart the Home Assistant mobile app.
4. Edit a dashboard → **Add card** → select **Fingerprint Access**.

You can also configure the existing card manually:

```yaml
type: custom:fingerprint-access-card
entity: sensor.registered_fingerprints
```

Replace the entity ID if your Registered fingerprints sensor uses a different
ID. You don't need to recreate existing dashboards or cards.

**Important:** if Lovelace resource mode is YAML, Home Assistant does not
allow integrations to register resources automatically. In that case, add
the following to your existing `lovelace: resources:` configuration:

```yaml
- url: /fingerprint_access/fingerprint-access-card.js?v=100rc5
  type: module
```

If older RC installations left **multiple Fingerprint Access resources**
using the same file path, the RC3 does not remove them: it logs an error
and requires you to retain only one resource using Dashboard Resources.
Do not remove any resource that belongs to a different custom card.

The fingerprint authorization register is independent from Lovelace resources
and remains stored in Home Assistant's own `.storage` entry. The card is
only the management UI; all access decisions are enforced by the backend.

### RC5: Fix for action failure in Home Assistant 2026.11

RC4 could recognize a fingerprint successfully but fail before running the
configured profile's action sequence, logging
`AttributeError: 'str' object has no attribute 'async_render_to_info'`.
The choose-action's template condition was incorrectly passed as a plain
string instead of a Home Assistant `Template` object. RC5 fixes that
condition and includes a regression test for the template interface.

The matching cooldown is now **1.5 seconds**. Matching remains suspended
during enrollment and for 5 seconds after it ends. These safeguards do not
fix a physically noisy reader, invalid ESPHome events or unavailable scripts.

### Reopening while the 90-second light timer is running

The RC5 no longer holds a lock throughout a configured action sequence. A
successful, authorized recognition starts the sequence asynchronously, and
a new successful recognition **after the global 1.5-second cooldown** restarts
the previous Fingerprint Access action sequence, even when switching between
full and partial access profiles. During enrollment and for 5 seconds after it
ends, matching remains suspended.

**For external Home Assistant scripts called in the configured actions**
(e.g. `script.cancello3q`), set the **script entity's own mode to
`restart`, not `parallel`**. Otherwise non-blocking script starts can leave
an older 90-second timer running, and lights might go off too early.
Stopping an action sequence does not undo hardware actions already executed,
such as a gate pulse or unlocking a door. Do not use `mode: parallel` for
a timer that must reset when a new fingerprint is accepted.

### Repeated fingerprints and event counter

The card shows the timestamp of the last backend outcome with milliseconds and
a **recognized scan event count since the current integration load**. This count
increases for repeated scans of the same ID: each `_finger_matched` event counts
even if the decision text remains `denied · ID 1`. It resets whenever the
integration/HA is reloaded, and is intended solely for diagnostics; it does not
influence authorization.

You can also listen to `fingerprint_access_access` under Developer Tools →
Events to see each reported decision and timestamp individually.

## View the live register on a dashboard

The integration adds a sensor named **Registered fingerprints**, whose state is
the number of identities authorized *in this integration* (not the fingerprint
count in the sensor hardware). Its `people` attribute contains an array of
`finger_id`, `name` and `profile`.

Add a standard Markdown card and replace the example sensor entity ID with
the one shown in **Developer tools → States**:

```yaml
type: markdown
title: Fingerprint Access — Rubrica
content: >
  {% set p = state_attr('sensor.fingerprint_access_registered_fingerprints', 'people') or [] %}
  | ID | Persona | Accesso |
  |---:|---|---|
  {% for item in p %}
  | {{ item.finger_id }} | {{ item.name }} | {{ 'Completo' if item.profile == 'full' else 'Parziale' }} |
  {% endfor %}
```

To modify a person or start enrollment, use **Settings → Devices & services →
Fingerprint Access → Configure**. The card itself has no editable permission fields.

## Administration and recovery

ESPHome stores fingerprint *templates in the physical reader*. Home Assistant
stores **only** names, ID mappings and access profiles. Home Assistant's
`.storage` is normally part of a full configuration backup. Replacing an ESP8266
alone does not change the authorization register; replacing the biometric reader
may require re-enrolling fingerprints.

Do not infer a free physical ID from the number of enrolled fingerprints:
the hardware's `fingerprint_count` is a **count**, not an occupied-slot list.
This integration cannot independently prove that a slot is empty, so enrollment
requires an explicit confirmation.

The integration listens to Home Assistant's event bus. Those events are not
cryptographic proof of a human scan: administrators or sufficiently privileged
automations can also fire events. Restrict access to Home Assistant and ESPHome.
For higher-security installations use an access controller with hardware-backed
authorization, a tamper-resistant reader, and independent fail-safe design.

A late enrollment result after Home Assistant restarts or the 120-second request
timeout is intentionally **not authorized**, even if the reader stored a template.
You can then revoke / clear it manually before attempting again.

Admin-only actions available under `fingerprint_access`:
`enroll`, `cancel_enrollment`, `update_person`, `delete_person` and
`list_people`. With multiple readers, supply an `entry_id`.
The integration also emits `fingerprint_access_access` events containing
test/authorization outcomes for troubleshooting.

## Development

```bash
python -m compileall -q custom_components tests
python -m unittest discover -s tests -v
```

These are pure-policy and syntax checks, **not** hardware or Home Assistant
integration tests. No release should be used to control a real lock until
the deployment-specific flow has been tested end to end.

License: MIT.


## Release candidate field-test checklist

1. Back up Home Assistant and save the ESPHome YAML. Keep manual entry available.
2. Disable all old fingerprint-opening automations; **leave the scripts chosen
   in profile actions enabled**. Disable/disconnect physical actuators during
   the initial dry run when possible.
3. Verify Full and Partial sequences individually: Partial must **never** unlock
   the door or disarm the alarm.
4. Verify unknown old finger IDs are denied; the registry is empty initially.
5. Confirm hardware slots 1 and 2 are actually empty. A count of enrolled
   fingerprints does **not** tell which slots are free.
6. Register your fingerprint as ID 1 with Full access; wait **at least 5 seconds**
   after enrollment before testing a fresh touch.
7. Register your relative with another ID and Partial access. Verify both
   physical action paths separately under supervision.
8. Try rapid repeat scans (within 1.5 seconds) to verify the cooldown, and
   repeat after several seconds to verify a new request can open.
9. Restart Home Assistant and confirm the registry and both access profiles
   persist. Recheck behavior after reconnection/power recovery.
10. Check logs and the recent events list for errors.

An ESPHome matched event is **not cryptographically authenticated to a live
finger**. Privileged Home Assistant integrations or automations could fire
synthetic matching events, and fingerprint hardware can misidentify prints or
emit repeated scans. The integration rejects some directly user-authored
events and adds safety delays, but these are **not guarantees against spoofing
or false recognition**. Use suitable dedicated hardware for higher-assurance
physical access control.

The local integration icon lives at
`custom_components/fingerprint_access/brand/icon.png` (Home Assistant 2026.3+).
The full register persists in Home Assistant; the biometric fingerprint
templates remain in the physical sensor and may require re-enrollment after
sensor replacement.

See [CHANGELOG.md](CHANGELOG.md) for version history.
