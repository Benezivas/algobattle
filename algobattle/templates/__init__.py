"""Package containing templates used for the algobattle init command."""

from enum import StrEnum
from pathlib import Path
from typing import Literal
from typing_extensions import TypedDict
from jinja2 import Environment, PackageLoader, Template


class Language(StrEnum):
    """Langues supported by `algobattle init`."""

    python = "python"


ENVS = {
    "python": Environment(
        loader=PackageLoader("algobattle.templates", "python"), keep_trailing_newline=True, line_statement_prefix="# ?"
    )
}


class TemplateArgs(TypedDict):
    """Template arguments."""

    problem: str
    team: str
    program: Literal["generator", "solver"]


def normalize(s: str) -> str:
    return s.lower().replace(" ", "-")


def write_templates(target: Path, lang: Language, args: TemplateArgs) -> None:
    """Yields all templates and where they should be placed."""
    template_args = args | {
        "project": f"{normalize(args['team'])}-{normalize(args['problem'])}-{normalize(args['program'])}",
    }
    env = ENVS[lang]
    for name in env.list_templates():
        template = env.get_template(name)
        formatted = template.render(template_args)
        formatted_path = Template(name).render(template_args)
        (target / formatted_path).parent.mkdir(parents=True, exist_ok=True)
        with open(target / formatted_path, "w+") as file:
            file.write(formatted)
