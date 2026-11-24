// Recent conversations live in the browser only: the backend contract has
// exactly three endpoints and no "list sessions" route.

export interface RecentItem {
  id: string; // session_id
  title: string; // first user message
  updatedAt: number;
}

const KEY = "echo.recent.v1";
const MAX = 20;

function safeRead(): RecentItem[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as RecentItem[]) : [];
    return Array.isArray(parsed) ? parsed.filter((r) => r && typeof r.id === "string") : [];
  } catch {
    return [];
  }
}

function safeWrite(items: RecentItem[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items.slice(0, MAX)));
  } catch {
    /* storage can be unavailable (private mode); recents are a convenience only */
  }
}

export function loadRecent(): RecentItem[] {
  return safeRead().sort((a, b) => b.updatedAt - a.updatedAt);
}

export function touchRecent(id: string, firstMessage: string): RecentItem[] {
  const items = safeRead();
  const existing = items.find((r) => r.id === id);
  const next: RecentItem[] = existing
    ? items.map((r) => (r.id === id ? { ...r, updatedAt: Date.now() } : r))
    : [{ id, title: firstMessage.slice(0, 140), updatedAt: Date.now() }, ...items];
  next.sort((a, b) => b.updatedAt - a.updatedAt);
  safeWrite(next);
  return next;
}

export function removeRecent(id: string): RecentItem[] {
  const next = safeRead().filter((r) => r.id !== id);
  safeWrite(next);
  return next;
}

export function timeAgo(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 45) return "Just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.round(h / 24);
  if (d === 1) return "Yesterday";
  if (d < 7) return `${d} days ago`;
  return new Date(ts).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
