from machine import UART, Pin
import time

uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1), bits=8, parity=None, stop=1)

print("UART loopback test: connect GP0 <-> GP1, then reset.")

counter = 0
while True:
    msg = "PING{}\n".format(counter)
    uart.write(msg)
    time.sleep_ms(50)
    data = uart.read()
    if data:
        print("RX:", data)
    else:
        print("RX: <none>")
    counter += 1
    time.sleep_ms(500)
