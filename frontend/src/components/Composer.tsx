import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { MAX_MESSAGE_CHARS } from "../lib/config";
import { Popover } from "./Popover";
import { IconBolt, IconCaret, IconClose, IconMic, IconPlus, IconSend } from "./Icons";

export type ResponseStyle = "normal" | "concise" | "detailed" | "custom";

export const STYLE_LABELS: Record<ResponseStyle, string> = {
  normal: "Normal",
  concise: "Concise",
  detailed: "Detailed",
  custom: "Custom",
};

export const FAILOVER_PRESETS = [
  { header: "key_1=429", label: "Fail key_1 · 429", hint: "Rate limit on key_1 → key_2 answers" },
  { header: "key_1=500", label: "Fail key_1 · 500", hint: "Server error on key_1 → key_2 answers" },
  { header: "key_1=503", label: "Fail key_1 · 503", hint: "Unavailable on key_1 → key_2 answers" },
  { header: "*=429", label: "Fail all keys · 429", hint: "Every key fails → clean 503, nothing saved" },
];

interface ComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  pending: boolean;
  docked: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  onNewChat: () => void;
  simulate: string | null;
  onSimulate: (header: string | null) => void;
  simulationEnabled: boolean;
  style: ResponseStyle;
  onStyle: (s: ResponseStyle) => void;
  customPrompt: string;
  onCustomPrompt: (v: string) => void;
  deepThink: boolean;
  onDeepThink: (v: boolean) => void;
}

