# Anchored 5 × 5 m survey and remote control

Use the **Manual Remote Control / Autonomous Boustrophedon / Active Mission**
tabs to switch screens. Manual control uses the existing `/ws/control` session:
take control, then hold a direction button or an arrow/WASD key. Release stops;
Space stops and Escape requests e-stop. The large red E-STOP stays in the sticky
header. Switching screens closes the manual socket and stops that session.
An autonomous mission must release motor ownership before manual control.

## Calibrate and set an origin

1. In Quick Calibration, enter measured ground speed at normalized output 1.0
   and the duration of a 90° pivot at the displayed pivot output. These map to
   the existing speed/effective-track model and persist in SQLite. Disarm and
   unload the current mission before saving; generate a new plan afterwards.
2. Select **Quick 5m x 5m Demo Box** (metres, 0.5 m lane spacing, pivot turns).
3. Choose **Use My Device GPS as Origin**, or click the origin map / enter
   coordinates. Browser geolocation requires HTTPS or localhost; manual map and
   coordinate entry work over ordinary HTTP. Reported phone GPS accuracy can be
   larger than the survey box.
4. The anchor is the grid's **near-left (0, 0) corner**. Its `heading_deg` is
   the geographic bearing of grid +y: 0 north, 90 east. Set this bearing manually.
   Place the rover at the route preview's start offset from that corner, facing
   the indicated local heading. The anchor is not a live rover GPS receiver.
5. Save/load, arm and start. Anchored grids require calibration and use commanded
   dead reckoning. The amber map position and trace are estimates; slip and
   stalls remain unobservable. Red markers identify unverified detection events.

`GET /api/calibration` returns `linear_speed_mps`, `turn_90_duration_sec`,
`pivot_output`, `calibrated`, and `notes`. `POST /api/calibration` accepts the two
measurements and optional notes. `anchor_gps: {lat, lon, heading_deg}` belongs
in grid plan / mission parameters; mission creation also accepts it at top level.

## Pi camera and custom detector

`backend/config/hardware.yaml` selects `camera.provider: picamera2`. Install
Raspberry Pi OS's `python3-picamera2` and use a `--system-site-packages` virtualenv
for libcamera access. `opencv_v4l2` selects OpenCV's V4L2 capture, with
`device_index`, `width`, and `height`; it requires `python3-opencv` or the
`camera-v4l2` extra and an exposed V4L2 device. CSI cameras on Pi OS normally use
Picamera2/libcamera rather than a raw `/dev/video0` stream. ESP32-CAM remains a
selectable provider. All drivers feed the same backend MJPEG and snapshot APIs.

Provide custom trained `backend/models/landmine_yolov8n.onnx` with class order
`landmine`, `ap_mine`, `at_mine`. Stock COCO weights cannot be renamed into a
landmine detector; mismatching model metadata/class counts are rejected.
Missing camera libraries or weights report unavailable without fabricated data.

With `vision.on_detection_action: pause_and_alert`, matching detections above
`event_min_confidence` immediately stop motion, pause a running mission and
disarm. The exact inference frame is saved to `vision.snapshot_dir`. Events
persist the local commanded x/y, anchored lat/lon where available, and
`magnetometer_context` (`ready` with readings, `unavailable`, or `not_installed`).
`vision.detection_alert` events carry the detection over the telemetry WebSocket;
the UI displays an alert, snapshot link and red map marker. Snapshots are served
through authenticated `GET /api/detections/{id}/snapshot`. Dismissal does not
re-arm or resume. Without an anchor or a valid localization source, geographic
coordinates remain absent. These are unverified visible-object candidates,
not proof of buried objects or safe terrain.
