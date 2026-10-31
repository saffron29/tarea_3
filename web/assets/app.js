// Tablero del voto territorial 2021. Los porcentajes se calculan aquí con las mismas fórmulas de
// scripts/analizar_datos.py: candidatos sobre votos válidos, participación sobre electores hábiles y
// blancos o nulos sobre votos emitidos.

const COLOR = { PL: "#C0392B", FP: "#E67E22", neutro: "#9C9286", crema: "#F7F3EC", acento: "#1F4E79" };
// Posición de cada partido en el arreglo c1 (orden del diccionario de la ONPE, VOTOS_P1 ... VOTOS_P18)
const I = { PNP: 0, FA: 1, PM: 2, PPS: 3, VN: 4, AP: 5, AVP: 6, PP: 7, JP: 8, PPC: 9, FP: 10, UPP: 11, RP: 12,
            RUNA: 13, SP: 14, PL: 15, DD: 16, APP: 17 };

const suma = (a) => a.reduce((x, y) => x + y, 0);
const pct = (a, b) => (b > 0 ? (100 * a) / b : null);
const validos1 = (t) => suma(t.c1);
const validos2 = (t) => t.pl2 + t.fp2;
const entero = (n) => Math.round(n).toLocaleString("en-US");
const fpct = (x, d = 1) => (x == null ? "–" : `${x.toFixed(d)}%`);

// Indicadores del control 1: nombre, fórmula, color y escala del mapa
const INDICADORES = {
  pl2: { grupo: "Segunda vuelta", nombre: "% Pedro Castillo", calc: (t) => pct(t.pl2, validos2(t)), escala: "pl" },
  fp2: { grupo: "Segunda vuelta", nombre: "% Keiko Fujimori", calc: (t) => pct(t.fp2, validos2(t)), escala: "fp" },
  part2: { grupo: "Segunda vuelta", nombre: "Participación", calc: (t) => pct(t.m2, t.e2), color: COLOR.acento },
  nulos2: { grupo: "Segunda vuelta", nombre: "% votos nulos", calc: (t) => pct(t.n2, t.m2), color: "#5E5850" },
  pl1: { grupo: "Primera vuelta", nombre: "% Pedro Castillo (Perú Libre)", calc: (t) => pct(t.c1[I.PL], validos1(t)), color: COLOR.PL },
  fp1: { grupo: "Primera vuelta", nombre: "% Keiko Fujimori (Fuerza Popular)", calc: (t) => pct(t.c1[I.FP], validos1(t)), color: COLOR.FP },
  rp1: { grupo: "Primera vuelta", nombre: "% Rafael López Aliaga (Renovación Popular)", calc: (t) => pct(t.c1[I.RP], validos1(t)), color: "#2E86C1" },
  avp1: { grupo: "Primera vuelta", nombre: "% Hernando de Soto (Avanza País)", calc: (t) => pct(t.c1[I.AVP], validos1(t)), color: "#7D3C98" },
  ap1: { grupo: "Primera vuelta", nombre: "% Yonhy Lescano (Acción Popular)", calc: (t) => pct(t.c1[I.AP], validos1(t)), color: "#1E8449" },
  jp1: { grupo: "Primera vuelta", nombre: "% Verónika Mendoza (Juntos por el Perú)", calc: (t) => pct(t.c1[I.JP], validos1(t)), color: "#16A085" },
  tres1: { grupo: "Primera vuelta", nombre: "% Fujimori + López Aliaga + De Soto",
           calc: (t) => pct(t.c1[I.FP] + t.c1[I.RP] + t.c1[I.AVP], validos1(t)), color: "#A04000" },
  part1: { grupo: "Primera vuelta", nombre: "Participación", calc: (t) => pct(t.m1, t.e1), color: COLOR.acento },
  blancos1: { grupo: "Primera vuelta", nombre: "% votos en blanco", calc: (t) => pct(t.b1, t.m1), color: "#5E5850" },
};
const NIVELES = { dep: "departamento", prov: "provincia", dist: "distrito" };
const NIVELES_PLURAL = { dep: "departamentos", prov: "provincias", dist: "distritos" };

const estado = { indicador: "pl2", territorio: "PE", nivel: "dep" };
let D = null;   // datos cargados

