from __future__ import annotations

import os
import sys
import json
import shlex
import typing
import validators

from collections import defaultdict
from telegram import Update, Message, ForceReply

from telegram.ext import (
    filters,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackContext
)

from core.user import User, Users
from core.mail import MailSender


with open('./mailer/config/config.json', 'r') as cfg:
    CONFIG: dict[str, str] = json.load(cfg)


class Messages:

    HELP_MENU_STR: typing.Final[
        str
    ] = '''
    <b>• Full-Access Mailer 🛠</b>

\t<code>/help</code>
• Displays this current menu.

\t<code>/template</code>
• Uploads a specified mail template.

\t<code>/emails</code>
• Lists the cached emails.

\t<code>/delmail</code>
• Removes a mail from the cache.

\t<code>/auth email password</code>
• Authenticates into an email.

• Supported mail clients: <code>aol</code>, <code>yahoo</code>, <code>gmail</code>

\t<code>/sendmail 'subject' from-name from-email reply-to-name reply-to target-email</code>
• Sends an email to the provided email address.
'''

    OPERATOR_MENU_STR: typing.Final[
        str
    ] = '''
    <b>• Full-Access Mailer 🛠</b>

\t<code>/operator</code>
• Displays this current menu.

\t<code>/adduser telegram-id admin</code>
• Adds a user to the bot.

\t<code>/listusers</code>
• Adds a user to the bot.

\t<code>/deluser telegram-id</code>
• Deletes a user from the bot.
'''

