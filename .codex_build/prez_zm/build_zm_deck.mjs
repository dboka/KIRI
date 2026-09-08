import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/deniss.boka/MESLI_PROJECT/KIRI";
const buildDir = path.join(workspaceDir, ".codex_build", "prez_zm");
const outputDir = path.join(workspaceDir, "outputs", "zm_prez_20260909");
const SKILL_DIR = "C:/Users/deniss.boka/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations";
const RUNTIME_PYTHON = "C:/Users/deniss.boka/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const RUNTIME_NODE_MODULES = "C:/Users/deniss.boka/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const FINAL_PPTX = path.join(outputDir, "PREZ_ZM_KIRI_2026-09-09.pptx");
const ROOT_COPY = path.join(workspaceDir, "PREZ_ZM_KIRI_2026-09-09.pptx");

process.env.RUNTIME_NODE_MODULES = RUNTIME_NODE_MODULES;

const { makeNativeBulletParagraphs, applyPresentationChartFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools", "artifact_tool_utils.mjs")).href,
);

await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });

const bgCover = await fs.readFile(path.join(buildDir, "media", "image2.png"));
const bgHeader = await fs.readFile(path.join(buildDir, "media", "image1.png"));
const screenshotCalendar = await fs.readFile(path.join(buildDir, "kiri_overview_calendar.png"));
const screenshotDetail = await fs.readFile(path.join(buildDir, "kiri_detail_cell.png"));
const analysis = JSON.parse(await fs.readFile(path.join(buildDir, "manifest_analysis.json"), "utf8"));

const family = "Arial";
const blue = "#004B87";
const darkBlue = "#083C66";
const text = "#142735";
const muted = "#66758A";
const lightLine = "#D8DEE7";
const green = "#69B88F";
const yellow = "#F4D35E";
const orange = "#F08A4B";
const red = "#C94F44";
const paleGreen = "#E4F1DC";
const paleBlue = "#E8F1F8";

const presentation = Presentation.create({
  slideSize: { width: 960, height: 720 },
});

function addImage(slide, bytes, position, alt, fit = "cover") {
  return slide.images.add({
    blob: bytes,
    contentType: "image/png",
    alt,
    fit,
    position,
  });
}

function addHeader(slide, section = "KIRI-LV", slideNo = "") {
  addImage(slide, bgHeader, { left: 0, top: 0, width: 960, height: 720 }, "LVĢMC presentation header background", "cover");
  if (section) addText(slide, section, 58, 684, 330, 22, { size: 15, color: "#8795AD" });
  if (slideNo) addText(slide, String(slideNo), 888, 684, 28, 22, { size: 15, color: "#8795AD", align: "right" });
}

function addText(slide, value, left, top, width, height, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: family,
    fontSize: opts.size ?? 24,
    bold: opts.bold ?? false,
    italic: opts.italic ?? false,
    color: opts.color ?? text,
    alignment: opts.align ?? "left",
    verticalAlignment: opts.vAlign ?? "top",
    autoFit: "shrinkText",
    wrap: "square",
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  };
  return shape;
}

function addTitle(slide, title, subtitle) {
  addText(slide, title, 58, 138, 830, 58, { size: 34, bold: true, color: blue });
  if (subtitle) addText(slide, subtitle, 60, 196, 760, 36, { size: 17, color: muted });
}

function addBullets(slide, items, left, top, width, height, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: opts.fill ?? "none",
    line: opts.line ?? { fill: "none", width: 0 },
  });
  shape.text = makeNativeBulletParagraphs(items, {
    marginLeftPoints: opts.marginLeftPoints ?? 18,
    hangingPoints: opts.hangingPoints ?? 8,
    spaceAfterPoints: opts.spaceAfterPoints ?? 8,
  });
  shape.text.style = {
    typeface: family,
    fontSize: opts.size ?? 22,
    color: opts.color ?? text,
    autoFit: "shrinkText",
    wrap: "square",
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  };
  return shape;
}

