from pydantic import BaseModel, ConfigDict


class StructuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
