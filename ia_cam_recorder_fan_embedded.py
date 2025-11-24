#!/usr/bin/env python3
import os, sys, time
from datetime import datetime
from typing import Optional
import cv2  # type: ignore

# ============================================
OUTPUT_DIR = "/Users/jerryhu/Library/CloudStorage/OneDrive-WhiteRockChristianAcademy/12/Physics SL/Physics IA/Videos/Trial"
TARGET_FPS = 60.0
FRAME_SIZE = (1080, 1920)
CAM_INDEX = 0

TOTAL_LEVELS = 11
VIDEOS_PER_LEVEL = 3
COUNTDOWN_BEFORE_RECORD = 2.0
RECORD_TOTAL_SECONDS = 5.0
TRIGGER_AFTER_SECONDS = 1.5

SERIAL_PORT: Optional[str] = None
SERIAL_BAUD = 115200

PORT_DESC_KEYWORDS = ("cp210", "ch340", "usb serial", "ftdi", "uart", "esp")
PORT_NAME_HINTS = ("usbserial", "usbmodem", "tty.SLAB", "tty.usb", "wchusb")
# ============================================

class FanController:
    def __init__(self, port: Optional[str], baud: int):
        self._port_req = port
        self._baud = baud
        self._ser = None

    def _pick_port(self) -> Optional[str]:
        try:
            from serial.tools import list_ports  # type: ignore
        except Exception:
            print("pyserial not installed. Run:  pip3 install pyserial", file=sys.stderr)
            return None

        ports = list(list_ports.comports())
        if self._port_req:
            for p in ports:
                if self._port_req in (p.device, p.description):
                    return p.device

        for p in ports:
            desc = (p.description or "").lower()
            if any(k in desc for k in PORT_DESC_KEYWORDS):
                return p.device

        for p in ports:
            name = (p.device or "").lower() + " " + (p.description or "").lower()
            if any(h in name for h in (h.lower() for h in PORT_NAME_HINTS)):
                return p.device

        return ports[0].device if ports else None

    def connect(self) -> bool:
        try:
            import serial  # type: ignore
        except Exception:
            print("pyserial not installed. Run:  pip3 install pyserial", file=sys.stderr)
            return False

        port = self._pick_port()
        if not port:
            print("[FAN] No serial port found. Plug in the ESP32 via USB.")
            return False
        try:
            self._ser = serial.Serial(port, self._baud, timeout=0.1, write_timeout=0.05)
            time.sleep(0.5)
            self._ser.reset_input_buffer()
            print(f"[FAN] Connected on {port} @ {self._baud} baud")
            return True
        except Exception as e:
            print(f"[FAN] Failed opening {port}: {e}")
            self._ser = None
            return False

    def _send_cmd(self, cmd: str, expect: Optional[str] = None, timeout: float = 0.25):
        """Blocking send (short timeout). Use outside the hot recording loop."""
        if not self._ser:
            return []
        try:
            self._ser.reset_input_buffer()
            self._ser.write((cmd.strip() + "\n").encode("utf-8"))
            self._ser.flush()
        except Exception as e:
            print(f"[FAN] Write failed: {e}")
            return []

        t0 = time.time()
        lines = []
        while time.time() - t0 < timeout:
            try:
                if self._ser.in_waiting:
                    line = self._ser.readline().decode("utf-8", "ignore").strip()
                    if line:
                        lines.append(line)
                        if expect and expect in line:
                            break
            except Exception:
                break
            time.sleep(0.005)
        return lines

    def _send_nowait(self, cmd: str):
        """Non-blocking write-only (used during recording to avoid frame drops)."""
        if not self._ser:
            return
        try:
            self._ser.write((cmd.strip() + "\n").encode("utf-8"))
        except Exception as e:
            print(f"[FAN] Write-nowait failed: {e}")

    def set_level(self, level: int):
        level = max(0, min(10, int(level)))
        lines = self._send_cmd(f"L{level}")
        if lines: print("\n".join(f"[FAN] {ln}" for ln in lines))
        print(f"[FAN] Level -> L{level}")

    def drop_ball(self):
        """Write-only 'r' to avoid blocking the capture loop."""
        self._send_nowait("r")
        print("[DROP] r sent") # debug

    def close(self):
        try:
            if self._ser: self._ser.close()
        except Exception:
            pass


def ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def open_camera(index: int, fps: float, size: tuple[int, int]) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
    cap.set(cv2.CAP_PROP_FPS, fps)
    # NOTE: might be ignored by AVFoundation, test with continuity camera first
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera. Try a different CAM_INDEX or check permissions.")
    return cap

def build_writer(path: str, size: tuple[int, int], fps: float) -> cv2.VideoWriter:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter for {path}.")
    return writer