function addKpi(slide, value, label, left, top, width, color = blue) {
  addText(slide, value, left, top, width, 48, { size: 32, bold: true, color });
  addText(slide, label, left, top + 48, width, 38, { size: 15, color: muted });
}

function addRule(slide, left, top, width, color = lightLine) {
  slide.shapes.add({
    geometry: "line",
    position: { left, top, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: 1 },
  });
}

function addSectionLabel(slide, label, left, top, width, fill = paleBlue) {
  const box = slide.shapes.add({
    geometry: "rect",
    position: { left, top, width, height: 32 },
    fill,
    line: { style: "solid", fill: "#C7D7E6", width: 1 },
  });
  box.text = label;
  box.text.style = {
    typeface: family,
    fontSize: 15,
    bold: true,
    color: darkBlue,
    alignment: "center",
    verticalAlignment: "middle",
    autoFit: "shrinkText",
  };
  return box;
}

function addNotes(slide, lines, sources = []) {
  const body = [
    ...lines,
    "",
    ...(sources.length ? ["Avoti:", ...sources] : []),
  ].join("\n");
  slide.speakerNotes.textFrame.setText(body);
  slide.speakerNotes.setVisible(true);
}

function addSourceLine(slide, line) {
  addText(slide, line, 58, 655, 780, 20, { size: 11, color: "#8A94A8" });
}

// 1
{
  const slide = presentation.slides.add();
  addImage(slide, bgCover, { left: 0, top: 0, width: 960, height: 720 }, "LVĢMC title background", "cover");
  addText(slide, "LVĢMC", 216, 106, 260, 62, { size: 44, color: blue });
  addText(slide, "Kūtsmēslu izkliedes riska karte", 52, 336, 800, 58, { size: 34, color: blue });
  addText(slide, "KIRI-LV pilotprojekts. Sagatavošanās sarunai ar Zemkopības ministriju 09.09.2026", 55, 398, 780, 50, { size: 18, color: muted });
  addNotes(slide, [
    "Sāku ar ļoti īsu rāmi: šis nav gala normatīvais instruments, bet pirmais aizstāvamais pilots.",
    "Mērķis sapulcei ir parādīt, kādus datus esmu atradis, kā esmu tos salicis vienā ķēdē un kā jau darbojas karte.",
    "Lūgums ZM pusē būs palīdzēt nofiksēt metodikas un normatīvos jautājumus, lai pilotu var pārvērst oficiāli izmantojamā rīkā.",
  ]);
}

// 2
{
  const slide = presentation.slides.add();
  addHeader(slide, "KIRI-LV pilots", 2);
  addTitle(slide, "Kas jau ir apkopots", "Stāsts sapulcei: dati, aprēķins un demonstrējams karšu rīks");
  addKpi(slide, "60", "dienu ripojošs kalendārs", 72, 274, 210, blue);
  addKpi(slide, "43", "pašvaldības pārskata kartē", 324, 274, 240, blue);
  addKpi(slide, "1 km", "detalizētais aprēķina režģis", 610, 274, 230, blue);
  addRule(slide, 70, 382, 820);
  addBullets(slide, [
    "Darba plāna satelītu bloks 2.1-2.4 jau sasaistīts ar H-SAF, Copernicus SWI un CLIDATA nokrišņu indikatoriem.",
    "Pilotā dati tiek normalizēti vienotā 1 km telpiskā režģī un rādīti pašvaldību līmenī ar iespēju atvērt grid skatu.",
    "Rīks jau atdala riska līmeni, aktīvos iemeslus, konteksta iemeslus un datu pārliecības līmeni.",
  ], 76, 410, 790, 150, { size: 20, spaceAfterPoints: 9 });
  addSourceLine(slide, "Iekšējie avoti: Darbu_plans.xlsx, KIRI-LV projekta dokuments, GRID_SAGATAVE/frontend/data/data_metadata.json");
  addNotes(slide, [
    "Šeit varu pateikt: esmu koncentrējies uz to, kas vajadzīgs pirmajai sapulcei, nevis uz pilnu gala sistēmu.",
    "Svarīgākais ir pierādīt datu ķēdi. Mums jau ir kartes prototips, kur lietotājs izvēlas datumu, redz pašvaldības kopējo risku un var atvērt 1 km detalizāciju.",
    "Skaitļi šajā slaidā nāk no pašreizējā frontend datu laidiena.",
  ], [
    "C:/Users/deniss.boka/Downloads/Darbu_plans.xlsx",
    "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/GRID_SAGATAVE/frontend/data/data_metadata.json",
  ]);
}