// Carga ------------------------------------------------------------------------------------------

async function cargar() {
  const leer = (archivo) => fetch(`data/${archivo}`).then((r) => {
    if (!r.ok) throw new Error(`${archivo}: ${r.status}`);
    return r.json();
  });
  const [distritos, extranjero, partidos, departamentos, geoDep, geoProv, geoDist] = await Promise.all([
    leer("distritos.json"), leer("extranjero.json"), leer("partidos.json"), leer("departamentos.json"),
    leer("departamentos.geojson"), leer("provincias.geojson"), leer("distritos.geojson"),
  ]);
  return { distritos, extranjero, partidos, departamentos, geo: { dep: geoDep, prov: geoProv, dist: geoDist } };
}

// Agregación: se suman los conteos de los distritos (o países) de cada territorio
function sumar(filas) {
  const t = { e1: 0, e2: 0, m1: 0, m2: 0, b1: 0, b2: 0, n1: 0, n2: 0, pl2: 0, fp2: 0, c1: new Array(18).fill(0), n: 0 };
  for (const f of filas) {
    for (const k of ["e1", "e2", "m1", "m2", "b1", "b2", "n1", "n2", "pl2", "fp2"]) t[k] += f[k];
    for (let i = 0; i < 18; i++) t.c1[i] += f.c1[i];
    t.n += 1;
  }
  return t;
}

function agrupar(filas, clave, nombre) {
  const grupos = new Map();
  for (const f of filas) {
    const k = clave(f);
    if (!grupos.has(k)) grupos.set(k, { id: k, nombre: nombre(f), filas: [] });
    grupos.get(k).filas.push(f);
  }
  return [...grupos.values()].map((g) => ({ id: g.id, nombre: g.nombre, filas: g.filas, ...sumar(g.filas) }));
}

function territorios(nivel, filas) {
  if (nivel === "dep") return agrupar(filas, (f) => f.dep, (f) => f.nd);
  if (nivel === "prov") return agrupar(filas, (f) => f.prov, (f) => `${f.np} (${f.nd})`);
  return agrupar(filas, (f) => f.id, (f) => `${f.nombre} (${f.np}, ${f.nd})`);
}

function filasSeleccionadas() {
  if (estado.territorio === "EXT") return D.extranjero;
  if (estado.territorio === "PE") return D.distritos;
  return D.distritos.filter((f) => f.dep === estado.territorio);
}

function nombreTerritorio() {
  if (estado.territorio === "PE") return "todo el Perú";
  if (estado.territorio === "EXT") return "el extranjero";
  return D.departamentos[estado.territorio];
}

// Controles ----------------------------------------------------------------------------------------

function armarControles() {
  const selInd = document.getElementById("sel-indicador");
  for (const grupo of ["Segunda vuelta", "Primera vuelta"]) {
    const og = document.createElement("optgroup");
    og.label = grupo;
    for (const [k, v] of Object.entries(INDICADORES)) {
      if (v.grupo === grupo) og.append(new Option(`${v.nombre} · ${grupo.toLowerCase()}`, k));
    }
    selInd.append(og);
  }
  selInd.value = estado.indicador;
  selInd.addEventListener("change", () => { estado.indicador = selInd.value; actualizar(); });

  const selTer = document.getElementById("sel-territorio");
  selTer.append(new Option("Total nacional (Perú + extranjero)", "PE"));
  for (const [cod, nombre] of Object.entries(D.departamentos)) selTer.append(new Option(nombre, cod));
  selTer.append(new Option("Peruanos en el extranjero", "EXT"));
  selTer.addEventListener("change", () => {
    estado.territorio = selTer.value;
    // Con un departamento elegido, el nivel departamental mostraría un solo polígono: se pasa a provincias
    if (!["PE", "EXT"].includes(estado.territorio) && estado.nivel === "dep") fijarNivel("prov");
    actualizar();
  });

  document.querySelectorAll('#sel-nivel input').forEach((r) =>
    r.addEventListener("change", () => { estado.nivel = r.value; actualizar(); }));
}

function fijarNivel(nivel) {
  estado.nivel = nivel;
  document.querySelector(`#sel-nivel input[value="${nivel}"]`).checked = true;
}

