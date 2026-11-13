# Plan: build the LYWSD03MMC solar meter

Source: jozefpis/xiaomi-LYWSD03MMC-to-solar-meter (1 commit, `6ba1499`), cloned 2026-11-13.
Forks: **not reviewed**. This session can't reach the GitHub API for this repo, so the forks list couldn't be fetched (see "Open items").

## What the project is
- A small Home Assistant custom component (`custom_components/pvvx_display`, about 130 lines) that registers one service, `pvvx_display.show`.
- The service connects over BLE, writes an 8-byte frame to characteristic `0x1F1F` and disconnects.
- You need the pvvx ATC_MiThermometer firmware on the thermometer. Stock firmware won't work.
- Two example YAML files: template sensors (self-consumption %) and automations (day and night schedule).

## Phase 0: decisions and prerequisites (blocking)
- [ ] Confirm the HA host and its Bluetooth. You need a local adapter that can make **active connections**. A Pi's built-in adapter is the tested setup. ESPHome BLE proxies are untested.
- [ ] Identify the entities: PV production (W) and grid export (W). The export can be a separate sensor or a signed meter value. This depends on which inverter integration you use.
- [ ] Optional: a presence or motion entity near the display, for the 3-minute fast mode.
- [ ] Hardware: an LYWSD03MMC and a CR2032. Note the hardware revision once it's connected. The author used B1.4 with stock firmware 1.0.0_0130.

## Phase 1: flash the firmware (about 15 min)
1. Open the pvvx Telink Flasher in Chrome or Edge on a machine with Bluetooth. Connect, then run **Do Activation**.
2. Flash the latest ATC_vXX.bin (the README names v59). Check the pvvx README first if your hardware or stock firmware version is different.
3. Write down the MAC address (`A4:C1:38:…`).
- Risk: some hardware revisions or newer stock firmware need extra steps. Check before you flash.

## Phase 2: install the component
- HACS → Custom repositories → add the repo URL as type Integration → install **PVVX Display**.
- Or copy `custom_components/pvvx_display/` into `config/custom_components/` by hand.
- Add `pvvx_display:` to `configuration.yaml` and restart.

## Phase 3: smoke test
- Developer tools → Actions → `pvvx_display.show` with `big: 5.7, small: 98, percent: true, happy: true, bracket: true, validity: 65535`.
- Pass: the LCD changes within seconds.
- Fail with "not in range / not connectable": move the device closer, or check that the adapter supports connections.

## Phase 4: sensors and automation
- Copy `examples/template_sensors.yaml` and swap in your entity IDs. Check that the export sign convention is right.
- Copy `examples/automations.yaml`. Set the MAC address and entities. If you have no motion sensor, delete the motion condition and the slow trigger.
- Check over one day: the morning start trigger fires, the display updates every 3–8 min, and the night clear runs after sunset.

## Phase 5: hardening (optional, possible fork or PR work)
- Stale-value guard: with `validity: 65535` the display freezes if HA stops sending. Option: use a long-but-finite validity, e.g. 1800 s, and accept some flipping. Or add a watchdog automation that alerts when the last successful write is too old.
- Expose write success or failure, e.g. an event or a "last update" sensor, so failures are visible.
- Unit tests for `build_packet` (range clamping, flag bits, little-endian packing). These can run here without hardware.
- Battery: watch CR2032 life at the 3/8-min cadence. If needed, go slower or only send when the value changes by more than X.

## Open items
- **Forks:** to review them, either attach the repo with GitHub API access or paste the fork URLs here. I'll clone each one and diff it against `6ba1499`.
- What does "make it here" mean for you?
  - (a) Build the physical meter for your own HA setup (this plan).
  - (b) Develop the component in this cloud session: tests, improvements, your own fork.
  - Phases 0–4 need your HA and hardware. Phase 5 can be done here.
