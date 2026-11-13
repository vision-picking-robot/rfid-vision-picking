"""RFID 태그 관제 프로그램 (Windows): 콘솔 브리지(bridge.py)를 대신하는 화면.

리더기(ACR1555U, 키보드 모드)가 이 창에 입력한 UID를 로봇 PC로 보내고(bridge.send),
인식한 상품의 사진·정보·작업 상태를 크게 띄운다. 폰 NFC·대시보드 등 다른 경로로 들어온 태그와
로봇 사이클 연결 상태도 로봇 PC(/api/v1/mobile/status)에서 받아 함께 보여 준다.
색상은 갤럭시 리모컨 앱(robot_rfid/mobile_remote_ui.py)의 다크 모드 팔레트와 같다.

    python windows_rfid_bridge/control_panel.py [--api http://192.168.0.10:8000] [--fullscreen]
"""
import argparse
import math
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont

import httpx

try:  # smooth photo scaling; without Pillow the photos are shrunk by whole-number steps
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - depends on the PC
    Image = ImageTk = None

FROZEN = getattr(sys, 'frozen', False)
HERE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
sys.path.insert(0, str(HERE))
import bridge  # noqa: E402  (same folder; also bundled into the exe)

ASSETS = HERE / 'assets' / 'products'
API_FILE = (Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent) / 'api_url.txt'
DEFAULT_API = 'http://192.168.204.52:8000'

# Galaxy remote app, dark mode (mobile_remote_ui.py): black + navy + sky blue, no other accents.
C = {
    'bg': '#05080F', 'surface': '#0D1526', 'elevated': '#121D35', 'sunken': '#080D19',
    'border': '#1A2540', 'border_strong': '#1F4E6E',
    'navy': '#1E3A8A', 'navy_900': '#0F172A', 'sky': '#38BDF8', 'sky_600': '#0284C7', 'sky_soft': '#0B2A40',
    'text': '#F8FAFC', 'text2': '#94A3B8', 'muted': '#64748B', 'danger': '#F87171', 'danger_soft': '#3A1518',
}

# Photos and fallback names, used before the robot PC answers (and when it is offline).
PRODUCTS = {
    '0B71E55D': {'photo': 'chocochip.png', 'product_name': '쫀득초코칩', 'target_box_id': 'BOX-01'},
    '0B71E75D': {'photo': 'peach_green_tea.png', 'product_name': '복숭아녹차 340ml (페트병)', 'target_box_id': 'BOX-02'},
    '0B71E65D': {'photo': 'spam.png', 'product_name': '스팸 클래식 200g', 'target_box_id': 'BOX-03'},
    '0B71ED5D': {'photo': 'wet_wipes.png', 'product_name': '물티슈', 'target_box_id': 'BOX-04'},
}
CATEGORY = {'CONFECTIONERY': '과자', 'BEVERAGE': '음료', 'CANNED': '통조림', 'SANITARY': '생활용품'}
SOURCE = {'reader': '리더기 (이 PC)', 'remote_reader': '리더기', 'phone_nfc': '갤럭시 NFC', 'voice': '음성 명령',
          'dashboard': '웹 대시보드', 'pcsc': '로봇 PC 리더기'}
STATUS = {  # result status -> badge text, colors (fg, bg)
    'sending': ('전송 중', 'text2', 'elevated'),
    'registered': ('작업 등록 · 로봇 출동', 'bg', 'sky'),
    'completed': ('피킹 완료', 'bg', 'sky'),
    'duplicate': ('이미 대기 중인 작업', 'sky', 'sky_soft'),
    'unknown': ('미등록 태그', 'danger', 'danger_soft'),
    'rejected': ('등록 거부', 'danger', 'danger_soft'),
    'offline': ('로봇 PC 연결 실패', 'danger', 'danger_soft'),
}
TASK_STATE = {'READY': '대기', 'QUEUED': '대기', 'PICKING': '피킹 중', 'COMPLETED': '완료', 'DEFECTIVE': '불량'}
ROBOT_STATE = {'IDLE': '대기', 'RUNNING': '동작 중', 'PICKING': '피킹 중', 'SCANNING': '태그 스캔 중',
               'PAUSED': '일시정지', 'ESTOPPED': '비상 정지', 'ERROR': '오류', 'BUSY': '동작 중',
               'RETURNING_HOME': '홈 복귀 중', 'SAFETY_HOLD': '작업자 접근 · 안전 정지'}
