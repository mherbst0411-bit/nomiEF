"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, session } from "@/lib/api";

export default function Welcome() {
  const router = useRouter();
  const [handle, setHandle] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function start(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await api.createUser(handle.trim());
      session.set(user.id);
      router.push("/onboarding");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="wordmark">
          nomi<span className="knows">.</span>
        </div>
        <p className="tagline">
          Music that knows you. Nomi learns your taste with every listen and
          shapes each new track around it.
        </p>
        <form onSubmit={start} className="row" style={{ justifyContent: "center" }}>
          <input
            className="input"
            style={{ maxWidth: 260 }}
            placeholder="Pick a handle"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            minLength={2}
            required
            aria-label="Handle"
          />
          <button className="btn btn-primary" disabled={busy || handle.trim().length < 2}>
            {busy ? "Creating…" : "Start listening"}
          </button>
        </form>
        <p className="muted" style={{ maxWidth: 460, margin: "0 auto" }}>
          By starting, you accept the Nomi Terms and Privacy Policy. Your taste
          profile belongs to you — export or delete it anytime.
        </p>
        {error && <p className="error">{error}</p>}
      </section>
    </main>
  );
}
