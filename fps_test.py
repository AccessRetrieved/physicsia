import cv2
import time

def test_resolution(width, height, camera_index=0, duration=5):
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    time.sleep(1)

    count = 0
    start = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        count += 1
        if time.time() - start >= duration:
            break

    cap.release()
    fps = count / (time.time() - start)
    print(f"{width}x{height}: {fps:.2f} fps")

for w, h in [
    (640, 360),
    (640, 480),
    (1280, 720),
    (1920, 1080),
    (2560, 1440),
    (1920, 1440),
]:
    test_resolution(w, h)
