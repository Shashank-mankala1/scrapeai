const API_BASE = "https://ai-scrape-api-72345269003.us-central1.run.app/";
const $ = (id) => document.getElementById(id);
const setStatus = (t) => ($("status").textContent = t || "");
const showResult = (t) => { const el = $("result"); el.style.display = t ? "block" : "none"; el.textContent = t || ""; };

// NEW: mode switcher
function setMode(mode) {
  const askRow = $("askRow");
  const btnSum = $("btnSummarize");
  const btnAsk = $("btnAsk");
  const sumRow = $("summarizeRow");

  if (mode === "ask") {
    sumRow.style.display = "none";
    askRow.classList.remove("hidden");
    btnAsk.classList.add("btn-primary");
    btnAsk.classList.remove("btn-secondary");
    btnSum.classList.remove("btn-primary");
    btnSum.classList.add("btn-secondary");

    showResult("");          // ← clear old summary when entering Ask
    setStatus("");           // ← optional: clear status too
    $("question").focus();
  } else { // summarize
    sumRow.style.display = "block";
    askRow.classList.add("hidden");
    $("question").value = "";
    btnSum.classList.add("btn-primary");
    btnSum.classList.remove("btn-secondary");
    btnAsk.classList.remove("btn-primary");
    btnAsk.classList.add("btn-secondary");

    showResult("");          // ← clear old ask answer when going back
    setStatus("");           // ← optional
  }
}
function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function enrichAnswerWithAnchors(answer) {
  // change [#3] -> <a href="#cite-3" class="cite-link">[3]</a>
  return (answer || "").replace(/\[#(\d+)\]/g, (_, n) =>
    `<a href="#cite-${n}" class="cite-link" style="text-decoration:underline; cursor:pointer;">[${n}]</a>`
  );
}

function renderCitations(snippets) {
  const wrap = $("citesWrap");
  const btn = $("btnToggleCites");
  const list = $("citesList");

  if (!snippets || !snippets.length) {
    wrap.style.display = "none";
    list.innerHTML = "";
    return;
  }

  wrap.style.display = "block";
  btn.textContent = `See citations (${snippets.length}) ▾`;

  // build the list
  list.innerHTML = snippets.map((s, i) => {
    const idx = i + 1;
    const header = `[#${idx}] • chunk #${s.chunk_index} • score ${s.score.toFixed(3)}`;
    return `
      <li id="cite-${idx}" style="border:1px solid #eee; border-radius:8px; padding:8px; margin-bottom:8px;">
        <div style="font-size:11px; color:#666; margin-bottom:4px;">${escapeHtml(header)}</div>
        <div style="white-space:pre-wrap; font-size:13px; line-height:1.4;">${escapeHtml(s.text)}</div>
      </li>
    `;
  }).join("");

  // toggle open/close
  btn.onclick = () => {
    const open = list.style.display !== "none";
    list.style.display = open ? "none" : "block";
    btn.textContent = open ? `See citations (${snippets.length}) ▾` : `Hide citations (${snippets.length}) ▴`;
  };

  // delegate clicks on answer anchors to scroll to items
  document.addEventListener("click", (e) => {
    const a = e.target.closest(".cite-link");
    if (!a) return;
    const id = a.getAttribute("href").slice(1); // e.g., cite-3
    // ensure list is open and scroll into view
    list.style.display = "block";
    btn.textContent = `Hide citations (${snippets.length}) ▴`;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    e.preventDefault();
  }, { once: true }); // add per-render to keep simple
}


async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}
async function getDOM(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId }, func: () => document.documentElement.outerHTML
  });
  return result;
}
async function ingestDOM(url, html) {
  const res = await fetch(`${API_BASE}/ingest_dom`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, html })
  });
  if (!res.ok) throw new Error(`ingest_dom failed: ${res.status}`);
  return res.json();
}
async function summarize(doc_id) {
  const res = await fetch(`${API_BASE}/summarize`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_id, style: "tldr" })
  });
  if (!res.ok) throw new Error(`summarize failed: ${res.status}`);
  return res.json();
}
async function ask(doc_id, question) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_id, question, mode: "llm" })
  });
  if (!res.ok) throw new Error(`ask failed: ${res.status}`);
  return res.json();
}

async function runSummarize(tab) {
  try {
    setMode("summarize");           // ensure ask UI hidden & button styles correct
    setStatus("Reading page…"); showResult("");
    const html = await getDOM(tab.id);

    setStatus("Ingesting…");
    const ing = await ingestDOM(tab.url, html);

    setStatus("Summarizing…");
    const s = await summarize(ing.doc_id);
    const out = [
      s.title ? `# ${s.title}\n` : "",
      s.tldr ? s.tldr + "\n" : "",
      ...(s.bullets || []).map(b => `• ${b.text || b}`),
    ].join("\n");
    showResult("");                // clear
    $("result").innerHTML = escapeHtml(out.trim()); // summaries have no cites; keep plain
    $("result").style.display = "block";
    setStatus("Done ✓");
    renderCitations([]); 
  } catch (e) { setStatus("Error"); showResult(String(e)); console.error(e); }
}

async function runAsk(tab, q) {
  try {
    setMode("ask");                 // ensure Ask button is black
    setStatus("Reading page…"); showResult("");
    const html = await getDOM(tab.id);

    setStatus("Ingesting…");
    const ing = await ingestDOM(tab.url, html);

    setStatus("Asking…");
    const a = await ask(ing.doc_id, q);
    const cites = (a.cites || []).map(n => `[#${n}]`).join(" ");
    const out = `${a.answer || ""}\n\n${cites}`;
    const htmlAnswer = enrichAnswerWithAnchors(a.answer || "");
    showResult("");  // clear textContent
    $("result").innerHTML = htmlAnswer;
    $("result").style.display = "block";
    setStatus(a.degraded ? "Done (extractive fallback)" : "Done ✓");

    // show all snippets under a toggle
    renderCitations(a.snippets || []);
  } catch (e) { setStatus("Error"); showResult(String(e)); console.error(e); }
}

async function init() {
  const tab = await getCurrentTab();
  $("url").value = tab.url;

  // top buttons
  $("btnSummarize").addEventListener("click", () => runSummarize(tab));
  $("btnAsk").addEventListener("click", () => setMode("ask"));

  // ask row buttons
  $("btnRunAsk").addEventListener("click", () => {
    const q = $("question").value.trim();
    if (!q) { $("question").focus(); return; }
    runAsk(tab, q);
  });
  $("btnCancelAsk").addEventListener("click", () => {
    setMode("summarize");
  });

  // auto-summarize on open
  const goBtn = document.getElementById("btnGo");
  if (goBtn) {
    goBtn.addEventListener("click", () => runSummarize(tab));
  }
  setMode("summarize");
//   runSummarize(tab);
}

init().catch(console.error);
