import { lazy, Suspense, useState } from "react";
import type { GpsAnchor, SystemInfo } from "../lib/types";
import { Button, Field, Notice, Panel } from "./ui";

const GeoMap = lazy(() => import("./GeoMap"));

export default function GpsAnchorPanel({ anchor, onChange, system }: { anchor: GpsAnchor | null; onChange: (v: GpsAnchor | null) => void; system: SystemInfo | null }) {
  const [lat, setLat] = useState(anchor ? String(anchor.lat) : "");
  const [lon, setLon] = useState(anchor ? String(anchor.lon) : "");
  const [heading, setHeading] = useState(anchor ? String(anchor.heading_deg) : "0");
  const [message, setMessage] = useState("");
  const [locating, setLocating] = useState(false);
  const [fit, setFit] = useState(0);
  const apply = (latitude = Number(lat), longitude = Number(lon)) => {
    const h = Number(heading);
    if (!Number.isFinite(latitude) || Math.abs(latitude) >= 89.9 || !Number.isFinite(longitude) || Math.abs(longitude) > 180 || !Number.isFinite(h) || h < 0 || h >= 360) {
      setMessage("Enter valid coordinates and a heading from 0° to less than 360°."); return;
    }
    setLat(String(latitude)); setLon(String(longitude));
    onChange({ lat: latitude, lon: longitude, heading_deg: h });
    setFit((v) => v + 1); setMessage("Origin applied. Place the near-left survey corner at this point; grid forward follows the entered bearing.");
  };
  const locate = () => {
    if (!window.isSecureContext || !navigator.geolocation) {
      setMessage("Device GPS needs HTTPS or localhost. On HTTP, click the map or enter latitude/longitude below."); return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition((p) => {
      setLocating(false); apply(p.coords.latitude, p.coords.longitude);
      setMessage(`Device GPS origin applied (reported accuracy ±${Math.round(p.coords.accuracy)} m). Check the corner and heading before running.`);
    }, (e) => { setLocating(false); setMessage(`${e.message}. Click the map or enter coordinates below.`); }, { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 });
  };
  const center = anchor ?? { lat: system?.ui.map_center_lat ?? 12.9716, lon: system?.ui.map_center_lon ?? 77.5946 };
  return <Panel title="Survey GPS Origin (optional)">
    <div className="space-y-3">
      <Button onClick={locate} disabled={locating}>{locating ? "Locating…" : "Use My Device GPS as Origin"}</Button>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Latitude"><input className="input" type="number" step="any" value={lat} onChange={(e) => setLat(e.target.value)} /></Field>
        <Field label="Longitude"><input className="input" type="number" step="any" value={lon} onChange={(e) => setLon(e.target.value)} /></Field>
      </div>
      <Field label="Grid forward bearing (°)" hint="0 = north, 90 = east. Set this manually; GPS position does not provide stationary rover heading."><input className="input" type="number" min={0} max={359.99} step="any" value={heading} onChange={(e) => setHeading(e.target.value)} /></Field>
      <div className="flex gap-2"><Button disabled={!lat.trim() || !lon.trim()} onClick={() => apply()}>Apply origin</Button><Button onClick={() => { onChange(null); setMessage("Origin removed."); }}>Clear</Button></div>
      <p className="text-xs text-fg-muted">Or click the map to set the near-left corner. Projection is an estimate from commanded motion.</p>
      {system && <Suspense fallback={<p>Loading map…</p>}><GeoMap center={center} tileUrl={system.ui.map_tile_url} attribution={system.ui.map_tile_attribution} maxZoom={system.ui.map_max_zoom} boundary={[]} onAnchorChange={(p) => apply(p.lat, p.lon)} anchor={anchor} fitToken={fit} height="230px" /></Suspense>}
      {message && <Notice>{message}</Notice>}
    </div>
  </Panel>;
}
