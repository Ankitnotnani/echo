import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ApiError, getHealth, getHistory, postChat, waitForServer } from "./lib/api";
import { MAX_MESSAGE_CHARS, USER_NAME } from "./lib/config";
import { prefersReducedMotion, runEntrance } from "./lib/motion";
import { loadRecent, removeRecent, timeAgo, touchRecent, type RecentItem } from "./lib/recent";
import { newSessionId, uid } from "./lib/session";
import type { ChatMetadata, ChatRequest, ChatResponse, HealthState, ThreadItem } from "./lib/types";
import { Composer, type ResponseStyle } from "./components/Composer";
import { IconClose } from "./components/Icons";
import { Greeting, QuickActions, Recent } from "./components/Landing";
import { Orb } from "./components/Orb";
import { Overview } from "./components/Overview";
import { Rail, SubBar, TopBar } from "./components/Shell";
import { Thread } from "./components/Thread";

// Frontend copies of the prompts the style / Deep Think menus send as `system_prompt`.
const BASE_PROMPT =
  "You are Echo, a helpful, accurate and friendly AI assistant. Answer the user's questions directly and clearly. " +
  "Use the earlier messages in this conversation to stay consistent and remember what the user told you.";
const STYLE_PROMPTS: Record<Exclude<ResponseStyle, "custom" | "normal">, string> = {
  concise: "Keep every answer short: at most three sentences or five bullet points.",
  detailed: "Give thorough, well-structured answers with headings or lists and a short example where useful.",
};
const DEEP_THINK = "Before answering, reason step by step, then give a clear final answer with a short 'Reasoning' section.";
const DEFAULT_PROMPT =
  BASE_PROMPT + " Keep answers concise unless the user asks for more detail, and use simple Markdown (short lists, bold) when it makes the answer easier to read.";

type Mode = "chat" | "overview";
type ErrorItem = Extract<ThreadItem, { kind: "error" }>;

