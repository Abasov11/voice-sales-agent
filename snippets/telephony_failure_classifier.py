"""
Иллюстративная реконструкция из voice-sales-agent (портфолио-кейс, не рабочая
сборка). В реальном проекте это таксономия из 13 классов сбоев телефонии
(docs/TELEPHONY_FAILURES.md) с root-cause, детектом и recovery для каждого —
здесь только логика, дающая представление о подходе.

Идея: звонок может не задаться десятком разных способов (не взяли трубку,
попали на автоответчик, оператор заблокировал номер после серии звонков,
плохое качество звука и т.д.), и каждый способ требует СВОЕЙ recovery-политики
(разный retry, разное действие оператора). "Звонок не удался" одним общим
кодом ошибки — теряет эту разницу и ведёт к неверному ретраю (например,
ретраить voicemail так же часто, как no_answer, шлёт спам сообщения
автоответчику).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallSignal:
    sip_code: int | None
    ring_duration_s: float | None
    is_answering_machine: bool
    stt_confidence: float | None
    user_utterances: int
    recent_no_answer_rate: float  # доля no_answer за последний час в кампании


@dataclass
class Classification:
    failure_class: str
    retry_after_s: int | None  # None — не ретраить автоматически


def classify_call_failure(sig: CallSignal) -> Classification:
    # spam_block определяем КОСВЕННО, по статистике окна, а не по одному
    # звонку — единичный no_answer это норма, а не блокировка номера.
    if sig.recent_no_answer_rate > 0.6 and (sig.ring_duration_s or 0) < 3:
        return Classification("spam_block", retry_after_s=None)  # нужна ротация SIP-номера

    if sig.is_answering_machine or (
        sig.user_utterances == 0 and (sig.ring_duration_s or 0) > 8
    ):
        return Classification("voicemail_or_amd", retry_after_s=None)  # не оставляем сообщений

    if sig.sip_code == 486:
        return Classification("busy", retry_after_s=30 * 60)

    if sig.sip_code in (480, 487) and (sig.ring_duration_s or 0) >= 30:
        return Classification("no_answer", retry_after_s=4 * 3600)

    if sig.stt_confidence is not None and sig.stt_confidence < 0.3:
        return Classification("low_quality_audio", retry_after_s=3600)

    return Classification("unclassified", retry_after_s=3600)


RECOVERY_ACTIONS: dict[str, str] = {
    "spam_block": "алерт оператору: ротация SIP-номера, прогрев ≤20 звонков/день",
    "voicemail_or_amd": "hangup сразу, лид молчит 24ч, менеджер звонит лично",
    "busy": "автоматический retry (до 3 попыток), потом busy_persistent",
    "no_answer": "лид остаётся в очереди, retry не раньше чем через 4 часа",
    "low_quality_audio": "агент вежливо прощается, retry через 1 час",
    "unclassified": "retry через 1 час, требует ручного разбора при повторе",
}


if __name__ == "__main__":
    example = CallSignal(
        sip_code=None, ring_duration_s=9.0, is_answering_machine=False,
        stt_confidence=None, user_utterances=0, recent_no_answer_rate=0.1,
    )
    result = classify_call_failure(example)
    print(result.failure_class, "->", RECOVERY_ACTIONS[result.failure_class])
