import { timeAgo, type RecentItem } from "../lib/recent";
import { IconArrowUpRight, IconCalendar, IconForward, IconLightbulb, IconPen } from "./Icons";

export function greetingFor(date = new Date()): string {
  const h = date.getHours();
  if (h < 12) return "Good Morning";
  if (h < 17) return "Good Afternoon";
  return "Good Evening";
}

const HEADLINE = ["WHAT'S", "ON", "YOUR", "MIND?"];

export function Greeting({ name }: { name: string }) {
  return (
    <div className="greeting">
      <p className="greet" data-anim="greet">{greetingFor()}, {name}</p>
      <h1 className="headline" aria-label="What's on your mind?">
        {HEADLINE.map((w) => (
          <span className="word-mask" key={w} aria-hidden="true">
            <span className="word" data-anim="word">{w}</span>
          </span>
        ))}
      </h1>
      <p className="subline" data-anim="settle">Get instant answers, clear explanations and smarter suggestions.</p>
    </div>
  );
}

export const QUICK_ACTIONS = [
  {
    title: "Explain a Concept",
    action: "Learn Something New",
    tone: "blue",
    Icon: IconLightbulb,
    prompt: "Explain a concept to me in simple terms with one everyday example. Ask me which topic I'd like first.",
  },
  {
    title: "Draft a Message",
    action: "Write With Me",
    tone: "violet",
    Icon: IconPen,
    prompt: "Help me draft a clear, friendly message. Ask me who it's for and what I want to say.",
  },
  {
    title: "Plan My Day",
    action: "Get Organized",
    tone: "indigo",
    Icon: IconCalendar,
    prompt: "Help me plan my day. Ask me for my tasks, deadlines and priorities first, then suggest a schedule.",
  },
] as const;

export function QuickActions({ onPick, disabled }: { onPick: (prompt: string) => void; disabled: boolean }) {
  return (
    <div className="cards">
      {QUICK_ACTIONS.map(({ title, action, tone, Icon, prompt }) => (
        <button key={title} className="card" data-anim="card" onClick={() => onPick(prompt)} disabled={disabled}>
          <span className={`card-icon tone-${tone}`}><Icon /></span>
          <span className="card-text">
            <span className="card-title">{title}</span>
            <span className="card-action">{action}</span>
          </span>
          <IconArrowUpRight className="card-arrow" />
        </button>
      ))}
    </div>
  );
}

export const SUGGESTIONS = [
  "What is the capital of France?",
  "Explain how caching makes apps faster",
  "Give me three tips to stay focused while studying",
  "What's a good way to learn a new language?",
];

interface RecentProps {
  items: RecentItem[];
  onOpen: (id: string) => void;
  onSuggest: (q: string) => void;
  onSeeMore: () => void;
  query: string;
}

export function Recent({ items, onOpen, onSuggest, onSeeMore, query }: RecentProps) {
  const q = query.trim().toLowerCase();
  const filtered = q ? items.filter((r) => r.title.toLowerCase().includes(q)) : items;
  const showingSuggestions = items.length === 0;
  const rows = showingSuggestions
    ? SUGGESTIONS.map((s) => ({ key: s, title: s, meta: "Suggested", onClick: () => onSuggest(s) }))
    : filtered.slice(0, 4).map((r) => ({ key: r.id, title: r.title, meta: timeAgo(r.updatedAt), onClick: () => onOpen(r.id) }));

  return (
    <section className="recent" aria-label="Recent conversations">
      <h2 className="recent-title" data-anim="hist">{showingSuggestions ? "Try Asking" : "Recent Conversations"}</h2>
      <ul className="tree">
        {rows.length === 0 && <li className="tree-empty" data-anim="hist">No conversations match “{query}”.</li>}
        {rows.map((r) => (
          <li key={r.key} data-anim="hist">
            <button className="tree-row" onClick={r.onClick}>
              <span className="tree-q">{r.title}</span>
              <span className="tree-time">{r.meta}</span>
            </button>
          </li>
        ))}
      </ul>
      {!showingSuggestions && items.length > 0 && (
        <button className="see-more" data-anim="hist" onClick={onSeeMore}>
          See More <IconForward />
        </button>
      )}
    </section>
  );
}
