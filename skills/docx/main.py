import os
import logging
from docx import Document
from docx.shared import Inches

logger = logging.getLogger("DocxProSkill")

def handle_request(action, **kwargs):
    """
    Handle requests for advanced Word processing.
    """
    entities = kwargs.get("entities", {})
    file_path = entities.get("file_path") or entities.get("path") or kwargs.get("file_path")

    if action == "read":
        return read_docx(file_path)
    elif action == "create":
        title = entities.get("title") or kwargs.get("title", "Untitled Document")
        content = entities.get("content") or kwargs.get("content", "")
        output = entities.get("output") or kwargs.get("output", "new_doc.docx")
        return create_docx(title, content, output)
    elif action == "edit":
        old_text = entities.get("old_text") or kwargs.get("old_text")
        new_text = entities.get("new_text") or kwargs.get("new_text")
        output = entities.get("output") or kwargs.get("output", file_path)
        return edit_docx(file_path, old_text, new_text, output)
    elif action == "metadata":
        return get_metadata(file_path)
    elif action == "add_image":
        image_path = entities.get("image_path") or kwargs.get("image_path")
        output = entities.get("output") or kwargs.get("output", file_path)
        return add_image(file_path, image_path, output)

    return f"Error: Action '{action}' not supported."

def read_docx(file_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
    except Exception as e:
        return f"Error: {str(e)}"

def create_docx(title, content, output_path):
    try:
        doc = Document()
        doc.add_heading(title, 0)
        doc.add_paragraph(content)
        doc.save(output_path)
        return f"Successfully created {output_path}"
    except Exception as e:
        return f"Error: {str(e)}"

def edit_docx(file_path, old_text, new_text, output_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    if not old_text or new_text is None:
        return "Error: Missing search or replace text."
    try:
        doc = Document(file_path)
        for para in doc.paragraphs:
            if old_text in para.text:
                para.text = para.text.replace(old_text, new_text)
        doc.save(output_path)
        return f"Successfully edited and saved to {output_path}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_metadata(file_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: File not found."
    try:
        doc = Document(file_path)
        props = doc.core_properties
        metadata = {
            "author": props.author,
            "category": props.category,
            "comments": props.comments,
            "content_status": props.content_status,
            "created": str(props.created),
            "identifier": props.identifier,
            "keywords": props.keywords,
            "language": props.language,
            "last_modified_by": props.last_modified_by,
            "last_printed": str(props.last_printed),
            "modified": str(props.modified),
            "subject": props.subject,
            "title": props.title,
            "version": props.version
        }
        return str(metadata)
    except Exception as e:
        return f"Error: {str(e)}"

def add_image(file_path, image_path, output_path):
    if not file_path or not os.path.exists(file_path):
        return "Error: Document file not found."
    if not image_path or not os.path.exists(image_path):
        return "Error: Image file not found."
    try:
        doc = Document(file_path)
        doc.add_picture(image_path, width=Inches(4.0))
        doc.save(output_path)
        return f"Successfully added image and saved to {output_path}"
    except Exception as e:
        return f"Error: {str(e)}"