// 3
{
  const slide = presentation.slides.add();
  addHeader(slide, "Darba plāna sasaite", 3);
  addTitle(slide, "Darba plāna punkti, kurus sedz pilots", "Slaids sasaista ZM darba uzdevumu ar reāli pārbaudītu prototipa funkcionalitāti");
  const table = slide.tables.add({
    rows: 6,
    columns: 3,
    left: 58,
    top: 250,
    width: 844,
    height: 310,
    columnTracks: [{ mode: "fixed", value: 80 }, { mode: "fr", value: 1.5 }, { mode: "fr", value: 1.4 }],
    values: [
      ["Punkts", "Darba plāna jēga", "Pilotā jau parādāms"],
      ["2.1", "SSM un SWI satelītdatu ieguve", "H-SAF SSM un Copernicus SWI avoti identificēti un pieslēgti datu ķēdei"],
      ["2.2", "Telpisks pārklājums Latvijai", "1 km grid slāņi, pašvaldību pārskats un dienas manifesti"],
      ["2.3", "Satelīts pret stacijām", "Datu modelis paredz salīdzinājumu ar staciju sensoriem"],
      ["2.4", "Riska teritoriju algoritms", "KIRI riska līmenis 1-5, reason codes un pārliecības līmenis"],
      ["3.1-4.1", "References, sliekšņi un digitāls rīks", "60 dienu vēsture, kartes demo un nākamais sliekšņu kalibrēšanas posms"],
    ],
  });
  table.styleOptions = { headerRow: true, bandedRows: true };
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 3 }).assign({
    fill: blue,
    textStyle: { typeface: family, fontSize: 14, bold: true, color: "#FFFFFF" },
  });
  table.cells.block({ row: 1, column: 0, rowCount: 5, columnCount: 3 }).assign({
    textStyle: { typeface: family, fontSize: 13, color: text },
    margins: { left: 7, right: 7, top: 5, bottom: 5 },
  });
  table.borders.assign({ style: "solid", fill: "#B9C7D5", width: 1 });
  addNotes(slide, [
    "Šo slaidu izmantoju, lai ātri piesaistītu prezentāciju darba plānam.",
    "Es nerunāju abstrakti par satelītiem. Katru darba plāna punktu mēģinu sasaistīt ar kaut ko, ko var parādīt prototipā.",
    "3.1 un 3.2 vēl ir nākamais metodiskais posms: vajag vēsturisko references periodu un sliekšņu saskaņošanu ar monitoringa datiem.",
  ], [
    "C:/Users/deniss.boka/Downloads/Darbu_plans.xlsx",
  ]);
}

