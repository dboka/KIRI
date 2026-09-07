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
};

const weekdayLabels = ["P", "O", "T", "C", "P", "S", "Sv"];
const latviaBounds = L.latLngBounds([55.55, 20.45], [58.25, 28.35]);
const maplibreStyleUrl = "https://tiles.openfreemap.org/styles/positron";
const fallbackTileUrl = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

const map = L.map("map", {
  preferCanvas: true,
  zoomControl: false,
  attributionControl: true,
  minZoom: 6.5,
  maxZoom: 11.5,
  maxBounds: latviaBounds.pad(0.18),
  maxBoundsViscosity: 0.95,
  zoomSnap: 0.25,
  zoomDelta: 0.5,
  scrollWheelZoom: "center",
  wheelDebounceTime: 35,
  wheelPxPerZoomLevel: 220,
  bounceAtZoomLimits: false,
  inertia: true,
  fadeAnimation: true,
  zoomAnimation: true,
  zoomAnimationThreshold: 2,
  markerZoomAnimation: false,
});

L.control.zoom({ position: "topright" }).addTo(map);

let baseLayer = null;
let fallbackLayer = null;

function addRasterFallback() {
  if (fallbackLayer) return;
  document.body.classList.add("basemap-failed");
  fallbackLayer = L.tileLayer(fallbackTileUrl, {
    minZoom: 0,
    maxZoom: 19,
    maxNativeZoom: 19,
    keepBuffer: 5,
    updateWhenIdle: false,
    updateWhenZooming: false,
    crossOrigin: true,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  fallbackLayer.on("tileload", () => {
    document.body.classList.add("basemap-raster-fallback");
  });
}

function addMaplibreBasemap() {
  if (!L.maplibreGL || !window.maplibregl) {
    addRasterFallback();
    return;
  }

  baseLayer = L.maplibreGL({
    style: maplibreStyleUrl,
    interactive: false,
    renderWorldCopies: false,
  }).addTo(map);

  const glMap = baseLayer.getMaplibreMap?.();
  if (glMap) {
    glMap.on("load", () => {
      document.body.classList.add("basemap-maplibre-ready");
    });
    glMap.on("error", () => {
      addRasterFallback();
    });
  }
}

addMaplibreBasemap();

const canvasRenderer = L.canvas({ padding: 0.55, tolerance: 8 });
const dateCache = new Map();
const jsonCache = new Map();

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
const bootStartedAt = window.performance.now();

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

function gridStyle(feature) {
  const level = feature.properties.final_risk_level ?? feature.properties.kiri_risk_level;
  const drawCellLines = map.getZoom() >= 10.25;
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
    jsonCache.set(path, fetch(path).then((response) => {
      if (!response.ok) {
        throw new Error(`Could not load ${path}: ${response.status}`);
      }
      return response.json();
    }));
  }
  return jsonCache.get(path);
}

async function loadOptionalJson(path) {
  const response = await fetch(path);
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
  const finishDelay = Math.max(0, 850 - elapsed);
  window.setTimeout(() => {
    bootOverlay.classList.add("is-complete");
    window.setTimeout(() => {
      bootOverlay.hidden = true;
    }, 360);
  }, finishDelay);
}

function setPanelContent(summary, cellProperties = null) {
  const isCell = Boolean(cellProperties);
  document.querySelector("#panelKicker").textContent = isCell
    ? `${activeDate} · Grid šūna ${cellProperties.grid_id}`
    : `${activeDate} · Pašvaldības skats`;
  document.querySelector("#panelTitle").textContent = summary.municipality_name;
  document.querySelector("#overallRisk").textContent = isCell
    ? (cellProperties.final_risk_level ?? cellProperties.kiri_risk_level ?? "-")
    : summary.overall_risk;
  document.querySelector("#activeRisk").textContent = isCell
    ? (cellProperties.active_risk ?? "-")
    : "klikšķini uz grid";
  document.querySelector("#highRiskPercent").textContent = formatMetric(summary.high_risk_percent);
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
    document.querySelector("#confidenceCard").textContent = cellProperties.confidence || "-";
    return;
  }

  document.querySelector("#p30Card").textContent = "klikšķini uz grid";
  document.querySelector("#p90Card").textContent = "klikšķini uz grid";
  document.querySelector("#p730Card").textContent = "klikšķini uz grid";
  document.querySelector("#hsafCard").textContent = "klikšķini uz grid";
  document.querySelector("#swiCard").textContent = "klikšķini uz grid";
  document.querySelector("#confidenceCard").textContent = "klikšķini uz grid";
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
    const [boundaryGeojson, staticGridGeojson, gridValues] = await Promise.all([
      loadJson(`data/${summary.boundary_file}`),
      loadJson(`data/${summary.static_grid_file}`),
      summary.grid_values_file ? loadJson(`data/${summary.grid_values_file}`) : null,
    ]);

    const gridGeojson = gridValues
      ? mergeGridValues(staticGridGeojson, gridValues)
      : staticGridGeojson;

    selectedBoundaryLayer = L.geoJSON(boundaryGeojson, {
      renderer: canvasRenderer,
      style: boundaryStyle,
      interactive: false,
    }).addTo(map);

    gridLayer = L.geoJSON(gridGeojson, {
      renderer: canvasRenderer,
      style: gridStyle,
      smoothFactor: 1.2,
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
  if (dateText === activeDate && municipalityLayer) return;
  const previousMunicipality = keepMunicipality ? activeMunicipalityCode : null;
  setLoading(true);
  try {
    const data = await loadDateData(dateText);
    activeDate = dateText;
    activeDateMeta = data.meta;
    manifest = data.dayManifest;
    updateDateChrome();
    updateCalendarSelection();

    clearDetailLayers();
    drawOverview(data.overview, { fit });

    if (previousMunicipality && manifest[previousMunicipality]) {
      await openMunicipalityByCode(previousMunicipality, { fit: false });
    } else {
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
  setBootStatus("Zīmē jaunāko kartes slāni...");
  await setActiveDate(calendarManifest.default_date, { fit: true, keepMunicipality: false });
  setBootStatus("Gatavs");
  finishBootOverlay();
}

map.on("zoomstart movestart", () => {
  isMapMoving = true;
  document.body.classList.add("map-is-moving");
});

map.on("moveend", () => {
  isMapMoving = false;
  document.body.classList.remove("map-is-moving");
});

map.on("zoomend", () => {
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

boot().catch((error) => {
  console.error(error);
  setBootStatus("Neizdevās ielādēt kartes datus");
  if (bootOverlay) {
    bootOverlay.classList.add("has-error");
  }
  alert("Neizdevās ielādēt KIRI-LV kartes datus. Pārbaudi lokālo serveri un data mapi.");
});
