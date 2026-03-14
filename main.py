import time

import network
from machine import Pin, UART

import config
import kx2
try:
    import ujson as json
except ImportError:
    import json

try:
    import urequests as requests
except ImportError:
    import urequests as requests

DEBUG = getattr(config, "DEBUG", False)


def _log(msg):
    if DEBUG:
        print(msg)


class BlinkLed:
    def __init__(self, pin, toggle_ms):
        self.pin = pin
        self.toggle_ms = toggle_ms
        self.mode = "off"
        self.state = 0
        self.next_toggle = time.ticks_ms()

    def set_on(self):
        self.mode = "on"
        self.state = 1
        self.pin.value(1)

    def set_off(self):
        self.mode = "off"
        self.state = 0
        self.pin.value(0)

    def set_blink(self):
        if self.mode == "blink":
            return
        self.mode = "blink"
        self.state = 1
        self.pin.value(1)
        self.next_toggle = time.ticks_add(time.ticks_ms(), self.toggle_ms)

    def update(self):
        if self.mode != "blink":
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.next_toggle) >= 0:
            self.state ^= 1
            self.pin.value(self.state)
            self.next_toggle = time.ticks_add(now, self.toggle_ms)


class HttpBlinker:
    def __init__(self, pin, on_ms, off_ms):
        self.pin = pin
        self.on_ms = on_ms
        self.off_ms = off_ms
        self.remaining_toggles = 0
        self.state = 0
        self.next_change = time.ticks_ms()

    def trigger(self, count):
        if count <= 0:
            return
        self.remaining_toggles = count * 2
        self.state = 1
        self.pin.value(1)
        self.next_change = time.ticks_add(time.ticks_ms(), self.on_ms)

    def update(self):
        if self.remaining_toggles <= 0:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.next_change) >= 0:
            self.state ^= 1
            self.pin.value(self.state)
            self.remaining_toggles -= 1
            if self.remaining_toggles <= 0:
                self.pin.value(0)
                self.state = 0
                return
            delay = self.on_ms if self.state else self.off_ms
            self.next_change = time.ticks_add(now, delay)


def _scan_for_known(wlan, known_wifis):
    _log("[WIFI] scanning")
    scan = wlan.scan()
    available = set()
    for item in scan:
        ssid = item[0]
        if isinstance(ssid, bytes):
            ssid = ssid.decode()
        available.add(ssid)
    for entry in known_wifis:
        if entry["ssid"] in available:
            return entry
    return None


def _connect_wifi(wlan, led_wifi):
    wlan.active(True)
    entry = _scan_for_known(wlan, config.KNOWN_WIFIS)
    if not entry:
        _log("[WIFI] no known SSID found")
        return False
    ssid = entry["ssid"]
    password = entry["password"]
    _log("[WIFI] connecting ssid={}".format(ssid))
    wlan.connect(ssid, password)
    start = time.ticks_ms()
    while not wlan.isconnected():
        led_wifi.update()
        if time.ticks_diff(time.ticks_ms(), start) > config.WIFI_CONNECT_TIMEOUT_MS:
            _log("[WIFI] connect timeout")
            return False
        time.sleep_ms(50)
    _log("[WIFI] ip={}".format(wlan.ifconfig()[0]))
    return True


def _build_payload(freq_hz, mode):
    return {
        "freq": "{:.2f}".format(freq_hz / 1000.0),
        "mode": mode,
    }


def _build_headers():
    return {
        "Authorization": "Bearer {}".format(config.HTTP_API_KEY),
        "Content-Type": "application/json",
    }


def _valid_freq_hz(freq_hz):
    return isinstance(freq_hz, int) and 100000 <= freq_hz <= 60000000


def _probe_cat(uart, tick_fn):
    freq1 = kx2.get_fa(uart, config.CAT_CMD_TIMEOUT_MS, tick_fn=tick_fn)
    if not _valid_freq_hz(freq1):
        _log("[CAT] probe invalid freq1={}".format(freq1))
        return False

    mode_code = kx2.get_md(uart, config.CAT_CMD_TIMEOUT_MS, tick_fn=tick_fn)
    if mode_code is None:
        _log("[CAT] probe invalid mode={}".format(mode_code))
        return False

    # Confirm we are not latching onto a random/echo artifact by re-reading FA.
    time.sleep_ms(30)
    freq2 = kx2.get_fa(uart, config.CAT_CMD_TIMEOUT_MS, tick_fn=tick_fn)
    if not _valid_freq_hz(freq2):
        _log("[CAT] probe invalid freq2={}".format(freq2))
        return False

    if abs(freq2 - freq1) > 50000:
        _log("[CAT] probe unstable freq1={} freq2={}".format(freq1, freq2))
        return False

    _log("[CAT] probe ok freq={} mode={}".format(freq2, mode_code))
    return True


