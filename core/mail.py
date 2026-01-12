from __future__ import annotations

import validators

from typing import final
from abc import ABC, abstractmethod

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from imapclient import IMAPClient

class Sender(ABC):

    @final
    @staticmethod
    def template(
        subject: str,
        from_name: str,
        from_email: str,
        reply_to_name: str,
        reply_to_email: str,
        to_email: str,
        html: str,
        /
    ) -> MIMEMultipart:
        template: MIMEMultipart = MIMEMultipart()

        template['Subject'] = subject
        template['From'] = f'{from_name} <{from_email}>'
        template['Reply-To'] = f'{reply_to_name} <{reply_to_email}>'
        template['To'] = to_email

        template.attach(MIMEText(html, 'html'))
        return template

    @abstractmethod
    def sendmail(
        self: Sender,
        html: str,
        subject: str,
        from_name: str,
        from_email: str,
        reply_to_name: str,
        reply_to_email: str,
        to_email: str,
        /
    ) -> bool: ...


class Gmail(Sender):

    def __init__(self: Gmail, *, client: IMAPClient) -> None:
        self.client: IMAPClient = client

    def sendmail(
        self: Gmail,
        html: str,
        subject: str,
        from_name: str,
        from_email: str,
        reply_to_name: str,
        reply_to_email: str,
        to_email: str,
        /
    ) -> bool:
        self.client.select_folder(folder='INBOX')
        self.client.append(
            folder='INBOX',
            msg=self.template(
                subject,
                from_name,
                from_email,
                reply_to_name,
                reply_to_email,
                to_email,
                html
            ).as_bytes(),
            flags=[b'\\Flagged']
        )
        return True

class YahooAOL(Sender):

    def __init__(self: YahooAOL, *, client: IMAPClient) -> None:
        self.client: IMAPClient = client

    def sendmail(
        self: YahooAOL,
        html: str,
        subject: str,
        from_name: str,
        from_email: str,
        reply_to_name: str,
        reply_to_email: str,
        to_email: str,
        /
    ) -> bool:
        template: bytes = self.template(
            subject,
            from_name,
            from_email,
            reply_to_name,
            reply_to_email,
            to_email,
            html
        ).as_bytes()

        self.client.select_folder(folder='INBOX')
        self.client.append(folder='INBOX', msg=template, flags=[b'\\Flagged'])
        return True

class MailSender:

    SENDERS: dict[str, str | tuple[str, Sender]] = {
        'gmail.com': ('imap.gmail.com', Gmail),
        'aol.com':  ('imap.aol.com', YahooAOL),
        'yahoo.com': ('imap.mail.yahoo.com', YahooAOL)
    }

    def __init__(self: MailSender, *, email: str, password: str) -> None:
        self.email: str = email
        self.password: str = password
        
        try:
            if not validators.email(self.email):
                raise ValueError

            self.sender: tuple[str, Sender] = self.SENDERS.get(self.email.split('@')[1])

            if not self.sender:
                raise ValueError
        except (KeyError, ValueError):
            raise ValueError('Invalid email provided!')

        try:
            self.client: IMAPClient = IMAPClient(host=self.sender[0], use_uid=True)
            self.client.login(username=self.email, password=self.password)
        except Exception:
            raise RuntimeError('Failed to authenticate into email!')

    def sendmail(self: MailSender, *, args: list[str], html: str) -> bool:
        return self.sender[1](client=self.client).sendmail(html, *args)