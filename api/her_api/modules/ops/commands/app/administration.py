import json

from her_api.modules.conversations.actions.interfaces import IOwnerActions
from her_api.modules.ops.settings.interfaces import (
    ISettingsQueries,
    ISettingsService,
)
from her_contracts.commands import CommandResult
from her_contracts.policy import AccessPolicy, ModelPolicy, PersonaPolicy
from her_contracts.telegram import IncomingMessage


class AdministrationCommands:
    def __init__(
        self,
        actions: IOwnerActions,
        settings: ISettingsService,
        queries: ISettingsQueries,
    ):
        self.actions, self.settings, self.queries = actions, settings, queries

    async def handle(
        self, data: IncomingMessage, command: str, args: str
    ) -> CommandResult | None:
        if command in {"pause", "resume"}:
            name = (
                "pause_publishing"
                if command == "pause"
                else "resume_publishing"
            )
            await self.actions.execute(
                data.update_id,
                data.sender_id or 0,
                name,
                "{}",
                frozenset({name}),
            )
            return CommandResult(
                text="نشر خودکار متوقف شد. ارسال\u200cهایی که شروع "
                "شده\u200cاند ممکنه کامل بشن."
                if command == "pause"
                else "نشر خودکار ادامه پیدا می\u200cکنه؛ زمان\u200cها دو"
                "باره انتخاب نمی\u200cشن 🎀"
            )
        if command == "text_range":
            minimum, maximum = map(int, args.split())
            await self.actions.execute(
                data.update_id,
                data.sender_id or 0,
                "set_text_post_range",
                json.dumps({"minimum": minimum, "maximum": maximum}),
                frozenset({"set_text_post_range"}),
            )
            return CommandResult(text="بازهٔ متن برای برنامهٔ بعدی ثبت شد 🎀")
        if command in {"group_on", "group_off"}:
            current = await self.settings.get("access")
            if not isinstance(current.value, AccessPolicy):
                raise ValueError("Invalid access policy")
            if current.value.group_id is None:
                raise ValueError("Discussion group missing")
            await self.settings.write(
                "access",
                current.value.model_copy(
                    update={"group_enabled": command == "group_on"}
                ),
                current.revision,
            )
            return CommandResult(
                text="گفت‌وگوی اعضای گروه "
                + ("فعال" if command == "group_on" else "غیرفعال")
                + " شد 🎀"
            )
        if command in {"profile", "model"}:
            if data.chat_type != "private":
                return CommandResult(
                    text="تنظیمات شخصیت و مدل فقط تو خصوصی قابل تغییره."
                )
            key = "persona" if command == "profile" else "model"
            current = await self.settings.get(key)
            if not args:
                return CommandResult(
                    text=current.value.model_dump_json(indent=2)
                )
            value = (
                PersonaPolicy.model_validate_json(args)
                if key == "persona"
                else ModelPolicy.model_validate_json(args)
            )
            await self.settings.write(key, value, current.revision)
            return CommandResult(text="تنظیمات تو DB ذخیره شد 🎀")
        return None
