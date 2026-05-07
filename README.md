# Trakt iCal Bridge

A tiny self-hosted bridge that turns your Trakt upcoming show calendar into a private iCalendar feed.

It connects to Trakt with OAuth, reads your personal upcoming shows calendar, labels premieres/finales when available, and serves a private `.ics` URL for Home Assistant and iOS.

## OAuth Callback

Use the bridge callback URL in your Trakt API app, not Home Assistant's own OAuth callback:

```text
http://homeassistant.local:8765/auth/callback
```

## Install On Raspberry Pi

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
cd /opt
sudo git clone https://github.com/hindsight2021/trakt-ical-bridge.git
sudo chown -R "$USER":"$USER" /opt/trakt-ical-bridge
cd /opt/trakt-ical-bridge
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set your Trakt `Client ID`, `Client Secret`, and a long random `CALENDAR_TOKEN` in `.env`.

Run manually:

```bash
set -a
. ./.env
set +a
python -m trakt_ical_bridge.app
```

Then open:

```text
http://homeassistant.local:8765/setup
```

## systemd

A sample service is in `deploy/trakt-ical-bridge.service`.

## Calendar URL

```text
http://homeassistant.local:8765/calendar.ics?token=YOUR_TOKEN
```

Use that with Home Assistant Remote Calendar or as an iOS subscribed calendar.
