from __future__ import annotations

import logging
import sys


def run_server(host: str = "0.0.0.0", port: int = 8721) -> None:
    from alphacam_cli.gateway.server import GatewayServer

    server = GatewayServer(host, port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8721
    print(f"Starting AlphaCAM gateway on {host}:{port}...")
    run_server(host, port)


if __name__ == "__main__":
    main()
