"""Render the static landing page from the validated YAML profile."""

from datetime import datetime
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError


ROOT = Path(__file__).resolve().parents[1]


class ProfileError(ValueError):
    """A profile field is missing or has an invalid format."""


def mapping(value, path):
    if not isinstance(value, dict):
        raise ProfileError(f"{path}: esperado um objeto YAML.")
    return value


def required(obj, key, path):
    if key not in obj:
        raise ProfileError(f"{path}.{key}: campo obrigatório ausente.")
    return obj[key]


def text(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{path}: esperado um texto não vazio.")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ProfileError(f"{path}: texto contém caracteres de controle inválidos.")
    return value


def text_field(obj, key, path):
    return text(required(obj, key, path), f"{path}.{key}")


def sequence(value, path):
    if not isinstance(value, list):
        raise ProfileError(f"{path}: esperada uma lista YAML.")
    return value


def text_list(value, path):
    for index, item in enumerate(sequence(value, path)):
        text(item, f"{path}[{index}]")


def web_url(value, path):
    text(value, path)
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in ("https", "http")
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not any(char.isspace() or ord(char) < 32 for char in value)
            and not any(char in value for char in '\\<>"')
        )
        # Accessing port also validates malformed or out-of-range port numbers.
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ProfileError(f"{path}: esperada uma URL HTTP(S) absoluta, sem credenciais.")


def validate_profile(data):
    mapping(data, "profile")
    sections = {}
    for name in (
        "site", "personal", "presentation", "specialties",
        "skills", "impact", "community", "contact",
    ):
        sections[name] = mapping(required(data, name, "profile"), name)

    for key in ("title", "description", "skip_link"):
        text_field(sections["site"], key, "site")
    for key in ("name", "title"):
        text_field(sections["personal"], key, "personal")
    personal = sections["personal"]
    if "location" in personal:
        text(personal["location"], "personal.location")

    contacts = mapping(personal.get("contacts", {}), "personal.contacts")
    for kind, link in contacts.items():
        path = f"personal.contacts.{kind}"
        if kind not in ("email", "linkedin", "website"):
            raise ProfileError(f"{path}: contato desconhecido; use email, linkedin ou website.")
        mapping(link, path)
        text_field(link, "label", path)
        value = text_field(link, "value", path)
        if kind == "email":
            if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value):
                raise ProfileError(f"{path}.value: endereço de e-mail inválido.")
        else:
            web_url(value, f"{path}.value")

    text_field(sections["presentation"], "summary", "presentation")
    for name in ("specialties", "skills", "impact", "community", "contact"):
        text_field(sections[name], "title", name)
    for name in ("specialties", "community"):
        text_list(required(sections[name], "items", name), f"{name}.items")

    groups = sequence(required(sections["skills"], "groups", "skills"), "skills.groups")
    for index, group in enumerate(groups):
        path = f"skills.groups[{index}]"
        mapping(group, path)
        text_field(group, "category", path)
        items = required(group, "items", path)
        text_list(items, f"{path}.items")
        if not items:
            raise ProfileError(f"{path}.items: inclua ao menos uma competência ou remova o grupo.")

    for index, item in enumerate(sequence(required(sections["impact"], "items", "impact"), "impact.items")):
        path = f"impact.items[{index}]"
        mapping(item, path)
        for key in ("value", "description"):
            text_field(item, key, path)
    if "description" in sections["contact"]:
        text(sections["contact"]["description"], "contact.description")
    return data


def generate(
    profile_path=ROOT / "profile.yaml",
    template_path=ROOT / "templates" / "index.html",
    output_path=ROOT / "index.html",
):
    data = validate_profile(yaml.safe_load(profile_path.read_text(encoding="utf-8")))
    environment = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    environment.filters["email_uri"] = lambda value: quote(value, safe="@")
    # Missing optional contacts are normalized only in memory, never in the YAML.
    context = {**data, "personal": {**data["personal"]}}
    context["personal"]["contacts"] = data["personal"].get("contacts", {})
    html = environment.get_template(template_path.name).render(
        **context, year=datetime.now().year,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main():
    try:
        output = generate()
    except (ProfileError, yaml.YAMLError, TemplateError, OSError, UnicodeError) as error:
        print(f"Erro ao gerar a página: {error}", file=sys.stderr)
        return 1
    print(f"Página gerada: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
