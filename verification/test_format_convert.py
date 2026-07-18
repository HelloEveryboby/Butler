import os
import sys
import unittest
import base64
import io
import tempfile
import zipfile

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from skills.format_convert.format_convert import handle_request
from skills.format_convert.core.reverse_converters import html_to_markdown, docx_to_markdown, pdf_to_markdown


class TestFormatConvertSkillLocal(unittest.TestCase):

    def test_markdown_to_html_local(self):
        md_text = """# Main Header
* List item 1
* List item 2

This is **important** text."""

        result = handle_request(
            action="run",
            input=md_text,
            from_fmt="MD",
            to_fmt="HTML",
            options={"theme": "apple-light", "with_water": True}
        )

        self.assertIn('data-theme="apple-light"', result)
        self.assertIn('<h1>Main Header</h1>', result)
        self.assertIn('<li>List item 1</li>', result)
        self.assertIn('<strong>important</strong>', result)
        self.assertIn('Secure Watermarked Document', result)

    def test_json_to_csv_local(self):
        json_data = """[
            {"id": 10, "meta": {"owner": "Jules", "active": true}},
            {"id": 20, "meta": {"owner": "Butler", "active": false}}
        ]"""

        result = handle_request(
            action="run",
            input=json_data,
            from_fmt="JSON",
            to_fmt="CSV"
        )

        lines = result.strip().split('\r\n' if '\r\n' in result else '\n')
        self.assertEqual(len(lines), 3)

        # Keys should be flattened and sorted: id, meta.active, meta.owner
        self.assertEqual(lines[0], "id,meta.active,meta.owner")
        self.assertEqual(lines[1], "10,true,Jules")
        self.assertEqual(lines[2], "20,false,Butler")

    def test_yaml_to_csv_local(self):
        yaml_data = """
- name: service_1
  ports:
    - 80
    - 443
- name: service_2
  ports:
    - 8080
"""

        result = handle_request(
            action="run",
            input=yaml_data,
            from_fmt="YAML",
            to_fmt="CSV"
        )

        lines = result.strip().split('\r\n' if '\r\n' in result else '\n')
        self.assertEqual(len(lines), 3)

        # Keys should be sorted: name, ports.0, ports.1
        self.assertEqual(lines[0], "name,ports.0,ports.1")
        self.assertEqual(lines[1], "service_1,80,443")
        self.assertEqual(lines[2], "service_2,8080,")

    def test_json_to_xlsx_local_fallback(self):
        json_data = """[
            {"id": 10, "name": "Auth Service"}
        ]"""

        result = handle_request(
            action="run",
            input=json_data,
            from_fmt="JSON",
            to_fmt="XLSX"
        )

        # Should be a BOM-marked CSV
        self.assertTrue(result.startswith("\ufeff"))
        csv_part = result[1:]
        lines = csv_part.strip().splitlines()
        self.assertEqual(lines[0], "id,name")
        self.assertEqual(lines[1], "10,Auth Service")

    def test_json_to_md_table_local(self):
        json_data = r"""[
            {"Service": "Web", "Status": "Up|Active", "Details": "Online\nReady"}
        ]"""

        result = handle_request(
            action="run",
            input=json_data,
            from_fmt="JSON",
            to_fmt="MD"
        )

        self.assertIn("| Details | Service | Status |", result)
        self.assertIn("Up\\|Active", result)
        self.assertIn("Online<br />Ready", result)

    def test_csv_to_md_table_local(self):
        csv_data = "Name,Role,Status\nJules,Admin,Active|Online"

        result = handle_request(
            action="run",
            input=csv_data,
            from_fmt="CSV",
            to_fmt="MD"
        )

        self.assertIn("| Name | Role | Status |", result)
        self.assertIn("Active\\|Online", result)

    def test_image_to_base64_local(self):
        # Create a tiny 1-pixel red GIF encoded in Base64 as dummy input
        # GIF89a..
        dummy_gif_b64 = "R0lGODlhAQABAIABAP///wAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="

        result = handle_request(
            action="run",
            input=dummy_gif_b64,
            from_fmt="PNG",
            to_fmt="BASE64",
            options={"config": {"WithDataUri": True}}
        )

        self.assertTrue(result.startswith("data:image/png;base64,"))
        decoded_b64 = result.split(",", 1)[1]
        self.assertEqual(decoded_b64, dummy_gif_b64)

    def test_image_to_webp_local(self):
        # Create a tiny mock image in memory using PIL if possible, otherwise skip or verify output
        try:
            from PIL import Image
            # Create a 2x2 red image
            img = Image.new('RGB', (2, 2), color='red')
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            result = handle_request(
                action="run",
                input=img_b64,
                from_fmt="PNG",
                to_fmt="WEBP"
            )

            # WebP bytes returned in base64 encoding from main.py if no save_to is provided
            decoded_res = base64.b64decode(result)
            self.assertEqual(decoded_res[8:12], b"WEBP")
        except ImportError:
            self.skipTest("Pillow not installed, skipping test_image_to_webp_local")

    def test_markdown_to_docx_and_reverse(self):
        md_text = """# Project Title
## Subheading
This is a paragraph with **bold** text and *italic* text.

- List item 1
- List item 2
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.docx")
            res = handle_request(
                action="run",
                input=md_text,
                from_fmt="MD",
                to_fmt="DOCX",
                save_to=save_path
            )
            self.assertTrue(os.path.exists(save_path))

            # Reverse convert DOCX -> MD
            rev_md = handle_request(
                action="run",
                input=save_path,
                from_fmt="DOCX",
                to_fmt="MD"
            )
            self.assertIn("Project Title", rev_md)
            self.assertIn("Subheading", rev_md)
            self.assertIn("List item 1", rev_md)

    def test_markdown_to_epub_and_reverse(self):
        md_text = """# E-book Title
