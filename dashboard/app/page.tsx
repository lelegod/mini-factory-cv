"use client";

import { useEffect, useRef, useState } from "react";

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
  problem: string;
  explanation: string;
  solution: string;
  machine: string;
}

const DIAGNOSIS: Record<string, Diagnosis[]> = {
  triangle: [
    {
      problem: "Solder Bridge Short",
      explanation: "Excess solder has bridged adjacent pads on signal trace Q3, creating a short-circuit path.",
      solution: "Route board to rework station and reflow the affected joints; verify continuity after.",
      machine: "Reflow Oven (Stage 4)",
    },
    {
      problem: "Transistor Overheat",
      explanation: "Thermal signature indicates an overheated transistor junction at Q2, likely from a biasing fault.",
      solution: "Replace Q2 and inspect the surrounding bias resistor network for drift.",
      machine: "Reflow Oven (Stage 4)",
    },
  ],
  circle: [
    {
      problem: "Component Misplacement",
      explanation: "Surface-mount capacitor C7 is offset from its footprint beyond placement tolerance.",
      solution: "Flag for manual placement correction and re-run optical alignment check.",
      machine: "Pick & Place (Stage 2)",
    },
    {
      problem: "Cold Solder Joint",
      explanation: "A void in the solder fillet on the power rail suggests an unreliable cold joint.",
      solution: "Re-solder the joint and perform a continuity and load test.",
      machine: "Solder Paste Printer (Stage 1)",
    },
  ],
  unknown: [
    {
      problem: "Unclassified Anomaly",
      explanation: "A surface marking was detected but optical confidence is below the classification threshold.",
      solution: "Route for secondary manual inspection by a QA technician.",
      machine: "Optical Inspection (Stage 5)",
    },
  ],
};

function diagnose(tag_id: number, defect_type?: string): Diagnosis {
  const pool = DIAGNOSIS[defect_type ?? "unknown"] ?? DIAGNOSIS.unknown;
  return pool[tag_id % pool.length];
}

