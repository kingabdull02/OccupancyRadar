import serial
import datetime
import time

"""
Send the current system time to a serial-connected device.

This module opens a serial connection (default `COM5`) and sends a
SETTIME command in the format expected by the connected device. It
waits briefly for any reply and prints responses to stdout.
"""

COM_PORT = "COM5"  #Change to the COM port used by your device
BAUD_RATE = 115200

def _send_time():
    """
    Send the current datetime to the serial device as a SETTIME command.

    The function opens the serial port, configures control lines to avoid
    resetting the device, sends a single SETTIME command, and then reads
    any immediate replies for up to approximately one second.
    """
    current_dt = datetime.datetime.now()
    #Send milliseconds so the sketch can set RTC with ms precision
    time_command = current_dt.strftime("SETTIME %Y-%m-%d %H:%M:%S.%f\n")[:-4] + "\n"
    sent_ts_ms = current_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    #Open port without asserting modem control lines on open (prevents reset)
    #Pass `dsrdtr=False` to avoid pyserial toggling DTR on open.
    serial_connection = serial.Serial(COM_PORT, BAUD_RATE, timeout=2, dsrdtr=False)
    #Prevent toggling the device's reset line when opening the port
    try:
        serial_connection.rts = False
    except Exception:
        pass
    try:
        serial_connection.setDTR(False)
    except Exception:
        #Older pyserial versions expose `dtr` attribute instead
        try:
            serial_connection.dtr = False
        except Exception:
            pass
    serial_connection.rtscts = False
    serial_connection.dsrdtr = False
    time.sleep(0.5)

    serial_connection.write(time_command.encode("utf-8"))
    print("Sent:", time_command.strip(), "(host clock:", sent_ts_ms, ")")

    #Wait briefly and print any replies
    time.sleep(1)
    while serial_connection.in_waiting:
        reply = serial_connection.readline().decode("utf-8", errors="ignore").strip()
        print("Device replied:", reply)

    serial_connection.close()


if __name__ == "__main__":
    _send_time()