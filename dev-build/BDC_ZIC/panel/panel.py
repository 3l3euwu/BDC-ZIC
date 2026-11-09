"""Windows-only local controller. Uses no network services or third-party packages."""
import csv
import configparser
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
        self.save_job = None
        self.ready = False
        self.effect_vars = {}
        root.title('BDC-ZIC  •  Audio Studio')
        root.geometry('1100x740'); root.minsize(850, 650)
        root.configure(bg='#10131b')
        style = ttk.Style(); style.theme_use('clam')
        style.configure('.', background='#10131b', foreground='#e9edf7', font=('Segoe UI', 10))
        style.configure('Card.TFrame', background='#191f2b')
        style.configure('Card.TLabel', background='#191f2b', foreground='#e9edf7')
        style.configure('Muted.TLabel', background='#191f2b', foreground='#a5afc3')
        style.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'), foreground='#f3f5ff')
        style.configure('Section.TLabel', background='#191f2b', font=('Segoe UI', 13, 'bold'))
        style.configure('Accent.TButton', background='#7876e8', foreground='white', padding=(14, 9), borderwidth=0)
        style.map('Accent.TButton', background=[('active', '#918ff3')])
        style.configure('TButton', background='#2b3445', foreground='#e9edf7', padding=(10, 7), borderwidth=0)
        style.map('TButton', background=[('active', '#3a465b')])
        style.configure('TCheckbutton', background='#191f2b', foreground='#e9edf7')
        style.map('TCheckbutton', background=[('active', '#191f2b')], foreground=[('active', '#ffffff')])
        style.configure('Horizontal.TScale', background='#191f2b', troughcolor='#343d50')
        style.configure('TEntry', fieldbackground='#252d3b', foreground='#ffffff', insertcolor='#ffffff')
        style.configure('TCombobox', fieldbackground='#252d3b', background='#343d50', foreground='#ffffff', arrowcolor='#ffffff')
        style.map('TCombobox', fieldbackground=[('readonly', '#252d3b')], foreground=[('readonly', '#ffffff')])
        style.configure('Treeview', background='#202735', fieldbackground='#202735', foreground='#e9edf7', rowheight=27, borderwidth=0)
        style.configure('Treeview.Heading', background='#30394b', foreground='#e9edf7', padding=6)
        style.map('Treeview', background=[('selected', '#615fc5')], foreground=[('selected', '#ffffff')])

        top = ttk.Frame(root); top.pack(fill='x', padx=24, pady=(20, 12))
        ttk.Label(top, text='BDC-ZIC', style='Title.TLabel').pack(side='left')
        ttk.Label(top, text='  /  AUDIO STUDIO', foreground='#a5afc3').pack(side='left', pady=(8, 0))
        ttk.Label(top, text='LOCAL CAPTURE  •  EXPERIMENTAL', foreground='#a5afc3').pack(side='right', pady=(10, 0))
        body = ttk.Frame(root); body.pack(fill='both', expand=True, padx=24, pady=(0, 10))
        body.columnconfigure(0, weight=5); body.columnconfigure(1, weight=4); body.rowconfigure(0, weight=1)
        source = ttk.Frame(body, style='Card.TFrame', padding=18); source.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        effects = ttk.Frame(body, style='Card.TFrame', padding=18); effects.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        ttk.Label(source, text='01   SOURCE', style='Section.TLabel').pack(anchor='w')
        ttk.Label(source, text='Choose an app window or enter a process ID.', style='Muted.TLabel').pack(anchor='w', pady=(4, 14))
        header = ttk.Frame(source, style='Card.TFrame'); header.pack(fill='x', pady=(0, 10))
        self.preset = tk.StringVar(value=PRESETS[0])
        picker = ttk.Combobox(header, textvariable=self.preset, values=PRESETS, state='readonly', width=22)
        picker.pack(side='left', fill='x', expand=True); picker.bind('<<ComboboxSelected>>', self.refresh)
        ttk.Button(header, text='Refresh', command=self.refresh).pack(side='left', padx=(8, 0))
        treeframe = ttk.Frame(source, style='Card.TFrame'); treeframe.pack(fill='both', expand=True)
        self.items = ttk.Treeview(treeframe, columns=('pid', 'name', 'title'), show='headings', height=10)
        for col, title, width in [('pid', 'PID', 70), ('name', 'Process', 130), ('title', 'Window title', 280)]:
            self.items.heading(col, text=title); self.items.column(col, width=width, minwidth=50)
        scrollbar = ttk.Scrollbar(treeframe, orient='vertical', command=self.items.yview)
        self.items.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y'); self.items.pack(side='left', fill='both', expand=True)
        self.items.bind('<<TreeviewSelect>>', self.select)
        row = ttk.Frame(source, style='Card.TFrame'); row.pack(fill='x', pady=(14, 0))
        ttk.Label(row, text='PID', style='Card.TLabel').pack(side='left')
        self.pid = tk.StringVar(); ttk.Entry(row, textvariable=self.pid, width=10).pack(side='left', padx=(8, 14))
        ttk.Button(row, text='Start capture', style='Accent.TButton', command=self.start).pack(side='left', padx=(0, 7))
        ttk.Button(row, text='Stop', command=self.stop).pack(side='left')
        ttk.Label(source, text='The selected app stays audible on its normal output.', style='Muted.TLabel', wraplength=440).pack(anchor='w', pady=(15, 0))

        ttk.Label(effects, text='02   SOUND SHAPING', style='Section.TLabel').pack(anchor='w')
        ttk.Label(effects, text='Live controls  •  processed before the game', style='Muted.TLabel').pack(anchor='w', pady=(4, 12))
        settings = self.load_effects()
        descriptions = [('reverb', 'Reverb'), ('distance', 'Distance'), ('clarity', 'Clarity'),
                        ('muffle', 'Muffle'), ('size', 'Room size'), ('stereo', 'Stereo input blend')]
        for key, label in descriptions:
            enabled = tk.BooleanVar(value=settings[key][0]); level = tk.IntVar(value=settings[key][1])
            self.effect_vars[key] = (enabled, level)
            line = ttk.Frame(effects, style='Card.TFrame'); line.pack(fill='x', pady=(0, 7))
            ttk.Checkbutton(line, text=label, variable=enabled, command=self.queue_effects).pack(anchor='w')
            slider = ttk.Frame(line, style='Card.TFrame'); slider.pack(fill='x', padx=(23, 0))
            value = tk.StringVar(value=str(level.get()))
            def update(v, var=level, display=value):
                number = max(1, min(10, int(float(v) + 0.5)))
                var.set(number); display.set(str(number)); self.queue_effects()
            scale = ttk.Scale(slider, from_=1, to=10, command=update)
            scale.set(level.get()); scale.pack(side='left', fill='x', expand=True)
            ttk.Label(slider, textvariable=value, width=3, anchor='e', style='Card.TLabel').pack(side='left', padx=(8, 0))
        ttk.Label(effects, text='Stereo adjusts L/R blend; the game stream is mono.', style='Muted.TLabel', wraplength=370).pack(anchor='w', pady=(0, 8))
        volrow = ttk.Frame(effects, style='Card.TFrame'); volrow.pack(fill='x')
        ttk.Label(volrow, text='VOLUME', style='Card.TLabel').pack(anchor='w')
        self.volume = tk.IntVar(value=settings['volume'])
        self.volume_label = tk.StringVar(value=str(settings['volume']))
        def volume_changed(v):
            n = max(1, min(10, int(float(v) + 0.5)))
            self.volume.set(n); self.volume_label.set(str(n)); self.queue_effects()
        slider = ttk.Frame(volrow, style='Card.TFrame'); slider.pack(fill='x', pady=(5, 0))
        scale = ttk.Scale(slider, from_=1, to=10, command=volume_changed); scale.set(self.volume.get()); scale.pack(side='left', fill='x', expand=True)
        ttk.Label(slider, textvariable=self.volume_label, width=3, anchor='e', style='Card.TLabel').pack(side='left', padx=(8, 0))
        ttk.Label(volrow, text='5 = normal  •  higher levels may clip', style='Muted.TLabel').pack(anchor='w', pady=(5, 0))
        self.status = tk.StringVar(value='Ready.')
        ttk.Label(root, textvariable=self.status, foreground='#b9c4d8', wraplength=1000).pack(fill='x', padx=26, pady=(0, 16))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.ready = True
        self.refresh(); self.poll()

    def load_effects(self):
        result = {key: (False, 5) for key in ('reverb', 'distance', 'clarity', 'muffle', 'size', 'stereo')}
        result['volume'] = 5
        config = configparser.ConfigParser()
        try:
            config.read(STREAM / 'effects.ini', encoding='utf-8')
            section = config['effects'] if config.has_section('effects') else {}
            for key in list(result):
                if key == 'volume':
                    result[key] = max(1, min(10, int(section.get(key, 5))))
                else:
                    enabled = int(section.get(key, 0)) > 0
                    level = max(1, min(10, int(section.get(key + '_level', section.get(key, 5)))))
                    result[key] = (enabled, level)
        except (OSError, ValueError, configparser.Error):
            pass
        return result

    def queue_effects(self):
        if not self.ready: return
        if self.save_job is not None: self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(150, self.save_effects)

    def save_effects(self):
        self.save_job = None
        try:
            STREAM.mkdir(parents=True, exist_ok=True)
            lines = ['[effects]', f'volume={self.volume.get()}']
            for key, (enabled, level) in self.effect_vars.items():
                lines.append(f'{key}={level.get() if enabled.get() else 0}')
                lines.append(f'{key}_level={level.get()}')
            tmp = STREAM / 'effects.tmp'
            tmp.write_text('\n'.join(lines) + '\n', encoding='ascii')
            os.replace(tmp, STREAM / 'effects.ini')
            return True
        except OSError as e:
            self.status.set(f'Could not save effects: {e}')
            return False

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
            if self.save_job is not None:
                self.root.after_cancel(self.save_job); self.save_job = None
            if not self.save_effects(): return
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
            if self.save_job is not None:
                self.root.after_cancel(self.save_job); self.save_job = None
            if not self.save_effects(): return
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
        if self.save_job is not None:
            self.root.after_cancel(self.save_job); self.save_effects()
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
