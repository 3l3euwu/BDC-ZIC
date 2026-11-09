"""Windows-only local controller. Uses no network services or third-party packages."""
import csv
import ctypes
from ctypes import wintypes
import os
import pathlib
import subprocess
import sys

MOD = pathlib.Path(__file__).resolve().parent.parent
STREAM = pathlib.Path(os.environ['LOCALAPPDATA']) / 'BDC-ZIC' / 'stream' if os.environ.get('LOCALAPPDATA') else MOD / 'stream'
HELPER = MOD / 'native' / 'capture.exe'
CREATE_NO_WINDOW = 0x08000000
PRESETS = ('All processes', 'Spotify', 'YoloTube / YouTube')

def matches_preset(preset, process_name, window_title):
    name, title = process_name.casefold(), window_title.casefold()
    if preset == 'All processes':
        return True
    if preset == 'Spotify':
        # Spotify often replaces the window title with the currently playing song.
        return 'spotify' in title or (bool(title) and name == 'spotify.exe')
    if preset == 'YoloTube / YouTube':
        return 'yolotube' in title or 'youtube' in title
    return False

def visible_windows():
    """Return (PID, title) for titled top-level visible windows on this desktop."""
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    results = []
    @callback_type
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                text = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, text, length + 1)
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value and text.value.strip():
                    results.append((pid.value, text.value.strip()))
        return True
    if not user32.EnumWindows(visit, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return results

class Panel:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.log = None
        root.title('BDC-ZIC — experimental music capture')
        root.geometry('950x500')
        header = ttk.Frame(root); header.pack(fill='x', padx=8, pady=5)
        ttk.Label(header, text='App preset:').pack(side='left')
        self.preset = tk.StringVar(value=PRESETS[0])
        picker = ttk.Combobox(header, textvariable=self.preset, values=PRESETS, state='readonly', width=22)
        picker.pack(side='left', padx=5)
        picker.bind('<<ComboboxSelected>>', self.refresh)
        ttk.Label(header, text='Choose a matching window or enter a PID below.').pack(side='left', padx=5)
        self.items = ttk.Treeview(root, columns=('pid', 'name', 'title'), show='headings', height=13)
        for col, title, width in [('pid', 'PID', 75), ('name', 'Process', 180), ('title', 'Window title', 650)]:
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
    def refresh(self, _event=None):
        try:
            text = subprocess.check_output(['tasklist', '/fo', 'csv', '/nh'], creationflags=CREATE_NO_WINDOW).decode('mbcs', errors='replace')
            processes = {int(row[1]): row[0] for row in csv.reader(text.splitlines()) if len(row) > 1 and row[1].isdigit()}
            windows = visible_windows()
            self.items.delete(*self.items.get_children())
            self.pid.set('')  # Never retain a stale PID when the list or preset changes.
            entries = []
            for pid, title in windows:
                name = processes.get(pid, '(unknown)')
                if matches_preset(self.preset.get(), name, title):
                    entries.append((pid, name, title))
            if self.preset.get() == 'All processes':
                window_pids = {pid for pid, _ in windows}
                entries.extend((pid, name, '') for pid, name in processes.items() if pid not in window_pids)
            entries.sort(key=lambda entry: (entry[1].casefold(), entry[2].casefold(), entry[0]))
            for entry in entries:
                self.items.insert('', 'end', values=entry)
            if self.preset.get() != 'All processes' and len(entries) == 1:
                item = self.items.get_children()[0]
                self.items.selection_set(item); self.pid.set(str(entries[0][0]))
            if not entries:
                self.status.set('No matching windows. Open the app and press Refresh, or use All processes / a PID.')
            elif self.preset.get() != 'All processes' and len(entries) > 1:
                self.status.set(f'{len(entries)} matches: choose the correct window. Capturing a browser window may not capture its audio process.')
            else:
                self.status.set('Select a process or enter a PID. The app remains audible on its normal output.')
        except (OSError, subprocess.CalledProcessError) as e:
            self.items.delete(*self.items.get_children()); self.pid.set('')
            messagebox.showerror('Process list', str(e))
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
            self.status.set(f'Starting PID {pid}. Press F7 in a Bodycam match. See %LOCALAPPDATA%/BDC-ZIC/stream/capture.log for errors.')
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
            self.status.set(f'Capture stopped (exit {code}). See %LOCALAPPDATA%/BDC-ZIC/stream/capture.log for details.')
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
    import tkinter as tk
    from tkinter import ttk, messagebox
    app = tk.Tk(); Panel(app); app.mainloop()
