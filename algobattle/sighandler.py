"""Implementations used to safely kill a running battle, cleaning up possibly running docker containers."""
import signal
import logging
import os

from algobattle.docker import kill_all_running_containers

logger = logging.getLogger('algobattle.sighandler')

#* Due to a windows api bug (https://bugs.python.org/issue28168) we cannot
#* reliably kill the battle process while containers are being run as
#* subprocesses. This means that there is no need to kill children on windows.
#* On linux sending SIGINT currently kills each child in three different ways:
#* first the container gets the proxied SIGINT through docker and most likely
#* exits, then the kill_all_running_containers() call kills the container, and
#* then the signal handler kills the attached process. This last step is
#* nessecary if we want to avoid creating orphan processes, but they should get
#* reaped very quickly anyways.
#* This also means that on windows a docker container that ignores SIGINT will
#* not be forced to quit and can run until the timeout which makes this program
#* rather unresponsive to ctrl + C.
def signal_handler(sig, frame):
    """Handle interrupts and exit the process gracefully."""
    logger.info('Received SIGINT, terminating execution.')
    kill_all_running_containers()

    if os.name == 'posix':
        os.killpg(os.getpid(), signal.SIGTERM)

    raise SystemExit


signal.signal(signal.SIGINT, signal_handler)
