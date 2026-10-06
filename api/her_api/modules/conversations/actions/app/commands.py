import json
import secrets
from datetime import timedelta

from papilio.infra.db.transaction import transaction

from her_api.modules.content.channel.interfaces import IChannelQueries
from her_api.modules.conversations.actions.domain.dtos import ActionChange
from her_api.modules.conversations.actions.domain.models import (
    DeleteConfirmationModel,
    OwnerActionModel,
)
from her_api.modules.conversations.actions.domain.tools import (
    READ_TOOLS,
    TOOL_TYPES,
    DeleteArguments,
    EditArguments,
    GreetArguments,
    ListTracksArguments,
    PublishTextArguments,
    PublishTrackArguments,
    ReadChannelArguments,
    TextRangeArguments,
)
from her_api.modules.conversations.actions.infra.mysql import (
    DeleteConfirmationRepository,
    OwnerActionRepository,
)
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.ops.settings.interfaces import (
    ISettingsQueries,
    ISettingsService,
)
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
    IPublicationQueries,
)
from her_api.shared.clock import Clock
from her_contracts.policy import AccessPolicy, WindowPolicy
from her_contracts.publications import ManualPublication


class OwnerActions:
    def __init__(
        self,
        actions: OwnerActionRepository,
        confirmations: DeleteConfirmationRepository,
        settings: ISettingsService,
        queries: ISettingsQueries,
        publications: IPublicationCommands,
        publication_queries: IPublicationQueries,
        channel: IChannelQueries,
        tracks: ITrackService,
        clock: Clock,
    ):
        self.clock = clock
        (
            self.actions,
            self.confirmations,
            self.settings,
            self.queries,
            self.publications,
            self.publication_queries,
            self.channel,
            self.tracks,
        ) = (
            actions,
            confirmations,
            settings,
            queries,
            publications,
            publication_queries,
            channel,
            tracks,
        )

    async def execute(
        self,
        update_id: int,
        actor_id: int,
        name: str,
        arguments: str,
        allowed: frozenset[str],
    ) -> str:
        snapshot = await self.queries.snapshot()
        if (
            actor_id != snapshot.access.owner_id
            or name not in allowed
            or name not in TOOL_TYPES
        ):
            raise ValueError("Tool capability denied")
        args = TOOL_TYPES[name].model_validate_json(arguments)
        if isinstance(args, ReadChannelArguments):
            result = await self.channel.context(args.limit, args.query)
            return result.model_dump_json()
        if isinstance(args, ListTracksArguments):
            result = await self.tracks.page(1, args.limit, args.mood)
            return result.model_dump_json()
        if name == "get_status":
            jobs = await self.publication_queries.recent()
            return json.dumps(
                {
                    "access": snapshot.access.model_dump(),
                    "window": snapshot.window.model_dump(mode="json"),
                    "recent": [
                        {"id": j.id, "kind": j.kind, "status": j.status}
                        for j in jobs
                    ],
                },
                ensure_ascii=False,
            )
        if name in READ_TOOLS:
            raise ValueError("Tool arguments mismatch")
        async with transaction():
            existing = await self.actions.by_update(update_id)
            if existing is not None:
                return existing.result or '{"status":"already_reserved"}'
            claimed = await self.actions.reserve(
                OwnerActionModel(
                    update_id=update_id, owner_id=actor_id, capability=name
                )
            )
            if not claimed:
                return '{"status":"already_reserved"}'
            if isinstance(args, PublishTextArguments):
                job = await self.publications.reserve(
                    ManualPublication(
                        update_id=update_id,
                        actor_id=actor_id,
                        kind="text",
                        destination=args.destination,
                        text=args.text,
                    )
                )
                result = json.dumps(
                    {
                        "status": job.status,
                        "job_id": job.id,
                        "delivered": False,
                    }
                )
            elif isinstance(args, PublishTrackArguments):
                job = await self.publications.reserve(
                    ManualPublication(
                        update_id=update_id,
                        actor_id=actor_id,
                        kind="music",
                        track_id=args.track_id,
                        text=args.caption,
                    )
                )
                result = json.dumps(
                    {
                        "status": job.status,
                        "job_id": job.id,
                        "delivered": False,
                    }
                )
            elif isinstance(args, GreetArguments):
                job = await self.publications.reserve(
                    ManualPublication(
                        update_id=update_id,
                        actor_id=actor_id,
                        kind="greeting",
                        destination=args.destination,
                        text=args.text,
                    )
                )
                result = json.dumps(
                    {
                        "status": job.status,
                        "job_id": job.id,
                        "delivered": False,
                    }
                )
            elif name in {"pause_publishing", "resume_publishing"}:
                current = await self.settings.get("access")
                if not isinstance(current.value, AccessPolicy):
                    raise ValueError("Invalid access policy")
                await self.settings.write(
                    "access",
                    current.value.model_copy(
                        update={"paused": name == "pause_publishing"}
                    ),
                    current.revision,
                )
                result = json.dumps(
                    {
                        "status": "completed",
                        "paused": name == "pause_publishing",
                        "already_in_flight_may_finish": True,
                    }
                )
            elif isinstance(args, TextRangeArguments):
                current = await self.settings.get("window")
                if not isinstance(current.value, WindowPolicy):
                    raise ValueError("Invalid window policy")
                await self.settings.write(
                    "window",
                    WindowPolicy.model_validate(
                        current.value.model_dump()
                        | {"text_min": args.minimum, "text_max": args.maximum}
                    ),
                    current.revision,
                )
                result = '{"status":"completed","effective":"next_window"}'
            elif isinstance(args, EditArguments):
                await self.publication_queries.owned_post(args.message_id)
                job = await self.publications.reserve(
                    ManualPublication(
                        update_id=update_id,
                        actor_id=actor_id,
                        kind="edit",
                        target_message_id=args.message_id,
                        text=args.text,
                    )
                )
                result = json.dumps(
                    {
                        "status": job.status,
                        "job_id": job.id,
                        "delivered": False,
                    }
                )
            elif isinstance(args, DeleteArguments):
                await self.publication_queries.owned_post(args.message_id)
                token = secrets.token_urlsafe(18)
                await self.confirmations.create(
                    DeleteConfirmationModel(
                        token=token,
                        owner_id=actor_id,
                        channel_id=snapshot.access.channel_id,
                        message_id=args.message_id,
                        expires_at=self.clock.now() + timedelta(minutes=10),
                    )
                )
                result = json.dumps(
                    {
                        "status": "confirmation_required",
                        "message_id": args.message_id,
                        "command": "/delete_confirm " + token,
                    }
                )
            else:
                raise ValueError("Unsupported tool")
            await self.actions.finish(
                update_id, ActionChange(status="completed", result=result)
            )
        return result

    async def confirm_delete(
        self, update_id: int, actor_id: int, token: str
    ) -> str:
        snapshot = await self.queries.snapshot()
        if actor_id != snapshot.access.owner_id:
            raise ValueError("Owner required")
        async with transaction():
            existing = await self.actions.by_update(update_id)
            if existing:
                return existing.result
            row = await self.confirmations.by_token(token)
            if row is None or not await self.confirmations.claim(
                token, actor_id, snapshot.access.channel_id, self.clock.now()
            ):
                raise ValueError("Confirmation expired or denied")
            claimed = await self.actions.reserve(
                OwnerActionModel(
                    update_id=update_id,
                    owner_id=actor_id,
                    capability="delete_confirm",
                )
            )
            if not claimed:
                return '{"status":"already_reserved"}'
            job = await self.publications.reserve(
                ManualPublication(
                    update_id=update_id,
                    actor_id=actor_id,
                    kind="delete",
                    target_message_id=row.message_id,
                )
            )
            result = json.dumps(
                {"status": job.status, "job_id": job.id, "delivered": False}
            )
            await self.actions.finish(
                update_id, ActionChange(status="completed", result=result)
            )
        return result
