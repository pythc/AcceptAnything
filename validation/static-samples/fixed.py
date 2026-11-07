"""Inert comparison sample. Invoked by scanners only."""
import subprocess


def search(user_input):
    return subprocess.run(["/usr/bin/printf", "%s", user_input], shell=False, check=True)
