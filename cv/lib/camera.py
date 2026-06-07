import cv2
import os


def init_camera():
    """Try RealSense first, fall back to webcam."""
    try:
        import pyrealsense2 as rs  # type: ignore
        import numpy as np

        pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        pipeline.start(config)
        print("RealSense D435 connected")

        def get_frame():
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                return None
            return np.asanyarray(color_frame.get_data())

        def release():
            pipeline.stop()

        return get_frame, release

    except Exception:
        camera_index = int(os.getenv("CAMERA_INDEX", "0"))
        print(f"RealSense not available, falling back to webcam (index {camera_index})")
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError("No camera found")

        def get_frame():
            ret, frame = cap.read()
            return frame if ret else None

        def release():
            cap.release()

        return get_frame, release
