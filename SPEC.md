# Pico W ↔ Elecraft KX2/KX3 (MicroPython) — Project Spec

## Goal
Create a **MicroPython** application for **Raspberry Pi Pico W / WH** that:

1. Connects to a known Wi-Fi network after power-on.
2. Communicates with an **Elecraft KX2 or KX3** via CAT.
3. Every 2 seconds reads **frequency** and **mode** from the radio.
4. Sends the data to a server using an HTTPS **POST** request with a JSON body and **Bearer** authorization.
5. If HTTPS fails, retries once using HTTP.

Example request:

```http
POST /radio-upload.php HTTP/1.1
Authorization: Bearer <HTTP_API_KEY>
Content-Type: application/json

{"freq":"7025.00","mode":"CW"}
```

Keep it **KISS**: simple state machine, minimal dependencies, and straightforward logging.

---

## Hardware

### Current hardware setup
- Board: **Raspberry Pi Pico W / WH**
- Radio: **Elecraft KX2 or KX3**
- RS232 interface: **Waveshare Pico-2CH-RS232**
- Power regulator: **7805** (`TO-220`) to derive 5 V for the Pico side from the shared radio power supply
- Status LEDs:
  - `GP10` → `LED_WIFI`
  - `GP11` → `LED_CAT`
  - `GP12` → `LED_HTTP`
  - each LED uses a **560 ohm** series resistor

### Signal path
- Pico internal UART is **3.3 V TTL**
- External radio CAT connection is **RS232** through the Waveshare board
- UART pins:
  - `GP0` = `UART0 TX`
  - `GP1` = `UART0 RX`

### Grounding
- Pico/Waveshare, regulator, and radio share a common ground

---

## LED behavior
Use non-blocking timing based on `time.ticks_ms()` and avoid long sleeps.

- Blink rate **4 Hz**: period 250 ms, toggle every **125 ms**
- `LED_WIFI`
  - fast blink while scanning/connecting Wi-Fi
  - solid ON once Wi-Fi is connected
- `LED_CAT`
  - fast blink while trying to establish CAT communication
  - solid ON once CAT is working
- `LED_HTTP`
  - **1 blink** on successful HTTP request (2xx)
  - **2 blinks** on HTTP error (exception or non-2xx status)
  - blink timing: 100 ms ON, 100 ms OFF

---

## Wi-Fi logic
The source code contains a list of known networks:

```python
KNOWN_WIFIS = [
    {"ssid": "...", "password": "..."},
]
```

On boot:
- enable STA mode
- scan for nearby SSIDs
- pick the **first** SSID from `KNOWN_WIFIS` that appears in scan results
- connect using SSID + password
- if no known Wi-Fi can be connected, wait **2 seconds** and retry

After successful connection:
- log the assigned IP address
- keep `LED_WIFI` solid ON

If Wi-Fi disconnects during runtime:
- return to Wi-Fi connect state and reconnect automatically

---

## Radio CAT logic

### UART settings
- Use **9600 8N1** (configured in `config.py`)

Example:

```python
from machine import UART, Pin
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), bits=8, parity=None, stop=1)
```

### CAT commands
Use simple query commands and parse semicolon-terminated replies:

- `FA;` → frequency in **Hz** (`FAxxxxxxxxxxx;`)
- `MD;` → mode code (`MDn;`)

Mode mapping:
- `1=LSB`
- `2=USB`
- `3=CW`
- `4=FM`
- `5=AM`
- `6=DATA`
- `7=CW-REV` → send as `CW`
- `9=DATA-REV` → send as `DATA`

### Establishing CAT connectivity
After Wi-Fi is connected:
- enter `CAT_CONNECT` state
- `LED_CAT` blinks at 4 Hz
- consider CAT “connected” only after a probe sequence succeeds:
  - valid `FA;`
  - valid `MD;`
  - second valid `FA;`
  - first and second `FA;` must not differ by more than 50 kHz
- if the probe fails, wait **2 seconds** and retry forever

---

## Periodic read + HTTP send
In `RUN` state, every **2 seconds**:

1. Query the radio:
   - `FA;` → `freq_hz`
   - `MD;` → `mode_code` → map to normalized mode string

2. Build JSON payload:
   - `freq` is **kHz with two decimals**
   - `mode` is the normalized CAT mode string

```json
{
  "freq": "7025.00",
  "mode": "CW"
}
```

3. Build HTTP headers:

```text
Authorization: Bearer <HTTP_API_KEY>
Content-Type: application/json
```

4. Send HTTPS `POST` using `urequests`
   - on failure, retry once using `HTTP_FALLBACK_URL`
   - on success (2xx), blink `LED_HTTP` once
   - on failure, blink `LED_HTTP` twice
   - always log status/errors and continue running

---

## Server-side example behavior
The `web/` examples demonstrate a minimal server-side receiver:

- `radio-upload.php`
  - accepts `POST`
  - checks `Authorization: Bearer ...`
  - reads JSON from request body
  - requires `freq` and `mode`
  - adds `last_seen = time()` on the server side
  - stores the resulting JSON into `radio.json`
- `radio-json.php`
  - returns the latest stored JSON
  - returns a default JSON object if no file exists yet

The `last_seen` field is intentionally generated on the server, not by the Pico.

---

## Structure / files
- `config.py`
  - Wi-Fi list, URLs, API key, pins, UART parameters, intervals
- `main.py`
  - state machine, LED handling, Wi-Fi logic, CAT polling, HTTP POST sending
- `kx2.py`
  - CAT helpers for `FA;` and `MD;`
- `web/radio-upload.php`
  - sample authenticated JSON upload endpoint
- `web/radio-json.php`
  - sample JSON readback endpoint

---

## Robustness requirements
The program runs forever and recovers automatically:

- Wi-Fi drop → return to Wi-Fi reconnect state
- CAT read errors/timeouts → return to CAT reconnect state
- HTTP errors → log + continue main loop

---

## Debug logging
Debug logging is controlled by configuration flags:

- `DEBUG = False` by default for unattended operation
- `DEBUG = True` enables normal logs
- `DEBUG_CAT_VERBOSE = True` enables raw CAT command/response logging

Normal log examples:
- `[WIFI] scanning`
- `[WIFI] connecting ssid=...`
- `[WIFI] ip=...`
- `[CAT] connected`
- `[CAT] connect failed`
- `[CAT] read FA failed`
- `[CAT] read MD failed`
- `[HTTP] post url=...`
- `[HTTP] payload=...`
- `[HTTP] status=...`
- `[HTTP] error=...`

Verbose CAT log examples:
- `[CAT] cmd=FA;`
- `[CAT] resp=FA...;`
- `[CAT] skip frame=...`

Standalone note:
- on Pico without Thonny attached, excessive USB `print()` traffic can affect timing
- keep `DEBUG = False` for normal unattended operation

---

## Definition of done
- On boot:
  - `LED_WIFI` blinks until Wi-Fi is connected, then stays ON
  - `LED_CAT` blinks until CAT works, then stays ON
- Every 2 seconds:
  - reads frequency and mode from KX2/KX3
  - sends authenticated JSON `POST` request
  - `LED_HTTP` blinks once on success, twice on error
- The system self-recovers from Wi-Fi, CAT, and HTTP failures without reboot
