"""Prueba A/B de la voz clonada con dos frases del guion (escenas 3 y 5), antes de narrar el reel completo.

    python pruebas/comparar_voces.py            # desde reel/, con el entorno del reel

El autor escuchó la primera versión y observó problemas de tono, ritmo y pronunciación («Fujimori», «Castillo» y la
«r»). Se comparan el modelo de 0.6B y el de 1.7B, dos tramos de la grabación como referencia y el modo que usa solo
la huella de la voz (x_vector_only_mode), sin copiar la entonación de la referencia. Los audios quedan en
pruebas/voz_*.wav, que no se suben al repositorio.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import reel  # noqa: E402

GUION = json.loads((AQUI.parent / "guion.json").read_text(encoding="utf-8"))
FRASES = [GUION["escenas"][2]["frase"], GUION["escenas"][4]["frase"]]


def referencia(ini, fin, nombre):
    """Tramo de la grabación original, con el pico normalizado a -1 dBFS."""
    ruta = AQUI.parent / nombre
    if not ruta.exists():
        audio = reel.cargar_audio(AQUI.parent / "mi_voz.m4a")[int(ini * 16000):int(fin * 16000)]
        sf.write(ruta, (audio * 0.89 / np.abs(audio).max()).astype(np.float32), 16000, subtype="PCM_16")
    return ruta


PRUEBAS = {
    "A_0.6B_tramo0-17": ("Qwen/Qwen3-TTS-12Hz-0.6B-Base", (0.0, 17.2, "mi_voz_ref2.wav"), False),
    "B_1.7B_tramo17-35": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", (17.4, 35.2, "mi_voz_ref.wav"), False),
    "C_1.7B_tramo0-17": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", (0.0, 17.2, "mi_voz_ref2.wav"), False),
    "D_1.7B_solo_huella": ("Qwen/Qwen3-TTS-12Hz-1.7B-Base", (17.4, 35.2, "mi_voz_ref.wav"), True),
}

if __name__ == "__main__":
    import torch
    from qwen_tts import Qwen3TTSModel

    modelos = {}
    for nombre, (modelo, (ini, fin, archivo), solo_huella) in PRUEBAS.items():
        t0 = time.time()
        if modelo not in modelos:
            modelos.clear()   # un modelo a la vez en memoria
            modelos[modelo] = Qwen3TTSModel.from_pretrained(modelo, device_map="cpu", dtype=torch.float32)
        tts = modelos[modelo]
        ref = reel.cargar_audio(referencia(ini, fin, archivo))
        texto_ref = None if solo_huella else reel._transcribir(ref)
        prompt = tts.create_voice_clone_prompt(ref_audio=(ref, 16000), ref_text=texto_ref,
                                               x_vector_only_mode=solo_huella)
        wavs, sr = tts.generate_voice_clone(text=FRASES, language=["Spanish"] * 2, voice_clone_prompt=prompt)
        pausa = np.zeros(int(0.5 * sr), np.float32)
        audio = np.concatenate([np.asarray(wavs[0], np.float32), pausa, np.asarray(wavs[1], np.float32)])
        sf.write(AQUI / f"voz_{nombre}.wav", audio, sr)
        wer = [reel._wer(f, reel._a16k(w, sr)) for f, w in zip(FRASES, wavs)]
        palabras = sum(len(f.split()) for f in FRASES)
        print(f"{nombre}: {len(audio) / sr:.1f} s, {palabras / (len(audio) / sr):.2f} palabras/s, "
              f"WER = {wer[0]:.2f} y {wer[1]:.2f}, {time.time() - t0:.0f} s de cálculo", flush=True)
