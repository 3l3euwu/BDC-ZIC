"""Windows-only local controller. Uses no network services or third-party packages."""
import csv
import os
import pathlib
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

MOD = pathlib.Path(__file__).resolve().parent.parent
STREAM = MOD / 'stream'
HELPER = MOD / 'native' / 'capture.exe'
CREATE_NO_WINDOW = 0x08000000

class Panel:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.log = None
        root.title('BDC-ZIC — experimental music capture')
        root.geometry('720x460')
        ttk.Label(root, text='Select the app process playing audio (or enter a PID).').pack(anchor='w', padx=8, pady=5)
        self.items = ttk.Treeview(root, columns=('pid', 'name'), show='headings', height=13)
        for col, title, width in [('pid', 'PID', 100), ('name', 'Process', 500)]:
            self.items.heading(col, text=title); self.items.column(col, width=width)
        self.items.pack(fill='both', expand=True, padx=8)
        self.items.bind('<<TreeviewSelect>>', self.select)
        row = ttk.Frame(root); row.pack(fill='x', padx=8, pady=6)
        ttk.Label(row, text='PID:').pack(side='left')
        self.pid = tk.StringVar(); ttk.Entry(row, textvariable=self.pid, width=12).pack(side='left', padx=5)
        ttk.Button(row, text='Refresh', command=self.refresh).pack(side='left', padx=3)
        ttk.Button(row, text='Start capture', command=self.start).pack(side='left', padx=3)
        ttk.Button(row, text='Stop', command=self.stop).pack(side='left', padx=3)
        self.status = tk.StringVar(value='Ready. The selected app remains audible on its normal output.')
        ttk.Label(root, textvariable=self.status, wraplength=680).pack(anchor='w', padx=8, pady=4)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh(); self.poll()
    def refresh(self):
        try:
            text = subprocess.check_output(['tasklist', '/fo', 'csv', '/nh'], creationflags=CREATE_NO_WINDOW).decode('utf-8', errors='replace')
            self.items.delete(*self.items.get_children())
            for row in csv.reader(text.splitlines()):
                if len(row) > 1 and row[1].isdigit(): self.items.insert('', 'end', values=(row[1], row[0]))
        except OSError as e: messagebox.showerror('Process list', str(e))
    def select(self, _event):
        selected = self.items.selection()
        if selected: self.pid.set(self.items.item(selected[0], 'values')[0])
    def start(self):
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo('Capture', 'Stop the current capture first.'); return
        try:
            pid = int(self.pid.get())
            if pid <= 0 or pid == os.getpid(): raise ValueError('Choose a valid target PID.')
            if not HELPER.is_file(): raise ValueError(f'Build the capture helper first: {HELPER}')
            STREAM.mkdir(parents=True, exist_ok=True)
            (STREAM / 'stop').unlink(missing_ok=True)
            for i in range(8): (STREAM / f'chunk{i}.pcm').unlink(missing_ok=True)
            import time
            (STREAM / 'session').write_text(str(time.time_ns()), encoding='ascii')
            self.log = open(STREAM / 'capture.log', 'w', encoding='utf-8')
            self.proc = subprocess.Popen([str(HELPER), str(pid), str(STREAM)], stdout=self.log, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
            self.status.set(f'Starting PID {pid}. Press F7 in a Bodycam match. See stream/capture.log for errors.')
        except (OSError, ValueError) as e:
            if self.log: self.log.close(); self.log = None
            messagebox.showerror('Capture', str(e))
    def stop(self):
        if self.proc and self.proc.poll() is None:
            STREAM.mkdir(parents=True, exist_ok=True)
            (STREAM / 'stop').touch()
            self.status.set('Stopping capture…')
    def poll(self):
        if self.proc and self.proc.poll() is not None:
            code = self.proc.returncode
            self.proc = None
            if self.log: self.log.close(); self.log = None
            self.status.set(f'Capture stopped (exit {code}). See stream/capture.log for details.')
        self.root.after(500, self.poll)
    def close(self):
        self.stop()
        if self.proc:
            try: self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired: self.proc.terminate(); self.proc.wait()
        if self.log: self.log.close()
        self.root.destroy()

if __name__ == '__main__':
    if sys.platform != 'win32': sys.exit('The panel and process-loopback capture require Windows.')
    app = tk.Tk(); Panel(app); app.mainloop()
