import { useState } from "react";
import { httpUrl } from "../lib/api";
import type { DetectionEvent } from "../lib/types";
import { useTelemetry } from "../state/telemetry";

export default function DetectionAlert() {
  const { events, telemetry } = useTelemetry();
  const [dismissed, setDismissed] = useState<number | null>(null);
  const live = events.find((e) => e.code === "vision.detection_alert")?.data.detection as DetectionEvent | undefined;
  const recent = telemetry?.detections?.find((d) => d.data?.action === "pause_and_alert");
  const d = live && (!recent || live.id >= recent.id) ? live : recent;
  if (!d || d.id === dismissed) return null;
  return <div role="alert" aria-live="assertive" className="flex flex-wrap items-center gap-3 border-t border-red-400 bg-red-950 px-4 py-3 text-sm text-white">
    <div className="flex-1"><strong>{d.simulated ? "SIMULATED " : ""}{d.label} candidate · motion paused</strong>
      <p>Unverified detection. Review before re-arming and resuming.{d.position?.x != null && ` Local (${d.position.x.toFixed(2)}, ${d.position.y?.toFixed(2)}) m.`}</p>
    </div>
    {typeof d.data?.snapshot_file === "string" && <a className="underline" target="_blank" rel="noreferrer" href={httpUrl(`/api/detections/${d.id}/snapshot`, true)}>View snapshot</a>}
    <button className="rounded border border-red-300 px-3 py-2" onClick={() => setDismissed(d.id)}>Dismiss alert</button>
  </div>;
}
