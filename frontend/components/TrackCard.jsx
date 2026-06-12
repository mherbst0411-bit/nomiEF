"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";

const FEEDBACK = [
  ["save", "Save"],
  ["like", "Like"],
  ["regenerate", "Another take"],
  ["dislike", "Not for me"],
];

function traceChips(trace) {
  if (!trace?.applied?.length) return [];
  const chips = [];
  for (const a of trace.applied) {
    if (a.tags) chips.push(...a.tags);
    else if (a.dimension === "tempo_bpm") chips.push(`${a.value} bpm`);
    else if (a.dimension === "energy") chips.push(`energy ${a.value}`);
    else if (a.dimension === "vocals") chips.push("vocals");
  }
  return chips.slice(0, 6);
}

export default function TrackCard({ userId, track, onFeedback }) {
  const chips = traceChips(track.personalization_trace);
  const ready = track.status === "ready";
  const generating =
    track.status === "queued" || track.status === "generating";
  const [confirmed, setConfirmed] = useState(null); // event just acknowledged
  const [sending, setSending] = useState(false);
  const fullListenSent = useRef(false);

  async function send(eventType) {
    if (sending) return;
    setSending(true);
    try {
      await api.feedback(userId, track.id, eventType);
      setConfirmed(eventType);
      setTimeout(() => setConfirmed(null), 1600);
      onFeedback?.(eventType, track);
    } finally {
      setSending(false);
    }
  }

  function onEnded() {
    if (fullListenSent.current) return; // count a full listen once
    fullListenSent.current = true;
    send("full_listen");
  }

  return (
    <article className="card track">
      <div className="spread">
        <span className="track-title">{track.title}</span>
        <span className="track-meta">
          <span className={`status-dot status-${track.status}`} aria-hidden />
          {track.status}
          {track.backend ? ` · ${track.backend}` : ""}
        </span>
      </div>

      <p className="muted" style={{ margin: 0 }}>“{track.prompt}”</p>

      {chips.length > 0 && (
        <div aria-label="Personalized because">
          <span className="track-meta">because you like </span>
          {chips.map((c) => (
            <span key={c} className="chip trace">{c}</span>
          ))}
        </div>
      )}

      {generating && (
        <div className="shimmer" role="status" aria-live="polite">
          <span className="track-meta">Nomi is shaping it…</span>
        </div>
      )}

      {ready && (
        <>
          <audio
            controls
            preload="none"
            src={api.audioUrl(userId, track.id)}
            onEnded={onEnded}
          />
          <div className="row" aria-live="polite">
            {FEEDBACK.map(([type, labelText]) => (
              <button
                key={type}
                className={`btn btn-sm ${confirmed === type ? "btn-confirmed" : ""}`}
                disabled={sending}
                onClick={() => send(type)}
              >
                {confirmed === type ? "✓ Profile tuned" : labelText}
              </button>
            ))}
          </div>
        </>
      )}

      {track.status === "failed" && (
        <p className="error">
          Generation failed{track.error ? ` — ${track.error}` : ""}. Try the
          prompt again.
        </p>
      )}
    </article>
  );
}