REPEAT_S = 3.0      # same tag typed again within this time (reader repeating) is skipped
KEY_IDLE_MS = 1500  # half-typed reader input is dropped after this pause

# At scale 1 the full layout needs about 1580x795 px (+4% headroom here); it is scaled to fill the real
# window (laptops 1280x720 .. 4K). tests/test_rfid_control_panel.py checks it still fits on each size.
BASE_W, BASE_H = 1640, 830
PHOTO_W, PHOTO_H = 420, 560      # live-card photo at scale 1 (thumbnails are a quarter)
FONT_PX = {  # name: (family, px at scale 1, weight)
    'eyebrow': ('mono', 12, 'bold'), 'title': ('sans', 24, 'bold'), 'card': ('sans', 15, 'bold'),
    'body': ('sans', 13, 'normal'), 'small': ('sans', 12, 'normal'), 'name': ('sans', 35, 'bold'),
    'uid': ('mono', 40, 'bold'), 'badge': ('sans', 15, 'bold'), 'key': ('sans', 13, 'normal'),
    'value': ('sans', 16, 'bold'), 'value_s': ('sans', 13, 'bold'), 'mono': ('mono', 13, 'normal'),
    'mono_s': ('mono', 12, 'normal'), 'tile': ('sans', 13, 'bold'), 'clock': ('mono', 21, 'bold'),
    'button': ('sans', 13, 'bold'),
}


def layout_scale(width, height):
    """Scale of the whole layout for a window of this size (pixels)."""
    return round(max(0.5, min(2.6, width / BASE_W, height / BASE_H)), 3)


def read_api_file():
    try:
        text = API_FILE.read_text(encoding='utf-8-sig').strip()
        return text if text.lower().startswith('http') else None
    except OSError:
        return None


def pick_font(root, *names):
    families = set(tkfont.families(root))
    return next((n for n in names if n in families), 'TkDefaultFont')