def main():
    kx2.set_logger(_log)
    kx2.set_verbose(getattr(config, "DEBUG_CAT_VERBOSE", False))

    led_wifi = BlinkLed(Pin(config.LED_WIFI_PIN, Pin.OUT), config.FAST_BLINK_TOGGLE_MS)
    led_cat = BlinkLed(Pin(config.LED_CAT_PIN, Pin.OUT), config.FAST_BLINK_TOGGLE_MS)
    http_blinker = HttpBlinker(
        Pin(config.LED_HTTP_PIN, Pin.OUT),
        config.HTTP_BLINK_ON_MS,
        config.HTTP_BLINK_OFF_MS,
    )

    uart = UART(
        config.UART_ID,
        baudrate=config.UART_BAUDRATE,
        tx=Pin(config.UART_TX_PIN),
        rx=Pin(config.UART_RX_PIN),
        bits=8,
        parity=None,
        stop=1,
    )

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    state = "WIFI_CONNECT"
    next_wifi_retry = time.ticks_ms()
    next_cat_retry = time.ticks_ms()
    next_poll = time.ticks_ms()

    def _service_leds():
        led_wifi.update()
        led_cat.update()
        http_blinker.update()

    try:
        while True:
            led_wifi.update()
            led_cat.update()
            http_blinker.update()

            now = time.ticks_ms()

            if state == "WIFI_CONNECT":
                led_wifi.set_blink()
                if time.ticks_diff(now, next_wifi_retry) >= 0:
                    if _connect_wifi(wlan, led_wifi):
                        led_wifi.set_on()
                        state = "CAT_CONNECT"
                        next_cat_retry = now
                    else:
                        next_wifi_retry = time.ticks_add(now, config.WIFI_RETRY_MS)

            elif state == "CAT_CONNECT":
                if not wlan.isconnected():
                    _log("[WIFI] disconnected")
                    state = "WIFI_CONNECT"
                    continue
                led_cat.set_blink()
                if time.ticks_diff(now, next_cat_retry) >= 0:
                    if _probe_cat(uart, _service_leds):
                        _log("[CAT] connected")
                        led_cat.set_on()
                        state = "RUN"
                        next_poll = now
                    else:
                        _log("[CAT] connect failed")
                        next_cat_retry = time.ticks_add(time.ticks_ms(), config.CAT_RETRY_MS)

            elif state == "RUN":
                if not wlan.isconnected():
                    _log("[WIFI] disconnected")
                    state = "WIFI_CONNECT"
                    continue

                if time.ticks_diff(now, next_poll) >= 0:
                    next_poll = time.ticks_add(now, config.POLL_INTERVAL_MS)

                    freq = kx2.get_fa(uart, config.CAT_CMD_TIMEOUT_MS, tick_fn=_service_leds)
                    if freq is None:
                        _log("[CAT] read FA failed")
                        state = "CAT_CONNECT"
                        continue
                    _log("[CAT] parsed freq={}".format(freq))

                    mode_code = kx2.get_md(
                        uart, config.CAT_CMD_TIMEOUT_MS, tick_fn=_service_leds
                    )
                    if mode_code is None:
                        _log("[CAT] read MD failed")
                        state = "CAT_CONNECT"
                        continue
                    mode = kx2.mode_code_to_string(mode_code)
                    _log("[CAT] parsed mode={}".format(mode))

                    payload = _build_payload(freq, mode)
                    body = json.dumps(payload)
                    headers = _build_headers()
                    _log("[HTTP] post url={}".format(config.HTTP_BASE_URL))
                    _log("[HTTP] payload={}".format(payload))
                    try:
                        resp = requests.post(
                            config.HTTP_BASE_URL, data=body, headers=headers
                        )
                        status = resp.status_code
                        resp.close()
                        _log("[HTTP] status={}".format(status))
                        if 200 <= status < 300:
                            http_blinker.trigger(1)
                        else:
                            http_blinker.trigger(2)
                    except Exception as exc:
                        _log("[HTTP] error={}".format(exc))
                        fallback_url = getattr(config, "HTTP_FALLBACK_URL", None)
                        if fallback_url:
                            _log("[HTTP] fallback post url={}".format(fallback_url))
                            try:
                                resp = requests.post(
                                    fallback_url, data=body, headers=headers
                                )
                                status = resp.status_code
                                resp.close()
                                _log("[HTTP] fallback status={}".format(status))
                                if 200 <= status < 300:
                                    http_blinker.trigger(1)
                                else:
                                    http_blinker.trigger(2)
                            except Exception as exc2:
                                _log("[HTTP] fallback error={}".format(exc2))
                                http_blinker.trigger(2)
                        else:
                            http_blinker.trigger(2)

            time.sleep_ms(10)
    except KeyboardInterrupt:
        _log("[SYS] stopped")
    finally:
        led_wifi.set_off()
        led_cat.set_off()
        http_blinker.pin.value(0)
        try:
            wlan.disconnect()
        except Exception:
            pass
        wlan.active(False)


main()
