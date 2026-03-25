const $ = (id) => document.getElementById(id);

const tickerInput = $("tickerInput");
const horizonInput = $("horizonInput");
const runBtn = $("runBtn");
const cancelBtn = $("cancelBtn");

const statusBox = $("statusBox");
const spinner = $("spinner");
const statusTitle = statusBox.querySelector(".status-title");
const statusSub = statusBox.querySelector(".status-sub");

const outputPanel = $("outputPanel");

const marketBody = $("marketBody");
const marketSkeleton = $("marketSkeleton");
const recBody = $("recBody");
const recSkeleton = $("recSkeleton");
const reportBody = $("reportBody");
const reportSkeleton = $("reportSkeleton");
const auditPre = $("auditPre");
const disclaimerBox = $("disclaimerBox");

const recBadge = $("recBadge");
const thesisConf = $("thesisConf");
const asOfLine = $("asOfLine");
const buyCount = $("buyCount");
const holdCount = $("holdCount");
const sellCount = $("sellCount");
const stanceGrid = $("stanceGrid");

let es = null;
let latestState = {};
const dataPill = $("dataPill");
const themeToggle = $("themeToggle");

function applyTheme(theme) {
  // theme: 'light' | 'dark'
  document.documentElement.dataset.theme = theme;
  if (themeToggle) themeToggle.textContent = theme === "dark" ? "Dark" : "Light";
}

function initTheme() {
  const saved = localStorage.getItem("stockAnalystTheme");
  if (saved === "dark" || saved === "light") {
    applyTheme(saved);
    return;
  }
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(prefersDark ? "dark" : "light");
}

function directionBucket(direction) {
  const d = (direction || "neutral").toLowerCase();
  if (d === "bullish") return "buy";
  if (d === "bearish") return "sell";
  return "hold";
}

function overallRecommendation(weightedSignals) {
  if (!Array.isArray(weightedSignals) || weightedSignals.length === 0) return "Hold";

  const bull = weightedSignals
    .filter((s) => s.direction === "bullish")
    .reduce((acc, s) => acc + Number(s.score || 0), 0);
  const bear = weightedSignals
    .filter((s) => s.direction === "bearish")
    .reduce((acc, s) => acc + Number(s.score || 0), 0);

  const net = bull - bear;
  const scale = bull + bear + 1e-9;
  const norm = net / scale;

  if (norm > 0.12) return "Buy";
  if (norm < -0.12) return "Sell";
  return "Hold";
}

function bucketSignals(weightedSignals) {
  const buy = [];
  const hold = [];
  const sell = [];

  (weightedSignals || []).forEach((s) => {
    const b = directionBucket(s.direction);
    if (b === "buy") buy.push(s);
    else if (b === "sell") sell.push(s);
    else hold.push(s);
  });

  const byScore = (a, b) => Number(b.score || 0) - Number(a.score || 0);
  buy.sort(byScore);
  hold.sort(byScore);
  sell.sort(byScore);

  return { buy, hold, sell };
}

function setStatus(title, sub, isRunning) {
  statusTitle.textContent = title;
  statusSub.textContent = sub || "";
  spinner.classList.toggle("on", !!isRunning);
}

function clearDashboard() {
  latestState = {};

  marketBody.hidden = true;
  marketSkeleton.style.display = "block";
  recBody.hidden = true;
  recSkeleton.style.display = "block";
  reportBody.hidden = true;
  reportSkeleton.style.display = "block";

  recBadge.classList.remove("buy", "hold", "sell");
  recBadge.textContent = "—";
  thesisConf.textContent = "Thesis confidence: —";
  asOfLine.textContent = "—";
  buyCount.textContent = "0";
  holdCount.textContent = "0";
  sellCount.textContent = "0";
  stanceGrid.innerHTML = "";

  reportBody.innerHTML = "";
  auditPre.textContent = "{}";
  disclaimerBox.textContent = "";
}

function fmtPct(v) {
  const x = Number(v);
  if (!Number.isFinite(x)) return "—";
  return `${x.toFixed(1)}%`;
}

function fmtNum(v) {
  const x = Number(v);
  if (!Number.isFinite(x)) return "—";
  return `${x}`;
}

