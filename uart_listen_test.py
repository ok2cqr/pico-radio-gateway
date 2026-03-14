from machine import UART, Pin
import time

uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), bits=8, parity=None, stop=1)

print("UART listen test: connect KX2 TX -> Pico GP1, GND->GND. No TX needed.")

last_print = time.ticks_ms()
buf = bytearray()

while True:
    if uart.any():
        data = uart.read()
        if data:
            buf.extend(data)
    now = time.ticks_ms()
    if time.ticks_diff(now, last_print) >= 500:
        if buf:
            try:
                text = buf.decode()
            except Exception:
                text = str(buf)
            print("RX:", text)
            buf = bytearray()
        else:
            print("RX: <none>")
        last_print = now
