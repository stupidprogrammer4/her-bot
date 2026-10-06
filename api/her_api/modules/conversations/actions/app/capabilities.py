import re
from typing import Any

from her_api.modules.conversations.actions.domain.tools import (
    READ_TOOLS,
    TOOL_TYPES,
)
from her_api.modules.persona.privacy.app.guard import normalize


class OwnerCapabilities:
    def uses_tools(self, text: str, allowed: frozenset[str]) -> bool:
        return bool(allowed - READ_TOOLS) or bool(
            re.search(
                r"وضعیت|لیست آهنگ|پستهای کانال|پست های کانال|"
                r"خبر از کانال|کانال[و ]*بخون",
                normalize(text),
            )
        )

    def allowed(self, text: str) -> frozenset[str]:
        text = normalize(text)
        text = re.sub(r'«[^»]*»|"[^"]*"|```[\s\S]*?```', "", text)
        if re.search(
            r"نفرست|منتشر نکن|فقط.*(بنویس|پیشنویس)|/draft|"
            r"ترجمه کن|نقل قول|توضیح بده|متن زیر|یعنی چی|معنی.*چی",
            text,
        ):
            return READ_TOOLS
        write = None
        if re.search(r"(سلام کن|معرفی کن|معرفی شو)", text):
            write = "greet_audience"
        elif re.search(r"(توقف|متوقف کن|/pause)", text):
            write = "pause_publishing"
        elif re.search(r"(ادامه بده|از سر بگیر|/resume)", text):
            write = "resume_publishing"
        elif re.search(r"(تعداد متن|بازه متن|/text_range)", text):
            write = "set_text_post_range"
        elif re.search(r"(ویرایش کن|اصلاح پست)", text):
            write = "edit_own_text_post"
        elif re.search(r"(حذف کن|پاک کن)", text):
            write = "request_delete_own_post"
        elif re.search(r"(پخش کن|آهنگ.*(بفرست|بذار))", text):
            write = "publish_track"
        elif re.search(r"(منتشر کن|بفرست|تو کانال.*بذار)", text):
            write = "publish_text"
        return READ_TOOLS | ({write} if write else set())

    def schemas(self, allowed: frozenset[str]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": name.replace("_", " ")
                    + ". Program authenticates the owner and fi"
                    "xes destinations. A queued job is not a "
                    "successful send.",
                    "parameters": TOOL_TYPES[name].model_json_schema(),
                },
            }
            for name in sorted(allowed)
        ]
