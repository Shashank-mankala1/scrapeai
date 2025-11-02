"use client";
import './globals.css' 
import { useRef, useState } from "react";
export type AskResp = {
  answer: string;
  cites: number[];
  snippets: {
    chunk_index: number;
    score: number;
    text: string;
  }[];
};

type Tab = "summarize" | "ask";
// const [style, setStyle] = useState<"tldr" | "executive" | "notes">("tldr");
// const [docIdCache, setDocIdCache] = useState<Record<string, string>>({});

export default function Home() {
  const [tab, setTab] = useState<Tab>("summarize");
  const [url, setUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [output, setOutput] = useState<string | null>(null);
  const [style, setStyle] = useState<"tldr" | "executive" | "notes">("tldr");
  const docIdCacheRef = useRef<Record<string, string>>({});

  async function ensureDocId(u: string): Promise<string> {
    const cache = docIdCacheRef.current;
    if (cache[u]) return cache[u];

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: u }),
    });
    if (!res.ok) throw new Error(`Ingest failed: ${res.status}`);

    const data = await res.json();
    cache[u] = data.doc_id; // store in ref
    return data.doc_id;
  }

  async function onSummarize() {
    setOutput("⏳ Summarizing...");
    try {
      const doc_id = await ensureDocId(url);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/summarize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ doc_id, style }),
        }
      );
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data: {
        title: string | null;
        tldr: string;
        bullets: { text: string; cites: number[] }[];
      } = await res.json();

      const bulletsFmt = data.bullets
        .map((b) =>
          `• ${b.text} ${b.cites.map((c) => `[#${c}]`).join(" ")}`.trim()
        )
        .join("\n");

      setOutput(
        `# ${data.title ?? "Untitled"}\n\n${data.tldr}\n\n${bulletsFmt}`
      );
    } catch (e: any) {
      setOutput(`❌ ${e.message ?? "Failed to summarize"}`);
    }
  }

  async function onAsk() {
    setOutput("⏳ Answering...");
    try {
      const doc_id = await ensureDocId(url);

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id, question, mode: "llm" }),
      });

      if (!res.ok) {
        let msg = `Server error: ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) msg += ` — ${body.detail}`;
        } catch {}
        throw new Error(msg);
      }

      const data: AskResp = await res.json();
      setData(data);
      const badges = data.cites.map((c) => `[#${c}]`).join(" ");
      setOutput(`${data.answer}\n\n${badges}`);
    } catch (e: any) {
      console.error(e);
      // optional: try extractive once from the UI (in case you left backend strict)
      try {
        const doc_id = await ensureDocId(url);
        const res2 = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/ask`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ doc_id, question, mode: "extractive" }),
          }
        );
        const data2: AskResp = await res2.json();
        setData(data2);
        const badges2 = data2.cites.map((c) => `[#${c}]`).join(" ");
        setOutput(`${data2.answer}\n\n${badges2}`);
      } catch {
        setOutput(`❌ ${e?.message ?? "Failed to answer"}`);
      }
    }
  }

  function formatAnswer(a: string, cites: number[]): string {
    const badges = cites.map((c) => `[#${c}]`).join(" ");
    // normalize accidental double spaces
    const text = a.replace(/\s+/g, " ").trim();
    return `${text}\n\n${badges}`;
  }
  // escape HTML for safe attribute usage
  function escapeHtml(s: string) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // turn [#i] → <span title="snippet">[i]</span>
  function enrichAnswerWithTooltips(answer: string, snippets?: string[]) {
    if (!answer) return "";
    return answer.replace(/\[#(\d+)\]/g, (_m, g1) => {
      const idx = Number(g1) - 1;
      const snip = snippets?.[idx] ?? "Source text unavailable";
      const title = escapeHtml(snip);
      // use a <span> with a native title-tooltip (works everywhere, no libs)
      return `<span class="inline-block align-baseline underline decoration-dotted cursor-help" title="${title}">[${g1}]</span>`;
    });
  }

  const [data, setData] = useState<AskResp | null>(null);
  const [selectedCite, setSelectedCite] = useState<number | null>(null);
  const [showCites, setShowCites] = useState(false);
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold">AI Scrape</h1>
          <p className="text-gray-600">
            Paste a URL. Summarize it or ask questions about it.
          </p>
        </header>

        {/* Tabs */}
        <div className="mb-6 inline-flex rounded-xl border bg-white p-1 shadow-sm">
          <button
            onClick={() => setTab("summarize")}
            className={`rounded-lg px-4 py-2 text-sm ${
              tab === "summarize"
                ? "bg-gray-900 text-white"
                : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            Summarize
          </button>
          <button
            onClick={() => setTab("ask")}
            className={`rounded-lg px-4 py-2 text-sm ${
              tab === "ask"
                ? "bg-gray-900 text-white"
                : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            Ask
          </button>
        </div>

        {/* Form */}
        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <label className="mb-2 block text-sm font-medium">Webpage URL</label>
          <input
            type="url"
            placeholder="https://example.com/article"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="mb-4 w-full rounded-lg border px-3 py-2 outline-none focus:ring"
          />

          {tab === "summarize" ? (
            <>
              <div className="mb-4">
                <label className="mb-1 block text-sm font-medium">Style</label>
                <select
                  className="w-full rounded-lg border px-3 py-2"
                  value={style}
                  onChange={(e) => setStyle(e.target.value as any)}
                >
                  <option value="tldr">TL;DR</option>
                  <option value="executive">Executive</option>
                  <option value="notes">Study Notes</option>
                </select>
              </div>
              <button
                onClick={async () => {
                  setOutput("⏳ Summarizing...");
                  try {
                    const doc_id = await ensureDocId(url);

                    const res = await fetch(
                      `${process.env.NEXT_PUBLIC_API_BASE_URL}/summarize`,
                      {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ doc_id, style }),
                      }
                    );
                    if (!res.ok) throw new Error(`Server error: ${res.status}`);
                    const data: {
                      title: string | null;
                      tldr: string;
                      bullets: { text: string; cites: number[] }[];
                    } = await res.json();

                    const bulletsFmt = data.bullets
                      .map((b) =>
                        `• ${b.text} ${b.cites
                          .map((c) => `[#${c}]`)
                          .join(" ")}`.trim()
                      )
                      .join("\n");

                    setOutput(
                      `# ${data.title ?? "Untitled"}\n\n` +
                        `${data.tldr}\n\n` +
                        `${bulletsFmt}`
                    );
                  } catch (err: any) {
                    console.error(err);
                    setOutput("❌ Failed to summarize. Check API connection.");
                  }
                }}
                className="rounded-lg bg-gray-900 px-4 py-2 text-white"
              >
                Summarize
              </button>
            </>
          ) : (
            <>
              <div className="mb-4">
                <label className="mb-1 block text-sm font-medium">
                  Your question
                </label>
                <input
                  type="text"
                  placeholder="What's the main argument?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 outline-none focus:ring"
                />
              </div>
              <button
                onClick={async () => {
                  setOutput("⏳ Answering...");
                  try {
                    const doc_id = await ensureDocId(url);

                    const res = await fetch(
                      `${process.env.NEXT_PUBLIC_API_BASE_URL}/ask`,
                      {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          doc_id,
                          question,
                          mode: "llm", // UI chooses; backend still supports "extractive"
                        }),
                      }
                    );
                    if (!res.ok) throw new Error(`Server error: ${res.status}`);
                    // const data: {
                    //   answer: string;
                    //   cites: number[];
                    //   snippets: {
                    //     chunk_index: number;
                    //     score: number;
                    //     text: string;
                    //   }[];
                    // } = await res.json();

                    // const citesFmt = data.cites.map((c) => `[#${c}]`).join(" ");
                    // setOutput(formatAnswer(data.answer, data.cites));
                    const data: AskResp = await res.json();
                    setData(data);                  // <-- needed for tooltips + dropdown
                    setSelectedCite(null);          // reset dropdown
                    setOutput("");  
                  } catch (err: any) {
                    console.error(err);
                    setOutput("❌ Failed to answer. Check API connection.");
                  }
                }}
                className="rounded-lg bg-gray-900 px-4 py-2 text-white"
              >
                Ask
              </button>
            </>
          )}
        </section>

        {/* Output */}
        {/* {output && (
          <div className="mt-4 rounded-2xl border bg-white p-5 shadow-sm">
            <div className="text-sm font-semibold text-gray-500 mb-2">
              Result
            </div>
            <div className="prose whitespace-pre-wrap leading-7 text-gray-900">
              {output || "—"}
            </div>

            {data?.snippets?.length ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-gray-600">
                  Sources
                </summary>
                <ul className="mt-2 space-y-2">
                  {data.snippets.map((s, i) => (
                    <li
                      key={i}
                      className="rounded-lg border bg-gray-50 p-3 text-sm"
                    >
                      <div className="mb-1 text-xs text-gray-500">
                        Chunk #{s.chunk_index} • score {s.score.toFixed(3)}
                      </div>
                      <div className="whitespace-pre-wrap">{s.text}</div>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        )} */}
        {/* Output */}
{(data || output) && (
  <div className="mt-4 rounded-2xl border bg-white p-5 shadow-sm">
    <div className="text-sm font-semibold text-gray-500 mb-2">
      Result
    </div>

    {/* If we have LLM data, render enriched HTML with hover-tooltips.
        Otherwise fall back to plain `output` text. */}
    {data ? (
      <>
        {(() => {
          const snippetTexts = data.snippets?.map((s) => s.text) ?? [];
          const enrichedHtml = enrichAnswerWithTooltips(
            data.answer ?? "",
            snippetTexts
          );
          return (
            <div
              className="prose leading-7 text-gray-900"
              dangerouslySetInnerHTML={{ __html: enrichedHtml }}
            />
          );
        })()}
      </>
    ) : (
      <div className="prose whitespace-pre-wrap leading-7 text-gray-900">
        {output || "—"}
      </div>
    )}

    {/* One-dropdown Sources viewer */}
    {/* Citations dropdown — shows ALL citations when opened */}
{data?.snippets?.length ? (
  <div className="mt-4">
    <button
      type="button"
      onClick={() => setShowCites((v) => !v)}
      className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm shadow-sm hover:bg-gray-50"
    >
      {showCites ? "Hide citations" : `See citations (${data.snippets.length})`}
      <span className={`transition-transform ${showCites ? "rotate-180" : ""}`}>
        ▾
      </span>
    </button>

    {showCites && (
      <ul className="mt-3 space-y-3">
        {data.snippets.map((s, i) => (
          <li key={i} id={`cite-${i + 1}`} className="rounded-xl border bg-gray-50 p-3">
            <div className="mb-1 text-xs text-gray-500">
              [#{i + 1}] • chunk #{s.chunk_index} • score {s.score.toFixed(4)}
            </div>
            <div className="whitespace-pre-wrap text-sm leading-6">{s.text}</div>
          </li>
        ))}
      </ul>
    )}
  </div>
) : null}

  </div>
)}

      
      </div>
    </main>
  );
}