// KPIs -------------------------------------------------------------------------------------------------

function kpis() {
  const filas = filasSeleccionadas();
  const t = estado.territorio === "PE" ? sumar([...D.distritos, ...D.extranjero]) : sumar(filas);
  const pl2 = pct(t.pl2, validos2(t)), fp2 = pct(t.fp2, validos2(t));
  const pl1 = pct(t.c1[I.PL], validos1(t)), fp1 = pct(t.c1[I.FP], validos1(t));
  const unidades = filas;   // distritos o, en el extranjero, países
  const ganaPL = unidades.filter((f) => f.pl2 > f.fp2).length;
  const etiqueta = estado.territorio === "EXT" ? "países" : "distritos";

  document.getElementById("kpi-electores").textContent = entero(t.e2);
  document.getElementById("kpi-electores-nota").textContent =
    `Participación: ${fpct(pct(t.m1, t.e1))} en 1.ª vuelta y ${fpct(pct(t.m2, t.e2))} en 2.ª`;
  document.getElementById("kpi-pl").textContent = fpct(pl2, 1);
  document.getElementById("kpi-pl-nota").textContent =
    `1.ª vuelta: ${fpct(pl1)} · votos ×${(t.pl2 / t.c1[I.PL]).toFixed(1)} (${entero(t.c1[I.PL])} → ${entero(t.pl2)})`;
  document.getElementById("kpi-fp").textContent = fpct(fp2, 1);
  document.getElementById("kpi-fp-nota").textContent =
    `1.ª vuelta: ${fpct(fp1)} · votos ×${(t.fp2 / t.c1[I.FP]).toFixed(1)} (${entero(t.c1[I.FP])} → ${entero(t.fp2)})`;
  const margen = t.pl2 - t.fp2;
  document.getElementById("kpi-margen").textContent = `${entero(Math.abs(margen))} votos`;
  document.getElementById("kpi-margen-nota").textContent =
    `A favor de ${margen >= 0 ? "Castillo" : "Fujimori"} · Castillo ganó en ${entero(ganaPL)} de ${entero(unidades.length)} ${etiqueta}`;
}

// Escalas de color --------------------------------------------------------------------------------------

function escala(ind) {
  // Escala divergente centrada en 50%; de 15% a 85% para que se distingan mejor los territorios
  if (ind.escala === "pl") return { colorscale: [[0, COLOR.FP], [0.5, COLOR.crema], [1, COLOR.PL]], zmin: 15, zmax: 85 };
  if (ind.escala === "fp") return { colorscale: [[0, COLOR.PL], [0.5, COLOR.crema], [1, COLOR.FP]], zmin: 15, zmax: 85 };
  return { colorscale: [[0, COLOR.crema], [1, ind.color]] };
}

const BASE = {
  font: { family: "Public Sans, system-ui, sans-serif", size: 12, color: "#1F1D1A" },
  paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
  margin: { l: 10, r: 10, t: 10, b: 10 },
};
const CONFIG = { responsive: true, displaylogo: false, locale: "es",
                 modeBarButtonsToRemove: ["select2d", "lasso2d", "toggleSpikelines"] };

// 1. Mapa -----------------------------------------------------------------------------------------------

