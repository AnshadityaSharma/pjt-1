"""Fast checks for anchored surveys, camera adapters and detection responses."""

import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from PIL import Image

from rover.api.routes import QuickCalibration, calibration_values, detection_snapshot, save_calibration
from rover.camera import LocalCamera, NoCamera, build_camera
from rover.config import CameraConfig, RoverConfig, VisionConfig, load_config
from rover.core.enums import MissionState
from rover.core.events import EventLog
from rover.detection import DetectionRecorder
from rover.localization.base import NoLocalizationProvider
from rover.mission.manager import MissionManager
from rover.persistence.db import Database
from rover.persistence.repository import Repository
from rover.planning.geo import EnuFrame, project_grid
from rover.planning.models import GpsAnchor, GridPlanRequest
from rover.planning.service import plan_grid
from rover.runtime import RoverRuntime
from rover.vision.detector import Detection, DetectionResult
from rover.vision.service import VisionService


@pytest.mark.parametrize("heading,expected", [(0, (2, 5)), (90, (5, -2)), (180, (-2, -5))])
def test_anchor_rotation_round_trip(heading, expected):
    anchor = GpsAnchor(lat=12.97, lon=77.59, heading_deg=heading)
    lat, lon = project_grid(anchor, 2, 5)
    assert EnuFrame(anchor.lat, anchor.lon).to_enu(lat, lon) == pytest.approx(expected, abs=1e-5)


def test_five_metre_anchored_plan_has_projected_lanes_and_distinct_hash():
    req = GridPlanRequest(length=5, width=5, lane_spacing=0.5, margin=0.1, execution_mode="simulation",
                          anchor_gps={"lat": 12.97, "lon": 77.59, "heading_deg": 90})
    p = plan_grid(RoverConfig(), req)
    assert p.valid and p.summary.lane_count == 10
    assert p.boundary_geo and all(s.geo_points for s in p.segments)
    assert p.anchor_gps.heading_deg == 90 and p.kind == "grid"
    assert "commanded dead reckoning" in p.localization_note
    changed = req.model_copy(update={"anchor_gps": GpsAnchor(lat=12.98, lon=77.59, heading_deg=90)})
    assert p.plan_hash != plan_grid(RoverConfig(), changed).plan_hash
    manager = SimpleNamespace(localization=SimpleNamespace(provider=SimpleNamespace(kind="local")))
    assert MissionManager._execution_mode(manager, p) == "open_loop"


def test_projected_position_keeps_local_metres_and_labels_estimate():
    anchor = GpsAnchor(lat=12.97, lon=77.59, heading_deg=90)
    manager = SimpleNamespace(active=SimpleNamespace(plan=SimpleNamespace(kind="grid", anchor_gps=anchor),
                                                    executor=SimpleNamespace(est=SimpleNamespace(x=2, y=5))))
    position = MissionManager.projected_position(manager)
    assert position["x"] == 2 and position["y"] == 5 and position["measured"] is False
    assert position["provider"] == "commanded_dead_reckoning"
    assert position["lat"] is not None and position["lon"] is not None


@pytest.mark.parametrize("provider", ["picamera2", "opencv_v4l2"])
def test_camera_creation_is_lazy(provider):
    camera = build_camera(CameraConfig(provider=provider), None)
    assert isinstance(camera, LocalCamera)
    assert camera.provider == provider and camera._device is None


def test_picamera_capture_and_cleanup_without_pi(monkeypatch):
    device = Mock()
    device.wait.return_value = Image.new("RGB", (16, 16), "red")
    module = SimpleNamespace(Picamera2=Mock(return_value=device))
    monkeypatch.setitem(sys.modules, "picamera2", module)
    camera = LocalCamera(CameraConfig(provider="picamera2", device_index=1))
    camera._open()
    module.Picamera2.assert_called_once_with(camera_num=1)
    assert camera._capture().startswith(b"\xff\xd8")
    device.capture_image.assert_called_once_with("main", wait=False)
    camera._close()
    device.stop.assert_called_once()
    device.close.assert_called_once()


def test_v4l2_capture_and_cleanup_without_camera(monkeypatch):
    device = Mock()
    device.read.return_value = (True, object())
    encoded = Mock(tobytes=Mock(return_value=b"jpeg"))
    cv = SimpleNamespace(VideoCapture=Mock(return_value=device), CAP_V4L2=200, CAP_PROP_FRAME_WIDTH=3,
                         CAP_PROP_FRAME_HEIGHT=4, imencode=Mock(return_value=(True, encoded)))
    monkeypatch.setitem(sys.modules, "cv2", cv)
    camera = LocalCamera(CameraConfig(provider="opencv_v4l2"))
    camera._open()
    assert camera._capture() == b"jpeg"
    camera._close()
    device.release.assert_called_once()


