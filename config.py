KNOWN_WIFIS = [
    {"ssid": "SSID1", "password": "1234567"},
    {"ssid": "SSID2", "password": "7654321"},
]

HTTP_BASE_URL = "https://example.com/radio-upload.php"
HTTP_FALLBACK_URL = "http://example.com/radio-upload.php"
HTTP_API_KEY = "change-me"

UART_ID = 0
UART_BAUDRATE = 9600
UART_TX_PIN = 0
UART_RX_PIN = 1

LED_WIFI_PIN = 10
LED_CAT_PIN = 11
LED_HTTP_PIN = 12

WIFI_RETRY_MS = 2000
WIFI_CONNECT_TIMEOUT_MS = 10000

CAT_RETRY_MS = 2000
CAT_CMD_TIMEOUT_MS = 1000

POLL_INTERVAL_MS = 2000

FAST_BLINK_TOGGLE_MS = 125
HTTP_BLINK_ON_MS = 100
HTTP_BLINK_OFF_MS = 100

# Disable verbose USB serial logging by default for standalone boot reliability.
DEBUG = False

# Extra CAT command/response logging (very noisy). Use only during UART debugging.
DEBUG_CAT_VERBOSE = True