function mapa() {
  const ind = INDICADORES[estado.indicador];
  const titulo = document.getElementById("titulo-mapa");
  const nota = document.getElementById("nota-mapa");
  if (estado.territorio === "EXT") return continentes(ind);
  const filas = filasSeleccionadas();
  const datos = territorios(estado.nivel, filas);
  const ids = new Set(D.geo[estado.nivel].features.map((f) => f.properties.id));
  const conMapa = datos.filter((t) => ids.has(t.id));
  titulo.textContent = `${ind.nombre} (${ind.grupo.toLowerCase()}) por ${NIVELES[estado.nivel]}`;
  nota.textContent = `${nombreTerritorio()[0].toUpperCase()}${nombreTerritorio().slice(1)} · ${conMapa.length} ${NIVELES_PLURAL[estado.nivel]}`
    + (conMapa.length < datos.length ? ` (${datos.length - conMapa.length} sin polígono en la cartografía)` : "")
    + ". Pase el cursor para ver el detalle.";
  const traza = {
    type: "choropleth", geojson: D.geo[estado.nivel], featureidkey: "properties.id",
    locations: conMapa.map((t) => t.id), z: conMapa.map((t) => ind.calc(t)),
    customdata: conMapa.map((t) => [t.nombre, fpct(pct(t.pl2, validos2(t))), fpct(pct(t.fp2, validos2(t))),
                                    fpct(pct(t.c1[I.PL], validos1(t))), entero(t.e2)]),
    hovertemplate: "<b>%{customdata[0]}</b><br>" + `${ind.nombre}: %{z:.1f}%` +
      "<br>2.ª vuelta: Castillo %{customdata[1]} · Fujimori %{customdata[2]}" +
      "<br>Castillo en 1.ª vuelta: %{customdata[3]}<br>Electores: %{customdata[4]}<extra></extra>",
    marker: { line: { color: "#FFFFFF", width: estado.nivel === "dist" ? 0.2 : 0.6 } },
    colorbar: { thickness: 10, len: 0.45, x: 0.98, y: 0.25, ticksuffix: "%", title: { text: "" },
                bgcolor: "rgba(255,255,255,.7)" },
    ...escala(ind),
  };
  const layout = { ...BASE, margin: { l: 0, r: 0, t: 0, b: 0 },
                   geo: { fitbounds: "locations", visible: false, projection: { type: "mercator" },
                          bgcolor: "rgba(0,0,0,0)", domain: { x: [0, 1], y: [0, 1] } } };
  Plotly.react("grafico-mapa", [traza], layout, CONFIG);
}

// En el extranjero no hay mapa: el mismo panel compara los continentes
function continentes(ind) {
  const datos = agrupar(D.extranjero, (f) => f.continente, (f) => f.continente)
    .map((t) => ({ ...t, valor: ind.calc(t) })).sort((a, b) => a.valor - b.valor);
  document.getElementById("titulo-mapa").textContent = `Extranjero: ${ind.nombre} (${ind.grupo.toLowerCase()}) por continente`;
  document.getElementById("nota-mapa").textContent =
    "El voto en el extranjero no tiene mapa distrital; se compara por continente. El ranking muestra los países.";
  const traza = {
    type: "bar", orientation: "h", y: datos.map((t) => t.nombre), x: datos.map((t) => t.valor),
    marker: { color: datos.map((t) => (ind.escala ? (t.pl2 > t.fp2 ? COLOR.PL : COLOR.FP) : ind.color)) },
    text: datos.map((t) => `${fpct(t.valor)} · ${entero(t.e2)} electores`), textposition: "outside", cliponaxis: false,
    hovertemplate: "<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
  };
  const layout = { ...BASE, margin: { l: 10, r: 10, t: 10, b: 30 }, showlegend: false,
                   xaxis: { range: [0, 140], ticksuffix: "%", gridcolor: "#EEE", tickvals: [0, 20, 40, 60, 80, 100] },
                   yaxis: { automargin: true } };
  Plotly.react("grafico-mapa", [traza], layout, CONFIG);
}

// 2. Ranking -------------------------------------------------------------------------------------------

