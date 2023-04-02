import asyncio
import asyncio.protocols
import asyncio.subprocess
import atexit
import sys
import threading
import tkinter as tk
from tkinter import ttk


MAX_LINES = 1000


def run_in_terminal(cmd, *, actions=()):
    # Create window
    root = tk.Tk()
    root.title("Taguette")

    # Create frame
    mainframe = ttk.Frame(root, padding="3 3 3 3")
    mainframe.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    mainframe.columnconfigure(len(actions) + 1, weight=1)
    mainframe.rowconfigure(2, weight=1)

    # The buttons
    for col, (label, callback) in enumerate(actions):
        button = ttk.Button(
            mainframe,
            text=label,
            command=callback,
        )
        button.grid(column=col + 1, row=1)
    ttk.Frame(root).grid(column=len(actions) + 1, row=1)

    # The console
    console = tk.Text(mainframe)
    console.grid(
        column=1,
        row=2,
        columnspan=len(actions) + 1,
        sticky=(tk.N, tk.W, tk.E, tk.S),
    )

    def add_text(text):
        console.insert('end', text)
        lines = int(console.index('end - 1 line').split('.')[0]) - 1
        if lines > MAX_LINES:
            console.delete('1.0', '%d.0' % (lines - MAX_LINES + 1))

    # Set up the cross-thread signaling
    add_text_queue = []
    mutex = threading.Lock()

    def add_text_from_queue():
        with mutex:
            for line in add_text_queue:
                add_text(line)
            add_text_queue.clear()

    root.bind('<<AddLineToConsole>>', lambda *args: add_text_from_queue())

    def add_text_threadsafe(text):
        with mutex:
            add_text_queue.append(text)
        root.event_generate('<<AddLineToConsole>>', when='tail')

    # Start an asyncio event loop in a thread and run the command
    thread = threading.Thread(
        target=lambda: _start_process(
            cmd,
            add_text_threadsafe,
        ),
    )
    thread.daemon = True
    thread.start()

    root.mainloop()


def _start_process(cmd, add_text):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(loop.subprocess_exec(
        lambda: ProcessProtocol(add_text),
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    ))
    loop.run_forever()


class ProcessProtocol(asyncio.protocols.SubprocessProtocol):
    def __init__(self, add_text):
        self.add_text = add_text
        self.transport = None

    def connection_made(self, transport):
        self.add_text("Process started\n")
        self.transport = transport
        atexit.register(transport.terminate)

    def pipe_data_received(self, fd, data):
        self.add_text(data)

    def process_exited(self):
        retcode = self.transport.get_returncode()
        self.add_text("Process exited with status %d" % retcode)


def main():
    script = (
        'import sys\n'
        + 'sys.argv = %r\n'
        + 'from taguette.main import main\n'
        + 'main()\n'
    ) % (['taguette'] + sys.argv[1:],)
    run_in_terminal([sys.executable, '-c', script])
    exit(0)
