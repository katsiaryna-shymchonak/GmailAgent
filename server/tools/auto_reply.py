from typing import Dict, Any, List
import json
import ast

from .base import BaseTool


class AutoReplyTool(BaseTool):
    name = "auto_reply"

    def __init__(self):
        schema = {
            "auto_replies": [{"id": "int", "template": "string"}]
        }
        super().__init__(schema=schema)

    # ---------- Внутренние утилиты ----------

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

        if any(k in subject for k in ["privacy", "terms"]) or any(k in subject for k in ["политика", "условия"]):
            return "policy_update"
        if any(k in subject for k in ["invite", "webinar", "event"]) or any(
            k in body for k in ["мастер-класс", "марафон"]
        ):
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
        ru = lang.lower().startswith("rus") or "ru" in lang.lower()
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

    def _repair_json(self, raw: Any) -> Dict[str, Any]:
        """
        Универсальный JSON‑repair:
        - если модель вернула уже dict — вернём как есть;
        - если строка — вырежем JSON‑объект, попробуем json.loads, потом ast.literal_eval;
        - иначе вернём пустой словарь.
        """
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}

        text = raw.strip()
        if not text:
            return {}

        # Вырезаем по первой и последней фигурной скобке — защита от markdown/лишнего текста
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            text = text[start:end]
        except Exception:
            # если не нашли фигурные скобки — оставляем как есть
            pass

        # 1) Пытаемся json.loads
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2) Пытаемся literal_eval для Python-словарей "{'a': 1}"
        try:
            val = ast.literal_eval(text)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        return {}

    def _extract_template_from_nested(self, tmpl: str) -> str:
        """
        Если модель вернула строку вида:
        "{'id': 1, 'template': '...'}"
        — пытаемся распарсить и вытащить поле template.
        """
        text = (tmpl or "").strip()
        if not (text.startswith("{") and text.endswith("}")):
            return text

        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict) and "template" in parsed:
                inner = parsed["template"]
                return (inner or "").strip()
        except Exception:
            pass

        return text

    # ---------- Основной метод ----------

    async def run(
        self,
        messages: List[Dict[str, Any]],
        filter_data: Dict[str, Any],
        user_language: str = "English"
    ) -> Dict[str, Any]:
        """
        Генерация автоответов:
        - жёсткий промпт на JSON;
        - repair + нормализация;
        - fallback‑шаблоны для пустых/слишком общих ответов.
        """

        prompt = (
            "You are an AI agent that generates contextual auto-reply templates for emails.\n\n"
            "Your ONLY task:\n"
            "Return a STRICTLY VALID JSON object with the following structure:\n\n"
            "{\n"
            '  "auto_replies": [\n'
            "    {\n"
            '      "id": <integer>,\n'
            '      "template": "<string>"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "CRITICAL RULES:\n"
            "- Output MUST be valid JSON. No comments, no trailing commas, no Python syntax.\n"
            '- \"template\" MUST be a plain string. Do NOT embed JSON, Python dicts, or objects inside it.\n'
            '- Do NOT wrap objects inside strings (e.g. no \"{\'id\': 1, \'template\': \'...\' }\").\n'
            "- Do NOT include braces { } inside \"template\" unless they are literal text.\n"
            "- Each email with an integer-like id produces exactly ONE object {id, template}.\n"
            "- The \"id\" MUST match the email id.\n"
            "- Templates must be short (1–2 sentences), polite, contextual, and professional.\n"
            "- Avoid generic 'thank you' replies unless clearly appropriate.\n"
            "- If the email is unclear: ask for key points and required actions.\n"
            "- If promotion/discount: ask for summary, validity period, and key conditions.\n"
            "- If event invite/webinar: ask for agenda, timing, and recording availability.\n"
            "- If policy update: confirm whether any action is required.\n"
            "- If technical/tooling/docs: ask for a quick-start guide or key benefits.\n"
            "- If task/deadline: confirm, and request deadline and acceptance criteria.\n"
            "- If newsletter/digest: ask for key points or preference options.\n\n"
            f"Language for templates: {user_language}\n\n"
            "Emails (JSON):\n"
            f"{json.dumps(messages, ensure_ascii=False, indent=2)}\n\n"
            "Filter data (JSON):\n"
            f"{json.dumps(filter_data, ensure_ascii=False, indent=2)}\n\n"
            "Remember: STRICT JSON ONLY. NO explanations. NO markdown. NO text outside the JSON object."
        )

        raw_result = await self.call(
            prompt,
            variables={"messages": messages, "filter_data": filter_data},
            user_language=user_language,
        )

        result = self._repair_json(raw_result)

        auto_replies = result.get("auto_replies")
        if not isinstance(auto_replies, list):
            auto_replies = []

        normalized: List[Dict[str, Any]] = []

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

            # если template — вложенный dict в строке → распакуем
            tmpl = self._extract_template_from_nested(tmpl)

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
