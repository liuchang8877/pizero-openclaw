# pizero-openclaw

A voice-controlled AI assistant built on a Raspberry Pi Zero W with a [PiSugar WhisPlay board](https://www.pisugar.com). Press a button, speak, and get a streamed response on the LCD — powered by [OpenClaw](https://openclaw.ai) and OpenAI speech-to-text.

## How it works

```
Button press → Record audio → Transcribe (OpenAI) → Stream LLM response (OpenClaw) → Display on LCD
                                                                                    → Speak aloud (gateway TTS, optional)
```

1. **Press & hold** the button to record your voice via ALSA
2. **Release** — the WAV is sent to OpenAI for transcription (~0.7s)
3. The transcript (with conversation history) is streamed to an **OpenClaw gateway** for a response
4. Text streams onto the **LCD** in real time with pixel-accurate word wrapping
5. Optionally **speaks the response** via a TTS endpoint as sentences complete
6. The idle screen shows a **clock, date, battery %, and WiFi status**

The device maintains **conversation memory** across exchanges and includes a **silence gate** to skip empty recordings.

## Hardware

- **Raspberry Pi Zero 2 W** (or Pi Zero W)
- **[PiSugar WhisPlay board](https://www.pisugar.com)** — 1.54" LCD (240x240), push-to-talk button, LED, speaker, microphone
- **PiSugar battery** (optional) — shows charge level on screen

## Setup

### Prerequisites

- Raspberry Pi OS (Bookworm or later)
- Python 3.11+
- An [OpenAI API key](https://platform.openai.com/api-keys) for speech-to-text
- An [OpenClaw](https://openclaw.ai) gateway running somewhere accessible on your network
- Optional: a TTS endpoint exposed by the OpenClaw gateway or another machine on your LAN

### Install dependencies

```bash
sudo apt install python3-numpy python3-pil
pip install requests python-dotenv   # or: pip install -r requirements.txt
```

The WhisPlay hardware driver should be installed at `/home/pi/Whisplay/Driver/` per the [PiSugar WhisPlay setup guide](https://github.com/PiSugar/whisplay-ai-chatbot).

### Configure

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
export OPENAI_API_KEY="sk-your-openai-api-key"
export OPENCLAW_TOKEN="your-openclaw-gateway-token"
export OPENCLAW_BASE_URL="http://your-openclaw-host:18789"
export TTS_BASE_URL="http://your-mac-mini:18790"
export TTS_API_TOKEN="your-openclaw-gateway-token"
```

### Run

```bash
python3 main.py
```

Or deploy as a systemd service (see below).

## Configuration

All settings are configured via environment variables (loaded from `.env`):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(required)_ | OpenAI API key for transcription |
| `OPENCLAW_TOKEN` | _(required)_ | Auth token for the OpenClaw gateway |
| `OPENCLAW_BASE_URL` | `https://...` | OpenClaw gateway URL |
| `TTS_BASE_URL` | `OPENCLAW_BASE_URL` | Base URL for the TTS endpoint |
| `TTS_API_TOKEN` | `OPENCLAW_TOKEN` | Auth token for the TTS endpoint |
| `TTS_HTTP_PATH` | `/v1/audio/speech` | TTS endpoint path |
| `OPENAI_TRANSCRIBE_MODEL` | `gpt-4o-mini-transcribe` | Speech-to-text model |
| `ENABLE_TTS` | `false` | Speak responses aloud via the configured TTS endpoint |
| `OPENAI_TTS_MODEL` | `tts-1` | TTS model |
| `OPENAI_TTS_VOICE` | `alloy` | TTS voice |
| `OPENAI_TTS_SPEED` | `2.0` | TTS speed (0.25–4.0) |
| `OPENAI_TTS_GAIN_DB` | `9` | Software volume boost in dB |
| `AUDIO_DEVICE` | `plughw:1,0` | ALSA input device |
| `AUDIO_OUTPUT_DEVICE` | `default` | ALSA output device |
| `AUDIO_SAMPLE_RATE` | `16000` | Recording sample rate |
| `LCD_BACKLIGHT` | `70` | Backlight brightness (0–100) |
| `UI_MAX_FPS` | `4` | Max display refresh rate |
| `CONVERSATION_HISTORY_LENGTH` | `5` | Past exchanges to keep for context |
| `SILENCE_RMS_THRESHOLD` | `200` | Audio RMS below this is skipped |

## Deploy with systemd

The included `sync.sh` script deploys to the Pi and sets up the service:

```bash
./sync.sh
```

This rsyncs the project to `pi@pizero.local`, installs the systemd unit, and restarts the service. Logs are available via:

```bash
# On the Pi:
sudo journalctl -u pizero-openclaw -f

# Or check the debug log:
cat /tmp/openclaw.log
```

## Run a macOS `say` TTS service

On the Mac mini:

```bash
export TTS_API_TOKEN="your-openclaw-gateway-token"
export TTS_PORT="18790"
export TTS_VOICE="Tingting"
python3 mac_say_tts_server.py
```

On the Pi:

```bash
export ENABLE_TTS="true"
export TTS_BASE_URL="http://your-mac-mini:18790"
export TTS_API_TOKEN="your-openclaw-gateway-token"
```

The server exposes `POST /v1/audio/speech`, accepts an OpenAI-compatible JSON body, and returns `audio/wav`.

## Project structure

```
main.py               — Entry point and orchestrator
display.py            — LCD rendering (status, responses, idle clock, spinner)
openclaw_client.py    — Streaming HTTP client for the OpenClaw gateway
transcribe_openai.py  — Speech-to-text via OpenAI API
tts_openai.py         — Text-to-speech via gateway endpoint + ALSA playback
mac_say_tts_server.py — Minimal macOS `say` TTS server for `/v1/audio/speech`
record_audio.py       — Audio recording via ALSA arecord
button_ptt.py         — Push-to-talk button state machine
config.py             — Centralized configuration from .env
sync.sh               — Deploy script (rsync + systemd restart)
```

## License

MIT
