/** Explicit browser-only presentation mode. Never opens a rover connection. */
import fixture from "./fixture.json";
import type { CoveragePlan, LogEvent, MissionRecord, SystemInfo, Telemetry } from "../lib/types";

export const demoEnabled = import.meta.env.MODE === "demo";
const copy = <T>(v: T): T => JSON.parse(JSON.stringify(v));
const data = copy(fixture) as unknown as { telemetry: Telemetry; system: SystemInfo; events: LogEvent[]; plan: CoveragePlan; record: MissionRecord; config: unknown; preflight: unknown[] };
data.telemetry.camera = { ...data.telemetry.camera, provider: "simulated", online: true, fps: 0,
  frames_total: 1, error: null, last_frame_age_s: null };
let plan = data.plan;
let records = [data.record];
let trace: [number, number][] = [];
let elapsed = 0;
let turnSeconds = 1.5;
const listeners = new Set<() => void>();
const publish = () => listeners.forEach((fn) => fn());
const zero = () => {
  data.telemetry.motion.applied = { left: 0, right: 0 };
  data.telemetry.motion.requested = { left: 0, right: 0 };
};
function event(message: string) {
  data.events.unshift({ id: Date.now(), ts: new Date().toISOString(), level: "info", source: "presentation", code: "demo.action", message: `DEMO: ${message}`, mission_id: null, data: {} });
  data.events = data.events.slice(0, 50);
}

export function demoSnapshot() {
  const now = new Date().toISOString();
  data.telemetry.ts = now;
  data.telemetry.seq++;
  for (const s of data.telemetry.sensors) {
    s.age_s = s.enabled ? 0 : null;
    if (s.last_reading) s.last_reading.timestamp = now;
  }
  return { telemetry: copy(data.telemetry), system: copy(data.system), events: copy(data.events) };
}

export function subscribeDemo(listener: () => void) {
  listeners.add(listener);
  listener();
  const timer = window.setInterval(() => {
    const t = data.telemetry;
    if (t.mission.state === "RUNNING" && t.mission.mission) {
      elapsed += 0.25;
      const percent = Math.min(100, elapsed / 0.6);
      const index = Math.min(plan.segments.length - 1, Math.floor(percent / 100 * plan.segments.length));
      const seg = plan.segments[index];
      const pos = { x: seg.start.x, y: seg.start.y, heading_deg: seg.heading_start_deg };
      t.mission.mission.progress = { segment_index: index, segment_count: plan.segments.length, segment_fraction: 0,
        lanes_completed: Math.min(plan.summary.lane_count, Math.floor(percent / 100 * plan.summary.lane_count)), lane_count: plan.summary.lane_count,
        percent, distance_commanded_m: plan.summary.total_length_m * percent / 100, phase: "presentation animation", elapsed_s: elapsed,
        cross_track_m: null, execution: "open_loop", estimated_pose: pos, estimated_pose_kind: "presentation_animation", measured_pose: null };
      trace.push([pos.x, pos.y]);
      if (t.simulation) t.simulation.truth.pose = pos;
      if (percent === 100) { t.mission.state = "COMPLETED"; t.motion.owner = "none"; zero(); }
    }
    listener();
  }, 250);
  return () => { listeners.delete(listener); window.clearInterval(timer); zero(); };
}

function demoError(message: string): never { throw new Error(message); }

