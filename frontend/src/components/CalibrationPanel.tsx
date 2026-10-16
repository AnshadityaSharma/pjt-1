import { useEffect, useState } from "react";
import { api, post } from "../lib/api";
import { Button, Field, Notice, NumberInput, Panel } from "./ui";

interface Calibration { linear_speed_mps: number; turn_90_duration_sec: number; pivot_output: number; notes: string; calibrated: boolean }

export default function CalibrationPanel({ onSaved }: { onSaved?: () => void }) {
  const [value, setValue] = useState<Calibration | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<Calibration>("/api/calibration").then(setValue).catch((e) => setMessage(e.message)); }, []);
  const save = async () => {
    if (!value) return;
    setBusy(true);
    try {
      setValue(await post<Calibration>("/api/calibration", { linear_speed_mps: value.linear_speed_mps, turn_90_duration_sec: value.turn_90_duration_sec, notes: value.notes }));
      setMessage("Calibration saved. Generate a new plan with these measurements.");
      onSaved?.();
    } catch (e) { setMessage((e as Error).message); }
    finally { setBusy(false); }
  };
  return <Panel title="Quick Calibration">
    {value && <div className="space-y-3">
      <Field label="Linear speed at full output (m/s)"><NumberInput value={value.linear_speed_mps} min={0.01} max={3} step={0.01} onChange={(v) => setValue({ ...value, linear_speed_mps: v })} /></Field>
      <Field label="Measured 90° turn duration (seconds)" hint={`Measure at ${Math.round(value.pivot_output * 100)}% pivot output on the survey surface.`}><NumberInput value={value.turn_90_duration_sec} min={0.06} max={120} step={0.1} onChange={(v) => setValue({ ...value, turn_90_duration_sec: v })} /></Field>
      <Field label="Calibration notes"><input className="input" value={value.notes} maxLength={500} onChange={(e) => setValue({ ...value, notes: e.target.value })} /></Field>
      <Button onClick={save} disabled={busy || !Number.isFinite(value.linear_speed_mps) || !Number.isFinite(value.turn_90_duration_sec)}>Save calibration</Button>
      <p className="text-xs text-fg-faint">Disarm and unload any mission before changing calibration. Values persist on the rover.</p>
    </div>}
    {message && <Notice className="mt-3">{message}</Notice>}
  </Panel>;
}
