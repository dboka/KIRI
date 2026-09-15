(async function () {
  const [meta, heightBuffer] = await Promise.all([
    fetch("pilot-scene.json").then((response) => response.json()),
    fetch("terrain-buffer500.bin").then((response) => response.arrayBuffer()),
  ]);

  const heights = new Float32Array(heightBuffer);
  const size = meta.size;
  const host = document.querySelector("#scene");
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07151d);
  scene.fog = new THREE.FogExp2(0x07151d, 0.00036);

  const camera = new THREE.PerspectiveCamera(43, innerWidth / innerHeight, 1, 12000);
  camera.position.set(1420, 1480, 1780);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputEncoding = THREE.sRGBEncoding;
  host.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.065;
  controls.target.set(0, 70, 0);
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.minDistance = 500;
  controls.maxDistance = 4700;
  controls.saveState();

  scene.add(new THREE.HemisphereLight(0xbfe9f2, 0x102117, 1.15));
  const sun = new THREE.DirectionalLight(0xffffff, 1.25);
  sun.position.set(-1200, 2100, 900);
  scene.add(sun);

  const [xmin, ymin, xmax, ymax] = meta.bounds;
  const centerX = (xmin + xmax) / 2;
  const centerY = (ymin + ymax) / 2;
  const z0 = meta.heightMin;
  const zScale = 4.2;

  function elevation(x, y) {
    const column = Math.max(0, Math.min(size - 1, Math.round((x - xmin) / (xmax - xmin) * (size - 1))));
    const row = Math.max(0, Math.min(size - 1, Math.round((ymax - y) / (ymax - ymin) * (size - 1))));
    return (heights[row * size + column] - z0) * zScale;
  }

  function xyz(point, lift = 0) {
    return new THREE.Vector3(point[0] - centerX, elevation(point[0], point[1]) + lift, -(point[1] - centerY));
  }

  const terrainGeometry = new THREE.PlaneBufferGeometry(2000, 2000, size - 1, size - 1);
  terrainGeometry.rotateX(-Math.PI / 2);
  const terrainPositions = terrainGeometry.attributes.position;
  for (let row = 0; row < size; row += 1) {
    for (let column = 0; column < size; column += 1) {
      terrainPositions.setY(row * size + column, (heights[row * size + column] - z0) * zScale);
    }
  }
  terrainPositions.needsUpdate = true;
  terrainGeometry.computeVertexNormals();

  const texture = await new Promise((resolve) => new THREE.TextureLoader().load("restriction-terrain.png", resolve));
  texture.encoding = THREE.sRGBEncoding;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  const terrainMaterial = new THREE.MeshStandardMaterial({
    map: texture,
    roughness: 0.9,
    metalness: 0.02,
    side: THREE.DoubleSide,
  });
  const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
  terrain.renderOrder = 0;
  scene.add(terrain);

  // OSM draped on the same DEM geometry, aligned to the LKS-92 bounds.
  const osmTexture = await new Promise((resolve, reject) => {
    const loader = new THREE.TextureLoader();
    loader.load("osm-basemap.png?v=3", resolve, undefined, reject);
  });
  osmTexture.encoding = THREE.sRGBEncoding;
  osmTexture.minFilter = THREE.LinearFilter;
  osmTexture.magFilter = THREE.LinearFilter;
  osmTexture.generateMipmaps = false;
  const osmMaterial = new THREE.MeshBasicMaterial({
    map: osmTexture,
    transparent: true,
    opacity: 0.62,
    depthWrite: false,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
    side: THREE.DoubleSide,
  });
  const osmTerrain = new THREE.Mesh(terrainGeometry, osmMaterial);
  osmTerrain.name = "osm";
  osmTerrain.renderOrder = 1;
  osmTerrain.visible = false;

  const groups = {};
  function layerGroup(key) {
    if (!groups[key]) {
      groups[key] = new THREE.Group();
      groups[key].name = key;
      scene.add(groups[key]);
    }
    return groups[key];
  }
  groups.restriction = terrain;
  groups.osm = osmTerrain;
  scene.add(osmTerrain);
  layerGroup("fields");
  layerGroup("catchments");
  layerGroup("flow");
  layerGroup("buildings");
  layerGroup("companies");

  // OSM building footprints are extruded into simple clickable 3D volumes.
  // Heights come from the OSM `height` tag when present; otherwise a
  // conservative type-based default is used.
  for (const building of meta.buildings || []) {
    if (!building.ring || building.ring.length < 4) continue;
    const shape = new THREE.Shape();
    building.ring.forEach((point, index) => {
      const p = xyz(point, 0);
      if (index === 0) shape.moveTo(p.x, -p.z); else shape.lineTo(p.x, -p.z);
    });
    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: Math.max(2, Number(building.height) || 4), bevelEnabled: false,
      curveSegments: 1, steps: 1,
    });
    geometry.rotateX(-Math.PI / 2);
    const center = building.ring.reduce((acc, point) => [acc[0] + point[0], acc[1] + point[1]], [0, 0]);
    center[0] /= building.ring.length; center[1] /= building.ring.length;
    geometry.translate(0, elevation(center[0], center[1]), 0);
    const material = new THREE.MeshStandardMaterial({ color: 0xe8a66b, transparent: true, opacity: 0.82, roughness: 0.82 });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.renderOrder = 9;
    mesh.userData = { kind: "building", name: building.name || "OSM ēka", type: building.type, height: building.height };
    groups.buildings.add(mesh);
  }

  for (const company of meta.companies || []) {
    const house = new THREE.Group();
    const base = new THREE.Mesh(
      new THREE.BoxGeometry(18, 12, 16),
      new THREE.MeshStandardMaterial({ color: 0xd9825b, roughness: 0.82 }),
    );
    base.position.y = 6;
    const roof = new THREE.Mesh(
      new THREE.ConeGeometry(14, 8, 4),
      new THREE.MeshStandardMaterial({ color: 0x7b3f4a, roughness: 0.78 }),
    );
    roof.rotation.y = Math.PI / 4;
    roof.position.y = 16;
    house.add(base, roof);
    house.position.copy(xyz(company.point, 0));
    house.renderOrder = 16;
    house.userData = { kind: "company", id: company.id, name: company.name, type: company.type, tags: company.tags || {} };
    groups.companies.add(house);
  }

  function addTube(group, line, color, radius, opacity, lift, renderOrder) {
    if (!line || line.length < 2) return;
    const points = line.map((point) => xyz(point, lift));
    const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.06);
    const segments = Math.max(2, Math.min(100, (points.length - 1) * 4));
    const geometry = new THREE.TubeBufferGeometry(curve, segments, radius, 5, false);
    const material = new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthTest: false });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.renderOrder = renderOrder;
    group.add(mesh);
  }

  for (const line of meta.layers.fields || []) addTube(groups.fields, line, 0xfff7bb, 1.35, 0.95, 7, 5);

  const soilStyles = {
    S: { color: 0x43b175, opacity: 0.27 },
    mS: { color: 0xf2ca4c, opacity: 0.25 },
    sM: { color: 0xeb6f3e, opacity: 0.26 },
  };
  for (const item of meta.classified.soils || []) {
    const key = `soil-${item.value}`;
    const group = layerGroup(key);
    const style = soilStyles[item.value] || { color: new THREE.Color(item.color), opacity: 0.24 };
    for (const ring of item.lines || []) {
      addTube(group, ring, style.color, 1.05, 0.94, 10, 6);
    }
  }

  for (const item of meta.classified.water || []) {
    const key = `water-${item.value}`;
    const group = layerGroup(key);
    for (const ring of item.lines || []) {
      addTube(group, ring, item.color, 1.7, 0.98, 12, 8);
    }
  }

  const meliorationStyles = {
    mel_novadgravji: { radius: 2.7, opacity: 1 },
    mel_gravji: { radius: 2.1, opacity: 1 },
    mel_drenu_kolektori: { radius: 1.55, opacity: 0.98 },
    mel_drenas: { radius: 0.9, opacity: 0.88 },
  };
  for (const item of meta.classified.melioration || []) {
    if (item.value === "mel_udens_tecu_asis") continue;
    const key = `melioration-${item.value}`;
    const group = layerGroup(key);
    const style = meliorationStyles[item.value] || { radius: 1.2, opacity: 0.92 };
    for (const line of item.lines || []) addTube(group, line, item.color, style.radius, style.opacity, 15, 10);
  }

  const flowMovers = [];
  const trailMaterial = new THREE.LineBasicMaterial({ color: 0x8effeb, transparent: true, opacity: 0.34, depthTest: false });
  for (const line of meta.layers.flowPaths || []) {
    const points = line.map((point) => xyz(point, 19));
    if (points.length < 2) continue;
    const trail = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), trailMaterial);
    trail.renderOrder = 11;
    groups.flow.add(trail);
    const cumulative = [0];
    for (let index = 1; index < points.length; index += 1) cumulative.push(cumulative[index - 1] + points[index].distanceTo(points[index - 1]));
    const total = cumulative[cumulative.length - 1];
    if (total < 8) continue;
    const direction = points[1].clone().sub(points[0]).normalize();
    const arrow = new THREE.ArrowHelper(direction, points[0], 24, 0xc5fff5, 10, 6);
    arrow.line.material.transparent = true;
    arrow.line.material.opacity = 0.95;
    arrow.line.material.depthTest = false;
    arrow.cone.material.transparent = true;
    arrow.cone.material.opacity = 1;
    arrow.cone.material.depthTest = false;
    arrow.line.renderOrder = 12;
    arrow.cone.renderOrder = 12;
    groups.flow.add(arrow);
    flowMovers.push({ arrow, points, cumulative, total, segment: 0 });
  }

  function positionFlow(mover, progress) {
    const distance = Math.max(0, Math.min(0.999999, progress)) * mover.total;
    while (mover.segment < mover.cumulative.length - 2 && distance > mover.cumulative[mover.segment + 1]) mover.segment += 1;
    while (mover.segment > 0 && distance < mover.cumulative[mover.segment]) mover.segment -= 1;
    const startPoint = mover.points[mover.segment];
    const endPoint = mover.points[mover.segment + 1];
    const startDistance = mover.cumulative[mover.segment];
    const segmentLength = Math.max(0.001, mover.cumulative[mover.segment + 1] - startDistance);
    const interpolation = (distance - startDistance) / segmentLength;
    mover.arrow.position.copy(startPoint.clone().lerp(endPoint, interpolation));
    mover.arrow.setDirection(endPoint.clone().sub(startPoint).normalize());
  }

  function addDashedBorder(bounds, color, lift, dashSize, gapSize, opacity) {
    const points = [
      [bounds[0], bounds[1]], [bounds[2], bounds[1]], [bounds[2], bounds[3]],
      [bounds[0], bounds[3]], [bounds[0], bounds[1]],
    ].map((point) => xyz(point, lift));
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineDashedMaterial({ color, dashSize, gapSize, transparent: true, opacity, depthTest: false });
    const border = new THREE.Line(geometry, material);
    border.computeLineDistances();
    border.renderOrder = 13;
    scene.add(border);
  }
  function addDashedPaths(group, lines, color, lift, dashSize, gapSize, opacity) {
    const material = new THREE.LineDashedMaterial({ color, dashSize, gapSize, transparent: true, opacity, depthTest: false });
    for (const line of lines || []) {
      if (line.length < 2) continue;
      const geometry = new THREE.BufferGeometry().setFromPoints(line.map((point) => xyz(point, lift)));
      const path = new THREE.Line(geometry, material);
      path.computeLineDistances();
      path.renderOrder = 14;
      group.add(path);
    }
  }
  addDashedBorder(meta.bounds, 0x8ca4a6, 6, 14, 10, 0.42);
  addDashedBorder(meta.core, 0xffffff, 18, 16, 9, 1);
  addDashedPaths(groups.catchments, meta.layers.catchments, 0xd6a96a, 22, 20, 11, 1);

  document.querySelectorAll("[data-layer]").forEach((input) => {
    input.addEventListener("change", () => {
      const group = groups[input.dataset.layer];
      if (group) group.visible = input.checked;
    });
  });

  const areas = meta.risk.restriction_class_area_ha || {};
  for (let classNumber = 1; classNumber <= 4; classNumber += 1) {
    document.querySelector(`#area${classNumber}`).textContent = `${areas[String(classNumber)] || 0} ha`;
  }

  let flowRunning = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let flowRate = 1;
  const flowToggle = document.querySelector("#flowToggle");
  const flowSpeed = document.querySelector("#flowSpeed");
  function syncFlowButton() {
    flowToggle.setAttribute("aria-pressed", String(flowRunning));
    flowToggle.textContent = flowRunning ? "Apturēt" : "Atsākt";
  }
  flowToggle.addEventListener("click", () => {
    flowRunning = !flowRunning;
    syncFlowButton();
  });
  flowSpeed.addEventListener("input", () => { flowRate = Number(flowSpeed.value); });
  document.querySelector("#flowCount").textContent = `${flowMovers.length} trajektorijas`;
  syncFlowButton();

  function render() { renderer.render(scene, camera); }
  function setRotateAnimationMode(active) { controls.autoRotate = active; controls.autoRotateSpeed = 0.8; }
  function setWireframeMode(active) { terrainMaterial.wireframe = active; window.Q3D.application._wireframeMode = active; render(); }
  window.Q3D = { application: { controls, _wireframeMode: false, setRotateAnimationMode, setWireframeMode, render } };

  const featureInfo = document.querySelector("#featureInfo");
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  renderer.domElement.addEventListener("click", (event) => {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects([...groups.buildings.children, ...groups.companies.children], true);
    if (!hits.length || !featureInfo) return;
    let selected = hits[0].object;
    while (selected && !selected.userData?.kind) selected = selected.parent;
    const data = selected?.userData || {};
    const title = data.kind === "company" ? "Lauksaimniecības uzņēmums / objekts" : "OSM ēka";
    const detail = data.kind === "company"
      ? `${data.name || "Nenorādīts nosaukums"}<br><small>${data.type || ""}<br>Reģ. Nr.: ${data.id || "—"}<br>${data.tags?.address || "Adrese nav norādīta"}</small>`
      : `${data.name || "Nenorādīts nosaukums"}<br><small>Tips: ${data.type || "—"} · augstums: ${data.height || "—"} m</small>`;
    featureInfo.innerHTML = `<strong>${title}</strong>${detail}`;
    featureInfo.hidden = false;
  });

  let synchronizedProgress = 0;
  let lastFrame = performance.now();
  (function animate(now) {
    requestAnimationFrame(animate);
    const delta = Math.min(0.05, (now - lastFrame) / 1000);
    lastFrame = now;
    if (flowRunning) synchronizedProgress = (synchronizedProgress + delta * flowRate / 5.5) % 1;
    for (const mover of flowMovers) positionFlow(mover, synchronizedProgress);
    controls.update();
    render();
  })(performance.now());

  addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
  document.querySelector("#loading").classList.add("done");
})().catch((error) => {
  document.querySelector("#loading").textContent = `3D ainu neizdevās ielādēt: ${error?.message || error}`;
  console.error(error);
});
