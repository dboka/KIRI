const riskColors = {
  1: "#69b88f",
  2: "#cfe89a",
  3: "#f4d35e",
  4: "#f08a4b",
  5: "#c94f44",
};

const riskLabels = {
  1: "Ļoti zems risks",
  2: "Zems risks",
  3: "Vidējs risks / piesardzība",
  4: "Augsts risks",
  5: "Ļoti augsts risks / neizkliedēt",
};

const monthNames = {
  "2026-05": "Maijs 2026",
  "2026-06": "Jūnijs 2026",
  "2026-07": "Jūlijs 2026",
  "2026-08": "Augusts 2026",
  "2026-09": "Septembris 2026",
  "2026-10": "Oktobris 2026",
};

const weekdayLabels = ["P", "O", "T", "C", "P", "S", "Sv"];
const latviaBounds = L.latLngBounds([55.55, 20.45], [58.25, 28.35]);
const basemapTileUrl = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
let resolveBasemapReady = null;
let basemapReadySettled = false;
const basemapReady = new Promise((resolve) => {
  resolveBasemapReady = resolve;
});

const map = L.map("map", {
  preferCanvas: true,
  zoomControl: false,
  attributionControl: true,
  minZoom: 6.5,
  maxZoom: 11.5,
  maxBounds: latviaBounds.pad(0.18),
  maxBoundsViscosity: 0.95,
  zoomSnap: 0.5,
  zoomDelta: 1,
  scrollWheelZoom: true,
  wheelDebounceTime: 25,
  wheelPxPerZoomLevel: 180,
  bounceAtZoomLimits: false,
  inertia: true,
  fadeAnimation: false,
  zoomAnimation: false,
  zoomAnimationThreshold: 3,
  markerZoomAnimation: false,
});

L.control.zoom({ position: "topright" }).addTo(map);

function markBasemapReady(mode) {
  if (basemapReadySettled) return;
  basemapReadySettled = true;
  document.body.classList.add(`basemap-${mode}-ready`);
  resolveBasemapReady?.(mode);
}

function waitForBasemapReady(timeoutMs = 3000) {
  return Promise.race([
    basemapReady,
    new Promise((resolve) => {
      window.setTimeout(() => {
        markBasemapReady("timeout");
        resolve("timeout");
      }, timeoutMs);
    }),
  ]);
}

const baseLayer = L.tileLayer(basemapTileUrl, {
  minZoom: 0,
  maxZoom: 18,
  maxNativeZoom: 18,
  keepBuffer: 3,
  updateWhenIdle: false,
  updateWhenZooming: false,
  crossOrigin: true,
  attribution: "Tiles &copy; Esri, HERE, Garmin, OpenStreetMap contributors",
}).addTo(map);

baseLayer.once("tileload", () => markBasemapReady("raster"));
baseLayer.once("load", () => markBasemapReady("raster"));

const canvasRenderer = L.canvas({ padding: 0.22, tolerance: 5 });
const dateCache = new Map();
const jsonCache = new Map();
const mergedGridCache = new Map();
const maxMergedGridCacheSize = 18;

let calendarManifest = null;
let archiveManifest = null;
let activeDate = null;
let activeDateMeta = null;
let manifest = null;
let municipalityLayer = null;
let selectedBoundaryLayer = null;
let gridLayer = null;
let activeMunicipalityCode = null;
let selectedGridCellLayer = null;
let isMapMoving = false;
let gridStyleFrame = null;
let lastGridLineMode = null;
let activeIndicatorTarget = null;
let activeIndicatorSeries = null;
let indicatorHoverIndex = 0;

window.kiriDebug = { status: "booting" };

const detailPanel = document.querySelector("#detailPanel");
const backButton = document.querySelector("#backButton");
const calendarToggle = document.querySelector("#calendarToggle");
const calendarPanel = document.querySelector("#calendarPanel");
const calendarMonths = document.querySelector("#calendarMonths");
const archiveToggle = document.querySelector("#archiveToggle");
const archivePanel = document.querySelector("#archivePanel");
const archiveCoverage = document.querySelector("#archiveCoverage");
const archiveList = document.querySelector("#archiveList");
const activeDateLabel = document.querySelector("#activeDateLabel");
const dateCoverage = document.querySelector("#dateCoverage");
const loadingState = document.querySelector("#loadingState");
const bootOverlay = document.querySelector("#bootOverlay");
const bootStatus = document.querySelector("#bootStatus");
const riskBadge = document.querySelector("#riskBadge");
const indicatorHistoryButtons = document.querySelectorAll(".indicator-history-button");
const indicatorHistoryDialog = document.querySelector("#indicatorHistoryDialog");
const indicatorHistoryClose = document.querySelector("#indicatorHistoryClose");
const indicatorHistoryKicker = document.querySelector("#indicatorHistoryKicker");
const indicatorHistoryTitle = document.querySelector("#indicatorHistoryTitle");
const indicatorHistorySubtitle = document.querySelector("#indicatorHistorySubtitle");
const indicatorChartTitle = document.querySelector("#indicatorChartTitle");
const indicatorChartMeta = document.querySelector("#indicatorChartMeta");
const indicatorHistoryRange = document.querySelector("#indicatorHistoryRange");
const indicatorChartState = document.querySelector("#indicatorChartState");
const indicatorChartFrame = document.querySelector("#indicatorChartFrame");
const indicatorHistoryChart = document.querySelector("#indicatorHistoryChart");
const indicatorChartTooltip = document.querySelector("#indicatorChartTooltip");
const indicatorDownloadButton = document.querySelector("#indicatorDownloadButton");
const indicatorLegendLabel = document.querySelector("#indicatorLegendLabel");
const indicatorPointLabel = document.querySelector("#indicatorPointLabel");
const indicatorFallbackLegend = document.querySelector("#indicatorFallbackLegend");
const indicatorCredit = document.querySelector("#indicatorCredit");
const bootStartedAt = window.performance.now();

