from typing import Iterable, Dict
from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    """Convert HTML to plain text with line breaks."""
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator="\n")


def format_messages(messages: Iterable[Dict]) -> str:
    """
    Format a list of email messages into a plain text block.
    Escapes curly braces so PromptTemplate doesn't treat them as variables.
    """
    result = []
    for m in messages:
        body = m.get("body") or m.get("content") or m.get("snippet") or ""
        body = html_to_text(body)

        safe_body = body.replace("{", "{{").replace("}", "}}")

        result.append(
            (
                "ID: {id}\n"
                "From: {from_}\n"
                "Subject: {subject}\n"
                "Snippet: {snippet}\n"
                "Body:\n{body}"
            ).format(
                id=m.get("id", ""),
                from_=m.get("from") or m.get("sender_email", ""),
                subject=m.get("subject", ""),
                snippet=m.get("snippet", ""),
                body=safe_body,
            )
        )

    return "\n---\n".join(result) if result else "No emails."