// 4
{
  const slide = presentation.slides.add();
  addHeader(slide, "Datu avoti", 4);
  addTitle(slide, "Datu avotu kodols", "Pirmajai versijai pietiek ar pieciem indikatoriem, vēlāk pievieno hard-stop un hidroloģiju");
  const rows = [
    ["CLIDATA", "P30, P90, P730", "Nokrišņu fons īsā, sezonālā un ilgākā periodā"],
    ["H-SAF SSM", "Surface Soil Moisture", "Virsmas slāņa mitruma signāls zem 5 cm"],
    ["Copernicus SWI", "Soil Water Index", "Ikdienas Eiropas 1 km režģis, profila mitruma dinamika"],
    ["Stacijas", "Augsnes mitrums un temperatūra", "Verifikācija, sasalums un lokāls ground truth"],
    ["LBTU", "Drenas, mazie baseini, N/P epizodes", "Indeksa kalibrācija pret reālu zudumu risku"],
  ];
  let top = 242;
  rows.forEach((r, i) => {
    const fill = i % 2 === 0 ? "#FFFFFF" : "#F4F7FA";
    slide.shapes.add({ geometry: "rect", position: { left: 64, top, width: 832, height: 56 }, fill, line: { style: "solid", fill: "#D7E0EA", width: 1 } });
    addText(slide, r[0], 82, top + 13, 150, 28, { size: 18, bold: true, color: blue });
    addText(slide, r[1], 254, top + 10, 220, 32, { size: 16, bold: true, color: text });
    addText(slide, r[2], 500, top + 10, 360, 34, { size: 15, color: text });
    top += 58;
  });
  addSourceLine(slide, "Ārējie avoti: EUMETSAT H-SAF, Copernicus Land Monitoring Service, LVĢMC CLIDATA");
  addNotes(slide, [
    "Galvenais vēstījums: mums nav jāizdomā datu pasaule no nulles. Ir trīs praktiski avoti pirmajai versijai: nokrišņi, H-SAF SSM un Copernicus SWI.",
    "H-SAF dod neatkarīgu virsmas mitruma signālu. Copernicus SWI dod ikdienas 1 km Eiropas produktu, kas ir ļoti ērts operacionālai kartei.",
    "Stacijas un LBTU dati vajadzīgi ne tikai papildu slāņiem, bet arī uzticamai validācijai.",
  ], [
    "EUMETSAT H28 catalog: https://user.eumetsat.int/catalogue/EO:EUM:DAT:1032",
    "EUMETSAT H28 EUMETCast notice: https://user.eumetsat.int/news-events/news/new-h-saf-ascat-surface-soil-moisture-h28-product-on-eumet-cast",
    "EUMETSAT H29 EUMETCast notice: https://user.eumetsat.int/news-events/news/new-h-saf-ascat-surface-soil-moisture-h29-product-on-eumet-cast",
    "H-SAF soil moisture: https://hsaf.meteoam.it/products/soil-moisture",
    "Copernicus SWI v2: https://land.copernicus.eu/en/products/soil-moisture/daily-soil-water-index-europe-1km-v2",
  ]);
}

// 5
{
  const slide = presentation.slides.add();
  addHeader(slide, "Apstrādes ķēde", 5);
  addTitle(slide, "Kā dati kļūst par karti", "Operatīvais prototips strādā kā reproducējama datu ķēde līdz GitHub Pages kartei");
  const steps = [
    ["1", "Iegūt", "H-SAF, Copernicus SWI un CLIDATA avoti"],
    ["2", "Izgriezt Latviju", "Vienots datums, CRS un 1 km režģis"],
    ["3", "Aprēķināt indikatorus", "P30/P90/P730, SSM, SWI un kvalitātes pazīmes"],
    ["4", "Normalizēt risku", "1-5 līmeņi, aktīvie iemesli un pārliecība"],
    ["5", "Publicēt", "Pašvaldību pārskats un grid vērtības pārlūkā"],
  ];
  steps.forEach((s, i) => {
    const left = 68 + i * 170;
    addSectionLabel(slide, s[0], left, 260, 44, i < 2 ? paleBlue : paleGreen);
    addText(slide, s[1], left, 310, 142, 28, { size: 20, bold: true, color: blue });
    addText(slide, s[2], left, 346, 138, 82, { size: 14, color: text });
    if (i < 4) addRule(slide, left + 118, 276, 62, "#A9B7C6");
  });
  addText(slide, "Praktiskais ieguvums", 78, 492, 260, 28, { size: 20, bold: true, color: blue });
  addBullets(slide, [
    "Frontend glabā statisko grid ģeometriju vienreiz, bet katrai dienai ielādē tikai vērtības.",
    "Dienas refresh ģenerē tikai trūkstošo datu posmu, tāpēc rīks paliek uzturams arī ar lielu datu vēsturi.",
  ], 78, 528, 760, 74, { size: 18, spaceAfterPoints: 6 });
  addSourceLine(slide, "Koda avoti: GRID_SAGATAVE/ARCHITECTURE.md un GRID_SAGATAVE/README.md");
  addNotes(slide, [
    "Šis ir tehniskais slaids, bet to var izstāstīt vienkārši: dati ienāk no avotiem, tiek salikti vienā režģī, aprēķināti un publicēti kartē.",
    "Ļoti svarīgi ZM sapulcei: rīks nav vienreizēja bilde. Tas ir datu process, ko var atkārtot katru dienu.",
    "Pašreizējā arhitektūra samazina failu apjomu, jo ģeometrija nav jāglabā katram datumam no jauna.",
  ], [
    "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/GRID_SAGATAVE/ARCHITECTURE.md",
    "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/GRID_SAGATAVE/README.md",
  ]);
}