By Butler

Welcome to the digital world.
- Chapter One
- Chapter Two
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.epub")
            res = handle_request(
                action="run",
                input=md_text,
                from_fmt="MD",
                to_fmt="EPUB",
                save_to=save_path
            )
            self.assertTrue(os.path.exists(save_path))

            # Ensure zipfile signature of standard epub
            self.assertTrue(zipfile.is_zipfile(save_path))
            with zipfile.ZipFile(save_path, 'r') as zf:
                files = zf.namelist()
                self.assertIn("mimetype", files)
                self.assertIn("OEBPS/content.opf", files)
                self.assertIn("OEBPS/chapter1.xhtml", files)

    def test_markdown_to_image_drawing(self):
        md_text = """# Drawing Title
This is some drawing text to fit standard wrapping.
- Draw line 1
- Draw line 2
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.png")
            res = handle_request(
                action="run",
                input=md_text,
                from_fmt="MD",
                to_fmt="PNG",
                save_to=save_path
            )
            self.assertTrue(os.path.exists(save_path))

            # Read image and verify bytes size > 0
            self.assertTrue(os.path.getsize(save_path) > 100)

    def test_html_to_markdown_reverse(self):
        html_text = """<h1>Web Title</h1>
<p>Hello this is <strong>strong</strong> text and <em>em</em> text.</p>
<ul>
  <li>Bullet item A</li>
  <li>Bullet item B</li>
</ul>"""
        md = html_to_markdown(html_text)
        self.assertIn("Web Title", md)
        self.assertIn("**strong**", md)
        self.assertIn("*em*", md)
        # Bullet list is also matched as standard bullet character
        self.assertTrue(any(x in md for x in ["- Bullet item A", "* Bullet item A"]))

    def test_cross_conversion_html_to_docx(self):
        html_text = """<h1>Cross Conversion Header</h1>
<p>This is a paragraph.</p>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "cross.docx")
            res = handle_request(
                action="run",
                input=html_text,
                from_fmt="HTML",
                to_fmt="DOCX",
                save_to=save_path
            )
            self.assertTrue(os.path.exists(save_path))

            # Reverse docx to md
            md = docx_to_markdown(save_path)
            self.assertIn("Cross Conversion Header", md)


if __name__ == "__main__":
    unittest.main()