/** Lightweight rectangle preview only. Real polygon/Dubins planning remains in Python. */
function rectangle(input: Record<string, unknown>): CoveragePlan {
  if (input.turn_strategy === "arc") demoError("Arc preview needs the full simulator. Choose Pivot for this browser demonstration.");
  const scale = ({ m: 1, cm: 0.01, mm: 0.001 } as Record<string, number>)[String(input.units ?? "m")];
  const length = Number(input.length) * scale, width = Number(input.width) * scale;
  const spacing = Number(input.lane_spacing) * scale, margin = Number(input.margin ?? 0) * scale;
  if (![length, width, spacing, margin].every(Number.isFinite) || length <= 2 * margin || width <= 2 * margin || spacing <= 0 || margin < 0)
    demoError("Use positive dimensions and lane spacing, with margins smaller than half the box.");
  const alongWidth = input.lane_orientation === "along_width";
  const across = alongWidth ? length : width, along = alongWidth ? width : length;
  const swath = Number(input.swath_width ?? input.lane_spacing) * scale;
  const count = Math.max(1, Math.ceil(Math.max(0, across - 2 * margin - swath) / spacing) + 1);
  if (count > 100) demoError("Browser preview is limited to 100 lanes. Increase lane spacing.");
  const p = copy(data.plan);
  p.anchor_gps = null; // geographic projection is deliberately not emulated
  p.boundary_geo = null;
  p.origin = null;
  p.boundary = [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: width, y: length }, { x: 0, y: length }];
  p.inner_boundary = [[{ x: margin, y: margin }, { x: width - margin, y: margin }, { x: width - margin, y: length - margin }, { x: margin, y: length - margin }]];
  p.segments = [];
  p.waypoints = [];
  const coordinate = (a: number, b: number) => alongWidth ? { x: a, y: b } : { x: b, y: a };
  const corner = String(input.start_corner ?? "near_left");
  const reverseAcross = alongWidth ? corner.startsWith("far") : corner.endsWith("right");
  const reverseAlong = alongWidth ? corner.endsWith("right") : corner.startsWith("far");
  let previous: { x: number; y: number } | null = null;
  let previousHeading = 0;
  for (let i = 0; i < count; i++) {
    const offset = Math.min(across - margin - Math.min(swath / 2, (across - 2 * margin) / 2), margin + swath / 2 + i * spacing);
    const b = reverseAcross ? across - offset : offset;
    const reversed = (i % 2 === 1) !== reverseAlong;
    const start = coordinate(reversed ? along - margin : margin, b);
    const end = coordinate(reversed ? margin : along - margin, b);
    const heading = ((alongWidth ? 90 : 0) + (reversed ? 180 : 0)) % 360;
    if (previous) {
      p.segments.push({ ...copy(data.plan.segments.find((s) => s.kind === "shift") ?? data.plan.segments[0]),
        index: p.segments.length, kind: "shift", start: previous, end: start, points: [previous, start], geo_points: null,
        length_m: Math.hypot(start.x - previous.x, start.y - previous.y), heading_start_deg: previousHeading, heading_end_deg: heading });
    }
    p.segments.push({ ...copy(data.plan.segments[0]), index: p.segments.length, kind: "lane", lane_index: i,
      start, end, points: [start, end], geo_points: null, length_m: along - 2 * margin, heading_start_deg: heading, heading_end_deg: heading });
    previous = end; previousHeading = heading;
  }
  p.start_pose = { ...p.segments[0].start, heading_deg: p.segments[0].heading_start_deg };
  p.summary = { ...p.summary, lane_count: count, segment_count: p.segments.length, area_m2: length * width,
    inner_area_m2: (length - 2 * margin) * (width - 2 * margin), lane_length_m: count * (along - 2 * margin),
    total_length_m: p.segments.reduce((n, s) => n + s.length_m, 0), lane_spacing_m: spacing, swath_width_m: swath,
    pivot_count: (count - 1) * 2, total_rotation_deg: (count - 1) * 180, speed_mps: Number(input.speed_mps ?? 0.2) };
  p.summary.estimated_duration_s = p.summary.total_length_m / p.summary.speed_mps + (count - 1) * 2 * turnSeconds;
  p.valid = true; p.issues = [];
  p.plan_hash = "browser-preview";
  p.parameters = copy(input);
  p.localization_note = "Browser presentation preview: simplified rectangle sketch and indicative totals. Exact turns, geographic projection and verified coverage require the full backend simulator.";
  return p;
}

