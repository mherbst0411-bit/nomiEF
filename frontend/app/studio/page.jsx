"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, session } from "@/lib/api";
import ProfilePanel from "@/components/ProfilePanel";
import TopBar from "@/components/TopBar";
import TrackCard from "@/components/TrackCard";

const POLL_MS = 2500;

export default function Studio() {
  const router = useRouter();
  const [userId, setUserId] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [lyrics, setLyrics] = useState("");
  const [strength, setStrength] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    const id = session.get();
    if (!id) router.replace("/");
    else setUserId(id);
  }, [router]);

  const refresh = useCallback(async (id) => {
    const uid = id || userId;
    if (!uid) return;
    try {
      const [p, t] = await Promise.all([api.profile(uid), api.tracks(uid)]);
      setProfileData(p);
      setTracks(t);
      const pending = t.some((x) =>
        x.status === "queued" || x.status === "generating");
      clearTimeout(pollRef.current);
      if (pending) pollRef.current = setTimeout(() => refresh(uid), POLL_MS);
    } catch (err) {
      setError(err.message);
    }
  }, [userId]);

  useEffect(() => {
    if (userId) refresh(userId);
    return () => clearTimeout(pollRef.current);
  }, [userId, refresh]);

  async function generate(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.generate(userId, {
        prompt: prompt.trim(),
        lyrics: lyrics.trim() || null,
        personalization_strength: Number(strength),
      });
      setPrompt("");
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!userId) return null;

  return (
    <main className="page">
      <TopBar subtitle="studio" />

      <div className="studio">
        <ProfilePanel profileData={profileData} />

        <section className="stack">
          <form className="card stack" onSubmit={generate}>
            <h2>Make something</h2>
            <textarea
              className="textarea"
              placeholder="Describe it in your own words — “warm jazz for a rainy Sunday morning”"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              required
              aria-label="Describe the track"
            />
            <details>
              <summary className="muted" style={{ cursor: "pointer" }}>
                Add lyrics (optional)
              </summary>
              <textarea
                className="textarea"
                placeholder="Your words — Nomi will sing them"
                value={lyrics}
                onChange={(e) => setLyrics(e.target.value)}
                aria-label="Lyrics"
              />
            </details>
            <label className="field" htmlFor="strength">
              Nomi’s influence —{" "}
              {strength == 0 ? "off (prompt only)"
                : strength < 0.7 ? "light touch" : "full profile"}
            </label>
            <input
              id="strength" type="range" min="0" max="1" step="0.1"
              value={strength}
              onChange={(e) => setStrength(e.target.value)}
              style={{ width: "100%" }}
            />
            <div className="row">
              <button className="btn btn-primary" disabled={busy || !prompt.trim()}>
                {busy ? "Sending…" : "Generate track"}
              </button>
              {error && <span className="error">{error}</span>}
            </div>
          </form>

          <div className="spread">
            <h2>Your library</h2>
            <span className="track-meta">{tracks.length} tracks</span>
          </div>

          {tracks.length === 0 && (
            <p className="muted">
              Your first track starts the profile. Describe anything above.
            </p>
          )}

          {tracks.map((t) => (
            <TrackCard
              key={t.id}
              userId={userId}
              track={t}
              onFeedback={() => refresh()}
            />
          ))}
        </section>
      </div>
    </main>
  );
}
