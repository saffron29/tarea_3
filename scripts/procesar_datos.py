"""Paso 2: de las mesas de votación a una fila por distrito, con las dos vueltas unidas.

    uv run python scripts/procesar_datos.py

Salidas en datos/procesados/:
- distritos_2021.csv           una fila por distrito del Perú (ubigeo del INEI) con los votos de ambas vueltas
- extranjero_2021.csv          una fila por país donde votaron peruanos residentes en el extranjero
- pobreza_departamental_2020.csv  pobreza monetaria por departamento con la sumaria de la ENAHO 2020
- validacion.txt               controles de calidad y comparación con las cifras oficiales
"""
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"
PROCESADOS = RAIZ / "datos" / "procesados"

PRIMERA = ORIGINALES / "Resultados por mesa de las Elecciones Generales 2021.csv"
SEGUNDA = ORIGINALES / "Resultados por mesa de la Segunda Elección Presidencial 2021.csv"

# Códigos del diccionario de la ONPE (VOTOS_P1 ... VOTOS_P18): sigla, organización política y candidato
PARTIDOS_1V = {
    "P1": ("PNP", "Partido Nacionalista Peruano", "Ollanta Humala"),
    "P2": ("FA", "Frente Amplio", "Marco Arana"),
    "P3": ("PM", "Partido Morado", "Julio Guzmán"),
    "P4": ("PPS", "Perú Patria Segura", "Rafael Santos"),
    "P5": ("VN", "Victoria Nacional", "George Forsyth"),
    "P6": ("AP", "Acción Popular", "Yonhy Lescano"),
    "P7": ("AVP", "Avanza País", "Hernando de Soto"),
    "P8": ("PP", "Podemos Perú", "Daniel Urresti"),
    "P9": ("JP", "Juntos por el Perú", "Verónika Mendoza"),
    "P10": ("PPC", "Partido Popular Cristiano", "Alberto Beingolea"),
    "P11": ("FP", "Fuerza Popular", "Keiko Fujimori"),
    "P12": ("UPP", "Unión por el Perú", "José Vega"),
    "P13": ("RP", "Renovación Popular", "Rafael López Aliaga"),
    "P14": ("RUNA", "Renacimiento Unido Nacional", "Ciro Gálvez"),
    "P15": ("SP", "Somos Perú", "Daniel Salaverry"),
    "P16": ("PL", "Perú Libre", "Pedro Castillo"),
    "P17": ("DD", "Democracia Directa", "Andrés Alcántara"),
    "P18": ("APP", "Alianza para el Progreso", "César Acuña"),
}
PARTIDOS_2V = {"P1": ("PL", "Perú Libre", "Pedro Castillo"), "P2": ("FP", "Fuerza Popular", "Keiko Fujimori")}

# Cifras oficiales para validar
# Primera vuelta: ONPE, resultados al 100% de actas contabilizadas
# Segunda vuelta: Acta General de Proclamación, Resolución N.° 0750-2021-JNE
OFICIAL_1V = {"PL": 2_724_752, "FP": 1_930_762, "RP": 1_692_279, "AVP": 1_674_201}
OFICIAL_2V = {"PL": 8_836_380, "FP": 8_792_117, "validos": 17_628_497, "blancos": 121_489, "nulos": 1_106_816}

# Los nombres de la ONPE y del INEI vienen sin tildes; se restituyen solo para mostrar los departamentos
DEPARTAMENTOS = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho", "06": "Cajamarca",
    "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua",
    "19": "Pasco", "20": "Piura", "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali",
}


def leer_mesas(ruta):
    """Se leen las mesas como texto (para no perder los ceros del ubigeo) y luego se convierten los conteos."""
    mesas = pd.read_csv(ruta, sep=";", dtype=str, encoding="latin-1", index_col=False)
    for col in mesas.columns:
        # En la base de la segunda vuelta la Ñ llega dañada como «¿¿» (ESPA¿¿A, CA¿¿ETE): se restituye
        mesas[col] = mesas[col].str.strip().str.replace("¿¿", "Ñ", regex=False)
    conteos = [c for c in mesas.columns if c.startswith(("VOTOS_", "N_"))]
    # Una celda vacía en un conteo significa cero votos
    mesas[conteos] = mesas[conteos].apply(pd.to_numeric).fillna(0).astype("int64")
    return mesas


