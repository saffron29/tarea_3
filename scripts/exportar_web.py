"""Paso 4: datos del dashboard en web/data/.

    uv run python scripts/exportar_web.py

- distritos.json     una fila por distrito con los conteos de ambas vueltas; la página suma por provincia y
                     departamento y calcula los porcentajes con las mismas fórmulas de analizar_datos.py
- extranjero.json    una fila por país
- partidos.json      sigla, organización y candidato de la primera vuelta (orden del diccionario de la ONPE)
- *.geojson          límites con coordenadas redondeadas a 4 decimales (unos 11 m) y solo el código y el nombre
"""
import json
from pathlib import Path

import pandas as pd

from procesar_datos import DEPARTAMENTOS, PARTIDOS_1V

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"
PROCESADOS = RAIZ / "datos" / "procesados"
WEB = RAIZ / "web" / "data"
SIGLAS = [s for s, *_ in PARTIDOS_1V.values()]


def conteos(fila):
    """Conteos de una fila: electores, emitidos, válidos, blancos, nulos y votos por partido."""
    return {
        "e1": int(fila.v1_electores), "e2": int(fila.v2_electores),
        "m1": int(fila.v1_emitidos), "m2": int(fila.v2_emitidos),
        "b1": int(fila.v1_blancos), "b2": int(fila.v2_blancos),
        "n1": int(fila.v1_nulos), "n2": int(fila.v2_nulos),
        "c1": [int(fila[f"v1_{s}"]) for s in SIGLAS],   # votos de los 18 partidos, 1.ª vuelta
        "pl2": int(fila.v2_PL), "fp2": int(fila.v2_FP),
    }


def redondear(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 4), round(coords[1], 4)]
    return [redondear(c) for c in coords]


def geojson(origen, destino, id_campo, nombre_campo, renombrar=None):
    g = json.loads((ORIGINALES / origen).read_text(encoding="utf-8"))
    sin_geometria = [f["properties"][id_campo] for f in g["features"] if f["geometry"] is None]
    if sin_geometria:
        print(f"{origen}: se omiten polígonos sin geometría {sin_geometria}")
    # Un mismo código puede venir en varias piezas: se juntan en un MultiPolygon para que el mapa las pinte todas
    piezas, nombres = {}, {}
    for f in g["features"]:
        if f["geometry"] is None:
            continue
        p = f["properties"]
        id_ = (renombrar or {}).get(p[id_campo], p[id_campo])
        nombres[id_] = p[nombre_campo]
        coords = redondear(f["geometry"]["coordinates"])
        piezas.setdefault(id_, []).extend([coords] if f["geometry"]["type"] == "Polygon" else coords)
    g["features"] = [{"type": "Feature", "properties": {"id": id_, "nombre": nombres[id_]},
                      "geometry": {"type": "MultiPolygon", "coordinates": poligonos}}
                     for id_, poligonos in piezas.items()]
    (WEB / destino).write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(g["features"])


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    dist = pd.read_csv(PROCESADOS / "distritos_2021.csv", dtype={"ubigeo": str, "ubigeo_prov": str,
                                                                    "ubigeo_dep": str})
    registros = []
    for _, f in dist.iterrows():
        registros.append({"id": f.ubigeo, "dep": f.ubigeo_dep, "prov": f.ubigeo_prov, "nd": f.nombre_dep,
                          "np": f.provincia.title(), "nombre": f.distrito.title(),
                          "pob": round(float(f.pobreza_2018), 1), "idh": round(float(f.idh_2019), 3),
                          "alt": int(f.altitud) if pd.notna(f.altitud) else None, **conteos(f)})
    (WEB / "distritos.json").write_text(json.dumps(registros, ensure_ascii=False, separators=(",", ":")),
                                        encoding="utf-8")

    ext = pd.read_csv(PROCESADOS / "extranjero_2021.csv")
    paises = [{"id": f"EXT-{i}", "continente": f.continente.title(), "nombre": f.pais.title(), **conteos(f)}
              for i, f in ext.iterrows()]
    (WEB / "extranjero.json").write_text(json.dumps(paises, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")

    partidos = [{"sigla": s, "partido": p, "candidato": c} for s, p, c in PARTIDOS_1V.values()]
    (WEB / "partidos.json").write_text(json.dumps(partidos, ensure_ascii=False, indent=1), encoding="utf-8")
    (WEB / "departamentos.json").write_text(json.dumps(DEPARTAMENTOS, ensure_ascii=False, indent=1),
                                            encoding="utf-8")

    # Los dos distritos de Putumayo que siguen en la cartografía con su código antiguo (provincia de Maynas)
    # se reasignan a su código actual (provincia de Putumayo, creada en 2014)
    putumayo = {"160109": "160801", "160114": "160803"}
    n_dep = geojson("peru_departamental_simple.geojson", "departamentos.geojson", "FIRST_IDDP", "NOMBDEP")
    n_prov = geojson("peru_provincial_simple.geojson", "provincias.geojson", "FIRST_IDPR", "NOMBPROV")
    n_dist = geojson("peru_distrital_simple.geojson", "distritos.geojson", "IDDIST", "NOMBDIST", putumayo)

    for archivo in sorted(WEB.iterdir()):
        print(f"{archivo.name:22} {archivo.stat().st_size / 1e3:8.0f} KB")
    print(f"distritos con datos: {len(registros):,}; países: {len(paises)}; polígonos: {n_dep} departamentos, "
          f"{n_prov} provincias, {n_dist} distritos")


if __name__ == "__main__":
    main()
