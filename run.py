import groupmemail.groupmemail
import signal
import sys


def handle_sigterm(_signal, _frame):
    sys.exit()


signal.signal(signal.SIGTERM, handle_sigterm)
groupmemail.groupmemail.main()
