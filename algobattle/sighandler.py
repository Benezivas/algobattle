"""Implementations used to safely kill a running battle, cleaning up possibly running docker containers."""
import signal
import sys
import logging
import subprocess
import os

logger = logging.getLogger('algobattle.sighandler')


def signal_handler(sig, frame):
    """Handle interrupts and exit the process gracefully."""
    _kill_spawned_docker_containers()

    logger.info('Received SIGINT, terminating execution.')
    if os.name == 'posix':
        os.killpg(os.getpid(), signal.SIGTERM)
    else:
        os.kill(os.getpid(), signal.CTRL_BREAK_EVENT)

    sys.exit(0)


def _kill_spawned_docker_containers():
    """Terminate all running docker containers spawned by this program."""
    if latest_running_docker_image:
        containers = subprocess.run(f"docker ps -q -q --filter ancestor={latest_running_docker_image}", stdout=subprocess.PIPE)
        for id in containers.stdout.decode().splitlines():
            subprocess.run(f"docker kill {id.strip()}", stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


signal.signal(signal.SIGINT, signal_handler)
latest_running_docker_image = ""
