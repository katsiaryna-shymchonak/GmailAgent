from typing import Dict, Any, List
from .base import BaseTool

class NewsletterTool(BaseTool):
    name = "newsletter"

    def __init__(self):
        # Совместимо с NewsletterInsights моделью (List[str] + strings)
        schema = {
            "unsubscribe": ["string"],   # лучше: "Sender Name — Subject" или "Sender Name"
            "keep": ["string"],          # аналогично
            "digest": "string",
            "weekly_report": "string"
        }
        super().__init__(schema=schema)

    def _label_for(self, msg: Dict[str, Any]) -> str:
        """Формирует человекочитаемую метку письма: 'Sender — Subject' или 'Subject'."""
        sender = (msg.get("from_name") or msg.get("from") or "").strip()
        subject = (msg.get("subject") or "").strip()
        if sender and subject:
            return f"{sender} — {subject}"
        return sender or subject or "Unknown newsletter"

    def _is_newsletter_like(self, msg: Dict[str, Any]) -> bool:
        """Эврестика: определяем, похоже ли письмо на рассылку."""
        s = (msg.get("subject") or "").lower()
        t = " ".join(msg.get("tags", [])).lower()
        from_addr = (msg.get("from") or "").lower()
        return any([
            "newsletter" in s, "digest" in s, "дайджест" in s, "рассылка" in s,
            "no-reply" in from_addr, "news" in s, "подборка" in s,
            "newsletter" in t, "digest" in t, "marketing" in t
        ])

    def _utility_score(self, msg: Dict[str, Any], weekly_metrics: Dict[str, Any]) -> float:
        """
        Оцениваем полезность (0–1) по простым признакам:
        - открытия, клики, время чтения → +;
        - высокая частота, повторяемость тем без новых инсайтов → −;
        - наличие явных CTA/полезных ссылок → +.
        """
        # метрики по отправителю
        sender_key = (msg.get("from_name") or msg.get("from") or "").lower()
        metrics = (weekly_metrics.get(sender_key) or weekly_metrics.get("global") or {})
        opens = float(metrics.get("opens_rate", 0.0))
        clicks = float(metrics.get("clicks_rate", 0.0))
        read_time = float(metrics.get("avg_read_seconds", 0.0))
        freq = float(metrics.get("send_per_week", 0.0))
        repeats = float(metrics.get("topic_repeats", 0.0))
        ctas = int(metrics.get("cta_count", 0))

        score = 0.0
        score += 0.4 * min(opens, 1.0)
        score += 0.3 * min(clicks, 1.0)
        score += 0.2 * min(read_time / 60.0, 1.0)  # нормируем до минуты
        score += 0.1 * min(ctas, 3) / 3.0

        # штрафы
        if freq > 5:
            score -= 0.15
        if repeats > 3:
            score -= 0.15

        # мягкие границы
        return max(0.0, min(1.0, score))

    async def run(
        self,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        weekly_metrics: Dict[str, Any],
        user_language: str = "English"
    ) -> Dict[str, Any]:
        # Промпт усиливает анализ полезности и явные рекомендации
        prompt = (
            f"You are an agent for newsletter management.\n"
            f"Task: Identify newsletters among the emails and produce insights.\n\n"
            f"Output strictly valid JSON matching the schema.\n"
            f"Language: {user_language}\n\n"
            f"Rules:\n"
            f"- In 'unsubscribe' and 'keep' arrays, include the newsletter SUBJECT or SENDER NAME, not internal ids.\n"
            f"- Each newsletter subject must be placed as a separate string in the correct array.\n"
            f"- Do NOT output objects with id/subject, only plain strings.\n"
            f"- 'digest': short summary of newsletters kept, with brief explanations why they are useful.\n"
            f"- 'weekly_report': concise weekly insight, including recommendations to unsubscribe or keep, with short reasons (e.g. too frequent, low engagement, valuable insights).\n\n"
            f"Emails:\n{messages}\n\n"
            f"Filter data:\n{filter_data}\n\n"
            f"Weekly metrics:\n{weekly_metrics}"
        )

        result = await self.call(
            prompt,
            variables={"messages": messages, "filter_data": filter_data, "weekly_metrics": weekly_metrics},
            user_language=user_language
        )

        # --- Защитная нормализация и контекст ---
        if not isinstance(result, dict):
            result = {}

        ru = user_language.lower().startswith("rus")
        unsubscribe = result.get("unsubscribe", [])
        keep = result.get("keep", [])
        digest = result.get("digest")
        weekly_report = result.get("weekly_report")

        # Если модель вернула объекты/идентификаторы — переведём в строки-лейблы
        def normalize_list(items: List[Any], msgs: List[Dict[str, Any]]) -> List[str]:
            labels: List[str] = []
            for item in items or []:
                if isinstance(item, str) and item.strip():
                    labels.append(item.strip())
                elif isinstance(item, dict):
                    # пробуем сопоставить по id
                    msg = None
                    if "id" in item:
                        msg = next((m for m in msgs if m.get("id") == item["id"]), None)
                    # или собрать лейбл из полей
                    if not msg:
                        msg = {
                            "from_name": item.get("from_name") or item.get("sender") or "",
                            "from": item.get("from") or "",
                            "subject": item.get("subject") or "",
                        }
                    labels.append(self._label_for(msg))
                else:
                    labels.append(str(item))
            return labels

        unsubscribe = normalize_list(unsubscribe if isinstance(unsubscribe, list) else [], messages)
        keep = normalize_list(keep if isinstance(keep, list) else [], messages)

        # Автодополнение рекомендаций на основе эвристики, если пусто или мало
        newsletter_msgs = [m for m in messages if self._is_newsletter_like(m)]
        scored = sorted(
            [(self._label_for(m), self._utility_score(m, weekly_metrics)) for m in newsletter_msgs],
            key=lambda x: x[1],
            reverse=True
        )

        # добавим отсутствующие метки исходя из порогов
        existing = set(unsubscribe) | set(keep)
        for label, score in scored:
            if label in existing:
                continue
            if score >= 0.6:
                keep.append(label)
            elif score <= 0.3:
                unsubscribe.append(label)
            existing.add(label)

        # digest/weekly_report fallback
        if not isinstance(digest, str) or not digest.strip():
            if keep:
                digest = (
                    f"Сохранены рассылки: {', '.join(keep[:5])}. Тема недели: релевантные обзоры и практические материалы."
                    if ru
                    else f"Kept newsletters: {', '.join(keep[:5])}. Weekly theme: relevant roundups and practical resources."
                )
            else:
                digest = ("Полезных рассылок не выявлено." if ru else "No useful newsletters identified.")

        if not isinstance(weekly_report, str) or not weekly_report.strip():
            # краткие инсайты из распределения очков
            if scored:
                top = [lbl for lbl, s in scored[:3]]
                low = [lbl for lbl, s in scored[-3:]]
                weekly_report = (
                    f"Итоги недели: высокоценные — {', '.join(top)}; к отписке — {', '.join(low)}. "
                    f"Рекомендация: оставить высокоценные, отписаться от низкоценных."
                    if ru else
                    f"Weekly insights: high-value — {', '.join(top)}; unsubscribe candidates — {', '.join(low)}. "
                    f"Recommendation: keep high-value, unsubscribe low-value."
                )
            else:
                weekly_report = (
                    "Еженедельный отчёт: недостаточно данных для оценки."
                    if ru else "Weekly report: insufficient data for evaluation."
                )

        return {
            "unsubscribe": unsubscribe,
            "keep": keep,
            "digest": digest,
            "weekly_report": weekly_report,
        }
