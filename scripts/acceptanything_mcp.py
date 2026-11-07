"""Absolute-path launcher for MCP hosts that do not configure a working directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_tools.__main__ import main

if __name__ == '__main__':
    main()
