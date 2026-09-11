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
const basemapTileUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const demPilotGridIds = new Set(["27105"]);
const demPilotMunicipalityByGridId = { "27105": "100016688" };
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
  maxZoom: 19,
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
  maxZoom: 19,
  maxNativeZoom: 19,
  keepBuffer: 3,
  updateWhenIdle: false,
  updateWhenZooming: false,
  crossOrigin: true,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
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
let demOverlay = null;
let demOutlineLayer = null;
let demMaskLayer = null;
let demMetadata = null;
let demViewActive = false;
let activeDemMode = "3d";
let activeDemCellProperties = null;
let isMapMoving = false;
let gridStyleFrame = null;
let lastGridLineMode = null;

window.kiriDebug = { status: "booting" };

const detailPanel = document.querySelector("#detailPanel");
const demPanel = document.querySelector("#demPanel");
const demOpacity = document.querySelector("#demOpacity");
const demOpacityValue = document.querySelector("#demOpacityValue");
const dem3dStage = document.querySelector("#dem3dStage");
const dem3dFrame = document.querySelector("#dem3dFrame");
const dem3dLoading = document.querySelector("#dem3dLoading");
const dem3dOrbit = document.querySelector("#dem3dOrbit");
const dem3dWireframe = document.querySelector("#dem3dWireframe");
const dem3dReset = document.querySelector("#dem3dReset");
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

function demImagePath(mode = activeDemMode) {
  if (!demMetadata) return null;
  const filename = demMetadata.images?.[mode] || demMetadata.default_image;
  return `data/dem/${demMetadata.grid_id}/${filename}`;
}

function getDem3dApp() {
  try {
    return dem3dFrame.contentWindow?.Q3D?.application || null;
  } catch (error) {
    console.warn("3D viewer is not accessible", error);
    return null;
  }
}

function setDem3dButtonState(button, active) {
  button.classList.toggle("is-active", active);
  button.setAttribute("aria-pressed", String(active));
}

function stopDem3dAnimation() {
  const viewer = getDem3dApp();
  if (viewer?.controls?.autoRotate) viewer.setRotateAnimationMode(false);
  setDem3dButtonState(dem3dOrbit, false);
}

function setDemMode(mode) {
  const is3d = mode === "3d";
  if (!is3d && !demMetadata?.images?.[mode]) return;
  activeDemMode = mode;
  document.body.classList.toggle("dem-3d-active", is3d);
  dem3dStage.hidden = !is3d;

  if (is3d) {
    if (!dem3dFrame.src) {
      dem3dStage.classList.add("is-loading");
      dem3dFrame.src = dem3dFrame.dataset.src;
    }
  } else {
    stopDem3dAnimation();
    demOverlay?.setUrl(demImagePath(mode));
    demOverlay?.setOpacity(Number(demOpacity.value) / 100);
  }

  document.querySelectorAll("[data-dem-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.demMode === mode);
  });
}

function resetMapInteractionState() {
  isMapMoving = false;
  document.body.classList.remove("map-is-moving", "map-is-zooming");
}

function setDemRiskContent(cellProperties) {
  const level = Number(cellProperties.final_risk_level ?? cellProperties.kiri_risk_level);
  const label = cellProperties.final_risk_label_lv
    || cellProperties.kiri_risk_label_lv
    || riskLabels[level]
    || "Risks nav";
  const confidenceLabels = { high: "Augsta uzticamība", medium: "Vidēja uzticamība", low: "Zema uzticamība" };
  const legalLabels = { not_evaluated: "Nav izvērtēts" };
  const hsafValue = cellProperties.HSAF_SSM_pct ?? cellProperties.hsaf_ssm;
  const swiValue = cellProperties.SWI010_pct ?? cellProperties.swi;

  document.querySelector("#demRiskCard").style.setProperty("--dem-risk-color", getRiskColor(level));
  document.querySelector("#demRiskDate").textContent = cellProperties.date || activeDate || "—";
  document.querySelector("#demRiskLevel").textContent = Number.isFinite(level) ? level : "—";
  document.querySelector("#demRiskName").textContent = label;
  document.querySelector("#demRiskConfidence").textContent =
    confidenceLabels[cellProperties.confidence] || cellProperties.confidence || "Uzticamība nav zināma";
  document.querySelector("#demHsaf").textContent =
    `${formatMetric(hsafValue, "%")} · ${formatRisk(cellProperties.hsaf_ssm_risk)}`;
  document.querySelector("#demP30").textContent =
    `${formatMetric(cellProperties.P30_mm, " mm")} · ${formatRisk(cellProperties.p30_risk)}`;
  document.querySelector("#demSwi").textContent =
    `${formatMetric(swiValue, "%")} · ${formatRisk(cellProperties.swi_risk)}`;
  document.querySelector("#demP90").textContent =
    `${formatMetric(cellProperties.P90_mm, " mm")} · ${formatRisk(cellProperties.p90_risk)}`;
  document.querySelector("#demP730").textContent =
    `${formatMetric(cellProperties.P730_mm, " mm")} · ${formatRisk(cellProperties.p730_risk)}`;
  document.querySelector("#demLegal").textContent =
    legalLabels[cellProperties.legal_status] || cellProperties.legal_status || "Nav datu";
  renderList(
    "#demRiskReasons",
    cellProperties.main_reasons || cellProperties.active_reasons,
    "Nav identificētu riska iemeslu",
  );
  renderList(
    "#demDataWarnings",
    [...normalizeFactors(cellProperties.context_reasons), ...normalizeFactors(cellProperties.data_warnings)],
    "Nav datu brīdinājumu",
  );
}

