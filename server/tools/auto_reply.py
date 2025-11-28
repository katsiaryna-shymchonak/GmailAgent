from typing import Dict, Any, List
from .base import BaseTool

class AutoReplyTool(BaseTool):
    name = "auto_reply"

    def __init__(self):
        schema = {
            "auto_replies": [{"id": "int", "template": "string"}]
        }
        super().__init__(schema=schema)

    def _is_generic_thanks(self, text: str) -> bool:
        """Определяем слишком общий ответ типа 'спасибо'."""
        t = (text or "").lower()
        return any(kw in t for kw in ["thank you", "thanks", "спасибо", "благодарю"]) and len(t) < 120

    def _classify_email(self, email: Dict[str, Any]) -> str:
        """Классифицируем письмо по subject/tags/recommended_action."""
        subject = (email.get("subject") or "").lower()
        body = (email.get("body") or "").lower()
        tags = " ".join(email.get("tags", [])).lower()
        action = (email.get("recommended_action") or "").lower()

        if "privacy" in subject or "terms" in subject or "политика" in subject or "условия" in subject:
            return "policy_update"
        if "invite" in subject or "webinar" in subject or "event" in subject or "мастер-класс" in body or "марафон" in body:
            return "event_invite"
        if "discount" in subject or "black friday" in subject or "скидк" in body or "акция" in tags:
            return "promotion"
        if "tool" in subject or "seo" in tags or "graphite" in subject or "инструмент" in body:
            return "tooling"
        if action in {"reply", "save"} or "deadline" in body or "задача" in body:
            return "task"
        if "newsletter" in tags or "digest" in subject or "дайджест" in subject:
            return "newsletter"
        return "generic"

    def _fallback_template(self, kind: str, lang: str) -> str:
        """Контекстные fallback‑шаблоны."""
        ru = lang.lower().startswith("rus")
        if kind == "promotion":
            return "Получил предложение. Пришлите краткое резюме условий и срок действия акции." if ru \
                else "Received the offer. Please share a brief summary of terms and validity."
        if kind == "event_invite":
            return "Спасибо за приглашение. Пришлите программу и время проведения." if ru \
                else "Thanks for the invite. Please share the agenda and timing."
        if kind == "policy_update":
            return "Получил обновление. Верно ли, что действий не требуется?" if ru \
                else "Received the update. Can you confirm no action is required?"
        if kind == "tooling":
            return "Спасибо за материал. Пришлите краткий гайд по началу работы." if ru \
                else "Thanks for the resource. Please share a quick-start guide."
        if kind == "task":
            return "Принято. Уточните дедлайн и критерии готовности." if ru \
                else "Noted. Please specify the deadline and acceptance criteria."
        if kind == "newsletter":
            return "Получил дайджест. Можно краткие ключевые пункты за неделю?" if ru \
                else "Digest received. Could you send brief key points for the week?"
        return "Получил сообщение. Пришлите ключевые моменты и требуемые действия." if ru \
            else "Received your message. Please share key points and required actions."

    async def run(
        self,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        user_language: str = "English"
    ) -> Dict[str, Any]:
        prompt = (
            f"You are an agent for auto-reply generation.\n"
            f"Task: Create polite, concise, CONTEXTUAL auto-reply templates for the provided emails.\n\n"
            f"Output strictly valid JSON matching the schema.\n"
            f"Language: {user_language}\n\n"
            f"Rules:\n"
            f"- For EACH email with an integer-like id, produce ONE object {{id, template}}.\n"
            f"- Place ALL objects inside the 'auto_replies' array.\n"
            f"- Do NOT merge multiple replies into one text block.\n"
            f"- Templates must be short (1–2 sentences), professional, and relevant.\n"
            f"- Avoid generic 'thank you' replies; tailor to the email type.\n"
            f"- If promotion/discount: ask for summary/validity/pricing.\n"
            f"- If event invite/webinar: ask for agenda/timing/recording.\n"
            f"- If policy update: confirm if action is required.\n"
            f"- If technical tool/docs: ask for quick-start guide or key benefits.\n"
            f"- If task/deadline: confirm and request deadline/criteria.\n"
            f"- If newsletter/digest: ask for key points or preference center.\n"
            f"- If unclear: request a brief summary and required actions.\n\n"
            f"Emails:\n{messages}\n\n"
            f"Filter data:\n{filter_data}"
        )

        result = await self.call(
            prompt,
            variables={"messages": messages, "filter_data": filter_data},
            user_language=user_language
        )

        # --- Защитная нормализация ---
        if not isinstance(result, dict):
            result = {}
        auto_replies = result.get("auto_replies")
        if not isinstance(auto_replies, list):
            auto_replies = []

        normalized = []
        for idx, item in enumerate(auto_replies):
            if isinstance(item, dict):
                try:
                    _id = int(item.get("id", idx + 1))
                except Exception:
                    _id = idx + 1
                tmpl = (item.get("template") or "").strip()
            else:
                _id = idx + 1
                tmpl = str(item).strip()

            # если шаблон пустой или слишком общий — заменим на контекстный
            if not tmpl or self._is_generic_thanks(tmpl):
                # ищем письмо по id
                email = None
                for m in messages:
                    try:
                        mid = int(m.get("id", -1))
                        if mid == _id:
                            email = m
                            break
                    except Exception:
                        continue
                kind = self._classify_email(email or {})
                tmpl = self._fallback_template(kind, user_language)

            normalized.append({"id": _id, "template": tmpl})

        if not normalized:
            normalized = [{
                "id": 0,
                "template": self._fallback_template("generic", user_language)
            }]

        return {"auto_replies": normalized}
