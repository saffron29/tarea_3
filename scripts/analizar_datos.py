"""Paso 3: indicadores por departamento, provincia y distrito, hallazgos y figuras.

    uv run python scripts/analizar_datos.py

Salidas:
- datos/procesados/departamentos_2021.csv, provincias_2021.csv, indicadores_distritos_2021.csv
- datos/procesados/hallazgos.json   cifras de los hallazgos (las usa el dashboard y el guion del reel)
- figuras/*.png                     mapas y gráficos para el README y el reel

Los porcentajes de cada candidato se calculan sobre los votos válidos, como lo hace la ONPE; la participación,
los blancos y los nulos, sobre los votos emitidos o los electores hábiles, según corresponde.
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from procesar_datos import PARTIDOS_1V

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"
PROCESADOS = RAIZ / "datos" / "procesados"
FIGURAS = RAIZ / "figuras"

SIGLAS_1V = [s for s, *_ in PARTIDOS_1V.values()]
CANDIDATO = {s: c for s, _, c in PARTIDOS_1V.values()}
TEXTO_ID = {"ubigeo": str, "ubigeo_onpe": str, "ubigeo_dep": str, "ubigeo_prov": str}

# Colores de los dos finalistas (los mismos del dashboard)
ROJO_PL, NARANJA_FP = "#C0392B", "#E67E22"


def leer_distritos():
    return pd.read_csv(PROCESADOS / "distritos_2021.csv", dtype=TEXTO_ID)


def indicadores(tabla):
    """Se calculan los indicadores sobre una tabla de conteos (cualquier nivel territorial)."""
    t = tabla.copy()
    for v in ("v1", "v2"):
        t[f"participacion_{v}"] = 100 * t[f"{v}_emitidos"] / t[f"{v}_electores"]
        t[f"blancos_{v}"] = 100 * t[f"{v}_blancos"] / t[f"{v}_emitidos"]
        t[f"nulos_{v}"] = 100 * t[f"{v}_nulos"] / t[f"{v}_emitidos"]
    for s in SIGLAS_1V:
        t[f"pct_{s}_1v"] = 100 * t[f"v1_{s}"] / t.v1_validos
    t["ganador_1v"] = t[[f"v1_{s}" for s in SIGLAS_1V]].idxmax(axis=1).str[3:]
    t["pct_ganador_1v"] = t[[f"pct_{s}_1v" for s in SIGLAS_1V]].max(axis=1)
    t["pct_PL_2v"] = 100 * t.v2_PL / t.v2_validos
    t["pct_FP_2v"] = 100 * t.v2_FP / t.v2_validos
    t["ganador_2v"] = np.where(t.v2_PL > t.v2_FP, "PL", "FP")
    t["margen_2v"] = t.v2_PL - t.v2_FP
    # Votos de Fujimori, López Aliaga y De Soto (2.°, 3.° y 4.° lugar nacional en la primera vuelta)
    t["pct_FP_RP_AVP_1v"] = 100 * (t.v1_FP + t.v1_RP + t.v1_AVP) / t.v1_validos
    t["crecimiento_PL"] = t.v2_PL / t.v1_PL
    t["crecimiento_FP"] = t.v2_FP / t.v1_FP
    return t


def agrupar(distritos, claves):
    conteos = [c for c in distritos.columns if c.startswith(("v1_", "v2_"))]
    return distritos.groupby(claves)[conteos].sum().reset_index()


def r(x, y):
    return float(np.corrcoef(x, y)[0, 1])


def hallazgos(dist, dep, extranjero):
    """Cifras de los hallazgos; todas salen de las tablas procesadas."""
    peru, ext = dist.sum(numeric_only=True), extranjero.sum(numeric_only=True)
    total = peru + ext
    validos2 = total.v2_PL + total.v2_FP
    gana_pl = dep[dep.ganador_2v == "PL"].sort_values("pct_PL_2v", ascending=False)
    gana_fp = dep[dep.ganador_2v == "FP"].sort_values("pct_FP_2v", ascending=False)

    # Quintiles de distritos según la pobreza monetaria 2018 del INEI
    dist = dist.copy()
    dist["quintil"] = pd.qcut(dist.pobreza_2018, 5, labels=[1, 2, 3, 4, 5]).astype(int)
    q = dist.groupby("quintil").agg(pobreza_min=("pobreza_2018", "min"), pobreza_max=("pobreza_2018", "max"),
                                    distritos=("ubigeo", "size"), electores=("v2_electores", "sum"),
                                    v2_PL=("v2_PL", "sum"), v2_validos=("v2_validos", "sum"),
                                    v1_PL=("v1_PL", "sum"), v1_validos=("v1_validos", "sum"))
    q["pct_PL_2v"] = 100 * q.v2_PL / q.v2_validos
    q["pct_PL_1v"] = 100 * q.v1_PL / q.v1_validos

    paises = extranjero.sort_values("v2_emitidos", ascending=False)
    return {
        "nacional": {
            "electores": int(total.v2_electores),
            "mesas": int(total.v1_mesas),
            "distritos": len(dist), "provincias": int(dist.ubigeo_prov.nunique()), "paises": len(extranjero),
            "emitidos_1v": int(total.v1_emitidos), "emitidos_2v": int(total.v2_emitidos),
            "participacion_1v": 100 * total.v1_emitidos / total.v1_electores,
            "participacion_2v": 100 * total.v2_emitidos / total.v2_electores,
            "validos_1v": int(total.v1_validos), "validos_2v": int(validos2),
            "blancos_1v": int(total.v1_blancos), "blancos_2v": int(total.v2_blancos),
            "pct_blancos_1v": 100 * total.v1_blancos / total.v1_emitidos,
            "pct_blancos_2v": 100 * total.v2_blancos / total.v2_emitidos,
            "PL_1v": int(total.v1_PL), "FP_1v": int(total.v1_FP),
            "pct_PL_1v": 100 * total.v1_PL / total.v1_validos, "pct_FP_1v": 100 * total.v1_FP / total.v1_validos,
            "PL_2v": int(total.v2_PL), "FP_2v": int(total.v2_FP),
            "pct_PL_2v": 100 * total.v2_PL / validos2, "pct_FP_2v": 100 * total.v2_FP / validos2,
            "margen_2v": int(total.v2_PL - total.v2_FP),
            "crecimiento_PL": total.v2_PL / total.v1_PL, "crecimiento_FP": total.v2_FP / total.v1_FP,
            "oficial_JNE": {"PL": 8_836_380, "FP": 8_792_117, "pct_PL": 50.126, "pct_FP": 49.874, "margen": 44_263},
        },
        "territorio": {
            "departamentos_PL": len(gana_pl), "departamentos_FP": len(gana_fp),
            "lista_FP": gana_fp.nombre_dep.tolist(),
            "max_PL": {"departamento": gana_pl.iloc[0].nombre_dep, "pct": gana_pl.iloc[0].pct_PL_2v},
            "max_FP": {"departamento": gana_fp.iloc[0].nombre_dep, "pct": gana_fp.iloc[0].pct_FP_2v},
            "lima": dep.loc[dep.nombre_dep == "Lima", ["pct_PL_2v", "pct_FP_2v", "v2_electores"]].iloc[0].to_dict(),
            "distritos_PL": int((dist.ganador_2v == "PL").sum()),
            "distritos_PL_80": int((dist.pct_PL_2v >= 80).sum()),
            "distritos_ganador_1v": dist.ganador_1v.value_counts().to_dict(),
            "departamentos_ganador_1v": dep.ganador_1v.value_counts().to_dict(),
        },
        "margen": {
            "peru_PL": int(peru.v2_PL), "peru_FP": int(peru.v2_FP), "margen_peru": int(peru.v2_PL - peru.v2_FP),
            "pct_PL_peru": 100 * peru.v2_PL / peru.v2_validos,
            "ext_PL": int(ext.v2_PL), "ext_FP": int(ext.v2_FP), "margen_ext": int(ext.v2_PL - ext.v2_FP),
            "pct_FP_ext": 100 * ext.v2_FP / ext.v2_validos,
            "participacion_ext_2v": 100 * ext.v2_emitidos / ext.v2_electores,
            "electores_ext": int(ext.v2_electores),
            "paises_mas_votantes": paises.head(5)[["pais", "v2_emitidos"]].to_dict("records"),
        },
        "transferencia": {
            "r_FP2v_FP_RP_AVP_1v": r(dist.pct_FP_RP_AVP_1v, dist.pct_FP_2v),
            "r_PL2v_PL1v": r(dist.pct_PL_1v, dist.pct_PL_2v),
            "pct_FP_RP_AVP_1v_nacional": 100 * (total.v1_FP + total.v1_RP + total.v1_AVP) / total.v1_validos,
        },
        "pobreza": {
            "r_pobreza2018_PL2v": r(dist.pobreza_2018, dist.pct_PL_2v),
            "r_idh2019_PL2v": r(dist.idh_2019, dist.pct_PL_2v),
            "r_altitud_PL2v": r(dist.altitud, dist.pct_PL_2v),
            "r_pobreza2020_PL2v_departamentos": r(dep.pobreza_2020, dep.pct_PL_2v),
            "quintiles": q.reset_index().round(2).to_dict("records"),
        },
    }


# Figuras -------------------------------------------------------------------------------------------

CMAP_2V = LinearSegmentedColormap.from_list("vuelta", [NARANJA_FP, "#F7F3EC", ROJO_PL])


def estilo():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 100})


def mapa_distrital(dist):
    geo = gpd.read_file(ORIGINALES / "peru_distrital_simple.geojson")[["IDDIST", "geometry"]]
    geo = geo.merge(dist[["ubigeo", "pct_PL_2v"]], left_on="IDDIST", right_on="ubigeo", how="left")
    fig, ax = plt.subplots(figsize=(9, 12))
    geo.plot(column="pct_PL_2v", cmap=CMAP_2V, norm=TwoSlopeNorm(50, 0, 100), linewidth=0.05,
             edgecolor="white", ax=ax, missing_kwds={"color": "#DDDDDD"})
    ax.set_axis_off()
    ax.set_title("Segunda vuelta 2021: % de votos válidos de Pedro Castillo por distrito", fontsize=14, loc="left")
    sm = plt.cm.ScalarMappable(cmap=CMAP_2V, norm=TwoSlopeNorm(50, 0, 100))
    barra = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.03, pad=0.02)
    barra.set_label("← más Fujimori        % Castillo        más Castillo →")
    fig.text(0.02, 0.01, "Fuente: ONPE, resultados por mesa (datos abiertos). Gris: distritos sin polígono.",
             fontsize=10, color="#555")
    fig.savefig(FIGURAS / "mapa_distrital_2v.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def barras_departamentos(dep):
    dep = dep.sort_values("pct_PL_2v")
    fig, ax = plt.subplots(figsize=(9, 10))
    ax.barh(dep.nombre_dep, dep.pct_PL_2v, color=ROJO_PL, label="Castillo")
    ax.barh(dep.nombre_dep, dep.pct_FP_2v, left=dep.pct_PL_2v, color=NARANJA_FP, label="Fujimori")
    ax.axvline(50, color="black", lw=1, ls="--")
    for y, v in enumerate(dep.pct_PL_2v):
        ax.text(v - 1.5, y, f"{v:.1f}", va="center", ha="right", color="white", fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% de votos válidos, segunda vuelta")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Castillo ganó 16 de 25 departamentos; Fujimori, Lima y la costa norte", loc="left")
    fig.savefig(FIGURAS / "barras_departamentos_2v.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def dispersion_pobreza(dist, h):
    fig, ax = plt.subplots(figsize=(9, 7))
    colores = np.where(dist.ganador_2v == "PL", ROJO_PL, NARANJA_FP)
    ax.scatter(dist.pobreza_2018, dist.pct_PL_2v, s=np.sqrt(dist.v2_electores) / 3, c=colores, alpha=0.45,
               edgecolors="none")
    ax.axhline(50, color="black", lw=1, ls="--")
    ax.set_xlabel("Pobreza monetaria del distrito, 2018 (%) — INEI")
    ax.set_ylabel("% Castillo, segunda vuelta")
    ax.set_title(f"A más pobreza, más voto por Castillo (r = {h['pobreza']['r_pobreza2018_PL2v']:.2f}, "
                 "1,874 distritos)", loc="left")
    fig.savefig(FIGURAS / "dispersion_pobreza_2v.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def quintiles_pobreza(h):
    q = pd.DataFrame(h["pobreza"]["quintiles"])
    etiquetas = [f"Q{int(k)}\n{a:.0f}–{b:.0f}%" for k, a, b in zip(q.quintil, q.pobreza_min, q.pobreza_max)]
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(q))
    ax.bar(x - 0.2, q.pct_PL_1v, 0.4, color="#E8A598", label="Castillo, 1.ª vuelta")
    ax.bar(x + 0.2, q.pct_PL_2v, 0.4, color=ROJO_PL, label="Castillo, 2.ª vuelta")
    for xi, v in zip(x, q.pct_PL_2v):
        ax.text(xi + 0.2, v + 1, f"{v:.1f}%", ha="center", fontsize=11)
    ax.set_xticks(x, etiquetas)
    ax.set_ylabel("% de votos válidos")
    ax.set_xlabel("Quintiles de distritos según su pobreza monetaria 2018 (Q1 = menos pobres)")
    ax.legend(frameon=False)
    ax.set_title("Voto por Castillo según la pobreza del distrito", loc="left")
    fig.savefig(FIGURAS / "quintiles_pobreza.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def transferencia(dist, h):
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(dist.pct_FP_RP_AVP_1v, dist.pct_FP_2v, s=np.sqrt(dist.v2_electores) / 3, color=NARANJA_FP,
               alpha=0.4, edgecolors="none")
    ax.plot([0, 100], [0, 100], color="#555", lw=1, ls=":")
    ax.set_xlabel("Fujimori + López Aliaga + De Soto, 1.ª vuelta (% de válidos)")
    ax.set_ylabel("Fujimori, 2.ª vuelta (% de válidos)")
    ax.set_title(f"El voto de Fujimori en 2.ª vuelta siguió al de los tres (r = "
                 f"{h['transferencia']['r_FP2v_FP_RP_AVP_1v']:.2f})", loc="left")
    fig.savefig(FIGURAS / "transferencia_fp.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def main():
    FIGURAS.mkdir(exist_ok=True)
    estilo()
    dist = indicadores(leer_distritos())
    pobreza = pd.read_csv(PROCESADOS / "pobreza_departamental_2020.csv", dtype={"ubigeo_dep": str})
    dep = indicadores(agrupar(dist, ["ubigeo_dep", "nombre_dep"])).merge(
        pobreza[["ubigeo_dep", "pobreza_2020", "pobreza_extrema_2020"]], on="ubigeo_dep", validate="1:1")
    prov = indicadores(agrupar(dist, ["ubigeo_prov", "nombre_dep", "provincia"]))
    extranjero = pd.read_csv(PROCESADOS / "extranjero_2021.csv")

    dist.round(3).to_csv(PROCESADOS / "indicadores_distritos_2021.csv", index=False, encoding="utf-8")
    dep.round(3).to_csv(PROCESADOS / "departamentos_2021.csv", index=False, encoding="utf-8")
    prov.round(3).to_csv(PROCESADOS / "provincias_2021.csv", index=False, encoding="utf-8")

    h = hallazgos(dist, dep, extranjero)
    (PROCESADOS / "hallazgos.json").write_text(json.dumps(h, ensure_ascii=False, indent=2, default=float),
                                               encoding="utf-8")
    mapa_distrital(dist)
    barras_departamentos(dep)
    dispersion_pobreza(dist, h)
    quintiles_pobreza(h)
    transferencia(dist, h)

    n, t, m, tr, p = h["nacional"], h["territorio"], h["margen"], h["transferencia"], h["pobreza"]
    print(f"Electores hábiles: {n['electores']:,}; mesas: {n['mesas']:,}; distritos: {n['distritos']:,}; "
          f"países: {n['paises']}")
    print(f"Participación: {n['participacion_1v']:.1f}% → {n['participacion_2v']:.1f}%; "
          f"blancos: {n['pct_blancos_1v']:.1f}% → {n['pct_blancos_2v']:.1f}% de los emitidos")
    print(f"Castillo: {n['PL_1v']:,} ({n['pct_PL_1v']:.1f}%) → {n['PL_2v']:,} ({n['pct_PL_2v']:.3f}%), "
          f"×{n['crecimiento_PL']:.2f}")
    print(f"Fujimori: {n['FP_1v']:,} ({n['pct_FP_1v']:.1f}%) → {n['FP_2v']:,} ({n['pct_FP_2v']:.3f}%), "
          f"×{n['crecimiento_FP']:.2f}")
    print(f"H1 territorio: Castillo gana {t['departamentos_PL']} departamentos y {t['distritos_PL']:,} distritos "
          f"({t['distritos_PL_80']} con 80% o más); Fujimori gana {', '.join(t['lista_FP'])}")
    print(f"   máximo Castillo: {t['max_PL']}; máximo Fujimori: {t['max_FP']}")
    print(f"   margen dentro del Perú: {m['margen_peru']:+,}; en el extranjero: {m['margen_ext']:+,} "
          f"(Fujimori {m['pct_FP_ext']:.1f}%)")
    print(f"H2 transferencia: r(FP+RP+AVP 1v, FP 2v) = {tr['r_FP2v_FP_RP_AVP_1v']:.3f}; "
          f"r(PL 1v, PL 2v) = {tr['r_PL2v_PL1v']:.3f}")
    print(f"H3 pobreza: r(pobreza 2018, PL 2v) = {p['r_pobreza2018_PL2v']:.3f}; IDH = {p['r_idh2019_PL2v']:.3f}; "
          f"altitud = {p['r_altitud_PL2v']:.3f}; departamentos ENAHO 2020 = "
          f"{p['r_pobreza2020_PL2v_departamentos']:.3f}")
    for q in p["quintiles"]:
        print(f"   Q{q['quintil']} ({q['pobreza_min']:.1f}–{q['pobreza_max']:.1f}%): {q['distritos']} distritos, "
              f"{q['electores']:,} electores, Castillo 1v {q['pct_PL_1v']:.1f}% → 2v {q['pct_PL_2v']:.1f}%")


if __name__ == "__main__":
    main()
