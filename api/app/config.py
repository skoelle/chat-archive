# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_token: str
    mysql_host: str
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str
    mysql_database: str
    # Display name of the archive owner, used by the XING parser to tell
    # "my" messages from the contact's (e.g. "Stefan Kölle"). When empty the
    # parser falls back to the most frequent sender of the export.
    own_name: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"


settings = Settings()
