"""메일 발송 (Gmail SMTP + 앱 비밀번호 기본).

환경변수
    SMTP_USER          보내는 계정 (예: someone@gmail.com)
    SMTP_APP_PASSWORD  앱 비밀번호 (Gmail: 2단계 인증 후 발급)
    MAIL_TO            받는 주소, 여러 명이면 쉼표로 구분 (없으면 SMTP_USER)
    SMTP_HOST          기본 smtp.gmail.com
    SMTP_PORT          기본 465 (SSL). 587 이면 STARTTLS
"""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

XLSX_MIME = ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@dataclass
class MailConfig:
    user: str
    password: str
    to: list[str]
    host: str = "smtp.gmail.com"
    port: int = 465

    @classmethod
    def from_env(cls) -> "MailConfig":
        user = os.environ.get("SMTP_USER", "").strip()
        password = os.environ.get("SMTP_APP_PASSWORD", "").replace(" ", "")
        if not user or not password:
            raise RuntimeError("메일 설정이 없습니다: SMTP_USER, SMTP_APP_PASSWORD 환경변수(GitHub Secrets)를 등록하세요.")
        to = [a.strip() for a in os.environ.get("MAIL_TO", user).split(",") if a.strip()]
        return cls(
            user=user,
            password=password,
            to=to,
            host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
            port=int(os.environ.get("SMTP_PORT", "465")),
        )


def build_message(cfg: MailConfig, subject: str, html: str, text: str, attachment: Path | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.user
    msg["To"] = ", ".join(cfg.to)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if attachment is not None:
        msg.add_attachment(
            attachment.read_bytes(), maintype=XLSX_MIME[0], subtype=XLSX_MIME[1], filename=attachment.name
        )
    return msg


def send(cfg: MailConfig, msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    if cfg.port == 465:
        with smtplib.SMTP_SSL(cfg.host, cfg.port, context=context, timeout=60) as smtp:
            smtp.login(cfg.user, cfg.password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=60) as smtp:
            smtp.starttls(context=context)
            smtp.login(cfg.user, cfg.password)
            smtp.send_message(msg)
