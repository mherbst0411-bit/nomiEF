"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, session } from "@/lib/api";
import TopBar from "@/components/TopBar";

const GENRES = [
  "lo-fi", "jazz", "indie rock", "hip hop", "house", "techno", "ambient",
  "r&b", "folk", "classical", "pop", "synthwave", "afrobeats", "country",
];
const MOODS = [
  "chill", "uplifting", "melancholy", "focused", "energetic", "dreamy",
  "warm", "dark", "romantic", "playful",
];

export default function Onboarding() {
  const router = useRouter();
  const userId = session.get();
  const [genres, setGenres] = useState([]);
  const [moods, setMoods] = useState([]);
  const [tempo, setTempo] = useState(100);
  const [energy, setEnergy] = useState(0.5);
  const [vocals, setVocals] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!userId) router.replace("/");
  }, [userId, router]);
  if (!userId) return null;

  const toggle = (list, set, item) =>
    set(list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.onboard(userId, {
        genres,
        moods,
        tempo_bpm: Number(tempo),
        energy: Number(energy),
        prefers_vocals: vocals,
      });
      router.push("/studio");
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="page stack" style={{ maxWidth: 720 }}>
      <TopBar subtitle="onboarding" />
      <h1>Teach Nomi your starting point</h1>
      <p className="muted">
        Pick what already feels like you. This seeds your Nomi Profile —
        from here, it learns from how you actually listen.
      </p>

      <section className="card">
        <h2>Genres you reach for</h2>
        <div>
          {GENRES.map((g) => (
            <button
              key={g}
              type="button"
              className={`chip ${genres.includes(g) ? "on" : ""}`}
              onClick={() => toggle(genres, setGenres, g)}
              aria-pressed={genres.includes(g)}
            >
              {g}
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Moods you live in</h2>
        <div>
          {MOODS.map((m) => (
            <button
              key={m}
              type="button"
              className={`chip ${moods.includes(m) ? "on" : ""}`}
              onClick={() => toggle(moods, setMoods, m)}
              aria-pressed={moods.includes(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Feel</h2>
        <label className="field" htmlFor="tempo">
          Comfortable tempo — {tempo} bpm
        </label>
        <input
          id="tempo" type="range" min="60" max="180" value={tempo}
          onChange={(e) => setTempo(e.target.value)} style={{ width: "100%" }}
        />
        <label className="field" htmlFor="energy">
          Energy — {energy < 0.34 ? "calm" : energy < 0.67 ? "balanced" : "intense"}
        </label>
        <input
          id="energy" type="range" min="0" max="1" step="0.05" value={energy}
          onChange={(e) => setEnergy(e.target.value)} style={{ width: "100%" }}
        />
        <label className="field">Vocals</label>
        <div className="row">
          {[
            ["Mostly vocals", true],
            ["Mostly instrumental", false],
          ].map(([labelText, val]) => (
            <button
              key={labelText}
              type="button"
              className={`chip ${vocals === val ? "on" : ""}`}
              onClick={() => setVocals(vocals === val ? null : val)}
              aria-pressed={vocals === val}
            >
              {labelText}
            </button>
          ))}
        </div>
      </section>

      {error && <p className="error">{error}</p>}
      <div className="row">
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Open the studio"}
        </button>
        <button className="btn btn-ghost" onClick={() => router.push("/studio")}>
          Skip — let Nomi learn from scratch
        </button>
      </div>
    </main>
  );
}
