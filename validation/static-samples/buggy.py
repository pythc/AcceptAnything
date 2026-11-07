"""Inert source sample for Bandit; never execute this file."""
import subprocess


def search(user_input):
    return subprocess.run("echo " + user_input, shell=True, check=True)