async def test_quick_calibration_persists_and_matches_turn_duration():
    cfg = RoverConfig()
    rt = SimpleNamespace(config=cfg, supervisor=SimpleNamespace(armed=False), missions=SimpleNamespace(active=None), repo=Mock())
    result = await save_calibration(QuickCalibration(linear_speed_mps=0.4, turn_90_duration_sec=2.0), rt)
    assert result["turn_90_duration_sec"] == pytest.approx(2)
    assert cfg.calibration.full_speed_mps == 0.4 and cfg.calibration.calibrated
    rt.repo.set_meta.assert_called_once()
    assert calibration_values(rt) == result


async def test_quick_calibration_refuses_armed_or_loaded_rover():
    cfg = RoverConfig()
    rt = SimpleNamespace(config=cfg, supervisor=SimpleNamespace(armed=True), missions=SimpleNamespace(active=None), repo=Mock())
    body = QuickCalibration(linear_speed_mps=0.4, turn_90_duration_sec=2)
    with pytest.raises(HTTPException) as exc:
        await save_calibration(body, rt)
    assert exc.value.status_code == 409
    rt.supervisor.armed = False
    rt.missions.active = object()
    with pytest.raises(HTTPException):
        await save_calibration(body, rt)
    rt.repo.set_meta.assert_not_called()


def test_detection_stops_before_pause_and_disarms():
    calls = []
    rt = SimpleNamespace(controller=SimpleNamespace(emergency_halt=lambda _: calls.append("stop")),
                         missions=SimpleNamespace(state=MissionState.RUNNING, pause=lambda *a, **kw: calls.append("pause")),
                         supervisor=SimpleNamespace(disarm=lambda **kw: calls.append("disarm")))
    RoverRuntime._pause_for_detection(rt, "landmine")
    assert calls == ["stop", "pause", "disarm"]


@pytest.mark.parametrize("magnetometer", ["not_installed", {"status": "ready", "readings": [{"value": {"x": 20}}]}])
async def test_detection_snapshot_context_projection_alert_and_cooldown(tmp_path, magnetometer):
    db = Database.for_path(":memory:")
    db.migrate()
    repo = Repository(db)
    events = EventLog()
    recorder = DetectionRecorder(repo, events, NoLocalizationProvider(), lambda: "demo")
    recorder.position_context = lambda: {"x": 1, "y": 2, "lat": 12.97, "lon": 77.59, "provider": "commanded_dead_reckoning", "measured": False}
    cfg = VisionConfig(event_classes=["landmine"], on_detection_action="pause_and_alert", snapshot_dir=str(tmp_path))
    service = VisionService(cfg, NoCamera(), recorder, events)
    service.on_detection = Mock()
    service.magnetometer_context = lambda: magnetometer
    result = DetectionResult("custom.onnx", "onnx", [Detection("landmine", 0, 0.9, (0, 0, 1, 1))], 1, 16, 16, frame_seq=4)
    out = io.BytesIO()
    Image.new("RGB", (16, 16)).save(out, format="JPEG")
    service._maybe_events(result, out.getvalue())
    service._maybe_events(result, out.getvalue())
    rows = repo.list_detections("demo")
    assert len(rows) == 1
    row = rows[0]
    assert row["position"]["x"] == 1 and row["position"]["lat"] == 12.97
    assert row["localization_quality"] == "commanded_dead_reckoning"
    assert row["data"]["magnetometer_context"] == magnetometer
    assert (tmp_path / row["data"]["snapshot_file"]).read_bytes() == out.getvalue()
    assert events.recent(1)[0].code == "vision.detection_alert"
    service.on_detection.assert_called_once_with("landmine")
    response = await detection_snapshot(row["id"], SimpleNamespace(repo=repo, config=SimpleNamespace(vision=cfg)))
    assert Path(response.path).parent == tmp_path
    db.close()


def test_unconfigured_magnetometer_context():
    rt = SimpleNamespace(sensors=SimpleNamespace(of_type=lambda _: []))
    assert RoverRuntime._magnetometer_context(rt) == "not_installed"


def test_hardware_config_selects_pi_camera_custom_classes_and_pause_action():
    cfg = load_config(Path(__file__).parents[1] / "config/hardware.yaml")
    assert cfg.camera.provider == "picamera2"
    assert cfg.vision.class_names == ["landmine", "ap_mine", "at_mine"]
    assert cfg.vision.event_classes == cfg.vision.class_names
    assert cfg.vision.on_detection_action == "pause_and_alert"
