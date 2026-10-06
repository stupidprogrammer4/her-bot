from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from her_contracts.media import Mood


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyArguments(ToolArguments):
    pass


class ReadChannelArguments(ToolArguments):
    limit: int = Field(default=10, ge=1, le=30)
    query: str | None = Field(default=None, max_length=100)


class ListTracksArguments(ToolArguments):
    mood: Mood | None = None
    limit: int = Field(default=10, ge=1, le=30)


class PublishTextArguments(ToolArguments):
    text: str = Field(min_length=1, max_length=700)
    destination: Literal["channel", "discussion_group"] = "channel"


class PublishTrackArguments(ToolArguments):
    track_id: int = Field(gt=0)
    caption: str | None = Field(default=None, max_length=500)


class GreetArguments(ToolArguments):
    text: str | None = Field(default=None, min_length=1, max_length=400)
    destination: Literal["channel", "discussion_group"] = "channel"


class TextRangeArguments(ToolArguments):
    minimum: int = Field(ge=0, le=10)
    maximum: int = Field(ge=0, le=10)


class EditArguments(ToolArguments):
    message_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=700)


class DeleteArguments(ToolArguments):
    message_id: int = Field(gt=0)


TOOL_TYPES: dict[str, type[ToolArguments]] = {
    "read_channel_posts": ReadChannelArguments,
    "list_tracks": ListTracksArguments,
    "get_status": EmptyArguments,
    "publish_text": PublishTextArguments,
    "publish_track": PublishTrackArguments,
    "greet_audience": GreetArguments,
    "pause_publishing": EmptyArguments,
    "resume_publishing": EmptyArguments,
    "set_text_post_range": TextRangeArguments,
    "edit_own_text_post": EditArguments,
    "request_delete_own_post": DeleteArguments,
}

READ_TOOLS = frozenset({"read_channel_posts", "list_tracks", "get_status"})
