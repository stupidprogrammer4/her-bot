import re
import unicodedata


class Addressing:
    def __init__(self, aliases: list[str], username: str):
        self.aliases = aliases
        self.username = username

    def normalize(self, text: str) -> str:
        normalized = (
            unicodedata.normalize("NFKC", text)
            .casefold()
            .translate(str.maketrans({"ي": "ی", "ك": "ک"}))
        )
        return re.sub(
            r"\s+",
            " ",
            "".join(c for c in normalized if unicodedata.category(c) != "Cf"),
        ).strip()

    def addressed(self, text: str, *, replying_to_bot: bool) -> bool:
        text = self.normalize(text)
        alias = any(
            re.match(
                r"^"
                + r"\s*".join(
                    re.escape(part) for part in self.normalize(a).split()
                )
                + r"(?:\s|[،,:!؟?.]|$)",
                text,
            )
            for a in self.aliases
        )
        mention = bool(
            self.username
            and re.search(
                r"(?<!\w)@" + re.escape(self.username.casefold()) + r"(?!\w)",
                text,
            )
        )
        return replying_to_bot or alias or mention
