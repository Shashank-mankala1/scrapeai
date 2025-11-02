chrome.action.onClicked.addListener(async (tab) => {
  try {
    // 1) Read page DOM
    const [{ result: html }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.documentElement.outerHTML
    });

    // 2) POST to your FastAPI
    const res = await fetch("http://localhost:8000/ingest_dom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: tab.url, html })
    });
    const json = await res.json();

    // 3) Visible feedback
    const title = json.title || new URL(tab.url).hostname;

    // Badge: ✔ for 3 seconds
    await chrome.action.setBadgeText({ text: "✔" });
    await chrome.action.setBadgeBackgroundColor({ color: "#10b981" });
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);

    // Notification with doc_id
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icon.png",           // add any 128x128 PNG in the extension folder
      title: "AI-Scrape — Ingested",
      message: `${title}\nDoc ID: ${json.doc_id}`
    });

    // 4) (Optional) open your web app with doc_id
    // If your Next.js page can read ?doc_id=..., uncomment this:
    chrome.tabs.create({
      url: `http://localhost:3000/?doc_id=${encodeURIComponent(json.doc_id)}`
    });

  } catch (e) {
    // Show a red badge and a notification on failure
    await chrome.action.setBadgeText({ text: "!" });
    await chrome.action.setBadgeBackgroundColor({ color: "#ef4444" });
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icon.png",
      title: "AI-Scrape — Failed",
      message: String(e)
    });
    console.error("AI-Scrape ingest failed:", e);
  }
});