def draw_overlay(frame, text: str, subtext: Optional[str] = None):
    def draw_line(msg: str, y: int):
        cv2.putText(frame, msg, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, msg, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    draw_line(text, 40)
    if subtext:
        draw_line(subtext, 80)

def wait_with_preview(cap: cv2.VideoCapture, window_name: str, seconds: float) -> bool:
    start = time.perf_counter()
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        remaining = max(0.0, seconds - (time.perf_counter() - start))
        draw_overlay(frame, f"Starting in: {remaining:0.1f}s  — press Q to abort")
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q')):
            return False
        if remaining <= 0.0:
            return True

def record_clip(cap: cv2.VideoCapture,
                writer: cv2.VideoWriter,
                window_name: str,
                total_seconds: float,
                trigger_after: float,
                fan: Optional[FanController]) -> bool:
    start = time.perf_counter()
    r_sent = False
    last_frame_time: Optional[float] = None
    smoothed_fps: Optional[float] = None
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        now = time.perf_counter()

        if last_frame_time is not None:
            delta = now - last_frame_time
            if delta > 0:
                instant = 1.0 / delta
                if smoothed_fps is None:
                    smoothed_fps = instant
                else:
                    smoothed_fps = (smoothed_fps * 0.85) + (instant * 0.15)
        last_frame_time = now

        elapsed = now - start
        left = max(0.0, total_seconds - elapsed)
        fps_line = "FPS: -- (Target 120)"
        if smoothed_fps is not None:
            fps_line = f"FPS: {smoothed_fps:0.1f} (Target 120)"
        draw_overlay(frame, f"REC \u25cf  {elapsed:0.2f}s  (left {left:0.2f}s) — Q to abort", fps_line)
        writer.write(frame)
        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q')):
            return False

        if (not r_sent) and elapsed >= trigger_after:
            if fan and fan._ser:
                fan.drop_ball()
            else:
                print("[WARN] Drop skipped: ESP32 serial not connected.")
            r_sent = True

        if elapsed >= total_seconds:
            break
    return True


def main():
    ensure_output_dir(OUTPUT_DIR)
    window = "IA Live Preview (SPACE to start run, Q to quit)"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 720)

    cap = open_camera(CAM_INDEX, TARGET_FPS, FRAME_SIZE)

    def level_to_fan(level: int) -> int:
        if level <= 0:
            return 0
        return min(10, level)

    total_videos = TOTAL_LEVELS * VIDEOS_PER_LEVEL

    fan = FanController(SERIAL_PORT, SERIAL_BAUD)
    fan_connected = fan.connect()
    fan.set_level(level_to_fan(1))

    print(f"[INFO] Preview started. Focus this window and press SPACE to start the {total_videos}-video run. Press Q to quit.")

    started = False
    while not started:
        ret, frame = cap.read()
        if not ret:
            continue
        draw_overlay(frame, "Idle — press SPACE to start full run, Q to quit")
        cv2.imshow(window, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 32:
            started = True
        elif key in (ord('q'), ord('Q')):
            cap.release(); cv2.destroyAllWindows(); fan.close(); return

    global_index = 0
    for level in range(TOTAL_LEVELS):
        if fan_connected:
            fan.set_level(level_to_fan(level))
        print(f"\n===== Level L{level} =====")
        for vid in range(1, VIDEOS_PER_LEVEL + 1):
            global_index += 1
            label = f"L{level}V{vid}"
            save_path = os.path.join(OUTPUT_DIR, f"{label}.mp4")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting video {global_index}/{total_videos} — {label}")

            if not wait_with_preview(cap, window, COUNTDOWN_BEFORE_RECORD):
                print("[ABORT] Aborted during countdown.")
                cap.release(); cv2.destroyAllWindows(); fan.close(); return

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or FRAME_SIZE[0]
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or FRAME_SIZE[1]
            fps = cap.get(cv2.CAP_PROP_FPS) or TARGET_FPS
            writer = build_writer(save_path, (width, height), fps)

            ok = record_clip(cap, writer, window, RECORD_TOTAL_SECONDS, TRIGGER_AFTER_SECONDS, fan if fan_connected else None)
            writer.release()
            if not ok:
                print("[ABORT] Aborted during recording.")
                cap.release(); cv2.destroyAllWindows(); fan.close(); return

            print(f"[SAVED] {save_path}")

    print(f"\n[DONE] All {total_videos} videos captured. Press Q to close the preview window.")
    fan.set_level(1)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        draw_overlay(frame, "Run complete — press Q to quit")
        cv2.imshow(window, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q')):
            break

    cap.release(); cv2.destroyAllWindows(); fan.close()


if __name__ == "__main__":
    main()