function renderMarketSnapshot(ms) {
  if (!ms || typeof ms !== "object") return;

  const q = ms.quote || {};
  const m = ms.metrics || {};
  const p = ms.profile || {};

  const name = q.name || latestState.ticker || "—";
  const sector = p.sector || "—";
  const industry = p.industry || "—";

  marketBody.hidden = false;
  marketSkeleton.style.display = "none";

  const cards = [];
  const price = q.price;
  const curr = q.currency || "";

  cards.push(`<div class="market-name subtle">${name}</div>`);
  cards.push(`<div class="market-subline rec-small">*${sector}* · ${industry}</div>`);

  if (ms.error) {
    cards.push(`<div class="market-error">Market data error: ${ms.error}</div>`);
  } else {
    cards.push(`
      <div class="mix-row market-metrics">
        <div class="mix-item"><div class="mix-label">Last price</div><div class="mix-value">${price != null ? `${fmtNum(price)} ${curr}`.trim() : "—"}</div></div>
        <div class="mix-item"><div class="mix-label">P/E</div><div class="mix-value">${m.pe_trailing != null ? `${fmtNum(m.pe_trailing)}` : "—"}</div></div>
        <div class="mix-item"><div class="mix-label">YTD</div><div class="mix-value">${m.ytd_return_pct != null ? fmtPct(m.ytd_return_pct) : "—"}</div></div>
        <div class="mix-item"><div class="mix-label">52w</div><div class="mix-value">${m.distance_from_52w_high_pct != null ? fmtPct(m.distance_from_52w_high_pct) : "—"}</div></div>
      </div>
    `);

    if (m.position_in_52w_range_pct != null) {
      const pos = Number(m.position_in_52w_range_pct);
      const pct = Math.max(0, Math.min(100, pos));
      cards.push(`
        <div class="market-range-block">
          <div class="subtle">Position in 52-week range</div>
          <div class="market-range-track">
            <div class="market-range-fill" style="--pct:${pct}"></div>
          </div>
          <div class="market-range-caption">0 = low • 100 = high</div>
        </div>
      `);
    }
  }

  marketBody.innerHTML = cards.join("");
}

