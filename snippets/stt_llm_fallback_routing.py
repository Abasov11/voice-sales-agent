"""
Иллюстративный фрагмент из voice-sales-agent (портфолио-кейс, не рабочая сборка).

Параллельный модуль — аналитика звонков живых менеджеров (не голосового
агента): запись → транскрибация → LLM-оценка по критериям. Два инженерных
решения ради надёжности и стоимости:

  1) STT — каскад провайдеров: primary может быть недоступен/лимитирован,
     тогда без падения всего пайплайна переключаемся на secondary.
  2) LLM-оценку роутим по длительности звонка: короткие "звонок не
     состоялся" разговоры (~90% потока) не нуждаются в дорогой модели,
     длинные продающие диалоги — нуждаются.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provider = Literal["assemblyai", "whisper"]
Tier = Literal["short", "long"]


@dataclass
class TranscriptResult:
    provider: Provider
    text: str
    cost_cents: int | None


async def transcribe(
    path: str,
    *,
    assemblyai_key: str | None,
    openai_key: str | None,
    use_assemblyai_primary: bool,
) -> TranscriptResult:
    """AssemblyAI — primary (если включён флагом), OpenAI Whisper — fallback.
    Провайдер может временно ломаться (несовместимость SDK/API, квота) —
    падать в этом случае молчком в whisper надёжнее, чем ронять весь звонок."""
    if assemblyai_key and use_assemblyai_primary:
        try:
            return await _call_assemblyai(path, assemblyai_key)
        except Exception:
            pass  # переключаемся на fallback ниже, звонок не теряем
    if openai_key:
        return await _call_whisper(path, openai_key)
    if assemblyai_key:
        return await _call_assemblyai(path, assemblyai_key)
    raise RuntimeError("no STT provider configured")


def pick_tier(duration_s: int | None) -> Tier:
    """Короткие звонки (типично — не состоявшийся разговор, автоответ,
    быстрый отказ) достаточно оценить дешёвой моделью; длинные продающие
    диалоги — моделью классом выше, там решает нюанс аргументации."""
    if duration_s is None or duration_s < 60:
        return "short"
    return "long"


def pick_model(tier: Tier, *, short_model: str, long_model: str) -> str:
    return short_model if tier == "short" else long_model


async def _call_assemblyai(path: str, key: str) -> TranscriptResult:  # pragma: no cover
    raise NotImplementedError("иллюстративная заглушка — реальный вызов SDK опущен")


async def _call_whisper(path: str, key: str) -> TranscriptResult:  # pragma: no cover
    raise NotImplementedError("иллюстративная заглушка — реальный вызов API опущен")


if __name__ == "__main__":
    for duration in (12, 45, 60, 240):
        tier = pick_tier(duration)
        model = pick_model(tier, short_model="gpt-tier-fast", long_model="gpt-tier-quality")
        print(f"{duration:>4}s -> tier={tier:<5} model={model}")
