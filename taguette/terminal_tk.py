import asyncio
import asyncio.protocols
import asyncio.subprocess
import atexit
import os
import socket
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk


MAX_LINES = 1000


def run_in_terminal(cmd):
    # Create window
    root = tk.Tk()
    root.title("Taguette")

    # Create frame
    mainframe = ttk.Frame(root, padding="3 3 3 3")
    mainframe.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    mainframe.columnconfigure(3, weight=1)
    mainframe.rowconfigure(2, weight=1)

    def open_browser():
        if open_browser.url:
            webbrowser.open(open_browser.url)

    open_browser.url = None

    # The buttons
    browser_button = ttk.Button(
        mainframe,
        text="Open browser",
        command=open_browser,
    )
    browser_button.state(['disabled'])
    browser_button.grid(column=1, row=1)
    quit_button = ttk.Button(
        mainframe,
        text="Quit",
        command=lambda: sys.exit(0),
    )
    quit_button.grid(column=2, row=1)
    ttk.Frame(root).grid(column=3, row=1)
    ttk.Frame(root).grid(column=4, row=1)

    # The console
    console = tk.Text(mainframe)
    console.grid(
        column=1,
        row=2,
        columnspan=4,
        sticky=(tk.N, tk.W, tk.E, tk.S),
    )

    # Scrollbar
    scrollbar = ttk.Scrollbar(
        mainframe,
        orient='vertical',
        command=console.yview,
    )
    console['yscrollcommand'] = scrollbar.set
    scrollbar.grid(column=4, row=2, sticky=(tk.N, tk.S))

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

    root.bind(
        '<<EnableBrowserButton>>',
        lambda *args: browser_button.state(['!disabled']),
    )

    def set_url_threadsafe(url):
        with mutex:
            open_browser.url = url
        root.event_generate('<<EnableBrowserButton>>', when='tail')

    # Start an asyncio event loop in a thread and run the command
    thread = threading.Thread(
        target=lambda: _start_process(
            cmd,
            add_text_threadsafe,
            set_url_threadsafe,
        ),
    )
    thread.daemon = True
    thread.start()

    root.mainloop()


def _start_process(cmd, add_text, set_url):
    loop = asyncio.new_event_loop()

    # Create a TCP server to receive the URL from Taguette
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    print(port)

    def set_url_and_stop(url):
        set_url(url)
        url_server.close()

    url_server, _ = loop.run_until_complete(loop.create_datagram_endpoint(
        lambda: ReceiveOnceProtocol(set_url_and_stop),
        sock=sock,
    ))

    # Run the process
    loop.run_until_complete(loop.subprocess_exec(
        lambda: ProcessProtocol(add_text),
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=dict(os.environ, TAGUETTE_URL_PORT=str(port)),
    ))

    loop.run_forever()


class ReceiveOnceProtocol(asyncio.protocols.Protocol):
    def __init__(self, result):
        self._result = result

    def datagram_received(self, data, addr):
        data = data.decode('ascii')
        self._result(data)
        return False


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
