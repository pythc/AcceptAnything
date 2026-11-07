import sys

def main():
    print('ready')
    return 2 if '--fail' in sys.argv else 0