function ranking() {
  const ind = INDICADORES[estado.indicador];
  const ext = estado.territorio === "EXT";
  // En el extranjero hay países con muy pocos votantes: se toman los 15 con más electores
  let datos = ext ? [...D.extranjero].sort((a, b) => b.e2 - a.e2).slice(0, 15)
                      .map((f) => ({ ...f, nombre: `${f.nombre} (${f.continente})` }))
                  : territorios(estado.nivel, filasSeleccionadas());
  // En el total nacional por departamento se añade el extranjero como una barra más
  if (estado.territorio === "PE" && estado.nivel === "dep") {
    datos.push({ id: "EXT", nombre: "Extranjero", ...sumar(D.extranjero) });
  }
  datos = datos.map((t) => ({ ...t, valor: ind.calc(t) })).filter((t) => t.valor != null)
               .sort((a, b) => b.valor - a.valor);
  // Por departamento se muestran todos (25 y el extranjero); en provincias y distritos, los 15 primeros
  const limite = estado.nivel === "dep" && !ext ? 30 : 15;
  const total = datos.length;
  if (total > limite) datos = datos.slice(0, limite);
  datos.reverse();
  const unidad = ext ? "países" : NIVELES_PLURAL[estado.nivel];
  document.getElementById("titulo-ranking").textContent = `Ranking: ${ind.nombre} (${ind.grupo.toLowerCase()})`;
  document.getElementById("nota-ranking").textContent = ext
    ? `Los 15 países con más electores de los ${D.extranjero.length} con mesas, ordenados por el indicador.`
    : total > limite
      ? `Los ${limite} ${unidad} con el valor más alto de ${total} en ${nombreTerritorio()}.`
      : `Los ${total} ${unidad} de ${nombreTerritorio()}.`;
  const colorBarra = (t) => {
    if (t.id === "EXT") return "#7F8C8D";
    if (ind.escala) return t.pl2 > t.fp2 ? COLOR.PL : COLOR.FP;
    return ind.color;
  };
  const traza = {
    type: "bar", orientation: "h", y: datos.map((t) => t.nombre), x: datos.map((t) => t.valor),
    marker: { color: datos.map(colorBarra) },
    text: datos.map((t) => fpct(t.valor)), textposition: "outside", cliponaxis: false,
    customdata: datos.map((t) => entero(t.e2)),
    hovertemplate: "<b>%{y}</b><br>%{x:.1f}%<br>Electores: %{customdata}<extra></extra>",
  };
  const maximo = Math.max(...datos.map((t) => t.valor));
  const layout = { ...BASE, margin: { l: 10, r: 40, t: 10, b: 30 },
                   xaxis: { range: [0, Math.min(100, maximo * 1.15)], ticksuffix: "%", gridcolor: "#EEE" },
                   yaxis: { automargin: true, tickfont: { size: 11 } }, showlegend: false,
                   shapes: ind.escala ? [{ type: "line", x0: 50, x1: 50, y0: -0.5, y1: datos.length - 0.5,
                                           line: { color: "#1F1D1A", width: 1, dash: "dot" } }] : [] };
  Plotly.react("grafico-ranking", [traza], layout, CONFIG);
}

// 3. Dispersión pobreza-voto ---------------------------------------------------------------------------

function correlacion(x, y) {
  const n = x.length, mx = suma(x) / n, my = suma(y) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; syy += (y[i] - my) ** 2; }
  return sxy / Math.sqrt(sxx * syy);
}

function dispersion() {
  const ind = INDICADORES[estado.indicador];
  const titulo = document.getElementById("titulo-dispersion");
  const nota = document.getElementById("nota-dispersion");
  if (estado.territorio === "EXT") {
    titulo.textContent = "Pobreza y voto por distrito";
    nota.textContent = "No hay datos de pobreza para el voto en el extranjero.";
    Plotly.purge("grafico-dispersion");
    document.getElementById("grafico-dispersion").style.display = "none";
    return;
  }
  document.getElementById("grafico-dispersion").style.display = "";
  const filas = filasSeleccionadas().filter((f) => f.pob != null);
  const puntos = filas.map((f) => ({ f, y: ind.calc(sumar([f])) })).filter((p) => p.y != null);
  const r = correlacion(puntos.map((p) => p.f.pob), puntos.map((p) => p.y));
  titulo.textContent = `Pobreza del distrito y ${ind.nombre.replace("% ", "% de ")} (${ind.grupo.toLowerCase()})`;
  nota.textContent = `${puntos.length} distritos de ${nombreTerritorio()} · r = ${r.toFixed(2)} · tamaño según electores; color según el ganador de la 2.ª vuelta.`;
  const traza = (gana, nombre, color) => {
    const p = puntos.filter((q) => (q.f.pl2 > q.f.fp2) === gana);
    return {
      type: "scattergl", mode: "markers", name: nombre,
      x: p.map((q) => q.f.pob), y: p.map((q) => q.y),
      marker: { color, opacity: 0.55, size: p.map((q) => Math.max(4, Math.sqrt(q.f.e2) / 9)), line: { width: 0 } },
      customdata: p.map((q) => [`${q.f.nombre} (${q.f.np}, ${q.f.nd})`, entero(q.f.e2)]),
      hovertemplate: "<b>%{customdata[0]}</b><br>Pobreza 2018: %{x:.1f}%<br>" + `${ind.nombre}: %{y:.1f}%` +
        "<br>Electores: %{customdata[1]}<extra></extra>",
    };
  };
  const layout = { ...BASE, margin: { l: 55, r: 10, t: 10, b: 50 },
                   xaxis: { title: { text: "Pobreza monetaria del distrito, 2018 (%)" }, gridcolor: "#EEE", zeroline: false },
                   yaxis: { title: { text: `${ind.nombre}` }, ticksuffix: "%", gridcolor: "#EEE", zeroline: false },
                   legend: { orientation: "h", y: 1.08, x: 0 } };
  Plotly.react("grafico-dispersion", [traza(true, "Ganó Castillo", COLOR.PL), traza(false, "Ganó Fujimori", COLOR.FP)],
               layout, CONFIG);
}

