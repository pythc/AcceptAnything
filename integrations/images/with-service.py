import subprocess,sys,time,urllib.request
server=subprocess.Popen([sys.executable,sys.argv[1]],stdout=subprocess.DEVNULL)
try:
    for i in range(100):
        if server.poll() is not None:raise RuntimeError('target process exited')
        try:
            with urllib.request.urlopen('http://127.0.0.1:19300/health',timeout=.2) as response:
                if response.status==200:break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('target readiness timeout')
    sys.exit(subprocess.run(sys.argv[2:]).returncode)
finally:
    server.terminate()
    try:server.wait(timeout=2)
    except subprocess.TimeoutExpired:server.kill();server.wait()
