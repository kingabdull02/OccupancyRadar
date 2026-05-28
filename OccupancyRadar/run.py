import time
import subprocess
import sys
import os
import shutil

BOARD_FQBN = "esp32:esp32:esp32" #Replace with board's fully-qualified board name
PORT = "COM5" #Replace with the serial port of your computer and ESP32 connectio 
UPLOAD_WAIT = 3

def _run_cmd(cmd, check=True):
    print("Running:", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def upload_sketch_with_arduino_cli(sketch_path: str) -> bool:
    """
    Compile and upload an Arduino sketch using "arduino-cli".

    Returns True on success, False otherwise. Requires "arduino-cli" to be
    installed and the correct "BOARD_FQBN" and "PORT" set above.
    """
    cli = shutil.which("arduino-cli") or shutil.which("arduino-cli.exe")
    if not cli:
        return False

    #Ensure sketch path exists
    if not os.path.isdir(sketch_path):
        print(f"Sketch directory not found: {sketch_path}")
        return False

    try:
        _run_cmd([cli, "compile", "--fqbn", BOARD_FQBN, sketch_path])
        _run_cmd([cli, "upload", "-p", PORT, "--fqbn", BOARD_FQBN, sketch_path])
    except subprocess.CalledProcessError as e:
        print("Upload failed:", e)
        return False

    return True

if __name__ == "__main__":
    #compute the sketch path relative to this script, change if your layout differs
    base = os.path.dirname(__file__)
    sketch_path = os.path.join(base, "..", "sketch")
    sketch_path = os.path.normpath(sketch_path)

    try:
        uploaded = upload_sketch_with_arduino_cli(sketch_path)
        if uploaded:
            print("Upload succeeded, waiting for board to reboot")
            time.sleep(UPLOAD_WAIT)

        #Run the existing helpers with the active python executable
        subprocess.run([sys.executable, "time.py"])
        time.sleep(UPLOAD_WAIT)
        subprocess.run([sys.executable, "csv.py"])
    except KeyboardInterrupt:
        print("Stopped by user.")