"""Pasos 2 a 4: guion.json -> voz clonada -> reel vertical.

    Voz           Qwen3-TTS clona tu voz con 10 a 20 s de audio y narra cada escena
    VozExpresiva  VoxCPM2 clona tu voz y además acepta un estilo por escena (locutor, urgente, cálido)
    subtitulos()  Whisper transcribe la narración: subtítulos palabra por palabra y control de calidad
    video()       reel 1080x1920 con cifras, imágenes, música, subtítulos y aviso de voz generada con IA

El paso 1 (texto largo -> guion.json) está en guion.py. Adaptado de la Sesión 15 del curso
(sessions/15-texto-a-reel): se añadieron la imagen por escena, la música de fondo y los créditos.
"""
import re
import subprocess
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import imageio_ffmpeg
import jiwer
import numpy as np
import soundfile as sf
from num2words import num2words
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).parent
FUENTES = AQUI / "fuentes"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

TTS = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
ASR = "large-v3-turbo"

ANCHO, ALTO, FPS = 1080, 1920, 30
MARGEN = 90
# Acento amarillo: el naranja queda para Fujimori y el rojo para Castillo, como en el dashboard
FONDO, TEXTO, SUAVE, ACENTO, CAJA = "#1C1A17", "#F7F3EC", "#B8AE9F", "#F2C94C", "#2A2723"
PAUSA, INICIO, FINAL = 0.35, 0.3, 0.8   # segundos de silencio entre escenas, al inicio y al final
# Estilos de VoxCPM2 por defecto; en inglés funcionan mejor que en español. Una escena puede traer su "estilo" en guion.json
ESTILOS = {"inicio": "urgent, dramatic news anchor, strong emphasis",
           "medio": "confident news anchor, energetic, clear emphasis on the numbers",
           "cierre": "warm, friendly, inviting tone"}


def _reloj(msg, t):
    print(f"[{time.time() - t:5.1f}s] {msg}", flush=True)


# Voz clonada ---------------------------------------------------------------

