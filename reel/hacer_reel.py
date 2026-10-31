"""Pasos 3 a 5: guion.json -> voz clonada -> reel vertical con imágenes, música y subtítulos.

    python guion.py --texto texto_fuente.md --respuesta respuesta_guion.json --salida guion.json   # paso 1
    python hacer_reel.py --voz mi_voz_ref.wav --autor "Frank Pinares Gutiérrez" --fuente "ONPE" \
        --musica recursos/inspired_kevin_macleod.mp3 --creditos "..."

Adaptado de la Sesión 15 del curso. Guarda en esta carpeta: reel.mp4, subtitulos.srt, portada.png y posts.md
(y añade el WER por escena a guion.json). La narración intermedia (reel.wav) no se sube al repositorio.
"""
import argparse
import json
import time

import reel

p = argparse.ArgumentParser()
p.add_argument("--voz", required=True, help="15 a 25 s de tu voz: wav, m4a, ogg o mp3")
p.add_argument("--autor", required=True)
p.add_argument("--fuente", required=True, help="fuente de los datos, aparece en el video")
p.add_argument("--creditos", default="", help="créditos de música e imágenes, aparecen al pie del video")
p.add_argument("--musica", help="pista de música de fondo (con licencia de uso)")
p.add_argument("--volumen-musica", type=float, default=0.12, help="0.12 = unos -18 dB respecto de la pista original")
p.add_argument("--device", default="cpu", help="cpu, mps (Mac) o cuda")
p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base", help="modelo de Qwen3-TTS")
p.add_argument("--solo-huella", action="store_true",
               help="clona solo la huella de la voz, sin copiar la entonación de la referencia")
p.add_argument("--velocidad", type=float, default=1.0, help="1.08 = 8 %% más rápido, sin cambiar el tono")
p.add_argument("--salidas", default=str(reel.AQUI))
p.add_argument("--reusar-narracion", action="store_true",
               help="no vuelve a narrar: rehace subtítulos y video con el reel.wav de una corrida anterior")
a = p.parse_args()

t0 = time.time()
salidas = reel.Path(a.salidas)
salidas.mkdir(exist_ok=True)
archivo_guion = salidas / "guion.json"

guion = json.loads(archivo_guion.read_text(encoding="utf-8"))
for e in guion["escenas"]:
    print(f"   {'ok ' if e.get('cifra_en_texto') else '¡¡ '} {e['cifra'] or '-':>10} | {e['frase']}")
if not all(e.get("cifra_en_texto") for e in guion["escenas"]):
    print("   ¡Ojo! Hay cifras que no aparecen tal cual en el texto: revisen guion.json antes de publicar.")
if guion.get("cifras_dudosas_en_posts"):
    print("   Cifras de los posts que no están en el texto:", ", ".join(guion["cifras_dudosas_en_posts"]))

if a.reusar_narracion:
    audio, sr = reel.sf.read(salidas / "reel.wav", dtype="float32")
    narracion = reel.Narracion(audio, sr, [])
    reel.subtitulos(narracion, guion)
    reel.escenas_desde_palabras(narracion, guion)
    reel._reloj(f"narración reutilizada: {narracion.duracion:.1f} s", t0)
else:
    voz = reel.Voz(a.voz, modelo=a.tts, device=a.device, solo_huella=a.solo_huella)
    reel._reloj(f"voz cargada; referencia: «{voz.texto_ref}»", t0)
    narracion = reel.narrar(voz, guion, velocidad=a.velocidad)
    archivo_guion.write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
    reel._reloj(f"narración: {narracion.duracion:.1f} s; WER por escena: "
                + ", ".join(f"{e['wer']:.2f}" for e in guion["escenas"]), t0)
    reel.subtitulos(narracion, guion)
reel.a_srt(narracion, salidas / "subtitulos.srt")
reel._reloj(f"subtítulos: {len(narracion.palabras)} palabras", t0)

reel.portada(guion, narracion, salidas / "portada.png", a.fuente, a.autor, a.creditos)
reel.video(guion, narracion, salidas / "reel.mp4", a.fuente, a.autor, a.creditos, a.musica, a.volumen_musica)
reel.posts(guion, salidas / "posts.md")
reel._reloj(f"listo: {salidas / 'reel.mp4'} ({narracion.duracion:.1f} s)", t0)