function createDemOutsideMask(bounds) {
  const [[south, west], [north, east]] = bounds;
  const options = {
    renderer: canvasRenderer,
    stroke: false,
    fillColor: "#07131c",
    fillOpacity: 0.97,
    interactive: false,
  };
  return L.layerGroup([
    L.rectangle([[-85, -180], [south, 180]], options),
    L.rectangle([[north, -180], [85, 180]], options),
    L.rectangle([[south, -180], [north, west]], options),
    L.rectangle([[south, east], [north, 180]], options),
  ]).addTo(map);
}

function removeDemViewLayers() {
  document.body.classList.remove("dem-view-active", "dem-3d-active");
  dem3dStage.hidden = true;
  stopDem3dAnimation();
  if (demOverlay) {
    demOverlay.remove();
    demOverlay = null;
  }
  if (demOutlineLayer) {
    demOutlineLayer.remove();
    demOutlineLayer = null;
  }
  if (demMaskLayer) {
    demMaskLayer.remove();
    demMaskLayer = null;
  }
}

async function restoreMunicipalityView({ fit = true } = {}) {
  const municipalityCode = activeMunicipalityCode;
  removeDemViewLayers();
  demViewActive = false;
  demPanel.hidden = true;
  backButton.textContent = "Atpakaļ uz Latvijas karti";
  resetMapInteractionState();
  if (municipalityCode) {
    await openMunicipalityByCode(municipalityCode, { fit });
  }
}

async function openDemView(cellFeature) {
  const gridId = String(cellFeature.properties.grid_id);
  if (!demPilotGridIds.has(gridId)) return false;
  const metadata = await loadOptionalJson(`data/dem/${gridId}/metadata.json`);
  if (!metadata) return false;

  removeDemViewLayers();
  demMetadata = metadata;
  demViewActive = true;
  document.body.classList.add("dem-view-active");
  activeDemCellProperties = cellFeature.properties;
  activeDemMode = "3d";

  if (gridLayer && map.hasLayer(gridLayer)) gridLayer.remove();
  detailPanel.hidden = true;
  demPanel.hidden = false;
  backButton.hidden = false;
  backButton.textContent = "Atpakaļ uz Ogres novada gridu";

  demMaskLayer = createDemOutsideMask(metadata.bounds);
  demOutlineLayer = L.geoJSON(cellFeature, {
    renderer: canvasRenderer,
    interactive: false,
    className: "dem-cell-outline",
    style: {
      color: "rgba(255,255,255,0.96)",
      weight: 2,
      fillOpacity: 0,
    },
  }).addTo(map);

  document.querySelector("#demResolution").textContent = `${metadata.resolution_m} m`;
  document.querySelector("#demMean").textContent = `${metadata.elevation_mean_m} m`;
  document.querySelector("#demMin").textContent = `${metadata.elevation_min_m} m`;
  document.querySelector("#demMax").textContent = `${metadata.elevation_max_m} m`;
  document.querySelector("#demMinLegend").textContent = `${metadata.elevation_min_m} m`;
  document.querySelector("#demMaxLegend").textContent = `${metadata.elevation_max_m} m`;
  setDemRiskContent(cellFeature.properties);
  setDemMode("3d");

  const compactLayout = window.innerWidth <= 760;
  map.fitBounds(metadata.bounds, {
    paddingTopLeft: compactLayout ? [24, 112] : [30, 80],
    paddingBottomRight: compactLayout
      ? [24, demPanel.offsetHeight + 24]
      : [Math.min(demPanel.offsetWidth + 36, window.innerWidth * 0.44), 44],
    maxZoom: 17,
  });
  return true;
}