// 4. Composición de la primera vuelta ------------------------------------------------------------------

function composicion() {
  const filas = filasSeleccionadas();
  const t = estado.territorio === "PE" ? sumar([...D.distritos, ...D.extranjero]) : sumar(filas);
  const v = validos1(t);
  const datos = D.partidos.map((p, i) => ({ ...p, pct: pct(t.c1[i], v), votos: t.c1[i] }))
                          .sort((a, b) => a.pct - b.pct);
  const color = (p) => (p.sigla === "PL" ? COLOR.PL : p.sigla === "FP" ? COLOR.FP
                        : ["RP", "AVP"].includes(p.sigla) ? "#F0B27A" : "#C9C2B8");
  document.getElementById("titulo-composicion").textContent =
    `¿De dónde salieron los votos? Primera vuelta en ${nombreTerritorio()}`;
  document.getElementById("nota-composicion").textContent =
    `% de votos válidos de los 18 candidatos. En la 2.ª vuelta: Castillo ${fpct(pct(t.pl2, validos2(t)))} y Fujimori ${fpct(pct(t.fp2, validos2(t)))}. ` +
    "En tono claro, López Aliaga y De Soto, cuyo voto siguió en la 2.ª vuelta al de Fujimori.";
  const traza = {
    type: "bar", orientation: "h", y: datos.map((p) => `${p.candidato} (${p.sigla})`), x: datos.map((p) => p.pct),
    marker: { color: datos.map(color) }, text: datos.map((p) => fpct(p.pct)), textposition: "outside", cliponaxis: false,
    customdata: datos.map((p) => [p.partido, entero(p.votos)]),
    hovertemplate: "<b>%{y}</b><br>%{customdata[0]}<br>%{x:.1f}% · %{customdata[1]} votos<extra></extra>",
  };
  const maximo = Math.max(...datos.map((p) => p.pct));
  const layout = { ...BASE, margin: { l: 10, r: 40, t: 10, b: 30 }, showlegend: false,
                   xaxis: { range: [0, maximo * 1.18], ticksuffix: "%", gridcolor: "#EEE" },
                   yaxis: { automargin: true, tickfont: { size: 11 } } };
  Plotly.react("grafico-composicion", [traza], layout, CONFIG);
}

// Actualización general -------------------------------------------------------------------------------

// El estado de los controles se guarda en la URL (#ind=pl2&ter=PE&niv=dep) para compartir una vista
function leerURL() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (INDICADORES[p.get("ind")]) estado.indicador = p.get("ind");
  if (p.get("ter") && (["PE", "EXT"].includes(p.get("ter")) || D.departamentos[p.get("ter")])) estado.territorio = p.get("ter");
  if (NIVELES[p.get("niv")]) estado.nivel = p.get("niv");
}

function escribirURL() {
  history.replaceState(null, "", `#ind=${estado.indicador}&ter=${estado.territorio}&niv=${estado.nivel}`);
}

function actualizar() {
  escribirURL();
  kpis();
  mapa();
  ranking();
  dispersion();
  composicion();
}

cargar()
  .then((datos) => {
    D = datos;
    leerURL();
    armarControles();
    document.getElementById("sel-territorio").value = estado.territorio;
    fijarNivel(estado.nivel);
    actualizar();
    document.getElementById("estado").textContent = "";
  })
  .catch((e) => {
    document.getElementById("estado").textContent = `No se pudieron cargar los datos (${e.message}).`;
    console.error(e);
  });