// 6
{
  const slide = presentation.slides.add();
  addHeader(slide, "60 dienu dati", 6);
  addTitle(slide, "Riska signāls pēdējā datu logā", "Pilotā var parādīt ne tikai karti, bet arī datu dinamiku pa datumiem");
  const sample = analysis.sample_dates;
  const chart = slide.charts.add("line", {
    position: { left: 70, top: 245, width: 548, height: 285 },
    categories: sample.map((d) => d.date.slice(5)),
    series: [
      { name: "Riska 4-5 šūnas, %", values: sample.map((d) => Math.round(d.r45_pct)), line: { style: "solid", fill: orange, width: 3 }, marker: { symbol: "circle", size: 7 } },
      { name: "Riska 5 šūnas, %", values: sample.map((d) => Math.round(d.r5_pct)), line: { style: "solid", fill: red, width: 3 }, marker: { symbol: "circle", size: 7 } },
    ],
    legend: { position: "bottom", overlay: false, textStyle: { typeface: family, fontSize: 12, fill: muted } },
    yAxis: { numberFormatCode: "0", min: 0, max: 100, majorGridlines: { style: "solid", fill: "#E3E8EF", width: 1 }, textStyle: { typeface: family, fontSize: 12, fill: muted }, title: { text: "% no redzamām šūnām", textStyle: { typeface: family, fontSize: 12, fill: muted } } },
    xAxis: { textStyle: { typeface: family, fontSize: 12, fill: muted }, line: { style: "solid", fill: "#CED7E2", width: 1 } },
    chartFill: "#FFFFFF",
    plotAreaFill: "#FFFFFF",
  });
  applyPresentationChartFont(chart, { fontFamily: family });
  addKpi(slide, `${analysis.latest.r45_pct}%`, "redzamo šūnu 2026-09-06 ir 4. vai 5. riska līmenī", 660, 274, 215, orange);
  addKpi(slide, `${analysis.latest.r5_pct}%`, "redzamo šūnu 2026-09-06 ir 5. riska līmenī", 660, 394, 215, red);
  addText(slide, "Piezīme: jaunākajā datumā SWI vēl kavējas, tāpēc rīks parāda vidēju pārliecību, nevis slēpj datu trūkumu.", 660, 514, 216, 66, { size: 14, color: text });
  addSourceLine(slide, "Datu avots: GRID_SAGATAVE/frontend/data/calendar_manifest.json");
  addNotes(slide, [
    "Šo slaidu izmantoju, lai parādītu, ka no prototipa datiem var iegūt arī analītiku, ne tikai karti.",
    "Izvēlēti daži datumi no 60 dienu loga, lai redzētu dinamiku. Precīzākai metodikai vēl jāiet uz vēsturisko references periodu.",
    "2026-09-06 93 procenti redzamo šūnu ir 4. vai 5. līmenī. Tas nav juridisks aizliegums, bet riska signāls pēc pašreizējās pilotmetodikas.",
  ], [
    "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/GRID_SAGATAVE/frontend/data/calendar_manifest.json",
  ]);
}