document.querySelectorAll(".thresholds").forEach((details) => {
  details.open = false;
});

function getRiskColor(level) {
  return riskColors[level] || "#aab6bc";
}

function overviewStyle(feature) {
  const level = feature.properties.risk_level;
  return {
    renderer: canvasRenderer,
    color: "rgba(255,255,255,0.82)",
    weight: 1,
    fillColor: getRiskColor(level),
    fillOpacity: 0.78,
    opacity: 0.9,
  };
}

const overviewHoverStyle = {
  color: "rgba(255,255,255,1)",
  weight: 1.7,
  fillOpacity: 0.9,
};

function boundaryStyle() {
  return {
    renderer: canvasRenderer,
    color: "rgba(255,255,255,0.96)",
    weight: 2,
    fillOpacity: 0,
    opacity: 1,
  };
}

function confidenceFillOpacity(confidence) {
  if (confidence === "low") return 0.48;
  if (confidence === "medium") return 0.68;
  return 0.84;
}

function shouldDrawGridLines() {
  return map.getZoom() >= 10.75;
}

function gridStyle(feature) {
  const level = feature.properties.final_risk_level ?? feature.properties.kiri_risk_level;
  const drawCellLines = shouldDrawGridLines();
  return {
    renderer: canvasRenderer,
    color: drawCellLines ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0)",
    weight: drawCellLines ? 0.28 : 0,
    fillColor: getRiskColor(level),
    fillOpacity: confidenceFillOpacity(feature.properties.confidence),
    opacity: drawCellLines ? 0.5 : 0,
  };
}

async function loadJson(path) {
  if (!jsonCache.has(path)) {
    jsonCache.set(path, fetch(path, { cache: "no-cache" }).then((response) => {
      if (!response.ok) {
        throw new Error(`Could not load ${path}: ${response.status}`);
      }
      return response.json();
    }));
  }
  return jsonCache.get(path);
}

