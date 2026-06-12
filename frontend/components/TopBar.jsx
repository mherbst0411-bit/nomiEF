"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, session } from "@/lib/api";

/* Slim app bar shared by onboarding + studio. The account menu surfaces the
   privacy endpoints that already exist in the API: full data export and
   hard delete — "your taste profile belongs to you" made literal. */

export default function TopBar({ subtitle }) {
  const router = useRouter();
  const [userId, setUserId] = useState(null);
  useEffect(() => setUserId(session.get()), []);

  async function exportData() {
    const data = await api.exportData(userId);
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "nomi-export.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function switchListener() {
    session.clear();
    router.push("/");
  }

  async function deleteAccount() {
    const ok = window.confirm(
      "Delete your account? This permanently removes your taste profile, " +
        "tracks and audio. There is no undo."
    );
    if (!ok) return;
    await api.deleteUser(userId);
    session.clear();
    router.push("/");
  }

  return (
    <header className="topbar">
      <a className="topbar-mark" href="/studio" aria-label="Nomi home">
        nomi<span className="knows">.</span>
        {subtitle && <span className="topbar-sub">{subtitle}</span>}
      </a>
      {userId && (
        <details className="menu">
          <summary className="btn btn-ghost btn-sm">Account</summary>
          <div className="menu-pop" role="menu">
            <button className="menu-item" onClick={exportData}>
              Export my data
            </button>
            <button className="menu-item" onClick={switchListener}>
              Switch listener
            </button>
            <button className="menu-item danger" onClick={deleteAccount}>
              Delete account
            </button>
          </div>
        </details>
      )}
    </header>
  );
}
