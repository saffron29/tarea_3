"""Imágenes de cada escena del reel (fondo oscuro, 1800 × 1280 px) en reel/recursos/.

    uv run python reel/figuras_reel.py

Todas son de elaboración propia con los datos procesados (ONPE e INEI). La captura del tablero se toma aparte con
Chrome y se recorta aquí si existe reel/recursos/captura_tablero_completa.png.
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
PROCESADOS = RAIZ / "datos" / "procesados"
ORIGINALES = RAIZ / "datos" / "originales"
RECURSOS = AQUI / "recursos"

FONDO, TEXTO, SUAVE, CAJA = "#1C1A17", "#F7F3EC", "#B8AE9F", "#2A2723"
PL, FP, GRIS = "#E2533F", "#F39C3D", "#6E665C"
CMAP = LinearSegmentedColormap.from_list("vuelta", [FP, "#3A352F", PL])
TAM = (9, 6.4)   # pulgadas; a 200 dpi son 1800 × 1280 px


def estilo():
    plt.rcParams.update({
        "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
        "text.color": TEXTO, "axes.labelcolor": SUAVE, "xtick.color": SUAVE, "ytick.color": TEXTO,
        "axes.edgecolor": GRIS, "font.family": "DejaVu Sans", "font.size": 15,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def guardar(fig, nombre):
    fig.savefig(RECURSOS / nombre, dpi=200)
    plt.close(fig)
    print("listo", nombre)


def leer():
    texto = {"ubigeo": str, "ubigeo_dep": str, "ubigeo_prov": str}
    dist = pd.read_csv(PROCESADOS / "indicadores_distritos_2021.csv", dtype=texto)
    dep = pd.read_csv(PROCESADOS / "departamentos_2021.csv", dtype=texto)
    ext = pd.read_csv(PROCESADOS / "extranjero_2021.csv")
    h = json.loads((PROCESADOS / "hallazgos.json").read_text(encoding="utf-8"))
    return dist, dep, ext, h


def leyenda_vuelta(fig):
    fig.text(0.62, 0.62, "■", color=PL, fontsize=30)
    fig.text(0.67, 0.63, "Castillo", fontsize=22, fontweight="bold")
    fig.text(0.62, 0.50, "■", color=FP, fontsize=30)
    fig.text(0.67, 0.51, "Fujimori", fontsize=22, fontweight="bold")
    fig.text(0.62, 0.36, "Color más intenso:\nmayor ventaja", fontsize=16, color=SUAVE)


def mapa_distritos(dist):
    geo = gpd.read_file(ORIGINALES / "peru_distrital_simple.geojson")[["IDDIST", "geometry"]]
    geo = geo.merge(dist[["ubigeo", "pct_PL_2v"]], left_on="IDDIST", right_on="ubigeo", how="left")
    fig = plt.figure(figsize=TAM)
    ax = fig.add_axes([0.02, 0.02, 0.56, 0.96])
    geo.plot(column="pct_PL_2v", cmap=CMAP, norm=TwoSlopeNorm(50, 10, 90), linewidth=0.05, edgecolor=FONDO, ax=ax,
             missing_kwds={"color": "#3A352F"})
    ax.set_axis_off()
    fig.text(0.62, 0.86, "Segunda vuelta\npor distrito", fontsize=24, fontweight="bold")
    leyenda_vuelta(fig)
    fig.text(0.62, 0.06, "Fuente: ONPE", fontsize=13, color=SUAVE)
    guardar(fig, "r1_mapa_distritos.png")


def primera_vuelta(dep, ext):
    from procesar_datos import PARTIDOS_1V
    votos = {c: dep[f"v1_{s}"].sum() + ext[f"v1_{s}"].sum() for s, _, c in PARTIDOS_1V.values()}
    validos = sum(votos.values())
    serie = pd.Series({c: 100 * v / validos for c, v in votos.items()}).sort_values().tail(8)
    fig, ax = plt.subplots(figsize=TAM)
    fig.subplots_adjust(left=0.30, right=0.93, top=0.86, bottom=0.08)
    colores = [PL if "Castillo" in c else FP if "Fujimori" in c else GRIS for c in serie.index]
    ax.barh(serie.index, serie.values, color=colores, height=0.7)
    for y, v in enumerate(serie.values):
        ax.text(v + 0.3, y, f"{v:.1f}%", va="center", fontsize=16)
    ax.set_xlim(0, 22)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=16)
    fig.text(0.03, 0.92, "Primera vuelta: los 8 primeros de 18 candidatos", fontsize=22, fontweight="bold")
    guardar(fig, "r2_primera_vuelta.png")


def mapa_departamentos(dep):
    geo = gpd.read_file(ORIGINALES / "peru_departamental_simple.geojson")[["FIRST_IDDP", "geometry"]]
    geo = geo.merge(dep[["ubigeo_dep", "pct_PL_2v", "nombre_dep"]], left_on="FIRST_IDDP", right_on="ubigeo_dep")
    fig = plt.figure(figsize=TAM)
    ax = fig.add_axes([0.02, 0.02, 0.56, 0.96])
    # Se pinta cada departamento con el color de su ganador
    geo["color"] = np.where(geo.pct_PL_2v > 50, PL, FP)
    geo.plot(color=geo.color, linewidth=1.2, edgecolor=FONDO, ax=ax)
    for nombre in ["Puno", "Lima", "Piura"]:
        fila = geo[geo.nombre_dep == nombre].iloc[0]
        p = fila.geometry.representative_point()
        ax.annotate(f"{nombre}\n{fila.pct_PL_2v:.1f}%" if nombre == "Puno" else f"{nombre}\n{100 - fila.pct_PL_2v:.1f}%",
                    (p.x, p.y), ha="center", va="center", fontsize=13, fontweight="bold", color=FONDO)
    ax.set_axis_off()
    fig.text(0.62, 0.86, "Departamentos\nganados", fontsize=24, fontweight="bold")
    fig.text(0.62, 0.62, "16", color=PL, fontsize=40, fontweight="bold")
    fig.text(0.74, 0.635, "Castillo", fontsize=22, fontweight="bold")
    fig.text(0.62, 0.47, "9", color=FP, fontsize=40, fontweight="bold")
    fig.text(0.74, 0.485, "Fujimori", fontsize=22, fontweight="bold")
    fig.text(0.62, 0.30, "Lima, Callao, costa norte,\nIca, Loreto y Ucayali", fontsize=15, color=SUAVE)
    guardar(fig, "r3_departamentos.png")


def extranjero(ext, h):
    por = ext.groupby("continente")[["v2_PL", "v2_FP", "v2_electores"]].sum()
    por.loc["TOTAL EXTRANJERO"] = por.sum()
    por["fp"] = 100 * por.v2_FP / (por.v2_PL + por.v2_FP)
    por = por.sort_values("fp")
    nombres = [c.title().replace("America", "América").replace("Africa", "África").replace("Total Extranjero",
               "Total extranjero") for c in por.index]
    fig, ax = plt.subplots(figsize=TAM)
    fig.subplots_adjust(left=0.27, right=0.95, top=0.82, bottom=0.10)
    ax.barh(nombres, por.fp, color=FP, height=0.65)
    ax.barh(nombres, 100 - por.fp, left=por.fp, color=PL, height=0.65)
    for y, v in enumerate(por.fp):
        ax.text(v - 2, y, f"{v:.1f}%", va="center", ha="right", fontsize=16, fontweight="bold", color=FONDO)
    ax.axvline(50, color=TEXTO, lw=1, ls=":")
    ax.set_xlim(0, 100)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=16)
    fig.text(0.03, 0.90, "Segunda vuelta en el extranjero: % Fujimori", fontsize=22, fontweight="bold")
    fig.text(0.03, 0.84, f"Ventaja de Fujimori fuera del Perú: {abs(h['margen']['margen_ext']):,} votos",
             fontsize=16, color=SUAVE)
    guardar(fig, "r4_extranjero.png")


def transferencia(dist, h):
    fig, ax = plt.subplots(figsize=TAM)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.84, bottom=0.15)
    ax.scatter(dist.pct_FP_RP_AVP_1v, dist.pct_FP_2v, s=np.sqrt(dist.v2_electores) / 2.5, color=FP, alpha=0.45,
               edgecolors="none")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Fujimori + López Aliaga + De Soto en 1.ª vuelta (%)", fontsize=15)
    ax.set_ylabel("Fujimori en 2.ª vuelta (%)", fontsize=15)
    ax.tick_params(axis="y", colors=SUAVE)
    fig.text(0.03, 0.92, "Cada punto es un distrito", fontsize=22, fontweight="bold")
    fig.text(0.03, 0.865, f"Correlación r = {h['transferencia']['r_FP2v_FP_RP_AVP_1v']:.2f}", fontsize=16,
             color=SUAVE)
    guardar(fig, "r5_transferencia.png")


def quintiles(h):
    q = pd.DataFrame(h["pobreza"]["quintiles"])
    fig, ax = plt.subplots(figsize=TAM)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.82, bottom=0.20)
    x = np.arange(len(q))
    colores = [PL if i == len(q) - 1 else "#8E3A2F" for i in range(len(q))]
    ax.bar(x, q.pct_PL_2v, color=colores, width=0.65)
    for xi, v in zip(x, q.pct_PL_2v):
        ax.text(xi, v + 2, f"{v:.1f}%", ha="center", fontsize=17, fontweight="bold")
    etiquetas = ["20% menos\npobre", "", "", "", "20% más\npobre"]
    ax.set_xticks(x, [f"Q{int(k)}\n{e}" for k, e in zip(q.quintil, etiquetas)], fontsize=14)
    ax.set_ylim(0, 100)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    fig.text(0.03, 0.91, "Castillo en 2.ª vuelta según la pobreza del distrito", fontsize=21, fontweight="bold")
    fig.text(0.03, 0.85, "Quintiles de distritos por pobreza monetaria 2018 (INEI)", fontsize=15, color=SUAVE)
    guardar(fig, "r6_quintiles.png")


def captura_tablero():
    origen = RECURSOS / "captura_tablero_completa.png"
    if not origen.exists():
        print("falta la captura del tablero; se omite r7")
        return
    img = Image.open(origen).convert("RGB")
    # Se recortan los controles, los KPIs y los dos primeros paneles (captura de 1400 × 1400 px)
    recorte = img.crop((60, 440, 1340, 1385))
    lienzo = Image.new("RGB", (1800, 1280), FONDO)
    recorte.thumbnail((1760, 1240))
    lienzo.paste(recorte, ((1800 - recorte.width) // 2, (1280 - recorte.height) // 2))
    lienzo.save(RECURSOS / "r7_tablero.png")
    print("listo r7_tablero.png")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(RAIZ / "scripts"))
    estilo()
    dist, dep, ext, h = leer()
    mapa_distritos(dist)
    primera_vuelta(dep, ext)
    mapa_departamentos(dep)
    extranjero(ext, h)
    transferencia(dist, h)
    quintiles(h)
    captura_tablero()
