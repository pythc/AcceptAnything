"""Bounded read-only proof workers keep hashing/parsing off the HTTP process."""
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import multiprocessing
from pathlib import Path
import threading


def project_view(store, integrations, rid, page=None):
    from .unified import integration_view, workflow_view
    from .results import native_project
    view=integration_view(integrations,rid,page) if rid.startswith('int-') else workflow_view(store,integrations,store.snapshot(rid))
    if not rid.startswith('int-'):
        view['result_contract']=native_project(view)
        view['decision']=view['result_contract']['gate']['decision']
    return view


def read(root, operation, rid, page=None):
    from .engine import Store
    from .integrations.store import IntegrationStore
    store=Store(Path(root));integrations=IntegrationStore(store.root/'integrations')
    if operation=='contract' and rid.startswith('int-'):return integrations.snapshot(rid)['result_contract']
    view=project_view(store,integrations,rid,page)
    return view['result_contract'] if operation=='contract' else view


class ProofReaders:
    def __init__(self, root):
        self.root=str(root)
        self.pool=ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn'))
        self.lock=threading.RLock()
        self.pending={}

    def submit(self, operation, rid, page=None):
        import json
        key=(operation,rid,json.dumps(page,sort_keys=True))
        with self.lock:
            future=self.pending.get(key)
            if future is not None and not future.done():return future
            try:future=self.pool.submit(read,self.root,operation,rid,page)
            except BrokenProcessPool:
                # A later read can replace a failed proof worker. No execution
                # or model task is submitted here; in-flight errors stay errors.
                self.pool.shutdown(wait=False,cancel_futures=True)
                self.pool=ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn'))
                future=self.pool.submit(read,self.root,operation,rid,page)
            self.pending[key]=future
            def finished(f):
                with self.lock:
                    if self.pending.get(key) is f:self.pending.pop(key,None)
            future.add_done_callback(finished)
            return future

    def close(self):
        self.pool.shutdown(wait=True,cancel_futures=True)
