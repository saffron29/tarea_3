"""Paso 1: descarga de las fuentes originales en datos/originales/.

    uv run python scripts/obtener_datos.py

Se descargan:
- Resultados por mesa de la primera vuelta (EG2021) y de la segunda elección presidencial 2021 (ONPE,
  Plataforma Nacional de Datos Abiertos), con sus diccionarios.
- Equivalencia de ubigeos RENIEC-INEI con pobreza distrital 2018 e IDH 2019 (ubigeo-peru-aumentado).
- Límites departamentales y distritales del laboratorio de la sesión 06 del curso, y provinciales de peru-geojson
  (la misma colección de la que provienen los del curso).
- Sumaria de la ENAHO 2020 del INEI (módulo 34), para la pobreza departamental del año previo a la elección.

Si un archivo ya existe, no se vuelve a descargar.
"""
import zipfile
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"

# El portal de datos abiertos rechaza pedidos sin un agente de navegador
CABECERAS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
DATOS_ABIERTOS = "https://www.datosabiertos.gob.pe/sites/default/files"
GEOJSON = "https://raw.githubusercontent.com/juaneladio/peru-geojson/master"
# Los límites departamentales y distritales son los del laboratorio de la sesión 06 del curso
CURSO = "https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data"

FUENTES = {
    "EG2021_primera_vuelta.zip": f"{DATOS_ABIERTOS}/Resultados%20por%20mesa%20de%20las%20Elecciones%20Generales%202021.zip",
    "EG2021_segunda_vuelta.zip": f"{DATOS_ABIERTOS}/Resultados%20por%20mesa%20de%20la%20Segunda%20Elecci%C3%B3n%20Presidencial%202021.zip",
    "diccionario_primera_vuelta.xlsx": f"{DATOS_ABIERTOS}/Diccionario%20de%20las%20Elecciones%20Generales%202021.xlsx",
    "diccionario_segunda_vuelta.xlsx": f"{DATOS_ABIERTOS}/Diccionario%20de%20los%20resultados%20por%20mesa%20de%20la%20Segunda%20Elecci%C3%B3n%20Presidencial%202021.xlsx",
    "ubigeo_distrito_aumentado.csv": "https://raw.githubusercontent.com/jmcastagnetto/ubigeo-peru-aumentado/main/ubigeo_distrito.csv",
    "peru_departamental_simple.geojson": f"{CURSO}/peru_departamental_simple.geojson",
    "peru_provincial_simple.geojson": f"{GEOJSON}/peru_provincial_simple.geojson",
    "peru_distrital_simple.geojson": f"{CURSO}/peru_distrital_simple.geojson",
    "enaho/737-Modulo34.zip": "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/737-Modulo34.zip",
}


def descargar(nombre, url):
    destino = ORIGINALES / nombre
    if destino.exists():
        print(f"ya existe   {nombre}")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=CABECERAS, timeout=600)
    r.raise_for_status()
    destino.write_bytes(r.content)
    print(f"descargado  {nombre} ({len(r.content) / 1e6:.1f} MB)")
    return destino


def descomprimir(zip_path, solo=None):
    """Extrae el zip en su misma carpeta; con `solo`, únicamente los archivos cuyo nombre lo contiene."""
    with zipfile.ZipFile(zip_path) as z:
        for nombre in z.namelist():
            if solo is None or solo in nombre.lower():
                z.extract(nombre, zip_path.parent)
                print(f"extraído    {nombre}")


if __name__ == "__main__":
    for nombre, url in FUENTES.items():
        descargar(nombre, url)
    descomprimir(ORIGINALES / "EG2021_primera_vuelta.zip")
    descomprimir(ORIGINALES / "EG2021_segunda_vuelta.zip")
    descomprimir(ORIGINALES / "enaho" / "737-Modulo34.zip", solo="sumaria-2020.dta")
