import signal
import sys
import types

import groupmemail.groupmemail


def handle_sigterm(_signal: int, _frame: types.FrameType) -> None:
    sys.exit()


signal.signal(signal.SIGTERM, handle_sigterm)
groupmemail.groupmemail.main()
