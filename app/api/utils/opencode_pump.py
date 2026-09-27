import queue
import threading
from app.api.utils.opencode_stream import emit

KEEPALIVE_SECONDS = 10
STREAM_QUEUE_SIZE = 256


class StreamFailure:
    def __init__(self, message: str):
        self.message = message


def pump_stream(stream, out: queue.Queue, stop: threading.Event) -> None:
    try:
        for chunk in stream:
            while not stop.is_set():
                try:
                    out.put(chunk, timeout=0.5)
                    break
                except queue.Full:
                    continue
            if stop.is_set():
                break
    except Exception as error:
        try:
            out.put(StreamFailure(str(error) or error.__class__.__name__), timeout=1)
        except queue.Full:
            pass
    finally:
        try:
            out.put(None, timeout=1)
        except queue.Full:
            pass


def stream_with_keepalive(stream):
    out: queue.Queue = queue.Queue(maxsize=STREAM_QUEUE_SIZE)
    stop = threading.Event()
    worker = threading.Thread(target=pump_stream, args=(stream, out, stop), daemon=True)
    worker.start()
    try:
        while True:
            try:
                item = out.get(timeout=KEEPALIVE_SECONDS)
            except queue.Empty:
                yield b": keepalive\n\n"
                continue
            if item is None:
                break
            if isinstance(item, StreamFailure):
                yield emit({"error": item.message})
                break
            yield item
        yield b"data: [DONE]\n\n"
    finally:
        stop.set()
        try:
            stream.close()
        except Exception:
            pass
