#!/usr/bin/env python3
"""Reload SketchUp extension from command line.

This script sends a JSON-RPC request to the SketchUp extension to trigger
a reload without restarting SketchUp.

Usage:
    python reload_extension.py
    python reload_extension.py --host 127.0.0.1 --port 9876
"""

import argparse
import json
import socket
import sys
from typing import Any


# ANSI color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


def send_reload_request(host: str, port: int, timeout: int = 5) -> dict[str, Any]:
    """Send reload_extension request to SketchUp.

    Args:
        host: SketchUp extension host address
        port: SketchUp extension port number
        timeout: Socket timeout in seconds

    Returns:
        JSON-RPC response dictionary

    Raises:
        socket.timeout: If connection times out
        ConnectionRefusedError: If connection is refused
        Exception: For other socket errors
    """
    # Create JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "reload_extension",
            "arguments": {}
        },
        "id": 1
    }

    # Connect to SketchUp extension
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((host, port))

        # Send request
        request_json = json.dumps(request) + '\n'
        sock.sendall(request_json.encode('utf-8'))

        # Receive response (with chunking support)
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

            # Try to parse complete JSON
            try:
                data = b''.join(chunks)
                response = json.loads(data.decode('utf-8'))
                return response
            except json.JSONDecodeError:
                # Need more data
                continue

        # If we exit the loop without returning, we didn't get valid JSON
        raise ValueError("Failed to receive complete JSON response")

    finally:
        sock.close()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Reload SketchUp extension from command line"
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='SketchUp extension host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=9876,
        help='SketchUp extension port (default: 9876)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=5,
        help='Connection timeout in seconds (default: 5)'
    )

    args = parser.parse_args()

    print(f"{Colors.YELLOW}Reloading SketchUp extension...{Colors.NC}")

    try:
        response = send_reload_request(args.host, args.port, args.timeout)

        # Check if request was successful
        result = response.get('result', {})
        if result.get('success'):
            print(f"{Colors.GREEN}✓ Extension reloaded successfully{Colors.NC}")
            if 'message' in result:
                print(result['message'])
            return 0
        else:
            print(f"{Colors.RED}✗ Failed to reload extension{Colors.NC}")
            print(json.dumps(response, indent=2))
            return 1

    except socket.timeout:
        print(
            f"{Colors.RED}✗ Connection timeout - is SketchUp running?{Colors.NC}",
            file=sys.stderr
        )
        return 1

    except ConnectionRefusedError:
        print(
            f"{Colors.RED}✗ Connection refused - is SketchUp extension loaded?{Colors.NC}",
            file=sys.stderr
        )
        return 1

    except Exception as e:
        print(f"{Colors.RED}✗ Error: {e}{Colors.NC}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