async function loadOptionalJson(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Could not load ${path}: ${response.status}`);
  }
  return response.json();
}

async function loadDateData(dateText) {
  if (dateCache.has(dateText)) {
    return dateCache.get(dateText);
  }
  const meta = calendarManifest.dates.find((item) => item.date === dateText);
  if (!meta) {
    throw new Error(`Unknown date: ${dateText}`);
  }
  const data = await Promise.all([
    loadJson(`data/${meta.overview_file}`),
    loadJson(`data/${meta.manifest_file}`),
  ]).then(([overview, dayManifest]) => ({ overview, dayManifest, meta }));
  dateCache.set(dateText, data);
  return data;
}

function cacheMergedGrid(key, gridGeojson) {
  if (mergedGridCache.has(key)) {
    mergedGridCache.delete(key);
  }
  mergedGridCache.set(key, gridGeojson);
  if (mergedGridCache.size <= maxMergedGridCacheSize) return;
  const oldestKey = mergedGridCache.keys().next().value;
  mergedGridCache.delete(oldestKey);
}

function formatMetric(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "nav datu";
  }
  const numberValue = Number(value);
  const rendered = Number.isFinite(numberValue) ? numberValue.toFixed(2).replace(/\.00$/, "") : value;
  return `${rendered}${suffix}`;
}

function formatRisk(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "risks nav";
  }
  return `risks ${value}`;
}

function normalizeFactors(factors) {
  if (!factors || !factors.length) {
    return [];
  }
  if (typeof factors === "string") {
    return factors.split("|").filter(Boolean);
  }
  return factors;
}

function renderList(elementId, values, fallback) {
  const element = document.querySelector(elementId);
  element.innerHTML = "";
  const items = normalizeFactors(values);
  (items.length ? items : [fallback]).forEach((factor) => {
    const item = document.createElement("li");
    item.textContent = String(factor).replaceAll("_", " ");
    element.appendChild(item);
  });
}

function setLoading(isLoading) {
  loadingState.hidden = !isLoading;
}

function setBootStatus(text) {
  if (bootStatus) {
    bootStatus.textContent = text;
  }
}

function finishBootOverlay() {
  if (!bootOverlay) return;
  const elapsed = window.performance.now() - bootStartedAt;
  const finishDelay = Math.max(0, 1100 - elapsed);
  window.setTimeout(() => {
    bootOverlay.classList.add("is-complete");
    window.setTimeout(() => {
      bootOverlay.hidden = true;
    }, 360);
  }, finishDelay);
}

function setPanelContent(summary, cellProperties = null) {
  const isCell = Boolean(cellProperties);
  const overallRisk = isCell
    ? (cellProperties.final_risk_level ?? cellProperties.kiri_risk_level ?? "-")
    : summary.overall_risk;
  document.querySelector("#panelKicker").textContent = isCell
    ? `${activeDate} · Grid šūna ${cellProperties.grid_id}`
    : `${activeDate} · Pašvaldības skats`;
  document.querySelector("#panelTitle").textContent = summary.municipality_name;
  document.querySelector("#overallRisk").textContent = overallRisk;
  riskBadge.style.setProperty("--risk-color", getRiskColor(Number(overallRisk)));
  document.querySelector("#recommendation").textContent = summary.recommendation;

  renderList(
    "#dominantFactors",
    isCell ? cellProperties.active_reasons : summary.dominant_factors,
    "nav dominējošu aktīvu augsta riska faktoru",
  );
  renderList(
    "#contextFactors",
    isCell ? cellProperties.context_reasons : summary.context_factors,
    "ilgtermiņa fons normas robežās",
  );

  if (isCell) {
    activeIndicatorTarget = {
      gridId: String(cellProperties.grid_id),
      municipalityCode: String(activeMunicipalityCode),
      municipalityName: summary.municipality_name,
    };
    indicatorHistoryButtons.forEach((button) => { button.disabled = false; });
    const swiValue = cellProperties.SWI010_pct ?? cellProperties.swi;
    const hsafValue = cellProperties.HSAF_SSM_pct ?? cellProperties.hsaf_ssm;
    const hsafAge = Number(cellProperties.hsaf_age_days || 0);
    const hsafAgeText = hsafAge > 0
      ? `iepriekšējais pārlidojums, ${hsafAge} d. vecs`
      : "šodienas pārlidojums";
    document.querySelector("#p30Card").textContent =
      `${formatMetric(cellProperties.P30_mm, " mm")}, ${formatRisk(cellProperties.p30_risk)}`;
    document.querySelector("#p90Card").textContent =
      `${formatMetric(cellProperties.P90_mm, " mm")}, ${formatRisk(cellProperties.p90_risk)}`;
    document.querySelector("#p730Card").textContent =
      `${formatMetric(cellProperties.P730_mm, " mm")}, ${cellProperties.p730_context || "normal"}`;
    document.querySelector("#hsafCard").textContent =
      `${formatMetric(hsafValue, "%")}, ${formatRisk(cellProperties.hsaf_ssm_risk)} · ${hsafAgeText}`;
    document.querySelector("#swiCard").textContent =
      `${formatMetric(swiValue, "%")}, ${formatRisk(cellProperties.swi_risk)}`;
    return;
  }

  document.querySelector("#p30Card").textContent = "klikšķini uz grid";
  document.querySelector("#p90Card").textContent = "klikšķini uz grid";
  document.querySelector("#p730Card").textContent = "klikšķini uz grid";
  document.querySelector("#hsafCard").textContent = "klikšķini uz grid";
  document.querySelector("#swiCard").textContent = "klikšķini uz grid";
  activeIndicatorTarget = null;
  indicatorHistoryButtons.forEach((button) => { button.disabled = true; });
}

const indicatorConfigs = {
  hsaf: {
    title: "H-SAF virsmas augsnes mitrums",
    shortLabel: "H-SAF SSM",
    unit: "%",
    pointLabel: "Satelīta pārlidojums",
    credit: "H-SAF dati · KIRI-LV apstrāde",
    fixedDomain: [0, 100],
  },
  swi: {
    title: "Copernicus augsnes mitruma indekss",
    shortLabel: "Copernicus SWI",
    unit: "%",
    pointLabel: "SWI datu punkts",
    credit: "Copernicus SWI dati · KIRI-LV apstrāde",
    fixedDomain: [0, 100],
  },
  p30: {
    title: "30 dienu nokrišņu uzkrājums",
    shortLabel: "P30",
    unit: "mm",
    pointLabel: "Nokrišņu aprēķins",
    credit: "KIRI-LV interpolētie nokrišņu dati",
    baselineZero: true,
  },
  p90: {
    title: "90 dienu nokrišņu uzkrājums",
    shortLabel: "P90",
    unit: "mm",
    pointLabel: "Nokrišņu aprēķins",
    credit: "KIRI-LV interpolētie nokrišņu dati",
    baselineZero: true,
  },
  p730: {
    title: "730 dienu nokrišņu fons",
    shortLabel: "P730",
    unit: "mm",
    pointLabel: "Ilgtermiņa aprēķins",
    credit: "KIRI-LV interpolētais ilgtermiņa nokrišņu fons",
    zoomedDomain: true,
  },
};

const indicatorDateFormatter = new Intl.DateTimeFormat("lv-LV", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const indicatorAxisDateFormatter = new Intl.DateTimeFormat("lv-LV", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

function parseChartDate(dateText) {
  return new Date(`${dateText}T12:00:00Z`);
}

function formatIndicatorValue(value, unit) {
  if (!isIndicatorValue(value)) return "Nav datu";
  return `${Number(value).toLocaleString("lv-LV", { minimumFractionDigits: 1, maximumFractionDigits: 2 })} ${unit}`;
}

function isIndicatorValue(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

function buildChartPath(values, xFor, yFor) {
  let path = "";
  let drawing = false;
  values.forEach((value, index) => {
    if (!isIndicatorValue(value)) {
      drawing = false;
      return;
    }
    path += `${drawing ? " L" : "M"}${xFor(index).toFixed(2)} ${yFor(Number(value)).toFixed(2)}`;
    drawing = true;
  });
  return path;
}

function buildFallbackPath(values, ages, xFor, yFor) {
  let path = "";
  for (let index = 1; index < values.length; index += 1) {
    const current = Number(values[index]);
    const previous = Number(values[index - 1]);
    if (!isIndicatorValue(values[index]) || !isIndicatorValue(values[index - 1]) || Number(ages[index] || 0) <= 0) continue;
    path += `M${xFor(index - 1).toFixed(2)} ${yFor(previous).toFixed(2)} L${xFor(index).toFixed(2)} ${yFor(current).toFixed(2)}`;
  }
  return path;
}

function chartDomain(config, values, thresholds) {
  if (config.fixedDomain) return config.fixedDomain;
  const numericValues = values.filter(isIndicatorValue).map(Number);
  const minValue = Math.min(...numericValues, ...thresholds);
  const maxValue = Math.max(...numericValues, ...thresholds);
  if (config.zoomedDomain) {
    const padding = Math.max(50, (maxValue - minValue) * 0.12);
    return [Math.max(0, Math.floor((minValue - padding) / 50) * 50), Math.ceil((maxValue + padding) / 50) * 50];
  }
  const step = maxValue > 400 ? 100 : maxValue > 160 ? 50 : 20;
  return [0, Math.ceil((maxValue * 1.08) / step) * step];
}

function renderIndicatorHistoryChart(history, series, indicatorKey) {
  const config = indicatorConfigs[indicatorKey];
  const dates = history.dates;
  const values = series.v;
  const ages = series.a || values.map(() => 0);
  const numericValues = values.filter(isIndicatorValue).map(Number);
  if (!numericValues.length) {
    indicatorChartFrame.hidden = true;
    indicatorChartState.hidden = false;
    indicatorChartState.textContent = `Šai grid šūnai saglabātajā periodā nav ${config.shortLabel} datu.`;
    indicatorDownloadButton.disabled = true;
    return;
  }

  const width = 1120;
  const height = 520;
  const margin = { top: 34, right: 52, bottom: 66, left: 70 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const thresholds = history.thresholds || [];
  const [yMin, yMax] = chartDomain(config, values, thresholds);
  const xFor = (index) => margin.left + (index / Math.max(1, dates.length - 1)) * plotWidth;
  const yFor = (value) => margin.top + plotHeight - ((value - yMin) / Math.max(1, yMax - yMin)) * plotHeight;
  const linePath = buildChartPath(values, xFor, yFor);
  const fallbackPath = indicatorKey === "hsaf" ? buildFallbackPath(values, ages, xFor, yFor) : "";
  const visibleThresholds = thresholds.filter((value) => value > yMin && value < yMax);
  const yTicks = Array.from({ length: 6 }, (_, index) => yMin + ((yMax - yMin) * index) / 5);

  const xTickCount = Math.min(6, dates.length);
  const xTickIndexes = Array.from({ length: xTickCount }, (_, index) =>
    Math.round((index * (dates.length - 1)) / Math.max(1, xTickCount - 1)));
  const bandEdges = [yMin, ...visibleThresholds, yMax];
  const riskBands = bandEdges.slice(0, -1).map((low, index) => {
    const high = bandEdges[index + 1];
    const riskLevel = Math.min(5, 1 + thresholds.filter((threshold) => threshold <= low).length);
    return [low, high, getRiskColor(riskLevel)];
  });

  const observedDots = values.map((value, index) => {
    if (!isIndicatorValue(value) || (indicatorKey === "hsaf" && Number(ages[index] || 0) !== 0)) return "";
    return `<circle cx="${xFor(index).toFixed(2)}" cy="${yFor(Number(value)).toFixed(2)}" r="3.1" fill="#a3163d" />`;
  }).join("");
  const fallbackDots = values.map((value, index) => {
    if (indicatorKey !== "hsaf" || !isIndicatorValue(value) || Number(ages[index] || 0) <= 0) return "";
    return `<circle cx="${xFor(index).toFixed(2)}" cy="${yFor(Number(value)).toFixed(2)}" r="2.7" fill="#fbfbfa" stroke="#cf6972" stroke-width="1.7" />`;
  }).join("");

  indicatorHistoryChart.innerHTML = `
    <defs>
      <clipPath id="hsafPlotClip"><rect x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${plotHeight}" /></clipPath>
      <linearGradient id="hsafLineGradient" x1="0" x2="1"><stop offset="0" stop-color="#6e1735" /><stop offset="1" stop-color="#b41843" /></linearGradient>
    </defs>
    <g clip-path="url(#hsafPlotClip)">
      ${riskBands.map(([low, high, color]) => `<rect x="${margin.left}" y="${yFor(high)}" width="${plotWidth}" height="${Math.max(0, yFor(low) - yFor(high))}" fill="${color}" opacity="0.045" />`).join("")}
    </g>
    ${yTicks.map((value) => `
      <line x1="${margin.left}" x2="${width - margin.right}" y1="${yFor(value)}" y2="${yFor(value)}" stroke="#d8dcde" stroke-width="1" />
      <text x="${margin.left - 13}" y="${yFor(value) + 5}" text-anchor="end" fill="#59636b" font-size="13">${Math.round(value).toLocaleString("lv-LV")}</text>
    `).join("")}
    ${visibleThresholds.map((value) => `
      <line x1="${margin.left}" x2="${width - margin.right}" y1="${yFor(value)}" y2="${yFor(value)}" stroke="#a3163d" stroke-width="1" stroke-dasharray="4 6" opacity="0.28" />
      <text x="${width - margin.right - 5}" y="${yFor(value) - 6}" text-anchor="end" fill="#9a6a76" font-size="10">slieksnis ${value} ${config.unit}</text>
    `).join("")}
    ${xTickIndexes.map((index, tickIndex) => `
      <text x="${xFor(index)}" y="${height - 29}" text-anchor="${tickIndex === 0 ? "start" : tickIndex === xTickIndexes.length - 1 ? "end" : "middle"}" fill="#4c555c" font-size="13">${indicatorAxisDateFormatter.format(parseChartDate(dates[index]))}</text>
    `).join("")}
    <g clip-path="url(#hsafPlotClip)">
      <path d="${linePath}" fill="none" stroke="url(#hsafLineGradient)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round" />
      <path d="${fallbackPath}" fill="none" stroke="#e58b8e" stroke-width="4.2" stroke-dasharray="5 5" stroke-linecap="round" opacity="0.95" />
      ${observedDots}${fallbackDots}
      <line id="hsafChartCursor" y1="${margin.top}" y2="${height - margin.bottom}" stroke="#213d58" stroke-width="1" opacity="0.4" />
      <circle id="hsafChartHoverDot" r="6.5" fill="#a3163d" stroke="#fff" stroke-width="2.5" />
      <rect id="hsafChartHitArea" x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${plotHeight}" fill="transparent" />
    </g>
    <text x="${margin.left}" y="18" fill="#76818a" font-size="11" font-weight="700">${config.shortLabel}, ${config.unit}</text>
  `;

  activeIndicatorSeries = {
    indicatorKey,
    config,
    dates,
    values,
    ages,
    gridId: activeIndicatorTarget.gridId,
    municipalityName: activeIndicatorTarget.municipalityName,
    chart: { width, margin, plotWidth, xFor, yFor },
  };
  const activeIndex = dates.indexOf(activeDate);
  const lastValueIndex = values.reduce((latest, value, index) => isIndicatorValue(value) ? index : latest, 0);
  indicatorHoverIndex = activeIndex >= 0 ? activeIndex : lastValueIndex;
  indicatorChartState.hidden = true;
  indicatorChartFrame.hidden = false;
  indicatorDownloadButton.disabled = false;
  updateIndicatorChartHover(indicatorHoverIndex);
}

function updateIndicatorChartHover(index) {
  if (!activeIndicatorSeries) return;
  const { dates, values, ages, chart, config, indicatorKey } = activeIndicatorSeries;
  indicatorHoverIndex = Math.max(0, Math.min(dates.length - 1, index));
  const value = Number(values[indicatorHoverIndex]);
  const hasValue = isIndicatorValue(values[indicatorHoverIndex]);
  const x = chart.xFor(indicatorHoverIndex);
  const cursor = document.querySelector("#hsafChartCursor");
  const dot = document.querySelector("#hsafChartHoverDot");
  cursor.setAttribute("x1", x);
  cursor.setAttribute("x2", x);
  dot.setAttribute("cx", x);
  dot.setAttribute("cy", hasValue ? chart.yFor(value) : chart.margin.top);
  dot.style.display = hasValue ? "" : "none";

  const dateLabel = indicatorDateFormatter.format(parseChartDate(dates[indicatorHoverIndex]));
  const age = Number(ages[indicatorHoverIndex]);
  const status = !hasValue
    ? `${config.shortLabel} nav pieejams`
    : indicatorKey === "hsaf" && age > 0
      ? `Iepriekšējais pārlidojums · ${age} d. vecs`
      : config.pointLabel;
  const valueLabel = document.createElement("strong");
  valueLabel.textContent = formatIndicatorValue(values[indicatorHoverIndex], config.unit);
  const dateElement = document.createElement("span");
  dateElement.textContent = dateLabel;
  const statusElement = document.createElement("small");
  statusElement.textContent = status;
  indicatorChartTooltip.replaceChildren(valueLabel, dateElement, statusElement);
  indicatorChartTooltip.hidden = false;
  const frameWidth = indicatorChartFrame.clientWidth;
  const rawLeft = (x / chart.width) * frameWidth;
  indicatorChartTooltip.style.left = `${Math.max(88, Math.min(frameWidth - 88, rawLeft))}px`;
  indicatorHistoryChart.setAttribute("aria-label", `${dateLabel}: ${formatIndicatorValue(values[indicatorHoverIndex], config.unit)}. ${status}`);
}

async function openIndicatorHistory(indicatorKey, button) {
  if (!activeIndicatorTarget) return;
  const config = indicatorConfigs[indicatorKey];
  const target = { ...activeIndicatorTarget };
  const loadingLabel = button.querySelector("i");
  const previousLabel = loadingLabel.textContent;
  button.classList.add("is-loading");
  loadingLabel.textContent = "Ielādē…";

  try {
    const history = await loadJson(`data/indicator_history/${indicatorKey}/${target.municipalityCode}.json`);
    if (!activeIndicatorTarget || activeIndicatorTarget.gridId !== target.gridId) return;
    const series = history.series[target.gridId];
    if (!series) throw new Error(`${config.shortLabel} history missing for grid ${target.gridId}`);

    activeIndicatorSeries = null;
    indicatorChartFrame.hidden = true;
    indicatorChartState.hidden = false;
    indicatorChartState.textContent = `Ielādē ${config.shortLabel} vēsturi…`;
    indicatorHistoryKicker.textContent = `KIRI-LV · ${config.shortLabel} laika rinda`;
    indicatorHistoryTitle.textContent = config.title;
    indicatorHistorySubtitle.textContent = `${target.municipalityName} · Grid šūna ${target.gridId}`;
    indicatorChartTitle.textContent = config.title;
    indicatorChartMeta.textContent = `Visas saglabātās KIRI-LV dienas · vienība: ${config.unit}`;
    indicatorHistoryRange.textContent = `${indicatorAxisDateFormatter.format(parseChartDate(history.dates[0]))}–${indicatorAxisDateFormatter.format(parseChartDate(history.dates.at(-1)))} · ${history.dates.length} dienas`;
    indicatorLegendLabel.textContent = config.shortLabel;
    indicatorPointLabel.textContent = config.pointLabel;
    indicatorFallbackLegend.hidden = indicatorKey !== "hsaf";
    indicatorCredit.textContent = config.credit;
    indicatorDownloadButton.disabled = true;
    renderIndicatorHistoryChart(history, series, indicatorKey);
    if (!indicatorHistoryDialog.open) indicatorHistoryDialog.showModal();
  } catch (error) {
    console.error(error);
    indicatorChartFrame.hidden = true;
    indicatorChartState.hidden = false;
    indicatorChartState.textContent = `Neizdevās ielādēt šīs šūnas ${config.shortLabel} vēsturi.`;
    indicatorHistoryTitle.textContent = config.title;
    indicatorHistorySubtitle.textContent = `${target.municipalityName} · Grid šūna ${target.gridId}`;
    indicatorHistoryRange.textContent = "Dati nav pieejami";
    if (!indicatorHistoryDialog.open) indicatorHistoryDialog.showModal();
  } finally {
    button.classList.remove("is-loading");
    loadingLabel.textContent = previousLabel;
  }
}

function downloadIndicatorHistoryCsv() {
  if (!activeIndicatorSeries) return;
  const { dates, values, ages, gridId, indicatorKey, config } = activeIndicatorSeries;
  const includeAge = indicatorKey === "hsaf";
  const rows = [`date,grid_id,${indicatorKey}_${config.unit === "%" ? "pct" : "mm"}${includeAge ? ",hsaf_age_days" : ""}`];
  dates.forEach((date, index) => {
    const row = [date, gridId, values[index] ?? ""];
    if (includeAge) row.push(ages[index] ?? "");
    rows.push(row.join(","));
  });
  const blob = new Blob([`\ufeff${rows.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `KIRI_${indicatorKey.toUpperCase()}_${gridId}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function clearDetailLayers() {
  if (gridLayer) {
    gridLayer.remove();
    gridLayer = null;
  }
  if (selectedBoundaryLayer) {
    selectedBoundaryLayer.remove();
    selectedBoundaryLayer = null;
  }
  selectedGridCellLayer = null;
}

function clearOverviewLayer() {
  if (municipalityLayer) {
    municipalityLayer.remove();
    municipalityLayer = null;
  }
}

async function showOverview({ fit = true } = {}) {
  activeMunicipalityCode = null;
  clearDetailLayers();
  if (!municipalityLayer && activeDate) {
    const data = await loadDateData(activeDate);
    drawOverview(data.overview, { fit: false });
  } else if (municipalityLayer && !map.hasLayer(municipalityLayer)) {
    municipalityLayer.addTo(map);
  }
  if (municipalityLayer && fit) {
    map.flyToBounds(municipalityLayer.getBounds(), {
      padding: [28, 28],
      duration: 0.45,
      easeLinearity: 0.35,
      maxZoom: 7,
    });
  }
  detailPanel.hidden = true;
  backButton.hidden = true;
}

function updateDateChrome() {
  activeDateLabel.textContent = activeDate || "-";
  if (!activeDateMeta) {
    dateCoverage.textContent = "-";
    return;
  }
  const swiText = activeDateMeta.swi_missing >= activeDateMeta.row_count ? "SWI kavējas" : "SWI pieejams";
  dateCoverage.textContent = `${activeDateMeta.municipality_count} pašvaldības · ${swiText}`;
}

async function openMunicipalityByCode(code, { fit = true } = {}) {
  if (!manifest || !manifest[code]) return;
  activeMunicipalityCode = code;
  const summary = manifest[code];
  detailPanel.hidden = false;
  backButton.hidden = false;
  setPanelContent(summary);

  clearDetailLayers();
  clearOverviewLayer();
  setLoading(true);

  try {
    const mergedGridKey = summary.grid_values_file
      ? `${summary.static_grid_file}|${summary.grid_values_file}`
      : null;
    const [boundaryGeojson, staticGridGeojson, gridValues] = await Promise.all([
      loadJson(`data/${summary.boundary_file}`),
      loadJson(`data/${summary.static_grid_file}`),
      summary.grid_values_file ? loadJson(`data/${summary.grid_values_file}`) : null,
    ]);

    let gridGeojson = mergedGridKey ? mergedGridCache.get(mergedGridKey) : staticGridGeojson;
    if (!gridGeojson) {
      gridGeojson = mergeGridValues(staticGridGeojson, gridValues);
      cacheMergedGrid(mergedGridKey, gridGeojson);
    }

    selectedBoundaryLayer = L.geoJSON(boundaryGeojson, {
      renderer: canvasRenderer,
      style: boundaryStyle,
      interactive: false,
    }).addTo(map);

    gridLayer = L.geoJSON(gridGeojson, {
      renderer: canvasRenderer,
      style: gridStyle,
      smoothFactor: 0.75,
      bubblingMouseEvents: false,
      onEachFeature: (cellFeature, layer) => {
        layer.on("click", (event) => {
          if (selectedGridCellLayer && selectedGridCellLayer !== event.target) {
            gridLayer.resetStyle(selectedGridCellLayer);
          }
          selectedGridCellLayer = event.target;
          event.target.setStyle({
            weight: 1.1,
            color: "rgba(255,255,255,0.98)",
            fillOpacity: 0.9,
            opacity: 0.95,
          });
          setPanelContent(summary, cellFeature.properties);
        });
      },
    }).addTo(map);
    lastGridLineMode = shouldDrawGridLines();

    selectedBoundaryLayer.bringToFront();
    if (fit) {
      map.fitBounds(selectedBoundaryLayer.getBounds(), {
        paddingTopLeft: [24, 72],
        paddingBottomRight: [Math.min(detailPanel.offsetWidth + 34, window.innerWidth * 0.46), 42],
        maxZoom: 10.5,
      });
    }
  } finally {
    setLoading(false);
  }
}

function mergeGridValues(staticGridGeojson, gridValues) {
  const fieldIndex = Object.fromEntries(gridValues.fields.map((field, index) => [field, index]));
  const valuesByGridId = new Map(
    gridValues.rows.map((row) => [String(row[fieldIndex.grid_id]), row]),
  );

  return {
    type: "FeatureCollection",
    features: staticGridGeojson.features
      .map((feature) => {
        const gridId = String(feature.properties.grid_id);
        const row = valuesByGridId.get(gridId);
        const properties = { grid_id: gridId };
        if (row) {
          gridValues.fields.forEach((field, index) => {
            properties[field] = row[index];
          });
        }
        return {
          type: "Feature",
          properties,
          geometry: feature.geometry,
        };
      })
      .filter((feature) => feature.properties.map_visible !== false),
  };
}

async function openMunicipality(feature) {
  await openMunicipalityByCode(String(feature.properties.municipality_code));
}

function bindMunicipality(feature, layer) {
  const properties = feature.properties;
  layer.bindTooltip(
    `<strong>${properties.municipality_name}</strong><br>${riskLabels[properties.risk_level] || "Risks nav"}`,
    {
      sticky: true,
      className: "kiri-tooltip",
    },
  );

  layer.on({
    mouseover: (event) => {
      if (!isMapMoving) event.target.setStyle(overviewHoverStyle);
    },
    mouseout: (event) => {
      if (municipalityLayer && !isMapMoving) {
        municipalityLayer.resetStyle(event.target);
      }
    },
    click: () => openMunicipality(feature),
  });
}

function drawOverview(overviewGeojson, { fit = false } = {}) {
  clearOverviewLayer();
  municipalityLayer = L.geoJSON(overviewGeojson, {
    renderer: canvasRenderer,
    style: overviewStyle,
    onEachFeature: bindMunicipality,
  }).addTo(map);

  if (fit) {
    map.fitBounds(municipalityLayer.getBounds(), { padding: [28, 28], maxZoom: 7 });
  }
}

async function setActiveDate(dateText, { fit = false, keepMunicipality = true } = {}) {
  if (dateText === activeDate) return;
  const previousMunicipality = keepMunicipality ? activeMunicipalityCode : null;
  setLoading(true);
  try {
    const data = await loadDateData(dateText);
    activeDate = dateText;
    activeDateMeta = data.meta;
    manifest = data.dayManifest;
    updateDateChrome();
    updateCalendarSelection();

    if (previousMunicipality && manifest[previousMunicipality]) {
      clearOverviewLayer();
      await openMunicipalityByCode(previousMunicipality, { fit: false });
    } else {
      clearDetailLayers();
      drawOverview(data.overview, { fit });
      detailPanel.hidden = true;
      backButton.hidden = true;
      activeMunicipalityCode = null;
    }

    window.kiriDebug = {
      status: "ready",
      activeDate,
      municipalityCount: data.overview.features.length,
      cachedDates: dateCache.size,
      mapZoom: map.getZoom(),
    };
  } finally {
    setLoading(false);
  }
}

function groupDatesByMonth(dates) {
  return dates.reduce((groups, item) => {
    const key = item.date.slice(0, 7);
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
    return groups;
  }, {});
}

function firstDayOffset(monthKey) {
  const first = new Date(`${monthKey}-01T00:00:00`);
  return (first.getDay() + 6) % 7;
}

function dayNumber(dateText) {
  return Number(dateText.slice(8, 10));
}

function renderCalendar() {
  const groups = groupDatesByMonth(calendarManifest.dates);
  calendarMonths.innerHTML = "";

  Object.entries(groups).forEach(([monthKey, dates]) => {
    const month = document.createElement("div");
    month.className = "calendar-month";

    const title = document.createElement("div");
    title.className = "calendar-month-title";
    title.textContent = monthNames[monthKey] || monthKey;
    month.appendChild(title);

    const weekdays = document.createElement("div");
    weekdays.className = "calendar-weekdays";
    weekdayLabels.forEach((label) => {
      const item = document.createElement("span");
      item.textContent = label;
      weekdays.appendChild(item);
    });
    month.appendChild(weekdays);

    const grid = document.createElement("div");
    grid.className = "calendar-grid";
    for (let i = 0; i < firstDayOffset(monthKey); i += 1) {
      const spacer = document.createElement("span");
      spacer.className = "calendar-spacer";
      grid.appendChild(spacer);
    }

    dates.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "calendar-day";
      button.dataset.date = item.date;
      button.textContent = dayNumber(item.date);
      button.title = `${item.date} · ${item.swi_missing >= item.row_count ? "SWI kavējas" : "SWI pieejams"}`;
      if (item.swi_missing >= item.row_count) {
        button.classList.add("has-delay");
      }
      button.addEventListener("click", () => setActiveDate(item.date, { keepMunicipality: true }));
      grid.appendChild(button);
    });

    month.appendChild(grid);
    calendarMonths.appendChild(month);
  });
}

function renderArchive() {
  if (!archiveManifest) {
    archiveToggle.hidden = true;
    return;
  }

  const archivedDates = archiveManifest.dates.filter((item) => item.archived);
  archiveCoverage.textContent = `${archivedDates.length} datumi`;
  archiveList.innerHTML = "";

  if (!archivedDates.length) {
    const empty = document.createElement("div");
    empty.className = "archive-empty";
    empty.textContent = "Arhīvs pagaidām tukšs";
    archiveList.appendChild(empty);
    return;
  }

  archivedDates.slice().reverse().forEach((item) => {
    const row = document.createElement("div");
    row.className = "archive-row";

    const dateText = document.createElement("strong");
    dateText.textContent = item.date;

    const status = document.createElement("span");
    const swiText = item.swi_missing === null || item.swi_missing === undefined
      ? "SWI statuss nav indeksēts"
      : `SWI trūkst: ${item.swi_missing}`;
    const hsafText = item.hsaf_missing === null || item.hsaf_missing === undefined
      ? "H-SAF statuss nav indeksēts"
      : `H-SAF trūkst: ${item.hsaf_missing}`;
    status.textContent = `${swiText} · ${hsafText}`;

    row.append(dateText, status);
    archiveList.appendChild(row);
  });
}

function updateCalendarSelection() {
  document.querySelectorAll(".calendar-day").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.date === activeDate);
  });
}

async function boot() {
  setBootStatus("Lasa pieejamos datumus...");
  calendarManifest = await loadJson("data/calendar_manifest.json");
  archiveManifest = await loadOptionalJson("data/archive_manifest.json");
  setBootStatus("Būvē kalendāru un arhīvu...");
  renderCalendar();
  renderArchive();
  setBootStatus("Zīmē riska slāni...");
  await setActiveDate(calendarManifest.default_date, { fit: true, keepMunicipality: false });
  setBootStatus("Gaida kartes pamatni...");
  await waitForBasemapReady();
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  setBootStatus("Gatavs");
  finishBootOverlay();
}

map.on("zoomstart movestart", () => {
  isMapMoving = true;
  document.body.classList.add("map-is-moving");
});

map.on("zoomstart", () => {
  document.body.classList.add("map-is-zooming");
});

map.on("moveend", () => {
  isMapMoving = false;
  document.body.classList.remove("map-is-moving");
});

map.on("zoomend", () => {
  document.body.classList.remove("map-is-zooming");
  const nextGridLineMode = shouldDrawGridLines();
  if (nextGridLineMode === lastGridLineMode) return;
  lastGridLineMode = nextGridLineMode;
  if (gridStyleFrame) {
    window.cancelAnimationFrame(gridStyleFrame);
  }
  gridStyleFrame = window.requestAnimationFrame(() => {
    gridStyleFrame = null;
    if (gridLayer) gridLayer.setStyle(gridStyle);
  });
});

backButton.addEventListener("click", () => {
  showOverview({ fit: true }).catch((error) => {
    console.error(error);
    alert("Neizdevās atgriezties uz Latvijas karti.");
  });
});
calendarToggle.addEventListener("click", () => {
  const hidden = calendarPanel.toggleAttribute("hidden");
  calendarToggle.setAttribute("aria-expanded", String(!hidden));
});

archiveToggle.addEventListener("click", () => {
  const hidden = archivePanel.toggleAttribute("hidden");
  archiveToggle.setAttribute("aria-expanded", String(!hidden));
});

indicatorHistoryButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openIndicatorHistory(button.dataset.indicator, button).catch((error) => console.error(error));
  });
});

indicatorHistoryClose.addEventListener("click", () => indicatorHistoryDialog.close());
indicatorDownloadButton.addEventListener("click", downloadIndicatorHistoryCsv);

indicatorHistoryDialog.addEventListener("click", (event) => {
  if (event.target === indicatorHistoryDialog) indicatorHistoryDialog.close();
});

indicatorHistoryChart.addEventListener("pointermove", (event) => {
  if (!activeIndicatorSeries) return;
  const bounds = indicatorHistoryChart.getBoundingClientRect();
  const svgX = ((event.clientX - bounds.left) / bounds.width) * activeIndicatorSeries.chart.width;
  const plotPosition = (svgX - activeIndicatorSeries.chart.margin.left) / activeIndicatorSeries.chart.plotWidth;
  const index = Math.round(plotPosition * (activeIndicatorSeries.dates.length - 1));
  updateIndicatorChartHover(index);
});

indicatorHistoryChart.addEventListener("keydown", (event) => {
  if (!activeIndicatorSeries || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  if (event.key === "Home") updateIndicatorChartHover(0);
  else if (event.key === "End") updateIndicatorChartHover(activeIndicatorSeries.dates.length - 1);
  else updateIndicatorChartHover(indicatorHoverIndex + (event.key === "ArrowRight" ? 1 : -1));
});

boot().catch((error) => {
  console.error(error);
  setBootStatus("Neizdevās ielādēt kartes datus");
  if (bootOverlay) {
    bootOverlay.classList.add("has-error");
  }
  alert("Neizdevās ielādēt KIRI-LV kartes datus. Pārbaudi lokālo serveri un data mapi.");
});