// 7
{
  const slide = presentation.slides.add();
  addHeader(slide, "Pilotsaites demonstrācija", 7);
  addTitle(slide, "Latvijas pārskata karte", "Lietotājs sāk ar vienu saprotamu riska karti un datuma izvēli");
  addImage(slide, screenshotCalendar, { left: 48, top: 236, width: 610, height: 382 }, "KIRI-LV overview map with date calendar", "cover");
  addBullets(slide, [
    "Augšā redzams aktīvais datums.",
    "Datuma panelis rāda pēdējo 60 dienu logu.",
    "Leģenda skaidro 1-5 riska līmeņus.",
    "Klikšķis uz pašvaldības atver 1 km grid skatu.",
  ], 692, 270, 198, 210, { size: 18, spaceAfterPoints: 8 });
  addText(slide, "Publiskā saite: https://dboka.github.io/KIRI/", 692, 534, 210, 36, { size: 15, bold: true, color: blue });
  addNotes(slide, [
    "Šajā brīdī sapulcē var atvērt saiti un parādīt dzīvo prototipu.",
    "Es sāku no Latvijas kartes. Te nav sarežģītu slāņu pārslēgu. Mērķis ir, lai lietotājs uzreiz saprot, kur šodien vai izvēlētajā datumā ir augstāks risks.",
    "Datuma izvēlē redzams arī kvalitātes signāls. Ja SWI kavējas, rīks to parāda.",
  ], [
    "https://dboka.github.io/KIRI/",
    "Lokālais ekrānattēls no GRID_SAGATAVE/frontend, uzņemts 2026-09-07.",
  ]);
}

// 8
{
  const slide = presentation.slides.add();
  addHeader(slide, "Grid detalizācija", 8);
  addTitle(slide, "Pašvaldības 1 km grid skats", "Klikšķis uz novada parāda, kur novada iekšienē veidojas augstais risks");
  addImage(slide, screenshotDetail, { left: 44, top: 230, width: 620, height: 388 }, "KIRI-LV municipality grid view with selected cell", "cover");
  addText(slide, "Ko demonstrēt", 700, 254, 178, 28, { size: 20, bold: true, color: blue });
  addBullets(slide, [
    "Novada panelī redzams kopējais risks un augsta riska šūnu īpatsvars.",
    "Grid šūna atver indikatorus: H-SAF SSM, P30, P90, P730 un SWI, kad tas ir pieejams.",
    "Reason codes rāda, kāpēc teritorija nokļuvusi riska līmenī.",
  ], 700, 294, 190, 190, { size: 16, spaceAfterPoints: 7 });
  addText(slide, "Šis ir svarīgākais pilots: pašvaldība nav tikai viena krāsa, aiz tās ir pārbaudāmas šūnas.", 700, 528, 190, 54, { size: 15, color: text });
  addNotes(slide, [
    "Šis ir praktiskākais slaids. Te parādu, ka karte nav tikai pašvaldības vidējā vērtība.",
    "Klikšķis uz novada atver grid skatu. Klikšķis uz šūnas parāda konkrētos indikatorus un iemeslus.",
    "Tas palīdz aizstāvēt pieeju: lēmumu var komunicēt pašvaldību līmenī, bet aprēķinu turēt telpiski detalizētu.",
  ], [
    "Lokālais ekrānattēls no GRID_SAGATAVE/frontend, uzņemts 2026-09-07.",
  ]);
}

