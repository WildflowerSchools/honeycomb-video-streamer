from threading import Thread
from queue import Queue, Empty


# Thanks https://gist.github.com/EyalAr/7915597
class NonBlockingStreamReader:
    def __init__(self, stream):
        """
        stream: the stream to read from.
                Usually a process' stdout or stderr.
        """
        self._s = stream
        self._q = Queue()

        def _populateQueue(stream, queue):
            """
            Collect lines from 'stream' and put them in 'queue'.
            """
            while True:
                line = stream.readline()
                queue.put(line)  # Final line will be a ''
                if not line:
                    break

        self._t = Thread(target=_populateQueue, args=(self._s, self._q))
        self._t.daemon = True
        self._t.start()

    def readline(self, timeout=None):
        try:
            return self._q.get(block=timeout is not None, timeout=timeout)
        except Empty as e:
            raise StreamTimeout from e


class StreamTimeout(Exception):
    pass
