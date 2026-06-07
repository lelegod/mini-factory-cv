"use client";

import { useEffect, useState } from "react";

interface TagImage {
  tag_id: number;
  defect_type?: string;
  image_base64: string;
  timestamp: string;
}

interface DashboardState {
  approved_count: number;
  defective_count: number;
  approved_images: TagImage[];
  defective_images: TagImage[];
  camera_image: string | null;
  last_scan: string | null;
}

const EMPTY: DashboardState = {
  approved_count: 0,
  defective_count: 0,
  approved_images: [],
  defective_images: [],
  camera_image: null,
  last_scan: null,
};

function formatTime(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

function PCBGrid({ images, accent }: { images: TagImage[]; accent: string }) {
  if (images.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-[11px] tracking-widest" style={{ color: "#333" }}>
        NO ITEMS
      </div>
    );
  }
  return (
    <div className="flex-1 overflow-y-auto p-3">
      <div className="flex flex-wrap gap-2">
        {images.map((img, i) => (
          <div key={i} className="relative w-16 h-16 flex-shrink-0 overflow-hidden"
            style={{ border: `1px solid ${accent}33`, background: "#141414" }}>
            {img.image_base64 ? (
              <img src={`data:image/jpeg;base64,${img.image_base64}`} alt={`tag ${img.tag_id}`} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-[9px]" style={{ color: "#333" }}>
                TAG {img.tag_id}
              </div>
            )}
            <div className="absolute bottom-0 left-0 px-1 text-[8px]" style={{ background: "rgba(0,0,0,0.8)", color: "#666" }}>
              {img.tag_id}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface Diagnosis {
  stage: string;
  text: string;
}

const DIAGNOSIS: Record<string, Diagnosis[]> = {
  triangle: [
    { stage: "Solder Reflow", text: "Solder bridge detected across adjacent pads — short-circuit risk on signal trace Q3. Route to rework station for reflow." },
    { stage: "Solder Reflow", text: "Triangular thermal anomaly consistent with overheated transistor junction. Recommend replacing Q2 and inspecting bias network." },
  ],
  circle: [
    { stage: "Pick & Place", text: "Displaced surface-mount capacitor (C7) — component offset from footprint exceeds tolerance. Flag for manual placement correction." },
    { stage: "Solder Paste", text: "Circular void detected in solder fillet — likely cold joint on power rail. Recommend re-soldering and continuity test." },
  ],
  unknown: [
    { stage: "Optical Inspection", text: "Unclassified surface marking detected; optical confidence below threshold. Route for secondary manual inspection." },
    { stage: "Final QA", text: "Anomalous region identified — defect signature does not match known fault library. Escalate to QA engineer." },
  ],
};

function diagnose(tag_id: number, defect_type?: string): Diagnosis {
  const pool = DIAGNOSIS[defect_type ?? "unknown"] ?? DIAGNOSIS.unknown;
  return pool[tag_id % pool.length];
}

function ErrorList({ images }: { images: TagImage[] }) {
  if (images.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-[11px] tracking-widest" style={{ color: "#333" }}>
        NO ERRORS
      </div>
    );
  }
  return (
    <div className="flex-1 overflow-y-auto px-5 py-3 flex flex-col gap-3">
      {images.map((img, i) => {
        const d = diagnose(img.tag_id, img.defect_type);
        return (
          <div key={i} className="flex items-start gap-3 text-[11px] leading-relaxed">
            <span className="font-bold flex-shrink-0" style={{ color: "#EF4444" }}>
              #{String(img.tag_id).padStart(2, "0")}
            </span>
            <span className="uppercase tracking-wider flex-shrink-0" style={{ color: "#EF4444" }}>
              [{img.defect_type ?? "unknown"}]
            </span>
            <div className="flex flex-col gap-1">
              <span className="text-[9px] tracking-[0.15em] uppercase" style={{ color: "#F59E0B" }}>
                ⚙ Stage: {d.stage}
              </span>
              <span style={{ color: "#CCC" }}>{d.text}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardState>(EMPTY);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/state");
        if (res.ok) {
          setData(await res.json());
          setOnline(true);
        }
      } catch {
        setOnline(false);
      }
    };
    poll();
    const interval = setInterval(poll, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-screen" style={{ background: "#0C0C0C" }}>
      <header className="flex justify-between items-center px-6 py-3" style={{ borderBottom: "1px solid #1e1e1e" }}>
        <span className="text-[11px] tracking-[0.15em] uppercase" style={{ color: "#888" }}>
          Mini Factory CV — PCB Inspection
        </span>
        <div className="flex items-center gap-2 text-[11px] tracking-[0.1em]" style={{ color: online ? "#22C55E" : "#555" }}>
          <div className="w-[7px] h-[7px] rounded-full"
            style={{ background: online ? "#22C55E" : "#555", animation: online ? "pulse 1.5s ease-in-out infinite" : "none" }} />
          {online ? "LIVE" : "OFFLINE"}
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden" style={{ gap: "1px", background: "#1a1a1a" }}>
        <div className="flex flex-col w-1/2" style={{ background: "#0C0C0C" }}>
          <div className="text-[10px] tracking-[0.2em] uppercase px-5 py-3" style={{ color: "#555", borderBottom: "1px solid #161616" }}>
            Live Camera
          </div>
          <div className="flex-1 flex items-center justify-center m-4" style={{ background: "#080808", border: "1px solid #1e1e1e" }}>
            {data.camera_image ? (
              <img src={`data:image/jpeg;base64,${data.camera_image}`} alt="camera feed" className="w-full h-full object-contain" />
            ) : (
              <div className="flex flex-col items-center gap-3" style={{ color: "#333" }}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                  <rect x="2" y="6" width="20" height="14" rx="2" />
                  <circle cx="12" cy="13" r="4" />
                  <path d="M8 6V4h8v2" />
                </svg>
                <span className="text-[11px] tracking-[0.15em]">Waiting for feed...</span>
              </div>
            )}
          </div>
          <div className="text-[10px] tracking-[0.1em] px-5 pb-4" style={{ color: "#444" }}>
            Last scan: {formatTime(data.last_scan)}
          </div>
        </div>

        <div className="flex flex-col w-1/2" style={{ gap: "1px", background: "#1a1a1a" }}>
          <div className="flex flex-col flex-1" style={{ background: "#0C0C0C" }}>
            <div className="flex justify-between items-baseline px-5 py-3" style={{ borderBottom: "1px solid #161616" }}>
              <span className="text-[10px] tracking-[0.2em] uppercase" style={{ color: "#EF4444" }}>Defective</span>
              <span className="text-[28px] font-bold leading-none" style={{ color: "#EF4444" }}>
                {String(data.defective_count).padStart(3, "0")}
              </span>
            </div>
            <PCBGrid images={data.defective_images} accent="#EF4444" />
          </div>

          <div className="flex flex-col flex-1" style={{ background: "#0C0C0C" }}>
            <div className="flex justify-between items-center px-5 py-3" style={{ borderBottom: "1px solid #161616" }}>
              <span className="text-[10px] tracking-[0.2em] uppercase" style={{ color: "#888" }}>Error Descriptions</span>
              <span className="flex items-center gap-1.5 text-[9px] tracking-[0.15em] uppercase" style={{ color: "#666" }}>
                <span style={{ color: "#22C55E" }}>✦</span> AI Diagnosis
              </span>
            </div>
            <ErrorList images={data.defective_images} />
          </div>
        </div>
      </main>

      <footer className="flex justify-between items-center px-6 py-2" style={{ borderTop: "1px solid #1a1a1a" }}>
        <span className="text-[10px] tracking-[0.1em]" style={{ color: "#444" }}>Last scan: {formatTime(data.last_scan)}</span>
        <span className="text-[10px] tracking-[0.1em]" style={{ color: "#444" }}>System: {online ? "Online" : "Offline"}</span>
      </footer>

      <style jsx global>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  );
}
