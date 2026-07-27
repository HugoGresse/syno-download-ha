# Synology Download Station for Home Assistant

Custom integration that shows Download Station progress in Home Assistant and
lets you queue magnet / torrent links straight from a dashboard.

- **Compact dashboard card** (bundled, auto-registered): active downloads
  with progress bars, latest completed download, magnet/URL submit box and a
  .torrent file upload button.
- **Sensors**: download speed, upload speed, active download count (with a
  per-task attribute list: title, status, progress %, speed, ETA), a
  size-weighted overall progress percentage and the latest completed
  download.
- **Add downloads**: from the card, the *Add download* text entity, or the
  `add_task` / `add_torrent` actions.
- Local polling of the DSM API — no cloud.

Requires Home Assistant **2025.8** or newer and the Download Station package
running on the NAS.

## Installation

### HACS

Add this repository as a HACS *custom repository* (type: integration), install
**Synology Download Station**, then restart Home Assistant.

### Manual

Copy `custom_components/synology_download_station/` into the
`custom_components/` folder of your Home Assistant config and restart.

## Configuration

*Settings → Devices & services → Add integration → Synology Download Station.*

| Field | Notes |
| --- | --- |
| Host | NAS IP or hostname, no protocol |
| Port | `5001` HTTPS (default), `5000` HTTP |
| Username / Password | DSM user with Download Station permission |
| Use HTTPS | On by default |
| Verify SSL certificate | Off by default (self-signed certificates) |
| Default destination folder | Optional shared folder (e.g. `downloads`) used for every task added without an explicit destination; empty = Download Station default. Changeable later under *Configure* |

2-factor authentication is not supported — create a dedicated DSM user
without 2FA and grant it Download Station only.

The polling interval (default 10 s) can be changed under the integration's
*Configure* button.

## Entities

| Entity | Description |
| --- | --- |
| `sensor.synology_download_station_download_speed` | Current total download rate |
| `sensor.synology_download_station_upload_speed` | Current total upload rate |
| `sensor.synology_download_station_active_downloads` | Number of downloading tasks. Attributes: `paused`, `seeding`, `finished`, `error`, `total` counts, a `tasks` list, `latest_completed` and a `completed` list (last 24 h, newest first, max 10) |
| `sensor.synology_download_station_overall_progress` | Size-weighted progress % of queued tasks, unknown when idle |
| `sensor.synology_download_station_latest_completed` | Title of the most recently completed download. Attributes: `completed_at`, `size` |
| `text.synology_download_station_add_download` | Submit box: paste a link to start a download |

Each item in the `tasks` attribute:

```yaml
id: dbid_123
title: ubuntu-24.04.iso
type: bt
status: downloading
size: 6114656256
downloaded: 3057328128
speed_download: 12582912
speed_upload: 0
progress: 50.0
eta: 243
completed_time: 0
```

## Dashboard card

The integration bundles a compact card and registers it automatically — no
resource setup needed. Add it from the card picker (*Synology Download
Card*) or with YAML:

```yaml
type: custom:syno-download-card
```

It shows every active/paused download with a progress bar, speed and ETA,
the downloads completed in the last 24 h (3 by default), and an add row:
paste a magnet/URL and press Enter, or use the folder button to upload a
`.torrent` file from the browser.

| Option | Default | Description |
| --- | --- | --- |
| `entity` | `sensor.synology_download_station_active_downloads` | Source sensor |
| `title` | `Downloads` | Card title |
| `show_add` | `true` | Show the magnet/torrent add row |
| `show_completed` | `true` | Show the completed section |
| `completed_count` | `3` | Max completed lines (last 24 h, up to 10 provided) |

## Adding downloads

### From a dashboard

Add the text entity to any card and paste a magnet or torrent URL. The state
box is limited to 255 characters — for very long magnet links (many
trackers), use the action below.

### Action

```yaml
action: synology_download_station.add_task
data:
  url: "magnet:?xt=urn:btih:c9e15763f722f23e98a29decdfae341b98d53056"
  destination: downloads
```

`destination` is optional (shared folder path on the NAS). With several NAS
configured, add `config_entry_id`.

### Torrent file upload

The card's folder button uploads a `.torrent` picked in the browser. From
automations, use the `add_torrent` action with either base64 content or a
file path readable by Home Assistant:

```yaml
action: synology_download_station.add_torrent
data:
  file_path: /config/torrents/ubuntu.torrent
```

Paths outside `/config` must be listed in `allowlist_external_dirs`.

## Dashboard examples

Compact indicator plus submit box (core cards only):

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - entity: text.synology_download_station_add_download
      - entity: sensor.synology_download_station_download_speed
        name: Speed
  - type: gauge
    entity: sensor.synology_download_station_overall_progress
    name: Downloads
    min: 0
    max: 100
```

Per-task progress bars with a markdown card:

```yaml
type: markdown
title: Download Station
content: |
  {% set tasks = state_attr('sensor.synology_download_station_active_downloads', 'tasks') or [] %}
  {% if not tasks %}
  Nothing downloading 🎉
  {% endif %}
  {% for t in tasks %}
  {% set p = t.progress or 0 %}
  {% set filled = ((p / 5) | round(0, 'floor')) | int %}
  **{{ t.title | truncate(45) }}**{% if t.status == 'paused' %} ⏸{% endif %}
  `{{ '█' * filled }}{{ '░' * (20 - filled) }}` {{ p | round(0) }}% · {{ t.speed_download | filesizeformat }}/s{% if t.eta %} · ~{{ (t.eta / 60) | round(0, 'ceil') | int }} min left{% endif %}
  {% endfor %}
```

Notify when a download finishes:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.synology_download_station_active_downloads
    attribute: finished
conditions:
  - condition: template
    value_template: >-
      {{ trigger.to_state.attributes.finished | int(0) >
         trigger.from_state.attributes.finished | int(0) }}
actions:
  - action: notify.mobile_app_your_phone
    data:
      message: A download finished on the NAS
```

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install homeassistant py-synologydsm-api pytest
.venv/bin/pytest tests
```

The card is TypeScript ([card-src/card.ts](card-src/card.ts)), compiled to
`custom_components/synology_download_station/frontend/card.js` (committed):

```bash
npm install
npm run build:card
```