export default function App() {
  const reducedMotion = useMemo(prefersReducedMotion, []);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [sessionId, setSessionId] = useState(newSessionId); // new session on every page load
  const [items, setItems] = useState<ThreadItem[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [pendingLabel, setPendingLabel] = useState("Thinking…");
  const [mode, setMode] = useState<Mode>("chat");
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [recent, setRecent] = useState<RecentItem[]>(loadRecent);
  const [search, setSearch] = useState("");
  const [drawer, setDrawer] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [entering, setEntering] = useState(!reducedMotion);

  const [simulate, setSimulate] = useState<string | null>(null);
  const [style, setStyle] = useState<ResponseStyle>("normal");
  const [customPrompt, setCustomPrompt] = useState("");
  const [deepThink, setDeepThink] = useState(false);

  const firstMessageRef = useRef<string | null>(null);
  const sentOverrideRef = useRef(false); // did this session ever send a system_prompt?

  const view = items.length === 0 && !pending ? "landing" : "chat";
  const simulationEnabled = health.state === "ok" ? Boolean(health.data.failure_simulation_enabled) : false;

  // ---- entrance timeline (one WAAPI run on first paint) ----
  useLayoutEffect(() => {
    if (reducedMotion || !rootRef.current) return;
    const anims = runEntrance(rootRef.current);
    setEntering(false);
    return () => anims.forEach((a) => a.cancel());
  }, [reducedMotion]);

  // ---- health polling ----
  const refreshHealth = useCallback(async () => {
    try {
      const data = await getHealth();
      setHealth({ state: "ok", data });
    } catch (err) {
      setHealth({ state: "down", reason: err instanceof ApiError ? err.message : "Backend unreachable" });
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const t = window.setInterval(refreshHealth, 30_000);
    return () => window.clearInterval(t);
  }, [refreshHealth]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(t);
  }, [toast]);

  function systemPromptForRequest(): string | undefined {
    let prompt: string | undefined;
    if (style === "custom" && customPrompt.trim()) prompt = customPrompt.trim();
    else if (style === "concise" || style === "detailed") prompt = `${BASE_PROMPT} ${STYLE_PROMPTS[style]}`;
    if (deepThink) prompt = `${prompt ?? DEFAULT_PROMPT} ${DEEP_THINK}`;
    // The backend keeps a session's override; switching back to Normal must send the default explicitly.
    if (!prompt && sentOverrideRef.current) prompt = DEFAULT_PROMPT;
    if (prompt) sentOverrideRef.current = true;
    return prompt;
  }

  async function send(rawText: string, opts: { retryOf?: ErrorItem } = {}) {
    const text = rawText.trim();
    if (!text || pending) return;
    if (text.length > MAX_MESSAGE_CHARS) return;

    const sim = opts.retryOf ? opts.retryOf.retry?.simulate : simulate ?? undefined;
    if (!opts.retryOf) {
      setInput("");
      setItems((prev) => [...prev, { id: uid("u"), kind: "user", text }]);
    } else {
      const retryId = opts.retryOf.id;
      setItems((prev) => prev.filter((i) => i.id !== retryId));
    }
    setSimulate(null);
    setMode("chat");
    setPending(true);
    setPendingLabel(sim ? `Thinking… (simulating ${sim})` : "Thinking…");

    const body: ChatRequest = { session_id: sessionId, message: text };
    const systemPrompt = systemPromptForRequest();
    if (systemPrompt) body.system_prompt = systemPrompt;

    const pushError = (message: string, retryable: boolean) =>
      setItems((prev) => [
        ...prev,
        { id: uid("e"), kind: "error", text: message, retry: retryable ? { message: text, simulate: sim } : undefined },
      ]);

    try {
      let res: ChatResponse;
      try {
        res = await postChat(body, sim);
      } catch (err) {
        if (err instanceof ApiError && (err.kind === "network" || err.kind === "timeout")) {
          setPendingLabel("Waking up the server… (free hosting can take ~50 s)");
          setHealth({ state: "checking" });
          const up = await waitForServer();
          if (!up) throw err;
          refreshHealth();
          setPendingLabel("Thinking…");
          res = await postChat(body, sim);
        } else {
          throw err;
        }
      }
      setItems((prev) => [...prev, { id: uid("a"), kind: "assistant", text: res.reply, meta: res.metadata }]);
      if (!firstMessageRef.current) firstMessageRef.current = text;
      setRecent(touchRecent(sessionId, firstMessageRef.current));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      const retryable = !(err instanceof ApiError && err.kind === "validation");
      pushError(message, retryable);
      if (err instanceof ApiError && (err.kind === "network" || err.kind === "timeout")) refreshHealth();
    } finally {
      setPending(false);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function newChat() {
    if (pending) return;
    setSessionId(newSessionId());
    setItems([]);
    setInput("");
    setSimulate(null);
    setMode("chat");
    firstMessageRef.current = null;
    sentOverrideRef.current = false;
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  async function openSession(id: string) {
    if (pending) return;
    setDrawer(false);
    try {
      const data = await getHistory(id);
      const loaded: ThreadItem[] = data.messages.map((m) =>
        m.role === "user"
          ? { id: uid("u"), kind: "user", text: m.content }
          : { id: uid("a"), kind: "assistant", text: m.content, meta: (m.metadata ?? {}) as Partial<ChatMetadata> },
      );
      setSessionId(id);
      setItems(loaded);
      setMode("chat");
      firstMessageRef.current = data.messages.find((m) => m.role === "user")?.content ?? null;
      sentOverrideRef.current = false;
    } catch (err) {
      if (err instanceof ApiError && err.kind === "not_found") {
        setRecent(removeRecent(id));
        setToast("That conversation is no longer stored on the server.");
      } else {
        setToast(err instanceof ApiError ? err.message : "Couldn't open that conversation.");
      }
    }
  }

  const showOverview = mode === "overview";

  return (
    <div ref={rootRef} className={`app ${entering ? "is-entering" : ""}`} data-view={showOverview ? "overview" : view}>
      <Rail onHome={newChat} onChat={() => setMode("chat")} onOverview={() => setMode("overview")} mode={mode} />

      <div className="main">
        <div className="glow" aria-hidden="true" />
        <TopBar onBack={newChat} canGoBack={view === "chat" || showOverview} search={search} onSearch={setSearch} onHome={newChat} />
        <SubBar mode={mode} onMode={setMode} health={health} />

        <main className="hero">
          {showOverview ? (
            <Overview health={health} items={items} sessionId={sessionId} />
          ) : (
            <>
              <div className="hero-space hero-space-top" />
              <div className="orb-row">
                <Orb reducedMotion={reducedMotion} thinking={pending} />
              </div>

              <div className="collapse collapse-greeting" inert={view === "chat"}>
                <div className="collapse-inner">
                  <Greeting name={USER_NAME} />
                </div>
              </div>

              {view === "chat" && <Thread items={items} pending={pending} pendingLabel={pendingLabel} onRetry={(item) => send(item.retry?.message ?? "", { retryOf: item })} />}

              <Composer
                value={input}
                onChange={setInput}
                onSend={() => send(input)}
                pending={pending}
                docked={view === "chat"}
                inputRef={inputRef}
                onNewChat={newChat}
                simulate={simulate}
                onSimulate={setSimulate}
                simulationEnabled={simulationEnabled}
                style={style}
                onStyle={setStyle}
                customPrompt={customPrompt}
                onCustomPrompt={setCustomPrompt}
                deepThink={deepThink}
                onDeepThink={setDeepThink}
              />

              <div className="collapse collapse-bottom" inert={view === "chat"}>
                <div className="collapse-inner">
                  <QuickActions onPick={(p) => send(p)} disabled={pending} />
                  <Recent items={recent} onOpen={openSession} onSuggest={(q) => send(q)} onSeeMore={() => setDrawer(true)} query={search} />
                </div>
              </div>
              <div className="hero-space hero-space-bottom" />
            </>
          )}
        </main>
      </div>

      {drawer && (
        <div className="drawer-backdrop" onClick={() => setDrawer(false)}>
          <aside className="drawer" role="dialog" aria-label="All conversations" onClick={(e) => e.stopPropagation()}>
            <header className="drawer-head">
              <h2>All Conversations</h2>
              <button className="tile" onClick={() => setDrawer(false)} aria-label="Close"><IconClose /></button>
            </header>
            <ul className="drawer-list">
              {recent
                .filter((r) => r.title.toLowerCase().includes(search.trim().toLowerCase()))
                .map((r) => (
                  <li key={r.id}>
                    <button className="tree-row" onClick={() => openSession(r.id)}>
                      <span className="tree-q">{r.title}</span>
                      <span className="tree-time">{timeAgo(r.updatedAt)}</span>
                    </button>
                  </li>
                ))}
            </ul>
          </aside>
        </div>
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