def controles(mesas, partidos, nombre):
    """Controles de calidad de las mesas; devuelve líneas de texto para validacion.txt."""
    votos = [f"VOTOS_{p}" for p in partidos] + ["VOTOS_VB", "VOTOS_VN", "VOTOS_VI"]
    suma = mesas[votos].sum(axis=1)
    return [
        f"[{nombre}] mesas: {len(mesas):,}; duplicadas: {mesas.MESA_DE_VOTACION.duplicated().sum()}",
        f"[{nombre}] estado de las actas: " + ", ".join(f"{k} = {v:,}" for k, v in
                                                     mesas.DESCRIP_ESTADO_ACTA.value_counts().items()),
        f"[{nombre}] mesas donde votaron más que los electores hábiles: {(mesas.N_CVAS > mesas.N_ELEC_HABIL).sum()}",
        f"[{nombre}] mesas donde la suma de votos difiere de los votantes: {(suma != mesas.N_CVAS).sum():,}",
        f"[{nombre}] nombres que aún tienen «¿»: "
        f"{mesas[['DEPARTAMENTO', 'PROVINCIA', 'DISTRITO']].apply(lambda c: c.str.contains('¿')).sum().sum()}",
    ]


def agregar(mesas, partidos, claves):
    """De mesas a una fila por territorio: electores, votantes, votos por partido, blancos y nulos."""
    renombrar = {f"VOTOS_{p}": sigla for p, (sigla, *_) in partidos.items()}
    renombrar |= {"VOTOS_VB": "blancos", "VOTOS_VN": "nulos", "VOTOS_VI": "impugnados",
                  "N_ELEC_HABIL": "electores", "N_CVAS": "emitidos"}
    tabla = mesas.rename(columns=renombrar)
    columnas = list(renombrar.values())
    agregado = tabla.groupby(claves)[columnas].sum()
    agregado["mesas"] = tabla.groupby(claves).size()
    siglas = [s for s, *_ in partidos.values()]
    agregado["validos"] = agregado[siglas].sum(axis=1)
    return agregado.reset_index()


def unir_vueltas(v1, v2, claves):
    """Se unen ambas vueltas con prefijos v1_ y v2_."""
    v1 = v1.set_index(claves).add_prefix("v1_")
    v2 = v2.set_index(claves).add_prefix("v2_")
    return v1.join(v2, how="outer").reset_index()


def pobreza_enaho_2020():
    """Pobreza monetaria por departamento con la sumaria 2020, como en la Clase 8: hogares ponderados por
    factor07 × mieperho y pobres los hogares con pobreza <= 2 (1 = extremo, 2 = no extremo)."""
    ruta = next((ORIGINALES / "enaho").rglob("sumaria-2020.dta"))
    sumaria = pd.read_stata(ruta, columns=["ubigeo", "pobreza", "factor07", "mieperho"], convert_categoricals=False)
    sumaria["ubigeo"] = sumaria.ubigeo.astype(str).str.zfill(6)
    sumaria["dep"] = sumaria.ubigeo.str[:2]
    sumaria["peso"] = sumaria.factor07 * sumaria.mieperho
    sumaria["pobre"] = (sumaria.pobreza <= 2) * sumaria.peso
    sumaria["extremo"] = (sumaria.pobreza == 1) * sumaria.peso
    nacional = 100 * sumaria.pobre.sum() / sumaria.peso.sum()
    por_dep = sumaria.groupby("dep")[["pobre", "extremo", "peso"]].sum()
    tabla = pd.DataFrame({
        "pobreza_2020": (100 * por_dep.pobre / por_dep.peso).round(1),
        "pobreza_extrema_2020": (100 * por_dep.extremo / por_dep.peso).round(1),
        "hogares_encuestados": sumaria.groupby("dep").size(),
    }).reset_index().rename(columns={"dep": "ubigeo_dep"})
    tabla.insert(1, "departamento", tabla.ubigeo_dep.map(DEPARTAMENTOS))
    return tabla, nacional, len(sumaria)


