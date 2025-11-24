import argparse, sys, time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    print("pyserial not installed. Run:  pip3 install pyserial")
    sys.exit(1)

def pick_port(prefer=None):
    ports = list(list_ports.comports())
    if prefer:
        for p in ports:
            if prefer in (p.device, p.description):
                return p.device
    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["cp210", "ch340", "usb serial", "ftdi", "uart", "esp"]):
            return p.device
    return ports[0].device if ports else None

def send_cmd(ser, cmd, expect=None, timeout=1.5):
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode("utf-8"))
    ser.flush()
    t0 = time.time()
    lines = []
    while time.time() - t0 < timeout:
        if ser.in_waiting:
            line = ser.readline().decode("utf-8", "ignore").strip()
            if line:
                lines.append(line)
                if expect and expect in line:
                    break
        time.sleep(0.01)
    return lines

def interactive(ser):
    print("Connected. Type one of:")
    print("  L0..L10  - set level (0=stop, 10=100%)")
    print("  S <pct>  - set exact percent (0..100)")
    print("  G        - get current level")
    print("  R        - read RPM")
    print("  H        - help")
    print("  r        - release (servo drop)")
    print("  Q        - quit")
    try:
        while True:
            cmd = input("> ").strip()
            if not cmd: 
                continue
            if cmd.upper() == 'Q':
                break
            lines = send_cmd(ser, cmd)
            print("\n".join(lines) if lines else "(no response)")
    except KeyboardInterrupt:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="Serial port (e.g., /dev/tty.usbserial-*)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--level", type=int, help="Set level 0..10 (0=stop)")
    ap.add_argument("--percent", type=int, help="Set percent 0..100")
    ap.add_argument("--rpm", action="store_true", help="Read RPM")
    args = ap.parse_args()

    port = args.port or pick_port()
    if not port:
        print("No serial port found. Plug in the ESP32 via USB and try again.")
        sys.exit(1)

    with serial.Serial(port, args.baud, timeout=0.1) as ser:
        time.sleep(0.5)
        ser.reset_input_buffer()

        if args.level is not None:
            if not (0 <= args.level <= 10):
                print("Level must be 0..10")
                sys.exit(2)
            lines = send_cmd(ser, f"L{args.level}")
            print("\n".join(lines)); return

        if args.percent is not None:
            p = max(0, min(100, int(args.percent)))
            lines = send_cmd(ser, f"S {p}")
            print("\n".join(lines)); return

        if args.rpm:
            lines = send_cmd(ser, "R")
            print("\n".join(lines)); return

        lines = send_cmd(ser, "G")
        if lines: print("\n".join(lines))
        interactive(ser)

if __name__ == "__main__":
    main()
