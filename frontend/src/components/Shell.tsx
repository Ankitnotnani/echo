import type { HealthState } from "../lib/types";
import { IconBack, IconBell, IconChart, IconChat, IconForward, IconHome, IconLogo, IconSearch } from "./Icons";

interface RailProps {
  onHome: () => void;
  onChat: () => void;
  onOverview: () => void;
  mode: "chat" | "overview";
}

export function Rail({ onHome, onChat, onOverview, mode }: RailProps) {
  return (
    <nav className="rail" aria-label="Main">
      <button className="tile tile-logo" data-anim="rail" onClick={onHome} aria-label="Echo home" title="Echo">
        <IconLogo />
      </button>
      <div className="rail-group">
        <button className="tile" data-anim="rail" onClick={onHome} aria-label="Home" title="Home (new chat)"><IconHome /></button>
        <button className={`tile ${mode === "chat" ? "is-active" : ""}`} data-anim="rail" onClick={onChat} aria-label="AI Assistant" title="AI Assistant"><IconChat /></button>
        <button className={`tile ${mode === "overview" ? "is-active" : ""}`} data-anim="rail" onClick={onOverview} aria-label="Overview" title="Overview"><IconChart /></button>
      </div>
    </nav>
  );
}

interface TopBarProps {
  onBack: () => void;
  canGoBack: boolean;
  search: string;
  onSearch: (v: string) => void;
  onHome: () => void;
}

export function TopBar({ onBack, canGoBack, search, onSearch, onHome }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="tile tile-logo topbar-logo" onClick={onHome} aria-label="Echo home"><IconLogo /></button>
        <button className="tile" data-anim="top" onClick={onBack} disabled={!canGoBack} aria-label="Back" title="Back to start">
          <IconBack />
        </button>
        <span className="fwd" data-anim="top" aria-hidden="true"><IconForward /></span>
        <nav className="crumbs" data-anim="top" aria-label="Breadcrumb">
          <button className="crumb" onClick={onHome}>Home</button>
          <span className="crumb-sep">›</span>
          <span className="crumb is-current" aria-current="page">AI Assistant</span>
        </nav>
      </div>
      <div className="topbar-right">
        <label className="search glass" data-anim="top">
          <IconSearch />
          <input
            type="search"
            placeholder="Search Anything..."
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            aria-label="Search conversations"
          />
        </label>
        <button className="tile tile-round" data-anim="top" aria-label="Notifications" title="No new notifications">
          <IconBell />
        </button>
        <span className="avatar" data-anim="top" title="Ankit Notnani" aria-label="Ankit Notnani">AN</span>
      </div>
    </header>
  );
}

interface SubBarProps {
  mode: "chat" | "overview";
  onMode: (m: "chat" | "overview") => void;
  health: HealthState;
}

export function SubBar({ mode, onMode, health }: SubBarProps) {
  return (
    <div className="subbar">
      <div className="segmented" role="tablist" aria-label="View" data-anim="top">
        <button role="tab" aria-selected={mode === "chat"} className={mode === "chat" ? "is-active" : ""} onClick={() => onMode("chat")}>
          Chat Mode
        </button>
        <button role="tab" aria-selected={mode === "overview"} className={mode === "overview" ? "is-active" : ""} onClick={() => onMode("overview")}>
          Overview
        </button>
      </div>
      <StatusPill health={health} />
    </div>
  );
}

export function StatusPill({ health }: { health: HealthState }) {
  const ok = health.state === "ok";
  const label = ok ? "AI Agents Running" : health.state === "checking" ? "Connecting…" : "Gateway Offline";
  const badge = ok ? String(health.data.keys_configured) : "–";
  const title = ok
    ? `Backend healthy · ${health.data.keys_configured} API keys in the pool · cache ${health.data.cache_enabled ? "on" : "off"}${health.data.model ? ` · ${health.data.model}` : ""}`
    : health.state === "down"
      ? health.reason
      : "Checking the backend…";
  return (
    <div className={`status-pill glass ${ok ? "is-ok" : health.state === "down" ? "is-down" : ""}`} data-testid="status-pill" data-anim="top" title={title} role="status">
      <span className="status-dot" aria-hidden="true" />
      <span className="status-label">{label}</span>
      <span className="status-badge" aria-label={`${badge} API keys configured`}>{badge}</span>
    </div>
  );
}
