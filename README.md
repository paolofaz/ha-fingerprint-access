# Fingerprint Access for Home Assistant

A custom Home Assistant integration for **ESPHome fingerprint readers**. It keeps names
and access profiles in Home Assistant, processes **an event for each scan** and executes
your own Home Assistant action sequences.

> [!WARNING]
> **Experimental beta – not yet validated on real door hardware.**
> Install in **test mode** first. Keep a separate manual means of entry, and test
> with physical lock/door actuators disconnected or safely disabled. Do not enable
> actions until you have verified the full-to-partial separation. This is not a
> certified physical access-control product.

## What it does

- Two user-configurable profiles: **Full access** and **Partial access**.
- Each profile has its **own Home Assistant action sequence** chosen in the integration's
  configuration screen. Actions may call a script, control a device, send a
  notification, or combine several steps.
- Names, IDs and profiles are stored in Home Assistant's `.storage` through its
  `Store` API, not in the ESP8266's flash or editable permission helpers.
- **Test mode enabled by default**: logs decisions but never executes the actions.
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
   *Partial access*. Leave **Test mode** enabled.
2. **Register new fingerprint**: type a previously verified empty slot, a name
   and one of the two profiles. Follow the reader's enrollment procedure.
3. **Manage fingerprints**: choose an existing person to edit name/profile or
   to revoke access and delete the template.
4. **Cancel enrollment**: stop an in-progress enrollment request.

Only after observing correct test results, turn off **Test mode**.

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
Otherwise **both systems might open the locks independently**.
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

## Dedicated dashboard card (beta)

The integration now includes a custom Lovelace card with a **live people table**,
and for administrators only, forms to register people, edit their name/profile
or revoke an ID and request deletion from the fingerprint reader. Permissions
continue to be enforced exclusively by the backend integration; the dashboard
has **no editable permission helpers**.

1. Install/update the integration, then **restart Home Assistant**.
2. **Refresh the Home Assistant frontend** (hard reload / close and reopen the app).
3. Edit a dashboard → **Add card**, and search for **Fingerprint Access**. The
   integration automatically registers the JavaScript module in the frontend;
   manually adding a Lovelace resource is no longer necessary.
4. If you want to add the card manually, use:

```yaml
type: custom:fingerprint-access-card
entity: sensor.registered_fingerprints
```

When using the visual card picker, the card tries to detect the actual
**Registered fingerprints** sensor automatically. When adding via YAML,
replace the example entity ID if Home Assistant assigned a different one.
The integration **registers a card**, not a new sidebar dashboard: you still
choose where to place it.

**Upgrading from 0.2.0b1?** Remove the old manually configured Lovelace
JavaScript resource if you added one, then refresh the browser. Avoid duplicate
resource registrations. If the card does not appear, check browser developer
console for JavaScript load errors and that the URL
`/fingerprint_access/fingerprint-access-card.js?v=0202` is reachable.

The card reads the authorization register through the sensor's read-only
attributes, including its internal `entry_id` for multi-reader operation.
Mutation buttons are shown only for administrator accounts; the corresponding
backend services independently enforce administrator permission. For deletion
the administrator must type the exact numeric slot ID; other changes also
require explicit confirmation.

**Security:** The browser-side visibility check is only a convenience, not
a permission boundary. Do not share the dashboard with untrusted users; the
backend actions require administrative privileges. The integration cannot
verify whether a biometric reader slot is empty. Confirm that separately
before enrolling, even if the UI suggests an ID.

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
