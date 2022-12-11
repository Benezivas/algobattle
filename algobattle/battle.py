"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from argparse import ArgumentParser, Namespace
from contextlib import ExitStack
from dataclasses import dataclass
from functools import partial
import sys
import logging
import datetime as dt
from pathlib import Path
import tomli
from algobattle.battle_wrapper import BattleWrapper
from algobattle.docker_util import DockerConfig

from algobattle.match import MatchConfig, MatchInfo
from algobattle.team import TeamInfo
from algobattle.ui import Ui
from algobattle.util import check_path, import_problem_from_path


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


@dataclass
class SystemConfig:
    problem: Path
    verbose: bool
    logging_path: Path
    silent: bool
    ui: bool
    safe_build: bool


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        if len(sys.argv) < 2:
            sys.exit('Expecting (relative) path to the parent directory of a problem file as argument. Use "battle --help" for more information on usage and options.')

        parser = ArgumentParser()
        parser.add_argument("path", type=check_path, help="Path to the needed files if they aren't specified seperately.")
        parser.add_argument("--problem", type=partial(check_path, type="file"), default=None, help="Path to a problem file.")
        parser.add_argument("--config", type=partial(check_path, type="file"), default=None, help="Path to a config file.")

        parser.add_argument("--verbose", "-v", dest="verbose", action="store_true", help="More detailed log output.")
        parser.add_argument("--logging_path", type=partial(check_path, type="dir"), default=Path.home() / ".algobattle_logs", help="Folder that logs are written into.")
        parser.add_argument("--silent", "-s", dest="silent", action="store_true", help="Disable forking to stderr.")
        parser.add_argument("--ui", action="store_true", help="Display a small UI on STDOUT that shows the progress of the battle.")
        parser.add_argument("--safe_build", action="store_true", help="Isolate docker image builds from each other. Significantly slows down battle setup but closes prevents images from interfering with each other.")

        parser.add_argument("--battle_type", choices=["iterated", "averaged"], default="iterated", help="ype of battle wrapper to be used.")
        parser.add_argument("--team", dest="teams", type=partial(check_path, type="dir"), help="Path to a folder containing /generator and /solver folders. For more detailed team configuration use the config file.")
        parser.add_argument("--rounds", type=int, default=5, help="Number of rounds that are to be fought in the battle (points are split between all rounds).")
        parser.add_argument("--points", type=int, default=100, help="number of points distributed between teams.")

        cfg_args = parser.parse_args(("path", "config"))
        if cfg_args.config is not None:
            cfg_path = cfg_args.config
        else:
            cfg_path = cfg_args.path / "config.toml"
        if cfg_path.is_file():
            with open(cfg_path, "rb") as file:
                try:
                    config = tomli.load(file)
                except tomli.TOMLDecodeError as e:
                    raise SystemExit(f"The config file at {cfg_path} is not a properly formatted TOML file!\n{e}")
        else:
            config = {}

        namespaces = {name: Namespace(**config[name]) if name in config else Namespace() for name in ("system", "battle")}
        parser.parse_args(("problem", "verbose", "logging_path", "silent", "ui", "safe_build"), namespaces["system"])
        if namespaces["system"].problem is None:
            namespaces["system"].problem = cfg_args.path
        parser.parse_args(("battle_type", "team", "rounds", "points"), namespaces["battle"])
        if namespaces["battle"].teams:
            teams_pre = namespaces["battle"].teams
        else:
            teams_pre = [cfg_args.path]
        team_infos = []
        for team_spec in teams_pre:
            if isinstance(team_spec, dict):
                try:
                    team_infos.append(TeamInfo(**team_spec))
                except TypeError:
                    raise SystemExit(f"The config file at {cfg_path} is incorrectly formatted!")
            else:
                team_infos.append(TeamInfo(name=team_spec.name, generator=team_spec / "generator", solver=team_spec / "solver"))
        
        sys_config = SystemConfig(**vars(namespaces["system"]))
        battle_config = MatchConfig(**vars(namespaces["battle"]))
        wrapper_config = BattleWrapper.Config()
        docker_config = DockerConfig()

        if sys_config.ui:
            sys_config.silent = True


        logger = setup_logging(sys_config.logging_path, sys_config.verbose, sys_config.silent)

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = import_problem_from_path(sys_config.problem)
        with MatchInfo.build(
            problem=problem,
            config=battle_config,
            wrapper_cfg=wrapper_config,
            docker_cfg=docker_config,
            safe_build=sys_config.safe_build,
        ) as match_info, ExitStack() as stack:
            if sys_config.ui:
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
