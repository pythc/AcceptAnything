import os
import tempfile

def temporary_location():
    with tempfile.TemporaryFile() as stream:
        for _ in range(35):
            stream.write(b'x' * 1024 * 1024)
        stream.write(b'tail')
        stream.flush()
        size=stream.tell()
        stream.seek(-4,os.SEEK_END)
        return dict(directory=tempfile.gettempdir(),bytes=size,tail=stream.read().decode(),
                    same_work_device=os.fstat(stream.fileno()).st_dev==os.stat('/work').st_dev,
                    different_tmp_device=os.fstat(stream.fileno()).st_dev!=os.stat('/tmp').st_dev)
