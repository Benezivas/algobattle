"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from argparse import ArgumentParser, Namespace
from contextlib import ExitStack
from dataclasses import MISSING, InitVar, dataclass, fields
from functools import partial
import sys
import logging
import datetime as dt
from pathlib import Path
from typing import Literal
import tomli
from algobattle.battle_wrapper import BattleWrapper
from algobattle.docker_util import DockerConfig
from algobattle.fight_handler import FightHandler

from algobattle.match import MatchInfo
from algobattle.team import TeamInfo
from algobattle.ui import Ui
from algobattle.util import check_path, import_problem_from_path
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated


def setup_logging(logging_path: Path, verbose_logging: bool, silent: bool):
    """Creates and returns a parent logger.

    Parameters
    ----------
    logging_path : Path
        Path to folder where the logfile should be stored at.
    verbose_logging : bool
        Flag indicating whether to include debug messages in the output
    silent : bool
        Flag indicating whether not to pipe the logging output to stderr.

    Returns
    -------
    logger : Logger
        The Logger object.
    """
    common_logging_level = logging.INFO

    if verbose_logging:
        common_logging_level = logging.DEBUG

    Path(logging_path).mkdir(exist_ok=True)

    t = dt.datetime.now()
    current_timestamp = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}"
    logging_path = Path(logging_path, current_timestamp + '.log')

    logging.basicConfig(handlers=[logging.FileHandler(logging_path, 'w', 'utf-8')],
                        level=common_logging_level,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%H:%M:%S')
    logger = logging.getLogger('algobattle')

    if not silent:
        # Pipe logging out to console
        _consolehandler = logging.StreamHandler(stream=sys.stderr)
        _consolehandler.setLevel(common_logging_level)

        _consolehandler.setFormatter(logging.Formatter('%(message)s'))

        logger.addHandler(_consolehandler)

    logger.info(f"You can find the log files for this run in {logging_path}")
    return logger


@dataclass(kw_only=True)
class BattleConfig:
    problem: Path
    verbose: bool
    logging_path: Path = Path.home() / ".algobattle_logs"
    display: Literal["silent", "logs", "ui"]
    safe_build: bool
    battle_type: Literal["iterated", "averaged"]
    teams: list[TeamInfo]
    rounds: int
    points: int


def parse_cli_args(args: list[str]) -> tuple[BattleConfig, BattleWrapper.Config, DockerConfig]:
    """Parse a given CLI arg list into config objects."""

    parser = ArgumentParser()
    parser.add_argument("path", type=check_path, help="Path to the needed files if they aren't specified seperately.")
    parser.add_argument("--problem", type=partial(check_path, type="file"), default=None, help="Path to a problem file.")
    parser.add_argument("--config", type=partial(check_path, type="file"), default=None, help="Path to a config file.")

    parser.add_argument("--verbose", "-v", dest="verbose", action="store_true", help="More detailed log output.")
    parser.add_argument("--logging_path", type=partial(check_path, type="dir"), default=Path.home() / ".algobattle_logs", help="Folder that logs are written into.")
    parser.add_argument("--display", choices=["silent", "logs", "ui"], default="logs", help="Choose output mode, silent disables all output, logs displays the battle logs on STDERR, ui displays a small GUI showing the progress of the battle.")
    parser.add_argument("--safe_build", action="store_true", help="Isolate docker image builds from each other. Significantly slows down battle setup but closes prevents images from interfering with each other.")

    parser.add_argument("--battle_type", choices=["iterated", "averaged"], default="iterated", help="ype of battle wrapper to be used.")
    parser.add_argument("--team", dest="teams", type=partial(check_path, type="dir"), help="Path to a folder containing /generator and /solver folders. For more detailed team configuration use the config file.")
    parser.add_argument("--rounds", type=int, default=5, help="Number of rounds that are to be fought in the battle (points are split between all rounds).")
    parser.add_argument("--points", type=int, default=100, help="number of points distributed between teams.")

    for wrapper in (Iterated, Averaged):
        group = parser.add_argument_group(wrapper.type)
        for field in fields(wrapper.Config):
            if field.default_factory != MISSING:
                default = field.default_factory()
            elif field.default != MISSING:
                default = field.default
            else:
                default = None
            group.add_argument(f"{wrapper.type}_{field.name}", type=field.type, default=default)

    cfg_args = parser.parse_args(args)
    if cfg_args.config is not None:
        cfg_path = cfg_args.config
    else:
        cfg_path = cfg_args.path / "config.toml"
    if cfg_path.is_file():
        with open(cfg_path, "rb") as file:
            try:
                config = tomli.load(file)
            except tomli.TOMLDecodeError as e:
                raise ValueError(f"The config file at {cfg_path} is not a properly formatted TOML file!\n{e}")
    else:
        config = {}

    battle_config = Namespace(**config.get("algobattle", {}))
    parser.parse_args(args, namespace=battle_config)

    if battle_config.problem is None:
        battle_config.problem = cfg_args.path
    if battle_config.teams:
        teams_pre = battle_config.teams
    else:
        teams_pre = [cfg_args.path]

    battle_config.teams = []
    for team_spec in teams_pre:
        if isinstance(team_spec, dict):
            try:
                name = team_spec["name"]
                gen = check_path(team_spec["generator"], type="dir")
                sol = check_path(team_spec["solver"], type="dir")
                battle_config.teams.append(TeamInfo(name=name, generator=gen, solver=sol))
            except TypeError:
                raise ValueError(f"The config file at {cfg_path} is incorrectly formatted!")
        else:
            battle_config.teams.append(TeamInfo(name=team_spec.name, generator=team_spec / "generator", solver=team_spec / "solver"))

    battle_config = BattleConfig(**vars(battle_config))
    wrapper_config = BattleWrapper.Config()
    docker_config = DockerConfig()

    return battle_config, wrapper_config, docker_config


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        battle_config, wrapper_config, docker_config = parse_cli_args(sys.argv)
        logger = setup_logging(battle_config.logging_path, battle_config.verbose, battle_config.display != "logs")

    except ValueError as e:
        raise SystemExit from e
    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = import_problem_from_path(battle_config.problem)
        fight_handler = FightHandler(problem, docker_config)
        wrapper = BattleWrapper.initialize(battle_config.battle_type, fight_handler, wrapper_config)
        with MatchInfo.build(
            problem=problem,
            wrapper=wrapper,
            teams=battle_config.teams,
            rounds=battle_config.rounds,
            docker_cfg=docker_config,
            safe_build=battle_config.safe_build,
        ) as match_info, ExitStack() as stack:
            if battle_config.display == "ui":
                ui = Ui()
                stack.enter_context(ui)
            else:
                ui = None

            result = match_info.run_match(ui)

            logger.info('#' * 78)
            logger.info(str(result))
            if battle_config.points > 0:
                points = result.calculate_points(battle_config.points)
                for team, pts in points.items():
                    logger.info(f"Group {team} gained {pts:.1f} points.")

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


if __name__ == "__main__":
    main()
