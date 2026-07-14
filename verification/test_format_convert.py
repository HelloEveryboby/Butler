import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
