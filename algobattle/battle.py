"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from argparse import ArgumentParser
from contextlib import ExitStack
from dataclasses import dataclass
import sys
import logging
import datetime as dt

from pathlib import Path

from algobattle.match import MatchInfo
from algobattle.team import TeamInfo
from algobattle.ui import Ui


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
        parser.add_argument("path", type=Path, help="Path to the needed files if they aren't specified seperately.")
        parser.add_argument("--problem", type=Path, default=None, help="Path to a problem file.")
        parser.add_argument("--config", type=Path, default=None, help="Path to a config file.")

        parser.add_argument("--verbose", "-v", dest="verbose", action="store_true", help="More detailed log output.")
        parser.add_argument("--logging_path", default=Path.home() / ".algobattle_logs", help="Folder that logs are written into.")
        parser.add_argument("--silent", "-s", action="store_true", help="Disable forking to stderr.")
        parser.add_argument("--ui", action="store_true", help="Display a small UI on STDOUT that shows the progress of the battle.")
        parser.add_argument("--safe_build", action="store_true", help="Isolate docker image builds from each other. Significantly slows down battle setup but closes prevents images from interfering with each other.")

        parser.add_argument("--battle_type", choices=["iterated", "averaged"], default="iterated", help="ype of battle wrapper to be used.")
        parser.add_argument("--team", dest="team_paths", help="Path to a folder containing /generator and /solver folders. For more detailed team configuration use the config file.")
        parser.add_argument("--rounds", type=int, default=5, help="Number of rounds that are to be fought in the battle (points are split between all rounds).")
        parser.add_argument("--points", type=int, default=100, help="number of points distributed between teams.")

        options = parser.parse_args()

        display_ui = options.display_ui
        if display_ui:
            options.silent = True

        problem_path = Path(problem_path)
        options.config = Path(options.config)
        solvers = [Path(path) for path in options.solvers.split(',')]
        generators = [Path(path) for path in options.generators.split(',')]
        team_names = options.team_names.split(',')

        if not (len(solvers) == len(generators) == len(team_names)):
            raise SystemExit(f"The number of provided generator paths ({len(generators)}), solver paths ({len(solvers)}) and group numbers ({len(team_names)}) is not equal!")

        for path in [problem_path, options.config] + solvers + generators:
            if not path.exists():
                raise SystemExit(f"Path '{path}' does not exist in the file system! "
                                 "Use 'battle --help' for more information on usage and options.")

        logger = setup_logging(options.logging_path, options.verbose_logging, options.silent)

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        logger.debug('Options for this run: {}'.format(options))
        logger.debug('Contents of sys.argv: {}'.format(sys.argv))
        logger.debug('Using additional configuration options from file "%s".', options.config)
        team_infos = [TeamInfo(*info) for info in zip(team_names, generators, solvers)]

        with MatchInfo.build(
            problem_path=problem_path,
            config_path=options.config,
            team_infos=team_infos,
            rounds=options.battle_rounds,
            battle_type=options.battle_type,
            safe_build=options.safe_build
        ) as match_info, ExitStack() as stack:
            if display_ui:
                ui = Ui()
                stack.enter_context(ui)
            else:
                ui = None

            result = match_info.run_match(ui)

            logger.info('#' * 78)
            logger.info(str(result))
            if not options.do_not_count_points:
                points = result.calculate_points(options.points)
                for team, pts in points.items():
                    logger.info(f"Group {team} gained {pts:.1f} points.")

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


if __name__ == "__main__":
    main()