// 9
{
  const slide = presentation.slides.add();
  addHeader(slide, "Riska algoritms", 9);
  addTitle(slide, "Pašreizējais riska aprēķins", "v0.1.3 dod skaidrojamu risku, bet sliekšņi vēl jāvalidē pret vēsturi un stacijām");
  const cols = [
    ["Indikatori", "P30, P90, P730, H-SAF SSM un Copernicus SWI tiek pārvērsti 1-5 riska līmenī."],
    ["Kombinācija", "Konfigurācijā izmantota moisture-first pieeja ar vismaz trīs aktīviem indikatoriem."],
    ["Skaidrojums", "Katram riskam līdzi nāk aktīvie iemesli, konteksts un pārliecības līmenis."],
  ];
  cols.forEach((c, i) => {
    const left = 72 + i * 282;
    slide.shapes.add({ geometry: "rect", position: { left, top: 270, width: 236, height: 190 }, fill: i === 0 ? paleBlue : (i === 1 ? "#FFF6DF" : "#F2F6F0"), line: { style: "solid", fill: "#C8D5DE", width: 1 } });
    addText(slide, c[0], left + 18, 292, 200, 26, { size: 20, bold: true, color: blue });
    addText(slide, c[1], left + 18, 332, 198, 92, { size: 16, color: text });
  });
  addText(slide, "Svarīgi sapulcei", 78, 520, 200, 28, { size: 20, bold: true, color: blue });
  addText(slide, "Pilotā šobrīd ir tehniski strādājošs aprēķins. ZM, LVĢMC un LBTU sarunā jāvienojas, kā robežvērtības zinātniski nostiprināt Latvijas apstākļiem.", 78, 554, 745, 56, { size: 18, color: text });
  addSourceLine(slide, "Koda avots: GRID_SAGATAVE/config/normalization_v01.yaml");
  addNotes(slide, [
    "Šeit necenšos pārdot sliekšņus kā galīgus. Godīgi saku: pilotā ir strādājoša loģika, kas ļauj testēt rezultātu.",
    "Nākamais zinātniskais darbs ir robežvērtības. Tās jānosaka no vēsturiskajiem datiem, stacijām un monitoringa rezultātiem.",
    "Manuprāt, ZM sapulcē tas ir jāpārvērš par darba uzdevumu, nevis par strīdu par vienu konkrētu skaitli.",
  ], [
    "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/GRID_SAGATAVE/config/normalization_v01.yaml",
  ]);
}

// 10
{
  const slide = presentation.slides.add();
  addHeader(slide, "Validācija", 10);
  addTitle(slide, "Kā pierādīt satelītdatu kvalitāti", "2.3, 3.1 un 3.2 prasa salīdzinājumu ar novērojumiem un vēsturisko fonu");
  addSectionLabel(slide, "Stacija pret gridu", 74, 262, 230, paleBlue);
  addSectionLabel(slide, "Vēsturiskā reference", 365, 262, 230, paleGreen);
  addSectionLabel(slide, "Robežvērtības", 656, 262, 230, "#FFF4D6");
  addBullets(slide, [
    "Tuvākā grid šūna vai 3x3 šūnu logs ap staciju.",
    "SSM/SWI salīdzinājums ar augsnes mitrumu un temperatūru.",
    "Kvalitātes pazīmes pie katra datuma.",
  ], 80, 318, 220, 150, { size: 16, spaceAfterPoints: 6 });
  addBullets(slide, [
    "Sezona un reģions jāņem vērā.",
    "P30/P90/P730 var pārvērst percentilēs.",
    "SWI un H-SAF jāvērtē pret vairāku gadu fonu.",
  ], 371, 318, 220, 150, { size: 16, spaceAfterPoints: 6 });
  addBullets(slide, [
    "Pārmitra un sasalusi augsne jādefinē atsevišķi.",
    "Juridiskais hard-stop jāglabā atsevišķi no hidroloģiskā riska.",
    "LBTU dati palīdz pārbaudīt N/P zudumu epizodes.",
  ], 662, 318, 220, 162, { size: 16, spaceAfterPoints: 6 });
  addText(slide, "Rezultāts: metodika, kas ir izskaidrojama arī tad, ja dati kavējas vai viens avots uz konkrētu dienu nav pieejams.", 86, 540, 760, 42, { size: 18, bold: true, color: text });
  addNotes(slide, [
    "Šis ir metodikas slaids. Galvenais teikt: satelītu dati jāvalidē, un pilots jau sagatavo datu struktūru šādai validācijai.",
    "Salīdzinājumam nevajag tikai vienu punktu kartē. Var lietot tuvāko grid šūnu vai 3x3 apkārtni, lai mazinātu ģeolokācijas un mēroga atšķirības.",
    "Robežvērtības pārmitrumam un sasalumam jābalsta datos. Juridiskais aizliegums jānodala no riska indeksa.",
  ]);
}

