"use client";

/* The Nomi Profile, rendered as resonance bars — taste weights drawn like
   frequency bands on a mixing console. Teal = affinity Nomi has learned;
   muted bars = learned aversions. Bars animate as the profile updates,
   making "Nomi is learning" visible in real time. */

function Band({ label, weight }) {
  const pct = Math.round(Math.abs(weight) * 100);
  return (
    <div className="res-row">
      <span className="res-label" title={label}>{label}</span>
      <div className="res-track" role="img"
           aria-label={`${label}: ${weight >= 0 ? "affinity" : "aversion"} ${pct}%`}>
        <div
          className={`res-fill ${weight < 0 ? "negative" : ""}`}
          style={{ width: `${Math.max(pct, 4)}%` }}
        />
      </div>
    </div>
  );
}

function topEntries(dim, k = 5) {
  return Object.entries(dim || {})
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, k)
    .filter(([, w]) => Math.abs(w) > 0.03);
}

export default function ProfilePanel({ profileData }) {
  if (!profileData) return null;
  const { profile, maturity } = profileData;
  const sections = [
    ["Genres", profile.genres],
    ["Moods", profile.moods],
    ["Instruments", profile.instruments],
  ];
  const hasAny = sections.some(([, d]) => topEntries(d).length > 0);

  return (
    <aside className="card stack" aria-label="Your Nomi Profile">
      <div className="spread">
        <h2>Nomi Profile</h2>
        <span className="maturity">{maturity}</span>
      </div>

      {!hasAny && (
        <p className="muted">
          Nothing here yet. Generate a track and react to it — every save,
          skip and replay tunes this profile.
        </p>
      )}

      {sections.map(([name, dim]) => {
        const entries = topEntries(dim);
        if (!entries.length) return null;
        return (
          <div key={name}>
            <p className="track-meta" style={{ margin: "0 0 8px" }}>{name}</p>
            <div className="resonance">
              {entries.map(([tag, w]) => (
                <Band key={tag} label={tag} weight={w} />
              ))}
            </div>
          </div>
        );
      })}

      {profile.tempo?.value && (
        <p className="track-meta">
          tempo ≈ {Math.round(profile.tempo.value)} bpm · energy{" "}
          {profile.energy?.value != null
            ? profile.energy.value.toFixed(2)
            : "—"}{" "}
          · {profile.event_count} signals
        </p>
      )}
    </aside>
  );
}
