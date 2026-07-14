import os
import sys
import unittest
import base64
import io

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from skills.format_convert.main import handle_request


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

    def test_pdf_local_fallback_error(self):
        result = handle_request(
            action="run",
            input="# Report",
            from_fmt="MD",
            to_fmt="PDF"
        )
        self.assertTrue(result.startswith("Error: Conversion failed locally:"))
        self.assertIn("Local fallback for PDF is not supported", result)


if __name__ == "__main__":
    unittest.main()
