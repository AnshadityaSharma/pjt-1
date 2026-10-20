"""Refresh browser-only presentation data from the real simulation schema."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from rover.config import load_config
from rover.runtime import RoverRuntime


async def main():
    cfg = load_config(ROOT / "backend/config/simulation.yaml")
    cfg.server.frontend_dist = None
    cfg.rover_name = "Survey Rover - Presentation Demo"
    cfg.simulation.obstacles = []
    cfg.calibration.calibrated = True
    rt = RoverRuntime(cfg, ":memory:")
    await rt.start()
    await asyncio.sleep(0.2)
    rec = rt.missions.create("5 x 5 m sample survey", "grid", dict(length=5, width=5, lane_spacing=0.5,
        margin=0.1, execution_mode="simulation", speed_mps=0.2))
    rt.missions.load(rec["id"])
    fixture = dict(telemetry=rt.telemetry(), system=rt.system_info(), events=[e.to_dict() for e in rt.events.recent(20)],
                   plan=rt.missions.active.plan.model_dump(mode="json"), record=rt.repo.get_mission(rec["id"]),
                   config=cfg.redacted(), preflight=[dict(id="demo", label="Browser presentation", passed=True,
                   required=True, message="Sample data only; no hardware connected")])
    (ROOT / "frontend/src/demo/fixture.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    (ROOT / "frontend/public/demo/camera.jpg").write_bytes(rt.camera.render())
    await rt.stop()


if __name__ == "__main__":
    asyncio.run(main())