export async function demoApi(path: string, init: RequestInit & { json?: unknown }): Promise<unknown> {
  const url = new URL(path, location.origin), route = url.pathname;
  const method = init.method ?? "GET";
  const body = (init.json ?? {}) as Record<string, unknown>;
  const t = data.telemetry;
  if (route === "/api/health") return { ok: true, mode: "simulation", auth_required: false };
  if (route === "/api/system") return data.system;
  if (route === "/api/status") return t;
  if (route === "/api/config") return data.config;
  if (route === "/api/faults") return { active: [], history: [] };
  if (route === "/api/events") return { items: data.events };
  if (route === "/api/safety/preflight") return { checks: data.preflight };
  if (route === "/api/sensors") return t.sensors;
  if (route === "/api/localization") return t.localization;
  if (route === "/api/detections") return [];
  if (route === "/api/calibration") {
    if (method !== "GET") {
      data.system.calibration.full_speed_mps = Number(body.linear_speed_mps);
      data.system.calibration.notes = String(body.notes ?? "Demo values");
      turnSeconds = Number(body.turn_90_duration_sec);
    }
    return { linear_speed_mps: data.system.calibration.full_speed_mps, turn_90_duration_sec: turnSeconds, pivot_output: 0.55, calibrated: true, notes: data.system.calibration.notes };
  }
  if (route === "/api/plan/grid") return rectangle(body);
  if (route === "/api/plan/gps") demoError("Polygon route generation requires the full backend simulator. You can explore the map editor here; use Grid plan for the browser-only route preview.");
  if (route === "/api/boundaries") return [];
  if (route === "/api/missions") {
    if (method === "POST") {
      if (body.kind !== "grid") demoError("Use a grid mission in browser presentation mode.");
      const p = rectangle(body.params as Record<string, unknown>);
      const rec = { ...copy(data.record), id: crypto.randomUUID(), name: String(body.name), params: body.params, plan: p, summary: p.summary, plan_hash: p.plan_hash, status: "planned" } as MissionRecord;
      records.unshift(rec); return rec;
    }
    const status = url.searchParams.get("status");
    const items = records.filter((r) => !status || r.status === status);
    return { items, total: items.length };
  }
  if (route.startsWith("/api/missions/")) {
    const parts = route.split("/"), rec = records.find((r) => r.id === parts[3]);
    if (parts[4] === "detections" || parts[4] === "events" || parts[4] === "telemetry") return [];
    if (method === "DELETE") { records = records.filter((r) => r.id !== parts[3]); return undefined; }
    return rec;
  }
  if (route === "/api/mission/active") return { ...t.mission, plan, mission: t.mission.mission ? { ...t.mission.mission, trace } : null };
  if (route === "/api/mission/load") {
    const rec = records.find((r) => r.id === body.mission_id);
    if (!rec?.plan) demoError("Select a sample mission first.");
    plan = copy(rec.plan!); elapsed = 0; trace = [];
    t.mission = { state: "READY", last_result: null, mission: { id: rec.id, name: rec.name, kind: "grid", execution: "open_loop", pause_reason: null, invalidated: null,
      message: "Browser presentation animation only", progress: null, plan_hash: plan.plan_hash, summary: plan.summary, localization_note: plan.localization_note } };
  } else if (route === "/api/mission/unload" || route === "/api/mission/acknowledge") {
    t.mission = { state: "IDLE", last_result: null, mission: null }; t.motion.owner = "none"; zero();
  } else if (route === "/api/mission/start" || route === "/api/mission/resume") {
    if (!t.safety.armed || t.safety.estop_latched) demoError("Arm the sample rover first.");
    if (t.motion.owner === "manual") demoError("Release manual control before starting a sample mission.");
    t.mission.state = "RUNNING"; t.motion.owner = "mission";
  } else if (route === "/api/mission/pause") { t.mission.state = "PAUSED"; zero();
  } else if (route === "/api/mission/stop") { t.mission.state = "READY"; t.motion.owner = "none"; zero();
  } else if (route === "/api/safety/arm") {
    if (t.safety.estop_latched) demoError("Reset the demo e-stop first.");
    t.safety.armed = true; t.safety.motion_permitted = true; t.safety.motion_blocked_reason = null;
  } else if (route === "/api/safety/disarm" || route === "/api/safety/estop") {
    t.safety.armed = false; t.safety.motion_permitted = false; zero();
    if (t.mission.state === "RUNNING") t.mission.state = "PAUSED";
    if (route.endsWith("estop")) { t.safety.estop_latched = true; t.safety.estop_reason = "Presentation e-stop"; t.mission.state = "EMERGENCY_STOP"; }
  } else if (route === "/api/safety/estop/reset") {
    t.safety.estop_latched = false; t.safety.estop_reason = null; t.mission.state = t.mission.mission ? "READY" : "IDLE"; t.motion.owner = "none";
  } else demoError("This operation needs the full backend simulator. Browser presentation mode only changes sample data.");
  event(route.split("/").slice(-2).join(" / ")); publish();
  return { ...t.mission, checks: data.preflight };
}

export function demoControlSocket(): WebSocket {
  let lease: number | undefined;
  const ws = { readyState: 1, onopen: null, onmessage: null, onclose: null,
    send(raw: string) {
      const msg = JSON.parse(raw), t = data.telemetry;
      const reply = (value: unknown) => ws.onmessage?.({ data: JSON.stringify(value) } as MessageEvent);
      if (msg.type === "acquire") {
        if (t.motion.owner === "mission") { reply({ type: "error", code: "controller_busy", message: "Stop the sample mission first." }); return; }
        t.motion.owner = "manual"; t.manual.session_active = true;
        reply({ type: "acquired", session_id: "browser-demo", heartbeat_interval_s: 0.1 });
      } else if (msg.type === "estop") { void demoApi("/api/safety/estop", { method: "POST" });
      } else if (msg.type === "drive" && t.safety.armed && !t.safety.estop_latched && t.motion.owner === "manual") {
        const directions: Record<string, [number, number]> = { forward: [1, 1], reverse: [-1, -1], left: [-1, 1], right: [1, -1], forward_left: [0.5, 1], forward_right: [1, 0.5], reverse_left: [-0.5, -1], reverse_right: [-1, -0.5] };
        const lr = msg.mode === "vector" ? [msg.throttle + msg.steer, msg.throttle - msg.steer] : directions[msg.direction] ?? [0, 0];
        t.motion.applied = { left: Math.max(-1, Math.min(1, lr[0])) * msg.speed, right: Math.max(-1, Math.min(1, lr[1])) * msg.speed };
        t.motion.requested = { ...t.motion.applied }; t.motion.lease_remaining_s = 0.35;
        window.clearTimeout(lease); lease = window.setTimeout(() => { zero(); publish(); }, 350);
        reply({ type: "ack", seq: msg.seq, accepted: true });
      } else if (msg.type === "release") { ws.close();
      } else { zero(); reply({ type: "ack", seq: msg.seq, accepted: msg.type === "stop" }); }
      publish();
    },
    close() { ws.readyState = 3; window.clearTimeout(lease); zero(); data.telemetry.motion.owner = "none"; data.telemetry.manual.session_active = false; ws.onclose?.({} as CloseEvent); publish(); },
  } as { readyState: number; onopen: ((e: Event) => void) | null; onmessage: ((e: MessageEvent) => void) | null; onclose: ((e: CloseEvent) => void) | null; send(raw: string): void; close(): void };
  window.setTimeout(() => ws.onopen?.(new Event("open")), 0);
  return ws as unknown as WebSocket;
}