// 11
{
  const slide = presentation.slides.add();
  addHeader(slide, "Demonstrācijas teksts", 11);
  addTitle(slide, "Ko tieši parādīt ZM sapulcē", "Īsa demonstrācijas secība, ja būs jārunā un jārāda saite");
  const demo = [
    ["1", "Atvērt saiti", "https://dboka.github.io/KIRI/"],
    ["2", "Parādīt datumu", "60 dienu kalendārs, jaunākais datums un SWI kavēšanās atzīme"],
    ["3", "Klikšķināt uz novada", "Pašvaldības risku nomaina 1 km grid detalizācija"],
    ["4", "Klikšķināt uz šūnas", "Parādās indikatori, reason codes un rekomendācija"],
    ["5", "Noslēgt ar metodiku", "Ko vajag saskaņot, lai pilots kļūst par oficiālu rīku"],
  ];
  let y = 248;
  demo.forEach((d) => {
    addSectionLabel(slide, d[0], 78, y, 42, "#FFFFFF");
    addText(slide, d[1], 142, y + 2, 210, 28, { size: 19, bold: true, color: blue });
    addText(slide, d[2], 370, y + 4, 478, 32, { size: 16, color: text });
    y += 62;
  });
  addNotes(slide, [
    "Šo var lietot kā tiešo demonstrācijas špikeri.",
    "Es atveru saiti, parādu, ka kartē ir datuma izvēle, tad izvēlos konkrētu pašvaldību un vienu grid šūnu.",
    "Svarīgi nerunāt pārāk ilgi par katru pogu. Galvenais ir parādīt datu ceļu no avotiem līdz lēmuma atbalstam.",
  ]);
}

// 12
{
  const slide = presentation.slides.add();
  addHeader(slide, "Nākamie lēmumi", 12);
  addTitle(slide, "Jautājumi, kurus vajag nofiksēt ar ZM", "Pēc demonstrācijas vajadzīgs kopīgs metodikas un datu piekļuves rāmis");
  addBullets(slide, [
    "Kuras robežvērtības ZM vēlas redzēt kā metodiski apstiprināmas pirmajā posmā.",
    "Kā piekļūt un izmantot 10 LVĢMC augsnes mitruma un temperatūras staciju datus validācijai.",
    "Kuri normatīvie hard-stop noteikumi jāievieš kā atsevišķs konfigurējams slānis.",
    "Kāds ir minimālais pilots, ko var demonstrēt nākamajā projekta starpposmā.",
    "Kā sadalīt lomas starp LVĢMC, ZM un LBTU sliekšņu validācijai un N/P riska pārbaudei.",
  ], 84, 262, 760, 230, { size: 20, spaceAfterPoints: 10 });
  addText(slide, "Mans ieteikums sapulces noslēgumam: vienoties par datu validācijas protokolu un robežvērtību darba grupu.", 86, 552, 738, 42, { size: 20, bold: true, color: blue });
  addNotes(slide, [
    "Noslēdzu ar praktiskiem jautājumiem.",
    "Es prasītu nevis vispārīgu atbalstu, bet konkrētu nākamo soli: validācijas protokols, staciju dati un robežvērtību saskaņošana.",
    "Tad pilots iegūst skaidru ceļu no demonstrācijas uz izmantojamu metodiku.",
  ]);
}

const requirements = {
  explicitTotalSlideCount: 12,
  requiredNativeTableOwnerSlides: [3],
  requiredNativeChartOwnerSlides: [6],
  materializeLiteralChartWorkbooks: true,
};
const fontPolicy = { basis: "design", families: [family] };
const expectedSlideSizeEmu = "9144000,6858000";

const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "prez_zm_candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", expectedSlideSizeEmu,
    "--validate-bullet-geometry",
    "--validate-heading-fit",
    "--require-native-table-slide", "3",
  ],
  requiredNativeTableOwnerSlides: requirements.requiredNativeTableOwnerSlides,
  requiredNativeChartOwnerSlides: requirements.requiredNativeChartOwnerSlides,
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "PREZ_ZM_KIRI_2026-09-09.validation.json"),
});

await fs.copyFile(FINAL_PPTX, ROOT_COPY);
console.log(JSON.stringify({ final: FINAL_PPTX, rootCopy: ROOT_COPY }, null, 2));