type SpeechCtor = new () => {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function getSpeech(): SpeechCtor | null {
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function Composer(props: ComposerProps) {
  const {
    value, onChange, onSend, pending, docked, inputRef, onNewChat, simulate, onSimulate,
    simulationEnabled, style, onStyle, customPrompt, onCustomPrompt, deepThink, onDeepThink,
  } = props;
  const [customHeader, setCustomHeader] = useState("");
  const [draftPrompt, setDraftPrompt] = useState(customPrompt);
  const [listening, setListening] = useState(false);
  const recRef = useRef<InstanceType<SpeechCtor> | null>(null);
  const speechSupported = typeof window !== "undefined" && getSpeech() !== null;

  const length = value.trim().length;
  const tooLong = length > MAX_MESSAGE_CHARS;
  const canSend = length > 0 && !tooLong && !pending;
  const placement = docked ? "up" : "down";

  useEffect(() => setDraftPrompt(customPrompt), [customPrompt]);

  // Grow the textarea with its content, within the composer's height.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value, inputRef]);

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) onSend();
    }
  }

  function toggleVoice() {
    const Ctor = getSpeech();
    if (!Ctor) return;
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const rec = new Ctor();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e) => {
      const text = Array.from(e.results).map((r) => r[0].transcript).join(" ");
      onChange((value ? value.trimEnd() + " " : "") + text);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }

  return (
    <div className={`composer ${simulate ? "is-armed" : ""}`} data-anim="settle">
      <textarea
        ref={inputRef}
        data-testid="chat-input"
        className="composer-input"
        placeholder="Ask Anything..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        rows={1}
        aria-label="Message"
      />

      <div className="composer-row">
        <div className="composer-chips">
          <Popover
            label="Chat options"
            placement={placement}
            trigger={({ toggle, open }) => (
              <button className={`chip chip-icon ${open ? "is-open" : ""}`} onClick={toggle} aria-label="New chat and failover test" data-testid="composer-plus" title="New chat · Failover test">
                <IconPlus />
              </button>
            )}
          >
            {(close) => (
              <div className="menu">
                <button className="menu-item" onClick={() => { onNewChat(); close(); }}>
                  <span className="menu-title">New chat</span>
                  <span className="menu-hint">Start a fresh session</span>
                </button>
                <div className="menu-sep" />
                <div className="menu-heading">Failover test · next message only</div>
                {!simulationEnabled && <div className="menu-note">Simulation is turned off on this server (ENABLE_FAILURE_SIMULATION).</div>}
                {FAILOVER_PRESETS.map((p) => (
                  <button
                    key={p.header}
                    className={`menu-item ${simulate === p.header ? "is-selected" : ""}`}
                    disabled={!simulationEnabled}
                    onClick={() => { onSimulate(p.header); close(); }}
                  >
                    <span className="menu-title">{p.label}</span>
                    <span className="menu-hint">{p.hint}</span>
                  </button>
                ))}
                <form
                  className="menu-custom"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (customHeader.trim()) { onSimulate(customHeader.trim()); close(); }
                  }}
                >
                  <input
                    value={customHeader}
                    onChange={(e) => setCustomHeader(e.target.value)}
                    placeholder="Custom, e.g. key_1=429,key_2=500"
                    disabled={!simulationEnabled}
                    aria-label="Custom X-Simulate-Failure header"
                  />
                  <button type="submit" disabled={!simulationEnabled || !customHeader.trim()}>Arm</button>
                </form>
              </div>
            )}
          </Popover>

          <Popover
            label="Response style"
            placement={placement}
            trigger={({ toggle, open }) => (
              <button className={`chip ${open ? "is-open" : ""} ${style !== "normal" ? "is-on" : ""}`} onClick={toggle} aria-haspopup="dialog">
                {STYLE_LABELS[style]} <IconCaret className="caret" />
              </button>
            )}
          >
            {(close) => (
              <div className="menu">
                <div className="menu-heading">Response style · this session</div>
                {(["normal", "concise", "detailed"] as ResponseStyle[]).map((s) => (
                  <button key={s} className={`menu-item ${style === s ? "is-selected" : ""}`} onClick={() => { onStyle(s); close(); }}>
                    <span className="menu-title">{STYLE_LABELS[s]}</span>
                    <span className="menu-hint">
                      {s === "normal" ? "Server default system prompt" : s === "concise" ? "Short, direct answers" : "Thorough, structured answers"}
                    </span>
                  </button>
                ))}
                <div className="menu-sep" />
                <div className="menu-heading">Custom system prompt</div>
                <textarea
                  data-testid="system-prompt-input"
                  className="menu-textarea"
                  placeholder="e.g. You are a patient tutor who explains with examples."
                  value={draftPrompt}
                  onChange={(e) => setDraftPrompt(e.target.value)}
                  rows={3}
                  maxLength={8000}
                  aria-label="System prompt for this session"
                />
                <div className="menu-actions">
                  <button
                    className="menu-btn"
                    onClick={() => { onCustomPrompt(draftPrompt.trim()); onStyle(draftPrompt.trim() ? "custom" : "normal"); close(); }}
                  >
                    Use this prompt
                  </button>
                </div>
              </div>
            )}
          </Popover>

          <Popover
            label="Deep Think"
            placement={placement}
            trigger={({ toggle, open }) => (
              <button className={`chip ${open ? "is-open" : ""} ${deepThink ? "is-on" : ""}`} onClick={toggle} aria-haspopup="dialog">
                Deep Think <IconCaret className="caret" />
              </button>
            )}
          >
            {(close) => (
              <div className="menu">
                <div className="menu-heading">Deep Think</div>
                <button className={`menu-item ${!deepThink ? "is-selected" : ""}`} onClick={() => { onDeepThink(false); close(); }}>
                  <span className="menu-title">Off</span>
                  <span className="menu-hint">Answer directly</span>
                </button>
                <button className={`menu-item ${deepThink ? "is-selected" : ""}`} onClick={() => { onDeepThink(true); close(); }}>
                  <span className="menu-title">On</span>
                  <span className="menu-hint">Reason step by step before answering</span>
                </button>
              </div>
            )}
          </Popover>

          {simulate && (
            <span className="armed-tag" title="Sent as X-Simulate-Failure with your next message">
              <IconBolt />
              <span>Sim: {simulate}</span>
              <button onClick={() => onSimulate(null)} aria-label="Cancel failover test"><IconClose /></button>
            </span>
          )}
        </div>

        <div className="composer-actions">
          {length > MAX_MESSAGE_CHARS - 500 && (
            <span className={`counter ${tooLong ? "is-over" : ""}`} aria-live="polite">
              {length}/{MAX_MESSAGE_CHARS}
            </span>
          )}
          <button
            className={`chip chip-voice ${listening ? "is-on" : ""}`}
            onClick={toggleVoice}
            disabled={!speechSupported}
            title={speechSupported ? (listening ? "Stop dictation" : "Dictate a message") : "Voice input isn't supported in this browser"}
          >
            <IconMic /> <span className="chip-label">{listening ? "Listening…" : "Voice"}</span>
          </button>
          <button className="send" data-testid="send-button" onClick={onSend} disabled={!canSend} aria-label="Send message">
            <IconSend />
          </button>
        </div>
      </div>
      {tooLong && <div className="composer-error" role="alert">Messages can be at most {MAX_MESSAGE_CHARS} characters.</div>}
    </div>
  );
}
