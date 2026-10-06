from pydantic import BaseModel


class ActionChange(BaseModel):
    status: str
    result: str
