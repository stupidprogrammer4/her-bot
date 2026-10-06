from pydantic import BaseModel


class CommandResult(BaseModel):
    text: str
    private: bool = True
