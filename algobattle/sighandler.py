"""Implementations used to safely kill a running battle, cleaning up possibly running docker containers."""
import signal
import logging
import os

from algobattle.docker import kill_all_running_containers

logger = logging.getLogger('algobattle.sighandler')


def signal_handler(sig, frame):
    """Handle interrupts and exit the process gracefully."""
    logger.info('Received SIGINT, terminating execution.')
    kill_all_running_containers()

    if os.name == 'posix':
        os.killpg(os.getpid(), signal.SIGTERM)

    raise SystemExit


signal.signal(signal.SIGINT, signal_handler)
