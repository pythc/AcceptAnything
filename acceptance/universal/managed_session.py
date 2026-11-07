"""Serve the actual public app while its per-case preparation remains alive."""
import asyncio,base64,json,signal,sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scenario import execute


async def main(request):
    destination=Path(request['receipt_directory']);destination.mkdir(parents=True,exist_ok=True)
    stop=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
    async def ready(state,work,steps):
        for step in request['steps']:
            result=state.get(step['id'])
            if step['op']=='cli' and result['exit_code']!=0:raise ValueError('CLI preparation failed: '+step['id'])
            if step['op']=='observe_call' and result.get('raised'):raise ValueError('Preparation captured an exception: '+step['id'])
        app=state[request['app']];adapter=request['adapter']
        if adapter=='wsgi':
            from werkzeug.serving import make_server
            server=make_server('0.0.0.0',0,app,threaded=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_port
            closer=lambda:server.shutdown()
        elif adapter=='asgi':
            import socket,uvicorn
            sock=socket.socket();sock.bind(('0.0.0.0',0));port=sock.getsockname()[1]
            server=uvicorn.Server(uvicorn.Config(app,log_level='info'));task=asyncio.create_task(server.serve(sockets=[sock]))
            for _ in range(300):
                if server.started:break
                if task.done():await task;raise RuntimeError('ASGI server exited before ready')
                await asyncio.sleep(.1)
            if not server.started:raise RuntimeError('ASGI server did not start')
            closer=lambda:setattr(server,'should_exit',True)
        else:raise ValueError('Python session needs wsgi/asgi adapter')
        try:
            path=destination/'ready.json';temp=destination/'ready.tmp'
            temp.write_text(json.dumps(dict(port=port,adapter=adapter,steps=steps,workspace=str(work))));temp.replace(path)
            await stop.wait()
        finally:
            await asyncio.to_thread(closer)
            if adapter=='wsgi':thread.join(timeout=10);server.server_close()
            else:await task;sock.close()
    receipt=await execute(request,Path('/work/repo'),ready)
    (destination/'final.json').write_text(json.dumps(receipt,ensure_ascii=False,allow_nan=False))
    print('\nACCEPTANCE_VALUE:'+json.dumps(receipt,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':asyncio.run(main(json.loads(base64.b64decode(sys.argv[1]))))
