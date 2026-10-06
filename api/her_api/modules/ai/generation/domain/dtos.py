from pydantic import BaseModel


class ModelCallChange(BaseModel):
    status: str
    input_tokens: int = 0
    output_tokens: int = 0
    error_code: str | None = None
