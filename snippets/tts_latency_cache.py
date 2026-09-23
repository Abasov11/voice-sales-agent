"""
Иллюстративный фрагмент из voice-sales-agent (портфолио-кейс, не рабочая сборка).

Латентность первого хода звонка. Раньше приветствие генерировала LLM — это
давало заметную тишину сразу после поднятия трубки (худшая пауза звонка,
разговор обрывался там же). Решение: первая реплика — детерминированный
шаблон без LLM (меняется только именем и настройками из БД), а TTS
кэшируется по содержимому — повторяющиеся фразы (приветствие, "не расслышала")
синтезируются один раз. По факту такая замена в проекте сократила паузу
приветствия с ~8.5с до ~1с.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def greet_text(client_name: str | None, agent_name: str, school_name: str) -> str:
    """Детерминированное приветствие — представление сразу, без LLM-паузы.
    Голое "Здравствуйте! Это Х?" без представления на прогонах читалось как
    роботичный чек-лист; живой менеджер представляется в первой же фразе."""
    name = (client_name or "").strip()
    if name:
        return (
            f"Здравствуйте! Меня зовут {agent_name}, звоню из детской "
            f"спортивной школы {school_name}. Это {name}?"
        )
    return (
        f"Здравствуйте! Меня зовут {agent_name}, звоню из детской "
        f"спортивной школы {school_name}. Подскажите, как могу к вам обращаться?"
    )


def tts_cache_key(voice_id: str, text: str, tts_knobs: dict[str, str]) -> str:
    """Контентно-адресуемый ключ кэша: одинаковый текст + голос + настройки
    синтеза → один аудиофайл, без повторного обращения к TTS-провайдеру.
    Настройки ОБЯЗАНЫ быть в ключе — иначе смена модели/голоса молча отдавала
    бы старый закэшированный файл, синтезированный прежними параметрами."""
    knobs = "|".join(tts_knobs.get(k, "") for k in sorted(tts_knobs))
    raw = f"{voice_id}|{knobs}|{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def resolve_cached_audio_path(audio_dir: Path, voice_id: str, text: str,
                               tts_knobs: dict[str, str]) -> tuple[Path, bool]:
    """Возвращает (путь_к_файлу, уже_есть_в_кэше). Вызывающий код обращается
    к TTS-провайдеру только если второй элемент — False."""
    key = tts_cache_key(voice_id, text, tts_knobs)
    dest = audio_dir / f"c{key}.mp3"
    hit = dest.exists() and dest.stat().st_size > 0
    return dest, hit


if __name__ == "__main__":
    greeting = greet_text("Айгерим", "Алия", "Старт")
    knobs = {"stability": "0.40", "style": "0.35", "model_id": "tts-fast-v2"}
    path, hit = resolve_cached_audio_path(Path("/tmp/tts-cache"), "voice-1", greeting, knobs)
    print(greeting, "->", path.name, "cached" if hit else "needs synth")
