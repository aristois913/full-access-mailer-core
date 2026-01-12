from __future__ import annotations

import sys
import json
import typing

from dataclasses import dataclass


CONFIG_DB_PATH: typing.Final[str] = f'./{sys.argv[0]}/config/db.json'


@dataclass(frozen=True, kw_only=True)
class User:
    uuid: int
    admin: bool
    template: str | bytes
    emails: dict[str, str]

class Users:

    @staticmethod
    def add_user(*, uuid: int, admin: bool = False) -> None:
        with open(CONFIG_DB_PATH) as data:
            users: typing.Any = json.load(data)

        users['users'].update(
            {
                str(uuid): {
                    'admin': admin,
                    'emails': {},
                    'template': '',
                }
            }
        )

        with open(CONFIG_DB_PATH, 'w') as data:
            json.dump(users, data, indent=4)

    @staticmethod
    def query_user(*, uuid: int) -> User | None:
        with open(CONFIG_DB_PATH) as data:
            users: typing.Any = json.load(data)

        return (
            User(
                uuid=str(uuid),
                admin=bool(int(users['users'][str(uuid)]['admin'])),
                emails=users['users'][str(uuid)]['emails'],
                template=users['users'][str(uuid)]['template']
            )
            if str(uuid) in users['users']
            else None
        )

    @staticmethod
    def modify_user(*, uuid: int, field: str, value: typing.Any) -> None:
        with open(CONFIG_DB_PATH) as data:
            users: typing.Any = json.load(data)

        users['users'][str(uuid)][field] = value

        with open(CONFIG_DB_PATH, 'w') as data:
            users: typing.Any = json.dump(users, data, indent=4)

    @staticmethod
    def del_user(*, uuid: int) -> None:
        with open(CONFIG_DB_PATH) as data:
            users: typing.Any = json.load(data)

        del users['users'][str(uuid)]

        with open(CONFIG_DB_PATH, 'w') as data:
            json.dump(users, data, indent=4)

    @staticmethod
    def is_whitelisted(*, uuid: int) -> bool:
        with open(CONFIG_DB_PATH, 'r+') as config:
            return str(uuid) in json.load(config)['users']

    @staticmethod
    def is_admin(*, uuid: int) -> bool:
        with open(CONFIG_DB_PATH) as cfg:
            users: dict[str, typing.Any] = json.load(cfg)

        return users['users'][str(uuid)]['admin'] if str(uuid) in users['users'] else False