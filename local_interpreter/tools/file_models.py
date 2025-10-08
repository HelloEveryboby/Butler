from pydantic import BaseModel, Field
from typing import List, Literal

class File(BaseModel):
    """
    A model representing a file to be created or modified.
    """
    file_path: str = Field(..., description="The full path to the file, including the extension.")
    content: str = Field(..., description="The content to be written to the file.")

class FileModification(BaseModel):
    """
    A model for modifying an existing file by applying a patch.
    """
    file_path: str = Field(..., description="The path to the file that needs to be modified.")
    action: Literal["create", "delete", "modify"] = Field(..., description="The action to perform on the file.")
    description: str = Field(..., description="A description of the changes to be made.")

class FilePatch(BaseModel):
    """
    Represents a set of changes to be applied to a single file.
    """
    file_path: str
    modifications: List[FileModification]