class Mailer:

    CONFIG_DB_PATH: typing.Final[str] = (
        f'./{sys.argv[0]}/config/db.json'
    )

    USER_DISPLAY_FORMAT: typing.Final[str] = (
        '<b>uuid: <code>{}</code> admin: <code>{}</code></b>\n'
    )
    EMAIL_DISPLAY_FORMAT: typing.Final[str] = (
        "<b>email: <code>{}</code> password: <code>{}</code></b>\n"
    )

    def __init__(self: Mailer, *, token: str, errors: bool) -> None:
        self.states: defaultdict = defaultdict(bool)
        self.application: ApplicationBuilder = ApplicationBuilder().token(token=token).build()

        self.application.add_handlers(
            [
                CommandHandler(
                    command=command.replace('_command', ''),
                    callback=getattr(self, command),
                )
                for command in dir(self)
                if command.endswith('_command')
            ]
        )

        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self._handle_io)
        )

        if errors:
            self.application.add_error_handler(self._raise_error)

        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    @staticmethod
    async def _raise_error(update: Update, /) -> Message:
        return await update.message.reply_html(
            text='<b>Forbidden.</b>',
            reply_markup=ForceReply(selective=True),
        )

    @staticmethod
    async def _handle_io_file(
        *, ident: str, filename: str, context: CallbackContext
    ) -> typing.Coroutine[typing.Any, typing.Any, str | None]:
        try:
            document: typing.Any = await context.bot.get_file(ident)
            await document.download_to_drive(f'./{filename}')

            with open(f'./{filename}', 'r') as f:
                content: str = f.read()

            os.remove(f'./{filename}')
            return content
        except FileNotFoundError:
            return None

    async def _handle_io(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message | None:
        if self.states[update.message.from_user.id]:
            if update.message.document:
                content: str | None = await self._handle_io_file(
                    ident=update.message.document.file_id,
                    filename=update.message.document.file_name,
                    context=context
                )

                if not content:
                    return await update.message.reply_html(
                        text='<b>File upload failed due to a backend error, please try again.</b>'
                    )

                with open(self.CONFIG_DB_PATH) as _presets:
                    presets: dict[str, str | dict[str, typing.Any]] = json.load(
                        _presets
                    )

                presets['users'][str(update.message.from_user.id)]['template'] = content

                with open(self.CONFIG_DB_PATH, 'w') as _presets:
                    json.dump(presets, _presets, indent=4)

                self.states[update.message.from_user.id] = False
            else:
                return await update.message.reply_html(
                    text='<b>Please ensure your file is a document, and not an image, video, etc.</b>'
                )
        else:
            return await update.message.reply_html(
                text='<b>Please run <code>/template</code> to upload a custom mail template.</b>'
            )

        return None

    # NOTE: User commands.

    async def auth_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        if len(context.args) != 2:
            return await update.message.reply_html(
                text="<b>Invalid number of arguments provided!</b>"
            )
        
        if not validators.email(context.args[0]):
            return await update.message.reply_html(
                text="<b>Invalid email provided!</b>"
            )

        try:
            mail: MailSender = MailSender(email=context.args[0], password=context.args[1])
        except Exception as exception:
            return await update.message.reply_html(text=f"<b>{exception}</b>")

        user: User = Users.query_user(uuid=update.message.from_user.id)

        slot: dict[str, str] = user.emails
        slot[context.args[0]] = context.args[1]

        Users.modify_user(uuid=update.message.from_user.id, field='emails', value=slot)
        return await update.message.reply_html(
            text=f"Successfully authenticated into <code>{context.args[0]}</code>"
        )

    async def sendmail_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)
        
        arguments: list[str] = shlex.split(" ".join(update.message.text.split(" ")[1:]))

        if len(arguments) < 6:
            return await update.message.reply_html(
                text="<b>Invalid number of arguments provided!</b>"
            )

        if not validators.email(arguments[4]) or not validators.email(arguments[5]):
            return await update.message.reply_html(
                text="<b>Invalid email provided, ensure all arguments that require emails contain valid emails!</b>"
            )

        user: User = Users.query_user(uuid=update.message.from_user.id)

        if arguments[5] not in user.emails:
            return await update.message.reply_html(
                text="<b>Email doesn't exist!</b>"
            )

        try:
            status: bool = MailSender(
                email=arguments[5], password=user.emails[arguments[5]]
            ).sendmail(args=arguments, html=user.template)
        except Exception as exception:
            return await update.message.reply_html(text=f"<b>{exception}</b>")

        return await update.message.reply_html(
            text=f'Mail sent to <code>{arguments[5]}</code>, status: <code>{status}</code>'
        )

    async def delmail_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)
        
        if len(context.args) != 1:
            return await update.message.reply_html(
                text="<b>Invalid number of arguments provided!</b>"
            )
        
        if not validators.email(context.args[0]):
            return await update.message.reply_html(
                text="<b>Invalid email provided!</b>"
            )
        
        user: User = Users.query_user(uuid=update.message.from_user.id)

        if context.args[0] not in user.emails:
            return await update.message.reply_html(
                text="<b>Email doesn't exist!</b>"
            )

        slot: dict[str, str] = user.emails
        del slot[context.args[0]]

        Users.modify_user(uuid=update.message.from_user.id, field='emails', value=slot)
        return await update.message.reply_html(
            text=f"<b>Successfully removed '{context.args[0]}' from the email cache!</b>"
        )

    async def emails_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)
        
        message: str = ''
        user: User = Users.query_user(uuid=update.message.from_user.id)

        for email in user.emails:
            message += self.EMAIL_DISPLAY_FORMAT.format(
                email,
                user.emails[email]
            )

        return (
            await update.message.reply_html(text=message)
            if message
            else await update.message.reply_html(
                text='<b>There are no emails in the cache!</b>'
            )
        )

    async def template_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        self.states[update.message.from_user.id] = True
        return await update.message.reply_html(
            text="<b>Upload your mail template!</b>"
        )

    async def start_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        return await update.message.reply_html(
            text='<b>If you\'re registered on the bot, run <code>/help</code> to get started.</b>'
        )

    async def help_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_whitelisted(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        return await update.message.reply_html(text=Messages.HELP_MENU_STR)

    # NOTE: Administrator commands.

    async def operator_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_admin(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        return await update.message.reply_html(text=Messages.OPERATOR_MENU_STR)

    async def adduser_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_admin(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        try:
            uuid: int = int(context.args[0])
        except ValueError:
            return await update.message.reply_html(text='<b>Invalid telegram ID passed!</b>')
        
        try:
            admin: bool = bool(int(context.args[1]))
        except ValueError:
            return await update.message.reply_html(text='<b>Invalid admin value passed!</b>')

        if Users.is_whitelisted(uuid=uuid):
            return await update.message.reply_html(text='<b>User already exists!</b>') 

        Users.add_user(uuid=uuid, admin=admin)
        return await update.message.reply_html(
            text=f'<b>Successfully added user ID <code>{uuid}</code> to the database!</b>'
        )

    async def listusers_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_admin(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        message: str = ''

        with open(self.CONFIG_DB_PATH) as _database:
            database: dict[str, dict[str, dict[str, str | bool | dict[str, str]]]] = json.load(
                _database
            )

        for uuid in database['users']:
            message += self.USER_DISPLAY_FORMAT.format(
                uuid,
                database['users'][uuid]['admin']
            )

        return (
            await update.message.reply_html(text=message)
            if message
            else await update.message.reply_html(
                text='<b>There are no users in the database!</b>'
            )
        )

    async def deluser_command(
        self: Mailer, update: Update, context: ContextTypes.DEFAULT_TYPE, /
    ) -> Message:
        if not Users.is_admin(uuid=update.message.from_user.id):
            return await self._raise_error(update)

        try:
            uuid: int = int(context.args[0])
        except ValueError:
            return await update.message.reply_html(text='<b>Invalid telegram ID passed!</b>')

        if not Users.is_whitelisted(uuid=uuid):
            return await update.message.reply_html(text='<b>User doesn\'t exist!</b>') 

        Users.del_user(uuid=uuid)
        return await update.message.reply_html(
            text=f'<b>Successfully removed user ID <code>{uuid}</code> from the database!</b>'
        )

if __name__ == '__main__':
    Mailer(**CONFIG)