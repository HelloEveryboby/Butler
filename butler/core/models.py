from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime

class PluginTask(BaseModel):
    """Input model for plugin execution."""
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)

class PluginResponse(BaseModel):
    """Output model for plugin execution."""
    success: bool = True
    result: Any = None
    error_message: Optional[str] = None
    need_call_brain: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

    @classmethod
    def success_response(cls, result: Any, **kwargs):
        return cls(success=True, result=result, **kwargs)

    @classmethod
    def error_response(cls, error_message: str, **kwargs):
        return cls(success=False, error_message=error_message, **kwargs)
