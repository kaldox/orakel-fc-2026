# -*- coding: utf-8 -*-
"""HTTP-Security-Header fuer alle Antworten der App."""
from flask import request


def apply_security_headers(resp):
    """Sinnvolle Basis-Sicherheitsheader fuer alle Antworten. HSTS nur ueber
    HTTPS (erkannt am vom Reverse-Proxy gesetzten X-Forwarded-Proto)."""
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # Bewusst tolerante CSP: App nutzt Google Fonts und einige Inline-Styles/-Skripte.
    resp.headers.setdefault("Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'")
    if request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers.setdefault("Strict-Transport-Security",
                                "max-age=31536000; includeSubDomains")
    return resp
