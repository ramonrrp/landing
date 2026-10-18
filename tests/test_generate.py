from copy import deepcopy
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
from io import StringIO

import yaml

from scripts.generate import ROOT, ProfileError, generate, main, validate_profile


class PageParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.profile = yaml.safe_load((ROOT / "profile.yaml").read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "profile.yaml"
        self.output = self.directory / "index.html"

    def render(self, profile=None):
        data = self.profile if profile is None else profile
        self.source.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        generate(self.source, ROOT / "templates" / "index.html", self.output)
        return self.output.read_text(encoding="utf-8")

    def test_profile_and_generated_page(self):
        self.assertIs(validate_profile(self.profile), self.profile)
        html = self.render()
        page = PageParser(html)
        self.assertIn(("html", {"lang": "pt-BR"}), page.elements)
        self.assertEqual(sum(tag == "h1" for tag, _ in page.elements), 1)
        self.assertEqual(sum(tag == "section" for tag, _ in page.elements), 6)
        self.assertFalse(any(tag == "script" for tag, _ in page.elements))
        self.assertIn(str(datetime.now().year), html)
        self.assertIn(self.profile["presentation"]["summary"], html)
        self.assertIn(self.profile["personal"]["contacts"]["email"]["value"], html)
        ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for _, attrs in page.elements:
            if attrs.get("href", "").startswith("#"):
                self.assertIn(attrs["href"][1:], ids)
            if "aria-labelledby" in attrs:
                self.assertIn(attrs["aria-labelledby"], ids)

    def test_links_metadata_and_relative_stylesheet(self):
        page = PageParser(self.render())
        hrefs = [attrs["href"] for _, attrs in page.elements if "href" in attrs]
        contacts = self.profile["personal"]["contacts"]
        for key, link in contacts.items():
            self.assertIn(("mailto:" if key == "email" else "") + link["value"], hrefs)
        self.assertIn(("link", {"rel": "stylesheet", "href": "style.css"}), page.elements)
        self.assertTrue((ROOT / "style.css").is_file())
        self.assertIn(("link", {"rel": "canonical", "href": contacts["website"]["value"]}), page.elements)
        for key in ("title", "description"):
            self.assertIn(("meta", {"property": f"og:{key}", "content": self.profile["site"][key]}), page.elements)
        self.assertIn(("meta", {"property": "og:url", "content": contacts["website"]["value"]}), page.elements)
        self.assertIn(("meta", {"name": "description", "content": self.profile["site"]["description"]}), page.elements)
        self.assertIn(("meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}), page.elements)

    def test_html_and_attribute_values_are_escaped(self):
        self.profile["personal"]["name"] = '<script>alert("x")</script> & Test'
        self.profile["site"]["description"] = '" onload="bad <tag> &'
        self.profile["personal"]["contacts"]["website"]["value"] = "https://example.com/?a=1&b=2"
        html = self.render()
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&#34; onload=&#34;bad &lt;tag&gt; &amp;", html)
        self.assertIn("https://example.com/?a=1&amp;b=2", html)
        self.assertFalse(any("onload" in attrs for _, attrs in PageParser(html).elements))

    def test_optional_fields_can_be_removed(self):
        self.profile["personal"].pop("contacts")
        self.profile["personal"].pop("location")
        self.profile["contact"].pop("description")
        html = self.render()
        for unwanted in ('href="mailto:', 'rel="canonical"', 'property="og:url"', 'id="contato"', 'class="eyebrow"'):
            self.assertNotIn(unwanted, html)

    def test_each_contact_is_independently_optional(self):
        for kind in ("email", "linkedin", "website"):
            with self.subTest(kind=kind):
                profile = deepcopy(self.profile)
                removed = profile["personal"]["contacts"].pop(kind)
                self.assertNotIn(removed["value"], self.render(profile))

    def test_empty_lists_hide_sections(self):
        for name in ("specialties", "community", "impact"):
            self.profile[name]["items"] = []
        self.profile["skills"]["groups"] = []
        page = PageParser(self.render())
        self.assertEqual(sum(tag == "section" for tag, _ in page.elements), 2)

    def test_missing_required_fields_are_clear(self):
        for section, key in (("personal", "name"), ("site", "description"), ("skills", "groups")):
            with self.subTest(section=section, key=key):
                profile = deepcopy(self.profile)
                profile[section].pop(key)
                with self.assertRaisesRegex(ProfileError, rf"{section}\.{key}: campo obrigatório"):
                    validate_profile(profile)

    def test_wrong_types_and_empty_values_are_rejected(self):
        cases = [
            ("personal", "name", 123),
            ("personal", "name", " "),
            ("personal", "contacts", []),
            ("specialties", "items", "not a list"),
            ("specialties", "items", [False]),
            ("skills", "groups", [{"category": "Test", "items": []}]),
            ("impact", "items", [{"value": "Test"}]),
            ("community", "items", [None]),
        ]
        for section, key, value in cases:
            with self.subTest(section=section, key=key, value=value):
                profile = deepcopy(self.profile)
                profile[section][key] = value
                with self.assertRaises(ProfileError):
                    validate_profile(profile)
        for value in (None, [], "text"):
            with self.subTest(root=value), self.assertRaises(ProfileError):
                validate_profile(value)

    def test_unsafe_or_invalid_urls_are_rejected(self):
        for value in (
            "javascript:alert(1)", "//example.com", "/relative", "https://",
            "******example.com", 'https://example.com/"bad',
            "https://example.com/\npath", "https://example.com:99999", "https://[",
            "https://example.com\\@other.example",
        ):
            with self.subTest(value=value):
                self.profile["personal"]["contacts"]["website"]["value"] = value
                with self.assertRaisesRegex(ProfileError, "personal.contacts.website.value"):
                    validate_profile(self.profile)

    def test_invalid_emails_are_rejected(self):
        for value in ("not-an-email", "mailto:a@example.com", "a@example.com?subject=bad", "a@example.com\r\nBcc:b@example.com"):
            with self.subTest(value=value):
                self.profile["personal"]["contacts"]["email"]["value"] = value
                with self.assertRaisesRegex(ProfileError, "e-mail inválido"):
                    validate_profile(self.profile)

    def test_invalid_input_preserves_existing_output(self):
        original = self.render()
        for source in ("personal: [", "!!python/object:builtins.object {}", "null", "personal: {}"):
            with self.subTest(source=source):
                self.source.write_text(source, encoding="utf-8")
                with self.assertRaises((ProfileError, yaml.YAMLError)):
                    generate(self.source, ROOT / "templates" / "index.html", self.output)
                self.assertEqual(self.output.read_text(encoding="utf-8"), original)

    def test_generation_is_repeatable_and_does_not_modify_inputs(self):
        first = self.render()
        paths = (self.source, ROOT / "templates" / "index.html", ROOT / "style.css", ROOT / "profile.yaml")
        originals = {path: path.read_bytes() for path in paths}
        generate(self.source, ROOT / "templates" / "index.html", self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), first)
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_template_does_not_hardcode_profile_data(self):
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        for value in (
            self.profile["personal"]["name"],
            self.profile["personal"]["title"],
            self.profile["presentation"]["summary"],
            *(link["value"] for link in self.profile["personal"]["contacts"].values()),
            *(item["description"] for item in self.profile["impact"]["items"]),
        ):
            self.assertNotIn(value, template)

    def test_command_works_outside_repository(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate.py")],
            cwd=self.directory, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Página gerada:", result.stdout)
        self.assertEqual((ROOT / "index.html").read_text(encoding="utf-8"), self.render())

    def test_command_reports_errors(self):
        errors = StringIO()
        with patch("scripts.generate.generate", side_effect=ProfileError("personal.name: campo obrigatório ausente.")):
            with redirect_stderr(errors):
                self.assertEqual(main(), 1)
        self.assertIn("Erro ao gerar a página: personal.name", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