async function openPilotGridById(gridId) {
  const municipalityCode = demPilotMunicipalityByGridId[gridId];
  if (!municipalityCode) return false;
  await openMunicipalityByCode(municipalityCode, { fit: false });
  let pilotLayer = null;
  gridLayer?.eachLayer((layer) => {
    if (String(layer.feature?.properties?.grid_id) === gridId) pilotLayer = layer;
  });
  if (!pilotLayer) return false;
  selectedGridCellLayer = pilotLayer;
  pilotLayer.setStyle({
    weight: 1.1,
    color: "rgba(255,255,255,0.98)",
    fillOpacity: 0.9,
    opacity: 0.95,
  });
  setPanelContent(manifest[municipalityCode], pilotLayer.feature.properties);
  return openDemView(pilotLayer.feature);
}

function clearDetailLayers() {
  removeDemViewLayers();
  demViewActive = false;
  demPanel.hidden = true;
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
  resetMapInteractionState();
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
  backButton.textContent = "Atpakaļ uz Latvijas karti";
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
  resetMapInteractionState();
  activeMunicipalityCode = code;
  const summary = manifest[code];
  detailPanel.hidden = false;
  backButton.hidden = false;
  backButton.textContent = "Atpakaļ uz Latvijas karti";
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
        layer.on("click", async (event) => {
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
          if (demPilotGridIds.has(String(cellFeature.properties.grid_id))) {
            try {
              setLoading(true);
              await openDemView(cellFeature);
            } catch (error) {
              console.error(error);
              alert("Neizdevās atvērt šūnas 27105 reljefa skatu.");
            } finally {
              setLoading(false);
            }
          }
        });
      },
    }).addTo(map);
    lastGridLineMode = shouldDrawGridLines();

    selectedBoundaryLayer.bringToFront();
    if (fit) {
      const compactLayout = window.innerWidth <= 760;
      map.fitBounds(selectedBoundaryLayer.getBounds(), {
        paddingTopLeft: compactLayout ? [24, 112] : [24, 72],
        paddingBottomRight: compactLayout
          ? [24, detailPanel.offsetHeight + 24]
          : [Math.min(detailPanel.offsetWidth + 34, window.innerWidth * 0.46), 42],
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
  const requestedGridId = new URLSearchParams(window.location.search).get("grid");
  if (requestedGridId) {
    setBootStatus(`Atver grid šūnu ${requestedGridId}...`);
    await openPilotGridById(requestedGridId);
  }
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

backButton.addEventListener("click", async () => {
  if (demViewActive) {
    try {
      setLoading(true);
      await restoreMunicipalityView({ fit: true });
    } catch (error) {
      console.error(error);
      alert("Neizdevās atgriezties uz Ogres novada gridu.");
    } finally {
      setLoading(false);
    }
    return;
  }
  showOverview({ fit: true }).catch((error) => {
    console.error(error);
    alert("Neizdevās atgriezties uz Latvijas karti.");
  });
});

document.querySelectorAll("[data-dem-mode]").forEach((button) => {
  button.addEventListener("click", () => setDemMode(button.dataset.demMode));
});

demOpacity.addEventListener("input", () => {
  const value = Number(demOpacity.value);
  demOpacityValue.textContent = `${value}%`;
  demOverlay?.setOpacity(value / 100);
});

dem3dFrame.addEventListener("load", () => {
  dem3dStage.classList.remove("is-loading");
  dem3dLoading.hidden = true;
});

dem3dOrbit.addEventListener("click", () => {
  const viewer = getDem3dApp();
  if (!viewer?.controls) return;
  const active = !viewer.controls.autoRotate;
  viewer.setRotateAnimationMode(active);
  setDem3dButtonState(dem3dOrbit, active);
});

dem3dWireframe.addEventListener("click", () => {
  const viewer = getDem3dApp();
  if (!viewer) return;
  const active = !viewer._wireframeMode;
  viewer.setWireframeMode(active);
  setDem3dButtonState(dem3dWireframe, active);
});

dem3dReset.addEventListener("click", () => {
  const viewer = getDem3dApp();
  if (!viewer?.controls) return;
  viewer.controls.reset();
  viewer.render();
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
