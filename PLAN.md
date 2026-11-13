# Plan: Xiaomi LYWSD03MMC solar meter

Fork: [scd29873/xiaomi-LYWSD03MMC-to-solar-meter](https://github.com/scd29873/xiaomi-LYWSD03MMC-to-solar-meter)
Upstream: [jozefpis/xiaomi-LYWSD03MMC-to-solar-meter](https://github.com/jozefpis/xiaomi-LYWSD03MMC-to-solar-meter), 1 commit (`6ba1499`)
Plan written 2026-11-13. Updated 2026-11-14: development now runs on a computer on the home network, and the hardware choice is made (a pre-flashed SCREEK THS-M6 display and a SCREEK BP2-POE Bluetooth proxy). Links accessed 2026-11-13 and 2026-11-14.

### Decisions at a glance (2026-11-14)
| Item | Choice | Why |
|---|---|---|
| Display | **SCREEK THS-M6, BLE (BTHome) version, with battery.** A Xiaomi MJWSD06MMC sold pre-flashed with pvvx firmware. | No flashing. Newer LYWSD03MMC batches block OTA flashing. Bigger screen, and a CR2450 battery. |
| Bluetooth link | **SCREEK BP2-POE** ESPHome Bluetooth proxy, on the existing PoE cable behind the TV | The HA host has no Bluetooth adapter. BP2-POE ships pre-flashed, cased, over Ethernet, and the maker states up to 4 active (GATT) connections. |
| Component | This repo's `pvvx_display` service, unchanged | The MJWSD06MMC firmware has the same external-display command and LCD functions (see section 3, Phase 3). |
| Fallback | Reflash the proxy role onto an ESP32 running ESPHome's `pvvx_mithermometer` display component | Only if writes through the proxy prove unreliable |

---

## 1. What the project is

A small, live solar display. It turns a cheap Xiaomi humidity monitor into a meter for Home Assistant (HA):

- **Big number:** current PV production in kW (e.g. `5.7`)
- **Small number:** the % of current production being used at home (self-consumption)
- **Face:** happier the more of your own energy you're using

### Repo contents
| Path | Purpose |
|---|---|
| `custom_components/pvvx_display/__init__.py` | HA custom component, about 130 lines. Registers the `pvvx_display.show` service. |
| `custom_components/pvvx_display/services.yaml` | Service UI definition |
| `custom_components/pvvx_display/manifest.json` | Depends on `bluetooth`. Requires `bleak-retry-connector>=3.5.0` |
| `hacs.json` | HACS metadata. Minimum HA version 2024.1.0 |
| `examples/template_sensors.yaml` | Template sensors for self-consumption in W and % |
| `examples/automations.yaml` | Day automation (sends every 3 or 8 min) and night automation (clears the display, stops sending) |

### How it works
HA connects to the thermometer over BLE using its own Bluetooth stack (`bleak-retry-connector`). It writes one 8-byte frame to characteristic `00001f1f-…` without waiting for a response, then disconnects.

```
[0]   0x22
[1:3] big number   int16 LE, value × 10   (-99.5 … 1999.5)
[3:5] small number int16 LE               (-9 … 99; 100 shows "Hi", so it is capped at 99)
[5:7] validity     uint16 LE, seconds     (65535 = show external data until reboot, pvvx fw 4.4+)
[7]   flags        bit0 happy, bit1 sad, bit2 bracket, bit3 %, bit4 battery, bits5-7 unit
```
This is the same frame the ESPHome `pvvx_mithermometer` display component sends.

The component handles one write at a time, behind a lock, because many BLE adapters can't hold parallel connections.

---

## 2. Where things run: home vs cloud

> **Update 2026-11-14:** development has moved to a Claude session on a computer on the home network. From there it can reach HA's web/API port, and git push to the fork works. The tables below still describe the physical constraints (BLE is local). The "bring Claude closer" options are no longer needed. To read HA entities and logs, the session only needs a long-lived HA access token, kept on that machine and never committed.
>
> Checked on 2026-11-14:
> - HA runs as a VM (HAOS) on a small server.
> - **Neither the server nor the VM has a Bluetooth adapter.** Hence the BP2-POE proxy.

**The meter can't run in the cloud.** It runs inside your own HA at home. A cloud session is only useful for development.

| Link | What it needs | Can the cloud do it? |
|---|---|---|
| HA ↔ thermometer | Bluetooth LE, a few metres, from the HA host's adapter or an ESPHome BT proxy | **No.** BLE is physically local. |
| HA ↔ inverter or grid meter | Usually your LAN (Modbus, local API) or the vendor's cloud API | No. The cloud container has no route to your LAN. |
| You ↔ HA | LAN, or remote access you configure | Only if you deliberately expose it. |

**What a cloud Claude session can do:**
- Write code and tests for the component. The tests can mock HA and BLE.
- Lint and validate YAML.
- Adapt the template sensors and automations to your entity IDs.
- Push to the fork, so you can install from it through HACS.

**What it can't do:**
- Flash the thermometer.
- Talk to the thermometer, see your HA, or read your inverter.
- Run the on-device smoke test.

**Ways to bring Claude closer to HA:**
1. **Remote Control (preferred):** link a computer on your LAN to the session (Claude desktop app → Settings → Claude Code → Remote Control). Commands can then run inside your network, e.g. checking HA reachability or logs. This still can't flash the device or do BLE.
2. **Expose the HA API to the internet** (Nabu Casa or a reverse proxy, plus a long-lived token). **Not recommended** for this project: it puts a powerful credential in a cloud environment for little gain.

**Recommended split:**
- Cloud: code, tests and YAML, pushed to the fork.
- Home: flashing, HACS install, on-device testing.
- When something fails, paste the HA logs back into the session to debug.

---

## 3. Build phases

### Phase 0: prerequisites and decisions (blocking)
- [ ] **Order the hardware** from shop.screek.io (one order, about US$46 plus shipping and GST, prices on 2026-11-14):
  - [BP2-POE](https://shop.screek.io/products/bp2-poe), US$29.99
  - [THS-M6](https://shop.screek.io/products/ths-m6), **"BLE (BTHome Supported) / With Battery / No External Probe"**, US$16.49. Not the Zigbee variant: Zigbee firmware has no external-display command.
- [ ] **PoE port:** confirm the switch port for the cable behind the TV has PoE enabled and is on the same LAN/VLAN as HA.
- [ ] **HA host and Bluetooth:** decided. The BP2-POE proxy provides an adapter that can make **active connections**.
  - Tested by the upstream author: a local adapter, e.g. a Raspberry Pi's built-in one.
  - Untested upstream: ESPHome BT proxies with active connections. The proxy route is the main thing Phase 3 proves.
  - Proxy placement: at the TV's top or side edge, not flat behind the panel (metal and electronics block BLE). Aim for under ~10 m to the display, with few walls between.
  - Alternatives considered (photos, prices, pros and cons in a separate comparison, 2026-11-14):
    - Seeed XIAO W5500 Ethernet Adapter V1.2: ESPHome ready-made, US$21.90, large 3D-printed case
    - Olimex ESP32-POE-ISO-EA + box: about €35, the most proven board
    - GL.iNet GL-S10: ready-made, but the first flash needs soldering
    - M5Stack AtomS3 Lite + Atomic PoE Base: community config only; open crash report with Ethernet plus the proxy
    - A Shelly can't do it: stock firmware is a passive-only proxy.
- [ ] **Inverter or energy integration:** identify these entities:
  - PV production (W)
  - Grid export (W), as a separate sensor or a signed meter value (+ export / − import)
- [ ] **Optional:** a motion or presence entity near the display, for the 3-minute fast mode.
- [x] **Display hardware:** THS-M6 (MJWSD06MMC, CR2450), pre-flashed. See the decisions table.
  - Fallback only: LYWSD03MMC and a CR2032. Check the hardware revision and stock firmware in the flasher before buying. The upstream author used B1.4 with stock firmware 1.0.0_0130. SCREEK reports that recent batches patch the BLE OTA hole and need a hardware programmer.
- [ ] **Placement:** within reliable BLE range of the adapter, e.g. the kitchen.

### Phase 1: set up the proxy and display (about 15 min, at home)
**With the chosen hardware there's nothing to flash.**
1. **BP2-POE:** plug it into the PoE cable. HA should auto-discover it under Settings → Devices & services. Click **Add**.
   - If it isn't discovered, use SCREEK's recovery and firmware tools at https://screek.io/bp2-poe.
   - Check that active connections are on (the maker documents up to 4).
2. **THS-M6:** fit the battery. HA should discover it as a BTHome device through the proxy.
3. Record its MAC address (from the BTHome device in HA, or the label on the back).
4. Optional: open the [pvvx Telink Flasher](https://pvvx.github.io/ATC_MiThermometer/TelinkMiFlasher.html) in Chrome or Edge near the device, **connect only** (don't flash), and note the firmware version. 4.4+ is needed for `validity: 65535`.

#### Fallback: flashing an LYWSD03MMC yourself
1. Open the [Telink Flasher](https://pvvx.github.io/ATC_MiThermometer/TelinkMiFlasher.html) in Chrome or Edge on a computer with Bluetooth.
2. Click **Connect**, select `LYWSD03MMC`, then click **Do Activation** and wait for *Login successful*.
3. Under *Custom Firmware*, choose the latest `ATC_vXX.bin` (the README names v59), then click **Start Flashing**.
4. Record the MAC address (`A4:C1:38:…`).
- **Risks:**
  - Newer stock firmware can block OTA flashing. One fork warns that stock 2.1.1_0159 is temporarily not supported.
  - If the OTA flasher shows an error, the only way in is a **USB-UART** connection. Read the [pvvx README](https://github.com/pvvx/ATC_MiThermometer#readme) first.

### Phase 2: install the component
- **HACS:** ⋮ → Custom repositories → add `https://github.com/scd29873/xiaomi-LYWSD03MMC-to-solar-meter` with type **Integration** → install **PVVX Display**.
  - Install from the fork so any changes made here are what you run.
- **Manual alternative:** copy `custom_components/pvvx_display/` into `config/custom_components/`.
- Add `pvvx_display:` to `configuration.yaml` and restart HA.

### Phase 3: smoke test
In Developer tools → Actions (YAML mode):
```yaml
action: pvvx_display.show
data:
  address: "A4:C1:38:XX:XX:XX"
  big: 5.7
  small: 98
  percent: true
  happy: true
  bracket: true
  validity: 65535
```
- **Pass:** the LCD changes within seconds.
- **Error "not in Bluetooth range (or not connectable)":** move the device closer, or check that the adapter supports active connections.
- **This test is the go/no-go for the proxy route.** Repeat it a few times over a day. If writes through the BP2-POE fail or are flaky, switch to the fallback in the decisions table.

**MJWSD06MMC display notes** (from pvvx's `src/lcd_mjwsd06mmc.c`, read 2026-11-14; not yet tested on hardware):
- Same functions as the LYWSD03MMC:
  - big number −99…1999, with a decimal point from −9.9 to 199.9
  - small number −9…99, with a `%` sign; above 99 it shows "Hi"
  - smiley: happy and sad
  - battery symbol
- Unit bits 5–7 map to slightly different glyphs: 0x20 "°Г", 0x40 "-", 0x80 "_". Check how a chosen unit looks on this screen.
- The firmware README lists command `0x22` "Get/Set show LCD ext.data" on characteristic `0x1F1F` for all supported devices. MJWSD06MMC support was added in pvvx firmware 5.1.

### Phase 4: sensors and automation
- [ ] Copy `examples/template_sensors.yaml` and swap in your entity IDs. Check the export sign convention.
  - Self-consumption % = (production − export) / production. It is forced to 0 when production is ≤ 50 W.
- [ ] Copy `examples/automations.yaml` and set the MAC address and entities.
  - No motion sensor? Delete the motion condition and the slow trigger, then set one interval.
- [ ] Watch it over one day:
  - the first-production trigger fires in the morning
  - updates arrive every 3–8 min
  - the night automation clears the display after sunset or 10 min of no production
  - nothing is sent overnight

### Phase 5: hardening and improvements (can be done in the cloud and pushed to the fork)
- [ ] **Unit tests for `build_packet`:** clamping at the range edges, every flag bit, unit bits, little-endian packing, rounding. Use `pytest`, and `pytest-homeassistant-custom-component` for service registration.
- [ ] **CI:** a GitHub Actions workflow with `hassfest`, HACS validation and pytest.
- [ ] **Stale-value guard:** with `validity: 65535` the display freezes on its last value if HA stops sending. Options:
  - a long but finite validity (e.g. 1800 s), accepting some temp/humidity flipping
  - a watchdog automation that alerts when the last successful write is too old
  - a distinctive "stale" display, e.g. the sad face with a dash unit
- [ ] **Observability:** fire an HA event, or keep a `last_success` / `last_error` sensor for each address, so failed writes are visible.
- [ ] **Battery:**
  - Only send when a value changes by more than a threshold (e.g. 0.1 kW or 2 %).
  - Watch battery life: one connection per minute drains a CR2032 in a few months. The THS-M6's CR2450 has roughly twice the capacity, but SCREEK notes its battery-voltage reading isn't accurate yet. Judge by days per battery, not the reported %.
- [ ] **Validation:** normalise the MAC address format and reject bad addresses early.
- [ ] **Config flow (UI setup):** stretch goal, to replace the YAML-only `pvvx_display:` setup.
- [ ] **Upstream:** offer generally useful fixes back to `jozefpis` as PRs.

---

## 4. Display ideas beyond solar
The same service can show any number from −99.5 to 1999.5, plus a 2-digit number and a face. Ideas:
- **Electricity price:** current spot or tariff price (c/kWh), with a face for cheap/expensive periods. Good for timing appliances.
- **Battery storage:** home battery state of charge (%) and charge/discharge power (kW).
- **Grid import:** current import in kW, sad face when importing.
- **EV charging:** charge power and car state of charge.
- **Outdoor weather:** outdoor temperature (big) with UV index or rain chance (small).
- **Air quality:** CO₂ ppm ÷ 100, or PM2.5, with the face as a ventilation hint.
- **Daily energy:** kWh produced today (big) and self-sufficiency % (small).
- **Countdowns:** minutes to the next bus or tram, or until the washer finishes.
- **Multiple displays:** several thermometers each showing different data. The component already serialises writes.

---

## 5. Related projects and other uses of the device

### Same idea: Home Assistant drives the LCD
- **ESPHome `pvvx_mithermometer` display platform:** an ESP32 pushes values over BLE. Big and small numbers, plus `update_interval` and `validity_period`. This repo reuses its message format.
  https://esphome.io/components/display/pvvx_mithermometer.html
- **AnthonyKNorman, Xiaomi_BLE_Temperature_Display_for_HA:** an early ESP32/MicroPython bridge. No longer maintained, as ESPHome now supports the display.
  https://github.com/AnthonyKNorman/Xiaomi_BLE_Temperature_Display_for_HA
- **AnthonyKNorman, Xiaomi_LYWSD03MMC_for_HA:** same author, same status.
  https://github.com/AnthonyKNorman/Xiaomi_LYWSD03MMC_for_HA
- **HA community thread "Xiaomi LYWSD03MMC BLE Temperature and Humidity Display":**
  https://community.home-assistant.io/t/xiaomi-lywsd03mmc-ble-temperature-and-humidity-display/171782

No other project using the LCD as a solar or energy meter was found. Doing it directly from HA, without an ESP32, looks uncommon. This was not an exhaustive search.

### Firmware for the device (Telink TLSR8258)
- **pvvx/ATC_MiThermometer:** the custom BLE firmware this project needs. It supports external display data, BTHome v2 advertising and better power management, and includes the web flasher.
  https://github.com/pvvx/ATC_MiThermometer
- **atc1441/ATC_MiThermometer:** the original custom firmware.
  https://github.com/atc1441/atc_MiThermometer
- **pvvx/BZdevice:** Zigbee 3 and BLE at the same time, with BTHome v2 and Zigbee/BLE OTA. Experimental.
  https://github.com/pvvx/BZdevice
- **devbis/z03mmc:** the original Zigbee firmware. Turns the device into a Zigbee sensor. **Note:** Zigbee mode loses the custom-number display used here.
  https://github.com/devbis/z03mmc
  - Guide: https://smarthomescene.com/guides/convert-xiaomi-lywsd03mmc-from-bluetooth-to-zigbee/
  - Zigbee2MQTT device page: https://www.zigbee2mqtt.io/devices/LYWSD03MMC.html
- Other forks:
  - https://github.com/kotborealis/atc_mithermometer
  - https://github.com/napobear/ATC_MiThermometer

### Receivers, loggers and documentation
- **matthias-bs/ATC_MiThermometer:** ESP32/Arduino library for receiving ATC/pvvx advertisements.
  https://github.com/matthias-bs/ATC_MiThermometer
- **jphppd/lywsd03mmc2influx-rs:** logs readings to InfluxDB (Rust).
  https://github.com/jphppd/lywsd03mmc2influx-rs
- **Magalex2x14/LYWSD03MMC-info:** protocol notes.
  https://relatedrepos.com/gh/Magalex2x14/LYWSD03MMC-info
- **ESPHome `xiaomi_ble` / `atc_mithermometer` sensors:** passive reading of advertisements.
  https://esphome.io/components/sensor/xiaomi_ble

### Background reading
- Hackaday, "Custom firmware for cheap Bluetooth thermometers" (2020): https://hackaday.com/2020/11/17/custom-firmware-for-cheap-bluetooth-thermometers
- Hackaday, "Exploring custom firmware on Xiaomi thermometers" (2020): https://hackaday.com/2020/12/08/exploring-custom-firmware-on-xiaomi-thermometers
- Hackaday, "Custom firmware for even cheaper Bluetooth thermometers" (2024), on clones: https://hackaday.com/2024/12/21/custom-firmware-for-even-cheaper-bluetooth-thermometers
- Hackaday, "Fighting to keep Bluetooth thermometers hackable" (2025), on newer stock firmware blocking OTA: https://hackaday.com/2025/01/16/fighting-to-keep-bluetooth-thermometers-hackable

### Alternative designs
| Option | Pros | Cons |
|---|---|---|
| **This repo: HA writes over BLE directly** | No extra hardware, no soldering | Needs the HA host's adapter within BLE range and able to make active connections |
| **ESPHome on an ESP32 as a BLE relay** (`pvvx_mithermometer`) | Best-documented route. Put the ESP32 near the display, anywhere on Wi-Fi | One more device to run and power |
| **Zigbee firmware** | Zigbee mesh range, battery-friendly reporting | Loses the custom-number display |

---

## 6. Forks of upstream
- Checked 2026-11-14 through the public GitHub API. Upstream has 4 forks:
  - `scd29873` (this fork)
  - `kolorafa`, `sunproject4444`, `orinocoz`
- The three others were last pushed at the same moment as the upstream commit (2026-09-29), so they have no changes of their own. **Nothing to merge.**
- To re-check later:
  - In a browser: https://github.com/jozefpis/xiaomi-LYWSD03MMC-to-solar-meter/forks
  - From the command line:
    ```bash
    gh api repos/jozefpis/xiaomi-LYWSD03MMC-to-solar-meter/forks --jq '.[] | [.full_name, .pushed_at] | @tsv'
    ```

---

## 7. Open items and decisions
- [ ] Order the BP2-POE and THS-M6 (BLE version) (Phase 0).
- [ ] Confirm PoE is enabled on the switch port for the cable behind the TV.
- [ ] Create a long-lived HA token for the local Claude session (kept on that machine, never committed). Then read the inverter's PV production and grid export entities from HA and tailor the example YAML.
  - The inverter is already integrated in HA over local Modbus, so the entities should exist.
  - Read them from HA only. No direct Modbus requests to the inverter.
- [ ] Motion sensor near the display: yes or no.
- [ ] Which Phase 5 items to do first. Suggested order: tests → CI → observability → stale guard. These can start before the hardware arrives.
- [ ] Update `README.md` and the examples to mention the MJWSD06MMC / THS-M6 once Phase 3 passes.
- [x] ~~HA hardware and Bluetooth adapter~~: HA VM with no Bluetooth, so the BP2-POE proxy (2026-11-14).
- [x] ~~Whether to link a LAN machine through Remote Control~~: not needed. The session now runs on the home network (2026-11-14).
- [x] ~~Review other forks~~: none has changes (2026-11-14).

## 8. Caveats
- Writing through an ESPHome Bluetooth proxy hasn't been tested by the upstream author. SCREEK states BP2-POE supports up to 4 GATT connections. Phase 3 is the real test.
- MJWSD06MMC compatibility comes from reading the pvvx source and README, not from a test on hardware.
- BP2-POE was released in January 2026 by a small maker, so it has little track record. One April 2026 forum report of a unit not being discovered turned out to be a different board.
- Flashing compatibility (fallback route only) depends on the LYWSD03MMC hardware revision and stock firmware version.
- The project's behaviour claims (range limits, `Hi` at 100, the validity semantics, battery life) come from the upstream README. They have not been independently tested here.
- Third-party project status, prices and stock are as shown on each page on 2026-11-13/14.
