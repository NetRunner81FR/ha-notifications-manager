"""Helpers de formatage email pour notifications_manager."""
from __future__ import annotations

from datetime import datetime
import re

_DATE_IN_TITLE_RE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
EMAIL_SIGNATURE_PRODUCT = "Notification Manager powered by NetRunner for Home Assistant"
EMAIL_UNSUBSCRIBE_NOTICE = (
    "Pour vous desinscrire de ces notifications, contactez l'administrateur "
    "de votre Home Assistant."
)


def format_email_title(title: str, now: datetime) -> str:
    """Ajoute la date du jour au titre email si le titre ne contient pas deja jj/mm."""
    safe_title = str(title or "")
    if _DATE_IN_TITLE_RE.search(safe_title):
        return safe_title
    return f"{safe_title} | {now.strftime('%d/%m/%Y')}"


def format_email_message(message: str, now: datetime) -> str:
    """Ajoute signature standardisee et mention de desinscription au corps email."""
    safe_message = str(message or "")
    emitted_at = now.strftime("%d/%m/%Y a %H:%M")
    footer = (
        "--------\n"
        f"{EMAIL_SIGNATURE_PRODUCT}\n"
        f"Emis le {emitted_at}\n\n"
        f"{EMAIL_UNSUBSCRIBE_NOTICE}"
    )
    return f"{safe_message.rstrip()}\n\n{footer}" if safe_message.strip() else footer