def cargar_audio(ruta, sr=16000):
    """Cualquier audio (wav, m4a, ogg de WhatsApp, mp3) a mono float32 con ffmpeg."""
    crudo = subprocess.run([FFMPEG, "-v", "error", "-i", str(ruta), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(crudo, np.float32)


class Voz:
    """Clona una voz a partir de 10 a 20 segundos de audio y su transcripción (la hace Whisper)."""

    def __init__(self, referencia, modelo=TTS, device="cpu", solo_huella=False):
        """Con solo_huella=True se usa solo la huella de la voz (x_vector_only_mode): no copia la entonación de la
        referencia ni necesita su transcripción."""
        import torch
        from qwen_tts import Qwen3TTSModel

        self.referencia = cargar_audio(referencia)
        self.texto_ref = _transcribir(self.referencia)
        self.tts = Qwen3TTSModel.from_pretrained(modelo, device_map=device, dtype=torch.float32)
        self.prompt = self.tts.create_voice_clone_prompt(ref_audio=(self.referencia, 16000),
                                                         ref_text=None if solo_huella else self.texto_ref,
                                                         x_vector_only_mode=solo_huella)

    def decir(self, frases, estilos=None):   # Qwen3-TTS no acepta estilo al clonar
        wavs, self.sr = self.tts.generate_voice_clone(text=frases, language=["Spanish"] * len(frases),
                                                      voice_clone_prompt=self.prompt)
        return wavs


class VozExpresiva:
    """VoxCPM2 (OpenBMB, Apache 2.0): clona la voz y sigue un estilo escrito entre paréntesis antes de la frase."""

    def __init__(self, referencia, device="cpu", con_estilo=True):
        import tempfile
        from voxcpm import VoxCPM

        audio = cargar_audio(referencia)
        self.ref = Path(tempfile.mkdtemp()) / "referencia.wav"
        sf.write(self.ref, audio, 16000)
        self.texto_ref = _transcribir(audio)
        self.con_estilo = con_estilo
        self.tts = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device=device)
        self.sr = self.tts.tts_model.sample_rate

    def decir(self, frases, estilos=None):
        estilos = estilos if self.con_estilo and estilos else [None] * len(frases)
        return [self.tts.generate(text=f"({e}){f}" if e else f, reference_wav_path=str(self.ref),
                                  cfg_value=2.0, inference_timesteps=10)
                for f, e in zip(frases, estilos)]


def _transcribir(audio16k):
    return " ".join(s.text.strip() for s in _whisper().transcribe(audio16k, language="es")[0])


def _acelerar(w, sr, factor):
    """Cambia el ritmo sin cambiar el tono (atempo de ffmpeg)."""
    crudo = subprocess.run([FFMPEG, "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                            "-af", f"atempo={factor}", "-f", "f32le", "-"],
                           input=np.asarray(w, np.float32).tobytes(), capture_output=True, check=True).stdout
    return np.frombuffer(crudo, np.float32)


# Subtítulos y control de calidad --------------------------------------------

_ASR = None


def _whisper():
    global _ASR
    if _ASR is None:
        from faster_whisper import WhisperModel
        _ASR = WhisperModel(ASR, device="cpu", compute_type="int8")
    return _ASR


@dataclass
class Narracion:
    audio: np.ndarray
    sr: int
    escenas: list            # (inicio, fin) en segundos de cada escena
    palabras: list = field(default_factory=list)   # (inicio, fin, palabra) de Whisper

    @property
    def duracion(self):
        return len(self.audio) / self.sr


def narrar(voz, guion, max_wer=0.25, reintentos=1, velocidad=1.0):
    """Narra cada escena; si Whisper no entiende bien una escena (WER alto), la vuelve a generar."""
    frases = [e["frase"] for e in guion["escenas"]]
    n = len(frases)
    estilos = [e.get("estilo") or ESTILOS["inicio" if i == 0 else "cierre" if i == n - 1 else "medio"]
               for i, e in enumerate(guion["escenas"])]
    wavs = voz.decir(frases, estilos)
    if velocidad != 1:
        wavs = [_acelerar(w, voz.sr, velocidad) for w in wavs]
    for intento in range(reintentos + 1):
        for e, w in zip(guion["escenas"], wavs):
            e["wer"] = _wer(e["frase"], _a16k(w, voz.sr))
        malas = [i for i, e in enumerate(guion["escenas"]) if e["wer"] > max_wer]
        if not malas or intento == reintentos:
            break
        for i, w in zip(malas, voz.decir([frases[i] for i in malas], [estilos[i] for i in malas])):
            wavs[i] = _acelerar(w, voz.sr, velocidad) if velocidad != 1 else w

    sr, partes, escenas, t = voz.sr, [np.zeros(int(INICIO * voz.sr), np.float32)], [], INICIO
    for w in wavs:
        w = np.asarray(w, np.float32)
        escenas.append((t, t + len(w) / sr))
        partes += [w, np.zeros(int(PAUSA * sr), np.float32)]
        t += len(w) / sr + PAUSA
    partes.append(np.zeros(int(FINAL * sr), np.float32))
    return Narracion(np.concatenate(partes), sr, escenas)


def _a16k(w, sr):
    w = np.asarray(w, np.float32)
    return np.interp(np.arange(0, len(w), sr / 16000), np.arange(len(w)), w).astype(np.float32)


def _normalizar(s):
    """Para comparar lo escrito con lo que oyó Whisper: números en palabras, sin tildes ni puntuación."""
    s = s.lower().replace("%", " por ciento")
    s = re.sub(r"(?<=\d)[,.](?=\d{3}\b)", "", s)
    s = re.sub(r"\d+", lambda m: num2words(int(m.group()), lang="es"), s)
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", s).split())


def _wer(referencia, audio16k):
    oido = " ".join(s.text for s in _whisper().transcribe(audio16k, language="es")[0])
    return jiwer.wer(_normalizar(referencia), _normalizar(oido)) if _normalizar(oido) else 1.0


def subtitulos(narracion, guion):
    """Palabras con tiempo; el guion va como contexto para que Whisper escriba bien los nombres propios."""
    contexto = " ".join(e["frase"] for e in guion["escenas"])
    segs, _ = _whisper().transcribe(_a16k(narracion.audio, narracion.sr), language="es",
                                    word_timestamps=True, initial_prompt=contexto)
    palabras = []
    for w in (w for s in segs for w in s.words if w.word.strip()):
        # Whisper a veces parte "8.7" o "126%" en dos palabras: se pegan a la anterior
        if palabras and re.match(r"^[.,%]", w.word.strip()):
            ini, _, prev = palabras.pop()
            palabras.append((ini, w.end, prev + w.word.strip()))
        else:
            palabras.append((w.start, w.end, w.word.strip()))
    # Whisper a veces oye mal (en este reel escribió «OMP» por «ONPE» y «setenta y seis» por «setenta y ocho»,
    # aunque la narración era correcta): los subtítulos muestran las palabras del guion con los tiempos de Whisper
    narracion.palabras = _alinear(palabras, guion)
    return narracion.palabras


def _alinear(palabras, guion):
    """Empareja las palabras de Whisper con las del guion (difflib). Las del guion que coinciden toman el tiempo de su
    pareja; las que no, se reparten el tramo de las palabras de Whisper que reemplazan."""
    import difflib
    del_guion = [w for e in guion["escenas"] for w in e["frase"].split()]
    a = [_normalizar(p[2]) for p in palabras]
    b = [_normalizar(w) for w in del_guion]
    tiempos = [None] * len(b)
    for etiqueta, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if etiqueta == "equal":
            for k in range(i2 - i1):
                tiempos[j1 + k] = palabras[i1 + k][:2]
        elif j2 > j1:
            if i2 > i1:
                ini, fin = palabras[i1][0], palabras[i2 - 1][1]
            else:   # palabras del guion que Whisper no escribió: se ubican entre sus vecinas
                ini = palabras[i1 - 1][1] if i1 > 0 else 0.0
                fin = palabras[i1][0] if i1 < len(palabras) else ini + 0.3 * (j2 - j1)
            paso = (fin - ini) / (j2 - j1)
            for k in range(j2 - j1):
                tiempos[j1 + k] = (ini + k * paso, ini + (k + 1) * paso)
    return [(t[0], t[1], w) for t, w in zip(tiempos, del_guion)]


def escenas_desde_palabras(narracion, guion):
    """Inicio y fin de cada escena a partir de sus palabras alineadas (para rehacer el video sin volver a narrar)."""
    escenas, k = [], 0
    for e in guion["escenas"]:
        n = len(e["frase"].split())
        escenas.append((narracion.palabras[k][0], narracion.palabras[k + n - 1][1]))
        k += n
    narracion.escenas = escenas
    return escenas


def _bloques(palabras, max_palabras=4, max_letras=24):
    """Agrupa palabras en bloques cortos para leer en el celular; corta en signos de puntuación."""
    bloques, actual = [], []
    for p in palabras:
        actual.append(p)
        largo = sum(len(x[2]) + 1 for x in actual)
        if len(actual) >= max_palabras or largo >= max_letras or p[2][-1] in ".,;:?!":
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def a_srt(narracion, ruta):
    def hms(t):
        return f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(t % 1 * 1000):03}"
    lineas = []
    for i, b in enumerate(_bloques(narracion.palabras), 1):
        lineas += [str(i), f"{hms(b[0][0])} --> {hms(b[-1][1])}", " ".join(p[2] for p in b), ""]
    Path(ruta).write_text("\n".join(lineas), encoding="utf-8")


# Video ---------------------------------------------------------------------
# Cambios respecto de la Sesión 15: cada escena lleva una imagen (mapa, gráfico o captura del tablero) con un zoom
# lento, el video suma una pista de música por debajo de la narración y el pie muestra los créditos.

ZONA_TEXTO = (400, 770)      # cifra y etiqueta (y en píxeles)
ZONA_IMAGEN = (800, 1430)    # imagen de la escena: hasta 900 × 630
Y_SUBTITULO = 1480
Y_PIE = 1620
ZOOM = 0.05                  # la imagen crece 5 % a lo largo de su escena


def _fuente(nombre, tam, peso):
    ruta = FUENTES / f"{nombre}.ttf"
    if not ruta.exists():   # Oswald y Public Sans, de Google Fonts (licencia OFL)
        import urllib.request
        FUENTES.mkdir(exist_ok=True)
        urllib.request.urlretrieve(f"https://github.com/google/fonts/raw/main/ofl/{nombre.lower()}/{nombre}%5Bwght%5D.ttf", ruta)
    f = ImageFont.truetype(str(ruta), tam)
    f.set_variation_by_axes([peso])
    return f


def _envolver(draw, texto, fuente, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if draw.textlength(prueba, font=fuente) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + [actual]


def _ajustar(draw, texto, nombre, peso, ancho, maximo, minimo=80):
    for tam in range(maximo, minimo, -10):
        f = _fuente(nombre, tam, peso)
        if draw.textlength(texto, font=f) <= ancho:
            return f
    return _fuente(nombre, minimo, peso)


def _base(titulo, fuente_datos, autor, creditos=""):
    """Lo que no cambia en todo el video: título, aviso de IA, fuente y créditos."""
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    d.text((MARGEN, 250), titulo.upper(), font=_fuente("PublicSans", 40, 800), fill=ACENTO)
    aviso = "VOZ GENERADA CON IA"
    f = _fuente("PublicSans", 28, 700)
    x1 = MARGEN + d.textlength(aviso, font=f) + 36
    d.rounded_rectangle((MARGEN, 315, x1, 365), radius=25, outline=SUAVE, width=2)
    d.text((MARGEN + 18, 340), aviso, font=f, fill=SUAVE, anchor="lm")
    y = Y_PIE
    pie = _fuente("PublicSans", 30, 600)
    for linea in _envolver(d, f"{autor} · Fuente: {fuente_datos}", pie, ANCHO - 2 * MARGEN):
        d.text((MARGEN, y), linea, font=pie, fill=SUAVE)
        y += 40
    chico = _fuente("PublicSans", 25, 500)
    for linea in (_envolver(d, creditos, chico, ANCHO - 2 * MARGEN) if creditos else []):
        d.text((MARGEN, y + 6), linea, font=chico, fill="#8C8377")
        y += 33
    return img


def _escena(e):
    """Capa transparente con la cifra grande y su etiqueta, centradas en ZONA_TEXTO."""
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    ancho = ANCHO - 2 * MARGEN
    def alto(texto, f):   # altura sobre la línea base
        return -d.textbbox((0, 0), texto, font=f, anchor="ls")[1]

    lineas = []
    if e.get("cifra"):
        f = _ajustar(d, e["cifra"], "Oswald", 700, ancho, 210)
        lineas.append((e["cifra"], f, TEXTO, alto(e["cifra"], f), 40))
        fe, color = _fuente("PublicSans", 52, 600), SUAVE
    else:
        fe, color = _fuente("Oswald", 84, 600), TEXTO
    lineas += [(x, fe, color, alto("H", fe), int(fe.size * 0.45)) for x in _envolver(d, e["etiqueta"], fe, ancho)]
    y = (ZONA_TEXTO[0] + ZONA_TEXTO[1] - sum(h + g for *_, h, g in lineas) + lineas[-1][4]) / 2
    for texto, f, color, h, g in lineas:
        y += h
        d.text((MARGEN, y), texto, font=f, fill=color, anchor="ls")
        y += g
    return capa


def _imagen(ruta):
    """Imagen de la escena ajustada a ZONA_IMAGEN, ampliada para el zoom, con su máscara de esquinas redondeadas."""
    if not ruta:
        return None
    ruta = Path(ruta) if Path(ruta).is_absolute() else AQUI / ruta
    img = Image.open(ruta).convert("RGB")
    caja_w, caja_h = ANCHO - 2 * MARGEN, ZONA_IMAGEN[1] - ZONA_IMAGEN[0]
    escala = min(caja_w / img.width, caja_h / img.height)
    w, h = int(img.width * escala), int(img.height * escala)
    ampliada = img.resize((int(w * (1 + ZOOM)), int(h * (1 + ZOOM))), Image.LANCZOS)
    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), radius=24, fill=255)
    return {"ampliada": ampliada, "w": w, "h": h, "mascara": mascara,
            "x": (ANCHO - w) // 2, "y": ZONA_IMAGEN[0] + (caja_h - h) // 2}


def _recorte_zoom(im, avance):
    """Recorta el centro de la imagen ampliada: el zoom va de 1.00 a 1 + ZOOM a lo largo de la escena."""
    fw, fh = im["ampliada"].size
    fraccion = 1 / (1 + ZOOM * avance)          # parte de la imagen que se muestra: toda al inicio
    cw, ch = fw * fraccion, fh * fraccion
    x0, y0 = (fw - cw) / 2, (fh - ch) / 2
    return im["ampliada"].resize((im["w"], im["h"]), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


def _cuadro(base, capas, imagenes, narracion, t, bloques, fuente_sub):
    img = base.copy()
    # escena actual, con una entrada suave (aparece y sube) en sus primeros 0.35 s
    i = max([k for k, (ini, _) in enumerate(narracion.escenas) if ini - PAUSA <= t] or [0])
    ini, fin = narracion.escenas[i]
    a = min(1.0, max(0.0, (t - ini + PAUSA) / 0.35))

    im = imagenes[i]
    if im:
        avance = min(1.0, max(0.0, (t - ini + PAUSA) / (fin - ini + 2 * PAUSA)))
        foto = _recorte_zoom(im, avance)
        mascara = im["mascara"] if a >= 1 else im["mascara"].point(lambda v: int(v * a))
        img.paste(foto, (im["x"], im["y"] + int(30 * (1 - a))), mascara)

    capa = capas[i]
    if a < 1:
        capa = capa.copy()
        capa.putalpha(capa.getchannel("A").point(lambda v: int(v * a)))
    img.paste(capa, (0, int(40 * (1 - a))), capa)

    d = ImageDraw.Draw(img)
    # barra de avance arriba, como en las historias
    d.rounded_rectangle((MARGEN, 180, ANCHO - MARGEN, 188), radius=4, fill=CAJA)
    d.rounded_rectangle((MARGEN, 180, MARGEN + (ANCHO - 2 * MARGEN) * t / narracion.duracion, 188), radius=4, fill=ACENTO)

    # subtítulo: el bloque que se está diciendo, con la palabra actual resaltada
    b = next((b for b in bloques if b[0][0] - 0.1 <= t <= b[-1][1] + 0.25), None)
    if b:
        texto = " ".join(p[2] for p in b)
        w = d.textlength(texto, font=fuente_sub)
        x, y = (ANCHO - w) / 2, Y_SUBTITULO
        d.rounded_rectangle((x - 36, y - 24, x + w + 36, y + fuente_sub.size + 30), radius=28, fill=CAJA)
        for ini_p, fin_p, palabra in b:
            d.text((x, y), palabra, font=fuente_sub, fill=ACENTO if ini_p <= t <= fin_p + 0.05 else TEXTO)
            x += d.textlength(palabra + " ", font=fuente_sub)
    return img


def video(guion, narracion, ruta, fuente_datos, autor, creditos="", musica=None, volumen_musica=0.12):
    """Dibuja cada cuadro con Pillow y se los pasa a ffmpeg con la narración normalizada a -14 LUFS y, si se indica,
    una pista de música por debajo (volumen_musica = 0.12 son unos -18 dB) con entrada y salida suaves."""
    ruta = Path(ruta)
    wav = ruta.with_suffix(".wav")
    sf.write(wav, narracion.audio, narracion.sr)
    base = _base(guion["titulo"], fuente_datos, autor, creditos)
    capas = [_escena(e) for e in guion["escenas"]]
    imagenes = [_imagen(e.get("imagen")) for e in guion["escenas"]]
    bloques = _bloques(narracion.palabras)
    fuente_sub = _fuente("PublicSans", 58, 800)
    voz = "[1:a]aformat=channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
    if musica:
        dur = narracion.duracion
        filtro = (f"{voz}[voz];[2:a]aformat=channel_layouts=stereo,aresample=48000,volume={volumen_musica},"
                  f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0.0, dur - 3):.2f}:d=3[mus];"
                  "[voz][mus]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
        entradas = ["-i", str(wav), "-stream_loop", "-1", "-i", str(musica)]
    else:
        filtro = f"{voz}[a]"
        entradas = ["-i", str(wav)]
    cmd = [FFMPEG, "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
           *entradas, "-filter_complex", filtro, "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-shortest", "-movflags", "+faststart", str(ruta)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(int(narracion.duracion * FPS)):
        proc.stdin.write(_cuadro(base, capas, imagenes, narracion, k / FPS, bloques, fuente_sub).tobytes())
    proc.stdin.close()
    proc.wait()
    return ruta


def portada(guion, narracion, ruta, fuente_datos, autor, creditos="", escena=1):
    """Un cuadro fijo para revisar el diseño o usar como miniatura."""
    t = narracion.escenas[escena][0] + 1.0
    img = _cuadro(_base(guion["titulo"], fuente_datos, autor, creditos), [_escena(e) for e in guion["escenas"]],
                  [_imagen(e.get("imagen")) for e in guion["escenas"]], narracion, t, _bloques(narracion.palabras),
                  _fuente("PublicSans", 58, 800))
    img.save(ruta)
    return ruta


def posts(guion, ruta):
    h = " ".join("#" + x.lstrip("#") for x in guion.get("hashtags", []))
    p = guion["posts"]
    Path(ruta).write_text(
        f"# {guion['titulo']}\n\n## LinkedIn\n\n{p['linkedin']}\n\n{h}\n\n"
        f"## X ({len(p['x'])} caracteres)\n\n{p['x']}\n\n## Facebook\n\n{p['facebook']}\n\n{h}\n",
        encoding="utf-8")
    return ruta
