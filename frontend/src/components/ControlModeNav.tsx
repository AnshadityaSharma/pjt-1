import { NavLink } from "react-router-dom";

export default function ControlModeNav() {
  return <nav aria-label="Control mode" className="mb-4 flex flex-wrap gap-2 rounded-xl border border-ink-600 bg-ink-900 p-2">
    {[["/drive", "Manual Remote Control"], ["/plan/grid", "Autonomous Boustrophedon"], ["/mission", "Active Mission"]].map(([to, label]) =>
      <NavLink key={to} to={to} className={({ isActive }) => `rounded-lg px-4 py-3 text-sm font-semibold ${isActive ? "bg-amber text-ink-950" : "text-fg-muted hover:bg-ink-700"}`}>{label}</NavLink>)}
  </nav>;
}