function buildContext(images: TagImage[]): string {
  if (images.length === 0) return "";
  return images
    .map((img, i) => {
      const d = diagnose(img.tag_id, img.defect_type);
      return [
        `Defect ${i + 1}:`,
        `  Tag ID: ${img.tag_id}`,
        `  Defect type: ${img.defect_type ?? "unknown"}`,
        `  Problem: ${d.problem}`,
        `  Explanation: ${d.explanation}`,
        `  Recommended solution: ${d.solution}`,
        `  Machine/stage to check: ${d.machine}`,
      ].join("\n");
    })
    .join("\n\n");
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
    <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
      {images.map((img, i) => {
        const d = diagnose(img.tag_id, img.defect_type);
        return (
          <div key={i} className="text-[11px] leading-relaxed">
            {/* Title row */}
            <div className="flex items-center gap-2 mb-2">
              <span className="font-bold" style={{ color: "#EF4444" }}>
                #{String(img.tag_id).padStart(2, "0")}
              </span>
              <span className="font-bold tracking-wide" style={{ color: "#EF4444" }}>
                {d.problem}
              </span>
              <span className="uppercase text-[9px] tracking-wider" style={{ color: "#666" }}>
                [{img.defect_type ?? "unknown"}]
              </span>
            </div>
            {/* Bullet points */}
            <ul className="flex flex-col gap-1 pl-1" style={{ color: "#AAA" }}>
              <li className="flex gap-2">
                <span style={{ color: "#555" }}>•</span>
                <span><span style={{ color: "#888" }}>Explanation:</span> {d.explanation}</span>
              </li>
              <li className="flex gap-2">
                <span style={{ color: "#555" }}>•</span>
                <span><span style={{ color: "#888" }}>Solution:</span> {d.solution}</span>
              </li>
              <li className="flex gap-2">
                <span style={{ color: "#555" }}>•</span>
                <span><span style={{ color: "#888" }}>Check Machine:</span> <span style={{ color: "#F59E0B" }}>{d.machine}</span></span>
              </li>
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardState>(EMPTY);
  const [online, setOnline] = useState(false);
  // Error descriptions update on a slower cadence so they don't flicker
  const [errorImages, setErrorImages] = useState<TagImage[]>([]);
  const latest = useRef<TagImage[]>([]);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/state");
        if (res.ok) {
          const json: DashboardState = await res.json();
          setData(json);
          latest.current = json.defective_images;
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

  // Snapshot the error list every 5s
  useEffect(() => {
    setErrorImages(latest.current);
    const interval = setInterval(() => setErrorImages(latest.current), 5000);
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
            <ErrorList images={errorImages} />
          </div>
        </div>
      </main>

      <footer className="flex justify-between items-center px-6 py-2" style={{ borderTop: "1px solid #1a1a1a" }}>
        <span className="text-[10px] tracking-[0.1em]" style={{ color: "#444" }}>Last scan: {formatTime(data.last_scan)}</span>
        <span className="text-[10px] tracking-[0.1em]" style={{ color: "#444" }}>System: {online ? "Online" : "Offline"}</span>
      </footer>

      <ChatPopup context={buildContext(data.defective_images)} />

      <style jsx global>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .chat-typing { animation: pulse 1s ease-in-out infinite; letter-spacing: 2px; }
      `}</style>
    </div>
  );
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

// Lightweight renderer: **bold** segments and line breaks
function formatMessage(text: string) {
  return text.split("\n").map((line, li) => (
    <span key={li}>
      {li > 0 && <br />}
      {line.split(/(\*\*[^*]+\*\*)/g).map((part, pi) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={pi} style={{ color: "#FFF" }}>
            {part.slice(2, -2)}
          </strong>
        ) : (
          <span key={pi}>{part}</span>
        )
      )}
    </span>
  ));
}

function ChatPopup({ context }: { context: string }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: "Hi — ask me about the current inspection results." },
  ]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const next = [...messages, { role: "user" as const, text }];
    setMessages(next);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next, context }),
      });
      const json = await res.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", text: json.reply ?? json.error ?? "(no response)" },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Connection error — please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end">
      <div
        className="mb-3 flex flex-col w-80 h-96 overflow-hidden origin-bottom-right"
        style={{
          background: "#161616",
          border: "1px solid #333",
          borderRadius: "8px",
          boxShadow: "0 12px 40px rgba(0,0,0,0.7)",
          transition: "opacity 220ms ease, transform 220ms cubic-bezier(0.22, 1, 0.36, 1)",
          opacity: open ? 1 : 0,
          transform: open ? "translateY(0) scale(1)" : "translateY(12px) scale(0.92)",
          pointerEvents: open ? "auto" : "none",
        }}
      >
          {/* Header */}
          <div
            className="flex justify-between items-center px-4 py-3"
            style={{ background: "#1c1c1c", borderBottom: "1px solid #333" }}
          >
            <span className="flex items-center gap-2 text-[10px] tracking-[0.2em] uppercase" style={{ color: "#888" }}>
              <span style={{ color: "#22C55E" }}>✦</span> Inspection Assistant
            </span>
            <button onClick={() => setOpen(false)} className="text-[14px] leading-none" style={{ color: "#666" }}>
              ✕
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className="max-w-[80%] px-3 py-2 text-[11px] leading-relaxed"
                  style={{
                    background: m.role === "user" ? "#22C55E" : "#242424",
                    color: m.role === "user" ? "#0C0C0C" : "#DDD",
                    borderRadius: "6px",
                    border: m.role === "assistant" ? "1px solid #333" : "none",
                  }}
                >
                  {m.role === "assistant" ? formatMessage(m.text) : m.text}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div
                  className="px-3 py-2 text-[11px]"
                  style={{ background: "#242424", color: "#888", borderRadius: "6px", border: "1px solid #333" }}
                >
                  <span className="chat-typing">●●●</span>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div className="flex items-center gap-2 px-3 py-3" style={{ borderTop: "1px solid #333" }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Ask about defects…"
              className="flex-1 bg-transparent outline-none text-[11px]"
              style={{ color: "#E0E0E0" }}
            />
            <button
              onClick={send}
              className="text-[10px] tracking-[0.15em] uppercase px-3 py-1.5"
              style={{ background: "#22C55E", color: "#0C0C0C", borderRadius: "4px" }}
            >
              Send
            </button>
          </div>
      </div>

      {/* Toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-center w-12 h-12 shadow-lg"
        style={{ background: "#22C55E", color: "#0C0C0C", borderRadius: "50%" }}
        aria-label="Toggle chat"
      >
        {open ? (
          <span className="text-[18px] leading-none">✕</span>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}
      </button>
    </div>
  );
}
