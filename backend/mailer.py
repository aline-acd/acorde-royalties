"""Email helpers using Emergent-managed Resend proxy.

Only transactional: notifies editoras that a new relatório Acorde is available
in the portal. Never attaches sensitive data or asks for credentials.
"""
import os
import re
import ipaddress
import logging
import httpx
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

logger = logging.getLogger("acorde.email")

EMAIL_BASE_URL = "https://integrations.emergentagent.com"


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    return val


_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password", "cvv",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "seed phrase", "recovery phrase", "verify your card",
    "social security number", "confirm your bank details",
)
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None) -> str | None:
    key = _env("EMERGENT_EMAIL_KEY")
    from_name = _env("EMAIL_FROM_NAME", "Acorde Music Rights")
    if not key:
        raise RuntimeError("EMERGENT_EMAIL_KEY not configured")
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": from_name}
    reply = reply_to or _env("EMAIL_REPLY_TO")
    if reply:
        payload["contact_email"] = reply
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{EMAIL_BASE_URL}/api/v1/email/send",
            headers={"X-Email-Key": key},
            json=payload,
        )
    if resp.status_code >= 400:
        logger.error("Email send failed %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Email send failed: {resp.status_code}")
    try:
        return resp.json().get("id")
    except Exception:
        return None


def build_editora_email_html(editora_name: str, competencia: str, portal_url: str) -> str:
    name = escape(editora_name)
    comp = escape(competencia or "última competência")
    link = escape(portal_url)
    return (
        f'<table role="presentation" width="100%" style="background:#f8f8f8;padding:0;margin:0">'
        f'<tr><td align="center" style="padding:32px 16px">'
        f'<table role="presentation" width="560" cellspacing="0" cellpadding="0" '
        f'style="background:#ffffff;border:1px solid #e5e5e5">'
        f'<tr><td style="background:#050505;padding:20px 24px">'
        f'<div style="font-family:Arial,sans-serif;font-size:22px;font-weight:800;color:#FFD700;'
        f'letter-spacing:0.08em">ACORDE</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:11px;color:#ffffff;'
        f'letter-spacing:0.2em;text-transform:uppercase;margin-top:4px">'
        f'Administradora de Direitos Autorais</div>'
        f'</td></tr>'
        f'<tr><td style="padding:28px 24px;font-family:Arial,sans-serif;color:#111">'
        f'<p style="margin:0 0 16px;font-size:14px">Olá, <strong>{name}</strong>,</p>'
        f'<p style="margin:0 0 16px;font-size:14px;line-height:1.55">'
        f'Seu relatório Acorde da competência <strong>{comp}</strong> já está disponível '
        f'no portal da editora. Acesse para visualizar o detalhamento por obra, a taxa '
        f'administrativa aplicada e o valor líquido a repassar.</p>'
        f'<p style="margin:28px 0" align="left">'
        f'<a href="{link}" style="background:#FFD700;color:#050505;'
        f'font-family:Arial,sans-serif;font-weight:700;font-size:13px;letter-spacing:0.1em;'
        f'text-transform:uppercase;text-decoration:none;padding:12px 22px;display:inline-block">'
        f'Acessar portal</a></p>'
        f'<p style="margin:16px 0 0;font-size:12px;color:#666;line-height:1.5">'
        f'Caso tenha qualquer dúvida sobre valores, períodos ou obras listadas, '
        f'responda este e-mail que falamos com você.</p>'
        f'</td></tr>'
        f'<tr><td style="background:#050505;padding:14px 24px;'
        f'font-family:Arial,sans-serif;color:#888;font-size:11px">'
        f'Enviado por Acorde Music Rights. Nunca pedimos senha, código ou dados bancários por e-mail.'
        f'</td></tr>'
        f'</table></td></tr></table>'
    )


def build_autor_email_html(autor_name: str, editora_name: str, competencia: str, portal_url: str) -> str:
    name = escape(autor_name)
    editora = escape(editora_name or "sua editora")
    comp = escape(competencia or "última competência")
    link = escape(portal_url)
    return (
        f'<table role="presentation" width="100%" style="background:#f8f8f8;padding:0;margin:0">'
        f'<tr><td align="center" style="padding:32px 16px">'
        f'<table role="presentation" width="560" cellspacing="0" cellpadding="0" '
        f'style="background:#ffffff;border:1px solid #e5e5e5">'
        f'<tr><td style="background:#050505;padding:20px 24px">'
        f'<div style="font-family:Arial,sans-serif;font-size:22px;font-weight:800;color:#FFD700;'
        f'letter-spacing:0.08em">ACORDE</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:11px;color:#ffffff;'
        f'letter-spacing:0.2em;text-transform:uppercase;margin-top:4px">'
        f'Administradora de Direitos Autorais</div>'
        f'</td></tr>'
        f'<tr><td style="padding:28px 24px;font-family:Arial,sans-serif;color:#111">'
        f'<p style="margin:0 0 16px;font-size:14px">Olá, <strong>{name}</strong>,</p>'
        f'<p style="margin:0 0 16px;font-size:14px;line-height:1.55">'
        f'O relatório Acorde das suas obras, administradas via <strong>{editora}</strong> '
        f'na competência <strong>{comp}</strong>, está pronto. Entre em contato com a sua '
        f'editora ou com a equipe Acorde para receber o detalhamento.</p>'
        f'<p style="margin:28px 0" align="left">'
        f'<a href="{link}" style="background:#FFD700;color:#050505;'
        f'font-family:Arial,sans-serif;font-weight:700;font-size:13px;letter-spacing:0.1em;'
        f'text-transform:uppercase;text-decoration:none;padding:12px 22px;display:inline-block">'
        f'Falar com a Acorde</a></p>'
        f'</td></tr>'
        f'<tr><td style="background:#050505;padding:14px 24px;'
        f'font-family:Arial,sans-serif;color:#888;font-size:11px">'
        f'Enviado por Acorde Music Rights. Nunca pedimos senha, código ou dados bancários por e-mail.'
        f'</td></tr>'
        f'</table></td></tr></table>'
    )
