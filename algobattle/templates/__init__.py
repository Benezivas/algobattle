"""Package containing templates used for the algobattle init command."""

from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Literal
from typing_extensions import TypedDict
from jinja2 import Environment, PackageLoader, Template


class Language(StrEnum):
    """Langues supported by `algobattle init`."""

    plain = "plain"
    python = "python"
    javascript = "javascript"
    typescript = "typescript"
    rust = "rust"
    java = "java"
    cpp = "cpp"
    c = "c"
    csharp = "csharp"
    go = "go"

    @cached_property
    def env(self) -> Environment:
        """The jinja environment for this language."""
        return Environment(
            loader=PackageLoader("algobattle.templates", self.value),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )


class PartialTemplateArgs(TypedDict):
    """Template arguments without the program role."""

    problem: str
    team: str
    with_solution: bool
    instance_json: bool
    solution_json: bool


class TemplateArgs(PartialTemplateArgs):
    """Template arguments."""

    program: Literal["generator", "solver"]


def normalize(s: str) -> str:
    """Normalizes a name so it can be used in project names."""
    return s.lower().replace(" ", "-")


def write_templates(target: Path, lang: Language, args: TemplateArgs) -> None:
    """Writes the formatted templates to the target directory."""
    template_args = args | {
        "project": f"{normalize(args['team'])}-{normalize(args['problem'])}-{normalize(args['program'])}",
        "team_normalized": args["team"].lower().replace(" ", ""),
    }
    for name in lang.env.list_templates():
        template = lang.env.get_template(name)
        formatted = template.render(template_args)
        formatted_path = Path(Template(name).render(template_args))
        if formatted_path.suffix == ".jinja":
            formatted_path = formatted_path.with_suffix("")

        (target / formatted_path).parent.mkdir(parents=True, exist_ok=True)
        with open(target / formatted_path, "w+") as file:
            file.write(formatted)
