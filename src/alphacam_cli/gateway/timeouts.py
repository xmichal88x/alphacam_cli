"""Gateway RPC timeout budgets.

Invariant: the client timeout must expire before the server watchdog so the
client reports a clean timeout error instead of a broken connection.
"""

DRAWING_MOVE_CLIENT_TIMEOUT = 45.0
DRAWING_MOVE_SERVER_WATCHDOG = 60.0
DRAWING_LINT_CLIENT_TIMEOUT = 150.0
DRAWING_LINT_SERVER_WATCHDOG = 180.0