def main():
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    v1, v2 = leer_mesas(PRIMERA), leer_mesas(SEGUNDA)
    informe = controles(v1, PARTIDOS_1V, "1.ª vuelta") + controles(v2, PARTIDOS_2V, "2.ª vuelta")

    # En el Perú el ubigeo de la ONPE es el de RENIEC: 01-25 son departamentos y 91-95 son continentes
    for mesas in (v1, v2):
        mesas["peru"] = mesas.UBIGEO.str[:2].astype(int) <= 25
    assert set(v1.MESA_DE_VOTACION) == set(v2.MESA_DE_VOTACION), "las vueltas no tienen las mismas mesas"

    # Perú: una fila por distrito ---------------------------------------------------------------
    claves = ["UBIGEO"]
    distritos = unir_vueltas(agregar(v1[v1.peru], PARTIDOS_1V, claves),
                             agregar(v2[v2.peru], PARTIDOS_2V, claves), claves)
    # El total de electores hábiles es igual en ambas vueltas, pero algunas mesas cambian unos pocos electores:
    # se conservan los electores de cada vuelta para calcular su participación
    electores = v1[["MESA_DE_VOTACION", "N_ELEC_HABIL"]].merge(v2[["MESA_DE_VOTACION", "N_ELEC_HABIL"]],
                                                               on="MESA_DE_VOTACION")
    informe.append(f"Mesas con distinto número de electores hábiles entre vueltas: "
                   f"{(electores.N_ELEC_HABIL_x != electores.N_ELEC_HABIL_y).sum()} "
                   f"(total 1.ª = {v1.N_ELEC_HABIL.sum():,}; total 2.ª = {v2.N_ELEC_HABIL.sum():,})")

    ubigeos = pd.read_csv(ORIGINALES / "ubigeo_distrito_aumentado.csv", dtype=str)
    ubigeos = ubigeos.dropna(subset=["reniec"]).rename(columns={"reniec": "UBIGEO", "inei": "ubigeo"})
    assert not ubigeos.UBIGEO.duplicated().any(), "códigos RENIEC repetidos en la equivalencia"
    distritos = distritos.merge(
        ubigeos[["UBIGEO", "ubigeo", "departamento", "provincia", "distrito", "altitude", "latitude", "longitude",
                 "idh_2019", "pct_pobreza_total"]],
        on="UBIGEO", how="left", validate="1:1", indicator=True)
    sin_equivalencia = distritos[distritos._merge == "left_only"]
    assert sin_equivalencia.empty, f"distritos de la ONPE sin ubigeo del INEI: {sin_equivalencia.UBIGEO.tolist()}"
    distritos = distritos.drop(columns="_merge").rename(columns={
        "UBIGEO": "ubigeo_onpe", "pct_pobreza_total": "pobreza_2018", "altitude": "altitud",
        "latitude": "latitud", "longitude": "longitud"})
    distritos["ubigeo_dep"] = distritos.ubigeo.str[:2]
    distritos["ubigeo_prov"] = distritos.ubigeo.str[:4]
    distritos["nombre_dep"] = distritos.ubigeo_dep.map(DEPARTAMENTOS)
    for col in ["altitud", "latitud", "longitud", "idh_2019", "pobreza_2018"]:
        distritos[col] = pd.to_numeric(distritos[col])
    primeras = ["ubigeo", "ubigeo_onpe", "ubigeo_dep", "ubigeo_prov", "nombre_dep", "departamento", "provincia",
                "distrito"]
    distritos = distritos[primeras + [c for c in distritos.columns if c not in primeras]]
    distritos = distritos.sort_values("ubigeo")
    distritos.to_csv(PROCESADOS / "distritos_2021.csv", index=False, encoding="utf-8")

    # Extranjero: una fila por país (dentro de un país, 18 mesas de Venezuela cambian de ciudad entre vueltas)
    claves = ["DEPARTAMENTO", "PROVINCIA"]
    extranjero = unir_vueltas(agregar(v1[~v1.peru], PARTIDOS_1V, claves),
                              agregar(v2[~v2.peru], PARTIDOS_2V, claves), claves)
    extranjero = extranjero.rename(columns={"DEPARTAMENTO": "continente", "PROVINCIA": "pais"})
    extranjero.to_csv(PROCESADOS / "extranjero_2021.csv", index=False, encoding="utf-8")

    # Pobreza departamental ENAHO 2020 ------------------------------------------------------------
    pobreza, pobreza_nacional, hogares = pobreza_enaho_2020()
    pobreza.to_csv(PROCESADOS / "pobreza_departamental_2020.csv", index=False, encoding="utf-8")

    # Validación contra las cifras oficiales -------------------------------------------------------
    total1 = agregar(v1.assign(todo=1), PARTIDOS_1V, ["todo"]).iloc[0]
    total2 = agregar(v2.assign(todo=1), PARTIDOS_2V, ["todo"]).iloc[0]
    informe += ["", "Primera vuelta (base abierta frente a ONPE al 100%):"]
    informe += [f"  {s}: {total1[s]:,} frente a {o:,} (diferencia {total1[s] - o:+,})" for s, o in OFICIAL_1V.items()]
    informe += [f"  votos válidos: {total1.validos:,}; Perú Libre = {100 * total1.PL / total1.validos:.3f}% "
                f"y Fuerza Popular = {100 * total1.FP / total1.validos:.3f}% de los válidos"]
    informe += ["", "Segunda vuelta (base abierta frente a la proclamación del JNE):"]
    informe += [f"  {s}: {total2[s]:,} frente a {o:,} (diferencia {total2[s] - o:+,})" for s, o in OFICIAL_2V.items()]
    informe += [f"  Perú Libre = {100 * total2.PL / total2.validos:.3f}% de los válidos (JNE: 50.126%)",
                f"  electores hábiles: {total1.electores:,}"]
    informe += ["", f"Distritos del Perú: {len(distritos):,}; países del extranjero: {len(extranjero)}",
                f"Distritos sin pobreza 2018 en la equivalencia: {distritos.pobreza_2018.isna().sum()}",
                f"Pobreza ENAHO 2020 (sumaria, {hogares:,} hogares, factor07 × mieperho): {pobreza_nacional:.1f}% "
                "(INEI: 30.1%)"]
    texto = "\n".join(informe)
    (PROCESADOS / "validacion.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
