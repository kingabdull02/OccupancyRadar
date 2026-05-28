import sysconfig
import sys
import serial
import datetime
import time
import importlib
import os

HEADER = ["timestamp", "raw"]
FRAME_HEADER = [0xAA, 0xBF, 0x10, 0x14]
FRAME_TAIL   = [0xFD, 0xFC, 0xFB, 0xFA]

def _import_stdlib(name):
    stdlib_path = sysconfig.get_paths().get("stdlib")
    if not stdlib_path or not os.path.isdir(stdlib_path):
        raise ImportError("Cannot locate stdlib path")
    script_dir = os.path.abspath(os.path.dirname(__file__))
    removed = False
    try:
        if script_dir in sys.path:
            sys.path.remove(script_dir)
            removed = True
        module = importlib.import_module(name)
    finally:
        if removed:
            sys.path.insert(0, script_dir)
    return module

csv = _import_stdlib("csv")

DATA_DIRECTORY = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIRECTORY, exist_ok=True)

COM_PORT = "COM5" #set to your ESP32 port
BAUD_RATE = 115200

def _today_filepath():
    date_str = datetime.date.today().isoformat()
    candidate = os.path.join(DATA_DIRECTORY, f"{date_str}.csv")
    suffix = 1
    while os.path.exists(candidate):
        candidate = os.path.join(DATA_DIRECTORY, f"{date_str}-{suffix}.csv")
        suffix += 1
    return candidate

def _ensure_header(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, mode="w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)

def _now_ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def _parse_csv():
    ser = serial.Serial()
    ser.port = COM_PORT
    ser.baudrate = BAUD_RATE
    ser.timeout = 2
    ser.rtscts = False
    ser.dsrdtr = False
    try: ser.dtr = False
    except Exception: pass
    try: ser.rts = False
    except Exception: pass

    ser.open()
    time.sleep(0.5)
    try:
        ser.reset_input_buffer()
    except Exception:
        try:
            ser.flushInput()
        except Exception:
            while ser.in_waiting:
                ser.readline()

    path = _today_filepath()
    _ensure_header(path)

    print(f"Listening on {COM_PORT} @ {BAUD_RATE}. Writing to {path}. Ctrl+C to stop.")

    #Frame accumulator (for framed payloads)
    collecting = False
    frame_bytes = []

    try:
        with open(path, mode="a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            while True:
                #Read raw bytes, try to reconstruct frames if present
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting)
                    #Convert to list of ints for pattern search
                    ints = list(chunk)
                    i = 0
                    while i < len(ints):
                        b = ints[i]

                        #Detect header start
                        if not collecting:
                            #Try to align on header sequence
                            if i + 3 < len(ints) and ints[i:i+4] == FRAME_HEADER:
                                collecting = True
                                frame_bytes = []
                                i += 4
                                continue

                        if collecting:
                            #Append until tail detected
                            if i + 3 < len(ints) and ints[i:i+4] == FRAME_TAIL:
                                #Emit CSV row: timestamp, raw hex (header..tail included for traceability)
                                ts = _now_ts()
                                payload_hex = " ".join(
                                    ["{:02X}".format(x) for x in FRAME_HEADER + frame_bytes + FRAME_TAIL]
                                )
                                w.writerow([ts, payload_hex])
                                f.flush()
                                print(f"{ts}, {payload_hex}")
                                collecting = False
                                frame_bytes = []
                                i += 4
                                continue
                            else:
                                frame_bytes.append(b)
                                i += 1
                                continue

                        i += 1

                #Also handle line-based prints (raw single-line hex dumps)
                line_bytes = ser.readline()
                if line_bytes:
                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    #If the ESP32 already prints "timestamp, raw", pass through
                    if "," in line and line[:4].isdigit():
                        #Normalize optional space after comma
                        ts_raw = line.split(",", 1)
                        ts = ts_raw[0].strip()
                        raw = ts_raw[1].strip()
                        w.writerow([ts, raw])
                        f.flush()
                        print(f"{ts}, {raw}")
                    else:
                        w.writerow(["", line])
                        f.flush()
                        print(line)

                ser.timeout = 2

    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        try: ser.close()
        except Exception: pass

if __name__ == "__main__":
    _parse_csv()