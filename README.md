# zap2py — a modern Python tribute to zap2xml

_In honor of the original zap2xml.pl — faithfully reimagined for the modern age._

**zap2py** is a YAML-driven XMLTV grabber orchestrator that supports:
- Multiple lineups per run
- Persistent caching under `cache/<lineup>`
- Tvheadend socket delivery (optional)
- Docker / cron / systemd scheduling
- Optional email notifications (container mode)

## Quick Start (Docker)
```bash
docker compose up -d --build
docker logs zap2py
```

XML files appear on host under `./output/` (mapped to `/tmp` in the container).

## Default Config File Behavior
If you don’t pass a path, `python -m zap2py` uses `./lineups.yaml` automatically.

```bash
python -m zap2py            # uses ./lineups.yaml
python -m zap2py custom.yaml
```

## YAML Configuration
- Anonymous grabs: provide `zip` and `lineup_id`
- Authenticated grabs: provide `user` and `password`
- If both are provided, credentials take priority

```yaml
defaults:
  verbosity: 1
  sleep: 0.5
  use_socket: false
  cache_base: cache

lineups:
  - name: Local OTA
    zip: 40013
    lineup_id: USA-OTA40013-DEFAULT
    outfile: /tmp/localxmltv.xml
```

## Tvheadend Socket Integration (Docker)
Share a volume so both containers see the socket file:

```yaml
volumes:
  tvh_socket:

services:
  tvheadend:
    image: linuxserver/tvheadend
    volumes:
      - tvh_socket:/config/epggrab
  zap2py:
    build: .
    volumes:
      - tvh_socket:/opt/stacks/tvheadend/config/epggrab
```

Then set in YAML:
```yaml
defaults:
  use_socket: true
  socket: /opt/stacks/tvheadend/config/epggrab/xmltv.sock
```

## Standalone Mode (no Tvheadend)
Set `use_socket: false` and use the generated XML files in `./output/`.

## Running Natively (Linux)
```bash
sudo apt install -y python3 python3-pip mailutils socat cron
pip install -e .
python -m zap2py               # uses ./lineups.yaml
# or schedule with cron:
# 17 4 * * * /usr/local/bin/update_epg.sh /etc/epg/lineups.yaml
```

## Systemd Alternative
Create `/etc/systemd/system/zap2py.service` and `.timer` to run `/usr/local/bin/update_epg.sh /etc/epg/lineups.yaml` daily.

## Windows
Tvheadend is Linux-only. On Windows, use Docker Desktop or run natively to generate XML files only.

## Troubleshooting
- Missing socket: ensure both containers share `tvh_socket` and paths match.
- No email: leave `MAIL_TO` unset (silent), or install/configure mailutils.
- File access: map `/tmp` to `./output` in Compose to see XMLs on host.

## License
MIT
