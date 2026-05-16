#!/usr/bin/env python3
import sys
import os
import subprocess
import tempfile
import openai
from dotenv import load_dotenv

load_dotenv()

MAX_BYTES = 24 * 1024 * 1024  # 24MB to stay safely under the 25MB limit
CHUNK_MINUTES = 10


def transcribe_file(client: openai.OpenAI, path: str, language: str) -> str:
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
        )
    return result.text


def split_and_transcribe(audio_path: str, language: str = "tr") -> str:
    client = openai.OpenAI()

    if os.path.getsize(audio_path) <= MAX_BYTES:
        return transcribe_file(client, audio_path, language)

    print(f"Dosya büyük, {CHUNK_MINUTES} dakikalık parçalara bölünüyor...")

    with tempfile.TemporaryDirectory() as tmp:
        chunk_pattern = os.path.join(tmp, "chunk_%03d.mp3")
        subprocess.run(
            [
                "ffmpeg", "-i", audio_path,
                "-f", "segment",
                "-segment_time", str(CHUNK_MINUTES * 60),
                "-ac", "1",        # mono
                "-ar", "16000",    # 16kHz
                "-q:a", "5",       # lower bitrate to keep size down
                chunk_pattern,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        chunks = sorted(f for f in os.listdir(tmp) if f.startswith("chunk_"))
        parts = []
        for i, chunk in enumerate(chunks, 1):
            chunk_path = os.path.join(tmp, chunk)
            print(f"  Parça {i}/{len(chunks)} transkript ediliyor...")
            parts.append(transcribe_file(client, chunk_path, language))

    return " ".join(parts)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python transcribe.py <audio_dosyası> [dil]")
        print("Örnek:    python transcribe.py ses.m4a tr")
        sys.exit(1)

    path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "tr"

    print(f"Transkript ediliyor: {path} (dil: {lang})\n")
    text = split_and_transcribe(path, lang)
    print("\n" + text)

    output_path = path.rsplit(".", 1)[0] + ".txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nKaydedildi: {output_path}")