function renderRecommendationAndSignals(state) {
  const weighted = state.weighted_signals || [];
  const thesis = state.final_thesis || {};

  const rec = overallRecommendation(weighted);
  recBadge.textContent = rec;
  recBadge.classList.remove("buy", "hold", "sell");
  recBadge.classList.add(rec === "Buy" ? "buy" : rec === "Sell" ? "sell" : "hold");

  const conf = Number(thesis.confidence_score || 0);
  thesisConf.textContent = `Thesis confidence: ${(conf * 100).toFixed(0)}%`;

  const ms = state.market_snapshot || {};
  const asOf = ms.as_of_utc ? new Date(ms.as_of_utc).toLocaleString() : "";
  asOfLine.textContent = asOf ? `As-of: ${asOf} (UTC)` : `As-of: —`;

  const { buy, hold, sell } = bucketSignals(weighted);
  buyCount.textContent = buy.length;
  holdCount.textContent = hold.length;
  sellCount.textContent = sell.length;

  // Stance cards
  const mkBucket = (title, bucket) => {
    const items = (bucket || []).slice(0, 6).map((s) => {
      const topic = s.topic || s.source_type || "Signal";
      const score = Number(s.score || 0);
      return `
        <div class="signal">
          <div class="signal-topic">${topic} · ${score.toFixed(2)}</div>
          <div class="signal-claim">${escapeHtml(s.claim || "")}</div>
          <div class="signal-meta">${escapeHtml(s.source_type || "—")} · Confidence ${Number(s.confidence || 0).toFixed(2)}</div>
          ${s.source ? `<div class="signal-meta">Source: ${escapeHtml(s.source)}</div>` : ""}
        </div>
      `;
    });
    return `
      <div class="stance-bucket">
        <div class="stance-title">${title} (${(bucket || []).length})</div>
        <div class="signal-list">${items.length ? items.join("") : `<div class="empty-state">No signals.</div>`}</div>
      </div>
    `;
  };

  stanceGrid.innerHTML = [
    mkBucket("Buy", buy),
    mkBucket("Hold", hold),
    mkBucket("Sell", sell),
  ].join("");

  recBody.hidden = false;
  recSkeleton.style.display = "none";
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function repairMarkdown(md) {
  const text = String(md || "");
  // If the model emits an unclosed fenced code block, everything after it
  // renders as code. Close it defensively.
  const fenceMatches = text.match(/```/g);
  const fenceCount = fenceMatches ? fenceMatches.length : 0;
  let fixed = text;
  if (fenceCount % 2 === 1) {
    fixed = `${fixed}\n\n\`\`\`\n`;
  }

  // Unwrap fenced blocks that are actually markdown prose/headings, not code.
  // Keep true code fences like json/bash/python.
  const lines = fixed.split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const start = lines[i].match(/^```(\w+)?\s*$/);
    if (!start) {
      out.push(lines[i]);
      i += 1;
      continue;
    }

    const lang = (start[1] || "").toLowerCase();
    const block = [];
    let j = i + 1;
    while (j < lines.length && !/^```\s*$/.test(lines[j])) {
      block.push(lines[j]);
      j += 1;
    }

    const isClosed = j < lines.length && /^```\s*$/.test(lines[j]);
    const blockText = block.join("\n");
    const looksLikeMarkdownProse =
      /(^|\n)\s{0,3}#{1,6}\s+\S/.test(blockText) ||
      /(^|\n)\s*[-*]\s+\S/.test(blockText) ||
      /\*\*[^*]+\*\*/.test(blockText);
    const proseFenceLang = !lang || lang === "md" || lang === "markdown" || lang === "text";
    const shouldUnwrap = proseFenceLang && looksLikeMarkdownProse;

    if (shouldUnwrap) {
      out.push(...block);
    } else {
      out.push(lines[i], ...block);
      if (isClosed) out.push(lines[j]);
    }

    i = isClosed ? j + 1 : j;
  }

  return out.join("\n");
}

function renderReport(reportMarkdown) {
  if (!reportMarkdown) return;

  reportBody.hidden = false;
  reportSkeleton.style.display = "none";
  const safeMarkdown = repairMarkdown(reportMarkdown);
  let html = "";
  if (window.marked && typeof window.marked.parse === "function") {
    html = window.marked.parse(safeMarkdown);
  } else {
    // Lightweight fallback if CDN markdown parser is unavailable.
    html = safeMarkdown
      .replace(/^### (.*)$/gm, "<h3>$1</h3>")
      .replace(/^## (.*)$/gm, "<h2>$1</h2>")
      .replace(/^# (.*)$/gm, "<h1>$1</h1>")
      .replace(/\n/g, "<br/>");
  }

  if (window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
    reportBody.innerHTML = window.DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
  } else {
    reportBody.innerHTML = html;
  }
}

function renderAuditAndDisclaimer(state) {
  // Mirror disclaimer from the report markdown so the page stays self-contained.
  const audit = state.audit || {};
  auditPre.textContent = JSON.stringify(audit, null, 2);

  if (dataPill) {
    const news = audit.news_data_mode || "mock";
    const fin = audit.financial_data_mode || "mock";
    const soc = audit.social_data_mode || "mock";
    const tav = audit.tavily_api_configured ? "Tavily on" : "Tavily off";
    dataPill.textContent = `Data: news=${news}, financial=${fin}, social=${soc} • ${tav}`;
  }

  const report = String(state.report || "");
  const importantMarker = "**Important**";
  if (!report.includes(importantMarker)) {
    disclaimerBox.textContent = "Disclaimer is included in the analyst report.";
    return;
  }

  // Backend disclaimer starts with a '---' marker.
  const markerIdx = report.lastIndexOf(importantMarker);
  const startIdx = report.lastIndexOf("---", markerIdx);
  const discMd = startIdx >= 0 ? report.slice(startIdx).trim() : report.slice(markerIdx).trim();

  const html = marked.parse(discMd);
  disclaimerBox.innerHTML = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

function onStateUpdate(newState) {
  latestState = { ...latestState, ...newState };

  if (newState.market_snapshot && newState.market_snapshot.quote) {
    renderMarketSnapshot(newState.market_snapshot);
  } else if (latestState.market_snapshot && latestState.market_snapshot.quote) {
    renderMarketSnapshot(latestState.market_snapshot);
  }

  if (latestState.weighted_signals && Array.isArray(latestState.weighted_signals) && latestState.weighted_signals.length >= 0) {
    // Only render when we have thesis populated too (prevents half-state flicker).
    if (latestState.final_thesis && Object.keys(latestState.final_thesis).length) {
      renderRecommendationAndSignals(latestState);
    }
  }

  if (latestState.report && String(latestState.report).trim().length > 0) {
    // Make recommendation visible as soon as we know the final thesis exists.
    if (
      latestState.weighted_signals &&
      Array.isArray(latestState.weighted_signals) &&
      latestState.final_thesis &&
      Object.keys(latestState.final_thesis).length
    ) {
      renderRecommendationAndSignals(latestState);
    }

    renderReport(latestState.report);
    renderAuditAndDisclaimer(latestState);
    setStatus("Complete", "Report generated successfully.", false);
    if (es) es.close();
    cancelBtn.disabled = true;
    runBtn.disabled = false;
  }

  const it = latestState.iteration_count;
  if (Number.isFinite(Number(it)) && String(statusTitle.textContent) !== "Complete") {
    setStatus("Running pipeline", `Iteration ${it}…`, true);
  }
}

function connectStream(ticker, horizon) {
  if (es) es.close();
  clearDashboard();
  outputPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  setStatus("Running pipeline", "Fetching market data and sources…", true);

  es = new EventSource(`/stream/${encodeURIComponent(ticker)}?horizon=${encodeURIComponent(horizon)}`);

  es.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      onStateUpdate(payload);
    } catch (err) {
      // Ignore non-JSON messages.
    }
  };

  es.onerror = () => {
    setStatus("Error", "The pipeline stream ended unexpectedly. Check console/network.", false);
    if (es) es.close();
    cancelBtn.disabled = true;
    runBtn.disabled = false;
  };
}

cancelBtn.addEventListener("click", () => {
  if (es) es.close();
  setStatus("Cancelled", "Run stopped.", false);
  cancelBtn.disabled = true;
  runBtn.disabled = false;
});

runBtn.addEventListener("click", () => {
  const ticker = String(tickerInput.value || "").trim().toUpperCase();
  const horizon = horizonInput.value;

  if (!ticker) return;

  runBtn.disabled = true;
  cancelBtn.disabled = false;
  connectStream(ticker, horizon);
});

// Initial disclaimer text slot.
disclaimerBox.textContent = " ";

// Theme toggle
initTheme();
if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.dataset.theme || "light";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem("stockAnalystTheme", next);
    applyTheme(next);
  });
}