class ControlPanel:
    def __init__(self, root, api, sender=bridge.send, poll=True, screen=None):
        self.root, self.api, self.sender = root, api.rstrip('/'), sender
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.tags = {}             # tag UID -> product row from the robot PC
        self.current = None        # what the live card shows: dict(uid, task_id, status, ...)
        self.scan_seq = None       # last /api/v1/mobile/status last_scan seq seen
        self.last_uid, self.last_at = None, 0.0
        self.buffer, self.buffer_job = '', None
        self.connected = None
        # Start at the size of this screen (the window opens maximized); resizing rescales live.
        sw, sh = screen or (root.winfo_screenwidth(), root.winfo_screenheight())
        self.screen = (sw, sh)
        self.s = layout_scale(sw, sh * 0.92)  # maximized window: screen minus taskbar and title bar
        self.resize_job = None
        self._fonts()
        self._images()
        self._build()
        self._render_images()
        root.bind('<Configure>', self._on_resize, add='+')
        root.bind_all('<Key>', self.on_key)
        root.bind('<F11>', lambda e: root.attributes('-fullscreen', not root.attributes('-fullscreen')))
        root.bind('<Escape>', lambda e: root.attributes('-fullscreen', False))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.log(f'로봇 PC: {self.api}', 'muted')
        self.log('이 창이 선택된 상태에서 태그를 리더기에 찍으세요. UID를 직접 입력해도 됩니다.', 'muted')
        self._tick()
        root.after(80, self.drain)
        if poll:
            threading.Thread(target=self._poll_loop, daemon=True).start()

    # ---- look ------------------------------------------------------------------------------------
    def px(self, n):
        """A layout length (padding, wrap width) at the current scale."""
        return max(1, round(n * self.s))

    def _fonts(self):
        families = {'sans': pick_font(self.root, 'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', 'Segoe UI'),
                    'mono': pick_font(self.root, 'JetBrains Mono', 'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono',
                                      'Courier New')}
        # Negative size = pixels: the same proportions at 100/125/150 % Windows scaling.
        self.f = {name: tkfont.Font(self.root, family=families[fam], size=-self.px(size), weight=weight)
                  for name, (fam, size, weight) in FONT_PX.items()}

    def _images(self):
        """Load the product photos once; _render_images() makes the sizes the layout needs."""
        self.sources = {}
        for uid, info in PRODUCTS.items():
            path = ASSETS / info['photo']
            try:
                self.sources[uid] = Image.open(path).convert('RGB') if Image else \
                    tk.PhotoImage(master=self.root, file=str(path))
            except (OSError, tk.TclError):
                continue
        self.photos, self.thumbs = {}, {}
        self.blank = tk.PhotoImage(master=self.root, width=1, height=1)

    def _sized(self, source, width, height):
        if Image:
            return ImageTk.PhotoImage(source.resize((width, height), Image.LANCZOS), master=self.root)
        step = max(1, math.ceil(source.height() / height))  # Tk alone shrinks by whole steps; never overflow
        return source.subsample(step) if step > 1 else source

    def _render_images(self):
        w, h = self.px(PHOTO_W), self.px(PHOTO_H)
        for uid, source in self.sources.items():
            self.photos[uid] = self._sized(source, w, h)
            self.thumbs[uid] = self._sized(source, max(40, w // 4), max(54, h // 4))
        blank = tk.PhotoImage(master=self.root, width=w, height=h)
        blank.put(C['sunken'], to=(0, 0, w, h))
        self.blank = blank
        uid = (self.current or {}).get('uid')
        self.photo.config(image=self.photos.get(uid, self.blank))
        for tile_uid, tile in self.tiles.items():
            tile['img'].config(image=self.thumbs.get(tile_uid, ''))
            tile['name'].config(wraplength=self.px(150))

    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(120, self.rescale)

    def rescale(self, width=None, height=None):
        """Fit fonts and photos to the window (laptop screens differ; F11 / resize also land here)."""
        self.resize_job = None
        s = layout_scale(width or self.root.winfo_width(), height or self.root.winfo_height())
        if abs(s - self.s) < 0.02:
            return False
        self.s = s
        for name, (_, size, _) in FONT_PX.items():
            self.f[name].configure(size=-self.px(size))
        self._render_images()
        return True

    def _card(self, parent, title, right=None):
        outer = tk.Frame(parent, bg=C['surface'], highlightbackground=C['border'], highlightthickness=1)
        head = tk.Frame(outer, bg=C['surface'])
        head.pack(fill='x', padx=self.px(16), pady=(self.px(12), self.px(6)))
        tk.Label(head, text=title, font=self.f['card'], fg=C['text2'], bg=C['surface']).pack(side='left')
        label = None
        if right is not None:
            label = tk.Label(head, text=right, font=self.f['mono_s'], fg=C['muted'], bg=C['surface'])
            label.pack(side='right')
        body = tk.Frame(outer, bg=C['surface'])
        body.pack(fill='both', expand=True, padx=self.px(16), pady=(0, self.px(14)))
        return outer, body, label

    def _dot(self, parent, size, color):
        d = self.px(size)
        dot = tk.Canvas(parent, width=d, height=d, bg=parent.cget('bg'), highlightthickness=0)
        dot.create_oval(1, 1, d - 1, d - 1, fill=color, outline='', tags='dot')
        return dot

    def _pill(self, parent):
        frame = tk.Frame(parent, bg=C['surface'], highlightbackground=C['border'], highlightthickness=1)
        dot = self._dot(frame, 10, C['muted'])
        dot.pack(side='left', padx=(self.px(12), self.px(6)), pady=self.px(9))
        text = tk.Label(frame, text='', font=self.f['body'], fg=C['text'], bg=C['surface'])
        text.pack(side='left', padx=(0, self.px(14)))
        return frame, dot, text

    def _button(self, parent, text, command, primary=True):
        bg, fg = (C['sky'], C['bg']) if primary else (C['elevated'], C['text'])
        return tk.Button(parent, text=text, command=command, font=self.f['button'], bg=bg, fg=fg, bd=0,
                         activebackground=C['sky_600'], activeforeground=C['text'], relief='flat',
                         cursor='hand2', padx=self.px(16), pady=self.px(6))

    def _entry(self, parent, width):
        return tk.Entry(parent, width=width, font=self.f['mono'], bg=C['sunken'], fg=C['text'], bd=0,
                        insertbackground=C['sky'], highlightthickness=1, highlightbackground=C['border'],
                        highlightcolor=C['sky'], relief='flat')

    def _build(self):
        r = self.root
        r.title('E0509 RFID 태그 관제')
        r.configure(bg=C['bg'])
        try:
            self.icon = tk.PhotoImage(master=r, file=str(HERE / 'assets' / 'app.png'))
            r.iconphoto(True, self.icon)
            if sys.platform == 'win32':
                r.iconbitmap(default=str(HERE / 'assets' / 'app.ico'))
        except tk.TclError:
            pass
        w, h = self.screen
        # restored (non-maximized) size: most of the screen; main() opens it maximized
        r.geometry(f'{int(w * 0.9)}x{int(h * 0.85)}+{int(w * 0.05)}+{int(h * 0.04)}')
        r.minsize(min(960, w), min(560, h))
        pad = self.px(22)

        # header
        head = tk.Frame(r, bg=C['bg'])
        head.pack(fill='x', padx=pad, pady=(self.px(18), self.px(12)))
        brand = tk.Frame(head, bg=C['bg'])
        brand.pack(side='left')
        tk.Label(brand, text='E0509 VISION PICKING  ·  RFID TAG CONTROL', font=self.f['eyebrow'],
                 fg=C['sky'], bg=C['bg']).pack(anchor='w')
        tk.Label(brand, text='태그 인식 관제', font=self.f['title'], fg=C['text'], bg=C['bg']).pack(anchor='w')
        self.clock = tk.Label(head, text='', font=self.f['clock'], fg=C['text'], bg=C['bg'])
        self.clock.pack(side='right', padx=(self.px(14), 0))
        pill, self.robot_dot, self.robot_text = self._pill(head)
        pill.pack(side='right', padx=(self.px(10), 0))
        pill, self.server_dot, self.server_text = self._pill(head)
        pill.pack(side='right')
        self.robot_text.config(text='로봇 사이클  확인 중')
        self.server_text.config(text='로봇 PC  확인 중')

        # body
        body = tk.Frame(r, bg=C['bg'])
        # footer first: packed before the body so a short window squeezes the body, never the footer
        foot = tk.Frame(r, bg=C['surface'], highlightbackground=C['border'], highlightthickness=1)
        foot.pack(side='bottom', fill='x', padx=pad, pady=(self.px(14), self.px(18)))
        self.reader_dot = self._dot(foot, 12, C['sky'])
        self.reader_dot.pack(side='left', padx=(self.px(16), self.px(8)), pady=self.px(14))
        self.reader_text = tk.Label(foot, text='리더기 입력 대기', font=self.f['body'], fg=C['text'], bg=C['surface'])
        self.reader_text.pack(side='left')
        self.buffer_label = tk.Label(foot, text='', font=self.f['mono'], fg=C['sky'], bg=C['surface'])
        self.buffer_label.pack(side='left', padx=self.px(10))

        self._button(foot, '연결', self.change_api, primary=False).pack(side='right', padx=(self.px(6), self.px(16)))
        self.api_entry = self._entry(foot, 26)
        self.api_entry.insert(0, self.api)
        self.api_entry.pack(side='right', ipady=self.px(5))
        self.api_entry.bind('<Return>', lambda e: self.change_api())
        tk.Label(foot, text='로봇 PC', font=self.f['small'], fg=C['text2'], bg=C['surface']).pack(
            side='right', padx=self.px(8))

        self._button(foot, '전송', self.send_manual).pack(side='right', padx=(self.px(6), self.px(22)))
        self.manual = self._entry(foot, 12)
        self.manual.pack(side='right', ipady=self.px(5))
        self.manual.bind('<Return>', lambda e: self.send_manual())
        tk.Label(foot, text='UID 직접 입력', font=self.f['small'], fg=C['text2'], bg=C['surface']).pack(
            side='right', padx=self.px(8))

        # body
        body.pack(fill='both', expand=True, padx=pad)
        body.columnconfigure(0, weight=3, uniform='col')
        body.columnconfigure(1, weight=2, uniform='col')
        body.rowconfigure(0, weight=1)
        self._build_live(body)
        right = tk.Frame(body, bg=C['bg'])
        right.grid(row=0, column=1, sticky='nsew', padx=(self.px(14), 0))
        self._build_tiles(right)
        self._build_log(right)

    def _build_live(self, parent):
        self.live, body, self.live_meta = self._card(parent, '최근 인식 태그', right='-')
        self.live.grid(row=0, column=0, sticky='nsew')
        self.photo = tk.Label(body, image=self.blank, text='TAG\nSTANDBY', compound='center', font=self.f['card'],
                              fg=C['muted'], bg=C['sunken'], bd=0)
        self.photo.pack(side='left', anchor='n', pady=(self.px(4), 0))
        info = tk.Frame(body, bg=C['surface'])
        info.pack(side='left', fill='both', expand=True, padx=(self.px(22), 0), pady=(self.px(4), 0))
        self.badge = tk.Label(info, text='  태그 대기  ', font=self.f['badge'], fg=C['text2'], bg=C['elevated'],
                              padx=self.px(10), pady=self.px(4))
        self.badge.pack(anchor='w')
        self.name = tk.Label(info, text='리더기에 태그를 찍어 주세요', font=self.f['name'], fg=C['text'],
                             bg=C['surface'], anchor='w', justify='left', wraplength=self.px(440))
        self.name.pack(anchor='w', fill='x', pady=(self.px(14), self.px(2)))
        self.uid = tk.Label(info, text='UID 대기 중', font=self.f['uid'], fg=C['muted'], bg=C['surface'], anchor='w')
        self.uid.pack(anchor='w')
        grid = tk.Frame(info, bg=C['surface'])
        grid.pack(anchor='w', fill='x', pady=(self.px(18), 0))
        self.fields = {}
        rows = [('box', '목적지 박스'), ('sku', 'SKU'), ('category', '분류'), ('price', '가격'),
                ('inbound', '입고일'), ('expired', '유통기한'), ('task', '작업 ID'), ('state', '작업 상태')]
        for i, (key, label) in enumerate(rows):
            cell = tk.Frame(grid, bg=C['elevated'], highlightbackground=C['border'], highlightthickness=1)
            cell.grid(row=i // 2, column=i % 2, sticky='nsew', padx=(0, self.px(8)), pady=(0, self.px(8)))
            tk.Label(cell, text=label, font=self.f['key'], fg=C['text2'], bg=C['elevated']).pack(
                anchor='w', padx=self.px(12), pady=(self.px(8), 0))
            value = tk.Label(cell, text='-', font=self.f['value_s' if key == 'sku' else 'value'], fg=C['text'],
                             bg=C['elevated'], anchor='w')
            value.pack(anchor='w', fill='x', padx=self.px(12), pady=(0, self.px(9)))
            self.fields[key] = value
        grid.columnconfigure(0, weight=1, uniform='f')
        grid.columnconfigure(1, weight=1, uniform='f')
        self.message = tk.Label(info, text='', font=self.f['body'], fg=C['text2'], bg=C['surface'], anchor='w',
                                justify='left', wraplength=self.px(380))
        self.message.pack(anchor='w', fill='x', pady=(self.px(6), 0))
        # wrap to the column's real width (it changes with the window and the screen scale)
        info.bind('<Configure>', lambda e: (self.message.config(wraplength=max(160, e.width - 8)),
                                            self.name.config(wraplength=max(160, e.width - 8))))

    def _build_tiles(self, parent):
        card, body, _ = self._card(parent, '등록 상품', right='TAG UID → BOX')
        card.pack(fill='x')
        self.tiles = {}
        for i, (uid, info) in enumerate(PRODUCTS.items()):
            tile = tk.Frame(body, bg=C['elevated'], highlightbackground=C['border'], highlightthickness=1)
            tile.grid(row=i // 2, column=i % 2, sticky='nsew', padx=(0, self.px(8)) if i % 2 == 0 else (0, 0),
                      pady=(0, self.px(8)))
            img = tk.Label(tile, bg=C['sunken'], bd=0)
            if uid not in self.sources:
                img.config(text='NO PHOTO', fg=C['muted'], width=14, height=8)
            img.pack(side='left', padx=self.px(8), pady=self.px(8))
            text = tk.Frame(tile, bg=C['elevated'])
            text.pack(side='left', fill='both', expand=True, pady=self.px(8), padx=(0, self.px(8)))
            name = tk.Label(text, text=info['product_name'], font=self.f['tile'], fg=C['text'], bg=C['elevated'],
                            anchor='w', justify='left', wraplength=self.px(150))
            name.pack(anchor='w')
            tk.Label(text, text=uid, font=self.f['mono_s'], fg=C['sky'], bg=C['elevated']).pack(
                anchor='w', pady=(self.px(4), 0))
            box = tk.Label(text, text=info['target_box_id'], font=self.f['small'], fg=C['text2'], bg=C['elevated'])
            box.pack(anchor='w')
            count = tk.Label(text, text='', font=self.f['small'], fg=C['muted'], bg=C['elevated'])
            count.pack(anchor='w', side='bottom')
            self.tiles[uid] = {'frame': tile, 'img': img, 'name': name, 'box': box, 'count': count, 'n': 0}
        body.columnconfigure(0, weight=1, uniform='t')
        body.columnconfigure(1, weight=1, uniform='t')

    def _build_log(self, parent):
        card, body, _ = self._card(parent, '이벤트 로그')
        card.pack(fill='both', expand=True, pady=(self.px(14), 0))
        self.log_box = tk.Text(body, font=self.f['mono_s'], bg=C['sunken'], fg=C['text2'], bd=0, wrap='word',
                               highlightthickness=0, padx=self.px(10), pady=self.px(8), height=3, width=10,
                               state='disabled',  # width/height are minimums; it fills the card
                               cursor='arrow')
        self.log_box.pack(fill='both', expand=True)
        for tag, color in (('time', C['muted']), ('ok', C['sky']), ('err', C['danger']), ('muted', C['muted']),
                           ('info', C['text2'])):
            self.log_box.tag_configure(tag, foreground=color)

    # ---- state -----------------------------------------------------------------------------------
    def log(self, message, kind=None):
        kind = kind or ('ok' if message.startswith('O ') else 'err' if message.startswith('X ') else 'info')
        self.log_box.config(state='normal')
        self.log_box.insert('end', time.strftime('%H:%M:%S  '), 'time')
        self.log_box.insert('end', message.strip() + '\n', kind)
        if int(self.log_box.index('end-1c').split('.')[0]) > 400:
            self.log_box.delete('1.0', '50.0')
        self.log_box.see('end')
        self.log_box.config(state='disabled')

    def _set_dot(self, canvas, color):
        canvas.itemconfigure('dot', fill=color)

    def _tick(self):
        self.clock.config(text=time.strftime('%H:%M:%S'))
        self.root.after(1000, self._tick)

    def product_for(self, uid, product=None):
        merged = dict(PRODUCTS.get(uid or '', {}))
        merged.update(self.tags.get(uid or '', {}))
        merged.update({k: v for k, v in (product or {}).items() if v is not None})
        return merged

    def show(self, uid, status, *, product=None, task=None, message='', source='reader', raw=None):
        """Put one tag read on the live card (and highlight its tile)."""
        info = self.product_for(uid, product)
        self.current = {'uid': uid, 'task_id': (task or {}).get('task_id'), 'status': status}
        text, fg, bg = STATUS.get(status, STATUS['rejected'])
        self.badge.config(text=f'  {text}  ', fg=C[fg], bg=C[bg])
        self.photo.config(image=self.photos.get(uid, self.blank),
                          text='' if uid in self.photos else ('SENDING' if status == 'sending' else
                                                              'UNKNOWN\nTAG' if status in ('unknown', 'rejected')
                                                              else 'NO PHOTO'))
        self.name.config(text=info.get('product_name') or '등록되지 않은 태그')
        self.uid.config(text=uid or raw or '-', fg=C['sky'] if uid else C['danger'])
        price = info.get('retail_price')
        values = {
            'box': info.get('target_box_id'), 'sku': info.get('sku_code'),
            'category': CATEGORY.get(info.get('category'), info.get('category')),
            'price': f'{price:,}원' if isinstance(price, int) else None,
            'inbound': (info.get('inbound_at') or '')[:10] or None, 'expired': (info.get('expired_at') or '')[:10] or None,
            'task': ((task or {}).get('task_id') or '')[:8] or None,
            'state': TASK_STATE.get((task or {}).get('status'), (task or {}).get('status')),
        }
        if status == 'completed':
            values['state'] = '완료'
        for key, value in values.items():
            self.fields[key].config(text=value or '-')
        self.message.config(text=message or '', fg=C['danger'] if status in ('unknown', 'rejected', 'offline')
                            else C['text2'])
        self.live_meta.config(text=f'{SOURCE.get(source, source)}  ·  {datetime.now():%H:%M:%S}')
        for tile_uid, tile in self.tiles.items():
            active = tile_uid == uid
            tile['frame'].config(highlightbackground=C['sky'] if active else C['border'],
                                 highlightthickness=2 if active else 1)
        if uid in self.tiles and status in ('registered', 'duplicate'):
            tile = self.tiles[uid]
            tile['n'] += status == 'registered'
            tile['count'].config(text=f'오늘 {tile["n"]}회 출동' if tile['n'] else '')
        self._flash(C['danger'] if status in ('unknown', 'rejected', 'offline') else C['sky'])

    def _flash(self, color):
        self.live.config(highlightbackground=color, highlightthickness=2)
        self.root.after(1400, lambda: self.live.config(highlightbackground=C['border'], highlightthickness=1))

    # ---- input -----------------------------------------------------------------------------------
    def on_key(self, event):
        if isinstance(event.widget, tk.Entry):
            return None  # typing an address or a manual UID
        if event.keysym in ('Return', 'KP_Enter'):
            raw, self.buffer = self.buffer, ''
            self._show_buffer()
            if raw:
                self.submit(raw)
            return 'break'
        ch = (event.char or '').upper()
        if ch and ch in '0123456789ABCDEF':
            self.buffer = (self.buffer + ch)[-32:]
            self._show_buffer()
            if self.buffer_job:
                self.root.after_cancel(self.buffer_job)
            self.buffer_job = self.root.after(KEY_IDLE_MS, self._drop_buffer)
        return None

    def _drop_buffer(self):
        self.buffer, self.buffer_job = '', None
        self._show_buffer()

    def _show_buffer(self):
        self.buffer_label.config(text=self.buffer)
        self.reader_text.config(text='리더기 입력 중' if self.buffer else '리더기 입력 대기')

    def send_manual(self):
        raw = self.manual.get()
        self.manual.delete(0, 'end')
        self.root.focus_set()  # back to reader input
        if raw.strip():
            self.submit(raw)

    def change_api(self):
        api = self.api_entry.get().strip().rstrip('/')
        if not api.lower().startswith('http'):
            api = 'http://' + api
        self.api = api
        self.api_entry.delete(0, 'end')
        self.api_entry.insert(0, api)
        self.tags, self.scan_seq, self.connected = {}, None, None
        try:
            API_FILE.write_text(api + '\n', encoding='utf-8')
        except OSError as error:
            self.log(f'X 주소 저장 실패: {error}')
        self.log(f'로봇 PC 주소 변경: {api}', 'muted')
        self.root.focus_set()

    def submit(self, line):
        raw = bridge.clean_uid(line)
        if len(raw) < 4:
            self.log(f'X 너무 짧은 값입니다: {line.strip()!r} (4글자 이상 필요). 태그를 다시 찍어 주세요.')
            return False
        now = time.monotonic()
        if raw == self.last_uid and now - self.last_at < REPEAT_S:
            self.log(f'같은 태그 반복 입력이라 건너뜁니다: {raw}', 'muted')
            return False
        self.last_uid, self.last_at = raw, now
        self.log(f'입력 UID: {raw}' + ('' if len(raw) >= 8 else '  (일부만 입력됨, 로봇 PC DB에서 매칭)'))
        known = raw if raw in PRODUCTS else None
        self.show(known, 'sending', raw=raw, message='로봇 PC로 전송하고 있습니다.')
        api = self.api
        threading.Thread(target=lambda: self.events.put(
            ('result', self.sender(api, raw, 1, log=lambda m: self.events.put(('log', m))))), daemon=True).start()
        return True

    def apply_result(self, result):
        status = result.get('status', 'rejected')
        uid = result.get('uid') or (result.get('product') or {}).get('tag_uid')
        message = {
            'registered': f'{self.product_for(uid, result.get("product")).get("target_box_id", "박스")}로 담을 작업을 '
                          '등록했습니다. 로봇이 집으러 갑니다.',
            'duplicate': '같은 상품의 작업이 이미 대기/진행 중이라 새로 등록하지 않았습니다.',
            'unknown': '등록되지 않은 태그입니다. 로봇 PC DB에 이 UID의 상품이 없어 작업을 만들지 않았습니다.',
            'offline': f'로봇 PC에 연결할 수 없습니다: {result.get("message", "")[:120]}',
        }.get(status, result.get('message', ''))
        if status in ('unknown', 'rejected', 'offline'):
            self.last_uid = None  # let the operator retry the same tag right away
        self.show(uid, status, product=result.get('product'), task=result.get('task'), message=message,
                  raw=result.get('raw_uid'))

    # ---- robot PC status -------------------------------------------------------------------------
    def _poll_loop(self):
        tags_at = 0.0
        while not self.stop.is_set():
            api = self.api
            try:
                status = httpx.get(f'{api}/api/v1/mobile/status', timeout=3).json()
                if not self.tags or time.monotonic() - tags_at > 30:
                    tags = httpx.get(f'{api}/api/v1/tags', timeout=3).json().get('tags', [])
                    self.events.put(('tags', tags))
                    tags_at = time.monotonic()
                self.events.put(('status', (api, status)))
            except Exception as error:  # noqa: BLE001
                self.events.put(('offline', (api, str(error))))
            self.stop.wait(1.5)

    def apply_status(self, status):
        if not self.connected:
            self.log(f'O 로봇 PC 연결 성공: {self.api}')
        self.connected = True
        self._set_dot(self.server_dot, C['sky'])
        self.server_text.config(text=f'로봇 PC  {self.api.split("//")[-1]}')
        link = status.get('robot_link') or {}
        if status.get('emergency_stopped'):
            color, text = C['danger'], '비상 정지'
        elif status.get('safety_hold'):
            color, text = C['danger'], '작업자 접근 · 안전 정지'
        elif status.get('robot_connected'):
            color, text = C['sky'], ROBOT_STATE.get(link.get('state'), link.get('state') or '연결됨')
            if status.get('paused'):
                text = '일시정지'
        else:
            color, text = C['muted'], '미연결'
        self._set_dot(self.robot_dot, color)
        self.robot_text.config(text=f'로봇 사이클  {text}', fg=C['danger'] if color == C['danger'] else C['text'])
        scan = status.get('last_scan') or {}
        seq = status.get('scan_seq', scan.get('seq'))
        if self.scan_seq is None:
            self.scan_seq = seq  # reads from before this program started are not shown
        elif seq != self.scan_seq and scan:
            self.scan_seq = seq
            if scan.get('source') != 'remote_reader':  # reads from this program are shown already
                self.log(f'{SOURCE.get(scan.get("source"), scan.get("source"))}에서 태그 인식: '
                         f'{scan.get("uid") or scan.get("raw_uid")} {scan.get("product_name") or ""}'.rstrip(),
                         'ok' if scan.get('accepted') else 'err')
                self.show(scan.get('uid'), 'registered' if scan.get('accepted') else 'unknown',
                          task={'task_id': scan.get('task_id'), 'status': 'READY' if scan.get('task_id') else None},
                          source=scan.get('source'), raw=scan.get('raw_uid'),
                          message=scan.get('error') or '')
        done = status.get('last_completed_event') or {}
        if self.current and self.current.get('task_id') and done.get('task_id') == self.current['task_id'] \
                and self.current['status'] != 'completed':
            self.current['status'] = 'completed'
            text, fg, bg = STATUS['completed']
            self.badge.config(text=f'  {text}  ', fg=C[fg], bg=C[bg])
            self.fields['state'].config(text='완료')
            self.message.config(text='로봇이 상품을 박스에 담았습니다.', fg=C['text2'])
            self.log(f'O 피킹 완료: {self.name.cget("text")}')

    def apply_offline(self, error):
        if self.connected is not False:
            self.log(f'X 로봇 PC 연결 실패: {self.api} -> {error[:120]}')
            self.log('  로봇 PC에서 start_lab.py --host 0.0.0.0 실행 여부, 같은 네트워크, 방화벽(8000), 아래 주소를 확인하세요.',
                     'muted')
        self.connected = False
        self._set_dot(self.server_dot, C['danger'])
        self.server_text.config(text='로봇 PC  연결 실패')
        self._set_dot(self.robot_dot, C['muted'])
        self.robot_text.config(text='로봇 사이클  -', fg=C['text'])

    def apply_tags(self, tags):
        self.tags = {t['tag_uid']: t for t in tags if t.get('tag_uid')}
        for uid, tile in self.tiles.items():
            info = self.product_for(uid)
            tile['name'].config(text=info.get('product_name', ''))
            tile['box'].config(text=info.get('target_box_id', ''))

    def drain(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.log(value)
                elif kind == 'result':
                    self.apply_result(value)
                elif kind == 'tags':
                    self.apply_tags(value)
                elif kind in ('status', 'offline'):
                    api, data = value
                    if api == self.api:  # ignore answers for an address that was just changed
                        (self.apply_status if kind == 'status' else self.apply_offline)(data)
        except queue.Empty:
            pass
        if not self.stop.is_set():
            self.root.after(80, self.drain)

    def close(self):
        self.stop.set()
        self.root.destroy()


def enable_dpi_awareness():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass


def maximize(root):
    try:
        root.state('zoomed')  # Windows
    except tk.TclError:
        try:
            root.attributes('-zoomed', True)  # Linux
        except tk.TclError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description='RFID 태그 관제 (리더기 UID -> 로봇 PC)')
    parser.add_argument('--api', help=f'로봇 PC 주소 (기본: api_url.txt, 없으면 {DEFAULT_API})')
    parser.add_argument('--fullscreen', action='store_true', help='전체 화면으로 시작 (F11 전환, Esc 해제)')
    args = parser.parse_args(argv)
    api = args.api or read_api_file() or DEFAULT_API
    enable_dpi_awareness()
    root = tk.Tk()
    ControlPanel(root, api)
    if args.fullscreen:
        root.attributes('-fullscreen', True)
    else:
        maximize(root)  # fills any laptop screen; the layout scales to it (see layout_scale)
    root.focus_force()
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
