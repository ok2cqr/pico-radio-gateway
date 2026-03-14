import time

_logger = print
_verbose = False


def set_logger(logger):
    global _logger
    _logger = logger


def set_verbose(enabled):
    global _verbose
    _verbose = bool(enabled)


def _log(msg):
    if _logger:
        print(msg)
        _logger(msg)


def _vlog(msg):
    if _verbose:
        _log(msg)


def _drain_uart(uart):
    drained = 0
    while uart.any():
        chunk = uart.read()
        if not chunk:
            break
        drained += len(chunk)
    if drained:
        _vlog("[CAT] drained {} stale bytes".format(drained))


def _read_frame_until_semicolon(uart, deadline_ms, tick_fn=None):
    buf = bytearray()
    while time.ticks_diff(deadline_ms, time.ticks_ms()) > 0:
        if tick_fn:
            tick_fn()
        if uart.any():
            b = uart.read(1)
            if b:
                buf.extend(b)
                if b == b";":
                    try:
                        return buf.decode()
                    except Exception:
                        return None
        else:
            time.sleep_ms(5)
    return None


def _read_until_semicolon(uart, timeout_ms, expected_prefix=None, tick_fn=None):
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    saw_frame = False
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        frame = _read_frame_until_semicolon(uart, deadline, tick_fn=tick_fn)
        if not frame:
            break
        saw_frame = True
        if expected_prefix and not frame.startswith(expected_prefix):
            _vlog("[CAT] skip frame={}".format(frame))
            continue
        return frame
    if not saw_frame:
        _log("[CAT] timeout no data")
    else:
        _log("[CAT] timeout no matching frame")
    return None


def send_cmd(uart, cmd, timeout_ms, tick_fn=None):
    _drain_uart(uart)
    _vlog("[CAT] cmd={}".format(cmd))
    uart.write(cmd)
    resp = _read_until_semicolon(
        uart, timeout_ms, expected_prefix=cmd[:2], tick_fn=tick_fn
    )
    _vlog("[CAT] resp={}".format(resp))
    return resp


def get_fa(uart, timeout_ms, tick_fn=None):
    resp = send_cmd(uart, "FA;", timeout_ms, tick_fn=tick_fn)
    if not resp or not resp.startswith("FA") or not resp.endswith(";"):
        return None
    digits = resp[2:-1]
    if len(digits) != 11 or not digits.isdigit():
        return None
    return int(digits)


def get_md(uart, timeout_ms, tick_fn=None):
    resp = send_cmd(uart, "MD;", timeout_ms, tick_fn=tick_fn)
    if not resp or not resp.startswith("MD") or not resp.endswith(";"):
        return None
    code = resp[2:-1]
    if not code.isdigit():
        return None
    value = int(code)
    if value not in (1, 2, 3, 4, 5, 6, 7, 9):
        return None
    return value


def get_po(uart, timeout_ms, tick_fn=None):
    resp = send_cmd(uart, "PO;", timeout_ms, tick_fn=tick_fn)
    if not resp or not resp.startswith("PO") or not resp.endswith(";"):
        return None
    digits = resp[2:-1]
    if not digits.isdigit():
        return None
    nnn = int(digits)
    if nnn <= 100:
        return nnn / 10.0
    return float(nnn)


def mode_code_to_string(code):
    mapping = {
        1: "LSB",
        2: "USB",
        3: "CW",
        4: "FM",
        5: "AM",
        6: "DATA",
        7: "CW",
        9: "DATA",
    }
    return mapping.get(code, "UNK")
