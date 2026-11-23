
"""TextTone Studio | NOIR & GOLD
One-file desktop app for Spyder. Requires nltk and the VADER lexicon.
"""
from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# COLOR SYSTEM
BLACK = '#08090C'
SIDEBAR = '#0D0F14'
PANEL = '#14171D'
PANEL2 = '#1C2028'
FIELD = '#101318'
STROKE = '#34302A'
GOLD = '#D6B36A'
CHAMPAGNE = '#F5DEAA'
DIM_GOLD = '#8F7952'
TEXT = '#F8F5ED'
MUTED = '#A9A49A'
GREEN = '#71D6AE'
RED = '#F08991'
NEUTRAL = '#D8C188'
FONT = 'Helvetica'
MAX_LENGTH = 2000
DB_FILE = Path.home() / 'TextToneStudio' / 'texttone_history.sqlite3'


@dataclass(frozen=True)
class AnalysisResult:
    text: str
    score: float
    category: str
    explanation: str
    emoji: str = ''
    created_at: str = ''
    record_id: int | None = None

    def __post_init__(self):
        if not self.text.strip():
            raise ValueError('Please type a message first.')
        if len(self.text.strip()) > MAX_LENGTH:
            raise ValueError('Your message must contain at most 2,000 characters.')
        if not -1 <= self.score <= 1:
            raise ValueError('Sentiment score must be between -1 and +1.')
        if self.category not in ('Positive', 'Neutral', 'Negative'):
            raise ValueError('Unrecognized sentiment category.')


class TextAnalyzer(ABC):
    @abstractmethod
    def analyze(self, text: str) -> AnalysisResult:
        """Return a sentiment result for text."""


class VaderSentimentAnalyzer(TextAnalyzer):
    """Replaceable sentiment analyzer: inheritance and polymorphism."""
    def __init__(self):
        try:
            import nltk
            from nltk.sentiment import SentimentIntensityAnalyzer
        except ImportError as error:
            raise RuntimeError('NLTK is missing. Install it in the Spyder Python environment.') from error
        try:
            self._model = SentimentIntensityAnalyzer()
        except LookupError:
            if not nltk.download('vader_lexicon', quiet=True):
                raise RuntimeError('VADER lexicon download failed. Check internet access.')
            self._model = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> AnalysisResult:
        clean = text.strip()
        if not clean:
            raise ValueError('Please type a message first.')
        if len(clean) > MAX_LENGTH:
            raise ValueError('Maximum length is 2,000 characters.')
        score = float(self._model.polarity_scores(clean)['compound'])
        if score >= 0.05:
            category = 'Positive'
        elif score <= -0.05:
            category = 'Negative'
        else:
            category = 'Neutral'
        notes = {
            'Positive': 'This message reads as upbeat, warm or encouraging.',
            'Neutral': 'This message reads as balanced or largely factual.',
            'Negative': 'This message reads as disappointed, critical or upset.',
        }
        return AnalysisResult(clean, score, category, notes[category])


class EmojiRecommender:
    """Keeps emoji recommendation rules separate from the interface."""
    def suggest(self, result: AnalysisResult) -> list[str]:
        strong = abs(result.score) >= 0.6
        if result.category == 'Positive':
            return ['🥳', '🤩', '✨', '😍', '🎉'] if strong else ['😊', '💛', '🙂', '🌟', '👍']
        if result.category == 'Negative':
            return ['😢', '💔', '😠', '😣', '😫'] if strong else ['😕', '😔', '💭', '😟', '😞']
        return ['😐', '🤔', '🤍', '👌', '📝']


class HistoryRepository:
    """Encapsulates all SQLite CRUD and summary queries."""
    def __init__(self, filename=DB_FILE):
        self._filename = Path(filename)
        self._filename.parent.mkdir(parents=True, exist_ok=True)
        with self._open() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL, score REAL NOT NULL,
                category TEXT NOT NULL, explanation TEXT NOT NULL,
                emoji TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def _open(self):
        connection = sqlite3.connect(str(self._filename), timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, item: AnalysisResult) -> int:
        time = datetime.now().astimezone().isoformat(timespec='seconds')
        with self._open() as connection:
            cursor = connection.execute('''INSERT INTO analyses
                (text, score, category, explanation, emoji, created_at)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (item.text, item.score, item.category, item.explanation, item.emoji, time))
            return int(cursor.lastrowid)

    def find(self, search='') -> list[AnalysisResult]:
        with self._open() as connection:
            rows = connection.execute('SELECT * FROM analyses ORDER BY id DESC').fetchall()
        return [AnalysisResult(row['text'], row['score'], row['category'],
                               row['explanation'], row['emoji'], row['created_at'], row['id'])
                for row in rows if search.casefold() in row['text'].casefold()]

    def delete(self, record_id: int):
        with self._open() as connection:
            connection.execute('DELETE FROM analyses WHERE id = ?', (record_id,))

    def clear(self):
        with self._open() as connection:
            connection.execute('DELETE FROM analyses')

    def summary(self, days=None) -> dict[str, int]:
        counts = {'Positive': 0, 'Neutral': 0, 'Negative': 0}
        sql = 'SELECT category, COUNT(*) AS number FROM analyses'
        parameters = ()
        if days is not None:
            cutoff = (datetime.now().astimezone() - timedelta(days=days)).isoformat(timespec='seconds')
            sql += ' WHERE created_at >= ?'
            parameters = (cutoff,)
        sql += ' GROUP BY category'
        with self._open() as connection:
            for row in connection.execute(sql, parameters):
                if row['category'] in counts:
                    counts[row['category']] = row['number']
        return counts


class GoldButton(tk.Canvas):
    """Custom-drawn button; avoids macOS native Tk button recoloring."""
    def __init__(self, parent, text, command, *, filled=False, width=160,
                 height=42, bg=PANEL, danger=False):
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor='hand2')
        self.command = command
        self.label_text = text
        self.filled = filled
        self.danger = danger
        self.hover = False
        self.bind('<Button-1>', lambda event: self.command())
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Configure>', lambda event: self._paint())
        self._paint()

    def _enter(self, event):
        self.hover = True
        self._paint()

    def _leave(self, event):
        self.hover = False
        self._paint()

    def _paint(self):
        self.delete('all')
        w = max(self.winfo_width(), int(self['width']))
        h = max(self.winfo_height(), int(self['height']))
        if self.danger:
            fill, fg, edge = ('#47252C' if self.hover else '#291B20'), '#FFD7D9', '#81545A'
        elif self.filled:
            fill = CHAMPAGNE if self.hover else GOLD
            fg, edge = BLACK, fill
        else:
            fill, fg, edge = (PANEL2 if self.hover else PANEL), CHAMPAGNE, DIM_GOLD
        self.create_rectangle(1, 1, w-2, h-2, fill=fill, outline=edge, width=1)
        self.create_text(w/2, h/2, text=self.label_text, fill=fg,
                         font=(FONT, 10, 'bold'))


def ui_label(parent, text, size=11, color=TEXT, weight='normal', **kwargs):
    return tk.Label(parent, text=text, fg=color, bg=parent.cget('bg'),
                    font=(FONT, size, weight), **kwargs)


def panel(parent, *, bg=PANEL, pad=20):
    frame = tk.Frame(parent, bg=bg, highlightbackground=STROKE,
                     highlightthickness=1, padx=pad, pady=pad)
    return frame


class TextToneApp:
    def __init__(self, root, analyzer, recommender, history):
        self.root = root
        self.analyzer = analyzer
        self.recommender = recommender
        self.history = history
        self.current = None
        self.emoji = ''
        self.suggestions = []
        self.records = {}
        self.counts = {'Positive': 0, 'Neutral': 0, 'Negative': 0}
        self.search_value = tk.StringVar()
        self.period_value = tk.StringVar(value='All time')
        self.status = tk.StringVar(value='●  Private, local sentiment analysis  ·  Ready')
        self.root.title('TEXTTONE  |  NOIR & GOLD')
        self.root.geometry('1190x790')
        self.root.minsize(1020, 690)
        self.root.configure(bg=BLACK)
        self._styles()
        self._layout()
        self.refresh_history()
        self.refresh_dashboard()

    def _styles(self):
        s = ttk.Style(self.root)
        if 'clam' in s.theme_names():
            s.theme_use('clam')
        s.configure('Gold.Treeview', background=PANEL, fieldbackground=PANEL,
                    foreground=TEXT, rowheight=40, font=(FONT, 10), borderwidth=0)
        s.configure('Gold.Treeview.Heading', background=PANEL2, foreground=CHAMPAGNE,
                    font=(FONT, 10, 'bold'), padding=10)
        s.map('Gold.Treeview', background=[('selected', '#62502F')],
              foreground=[('selected', TEXT)])

    def _layout(self):
        frame = tk.Frame(self.root, bg=BLACK)
        frame.pack(fill='both', expand=True)
        sidebar = tk.Frame(frame, bg=SIDEBAR, width=248)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=GOLD, height=3).pack(fill='x')
        ui_label(sidebar, '✦', 30, GOLD).pack(anchor='w', padx=26, pady=(30, 4))
        ui_label(sidebar, 'TEXTTONE', 22, CHAMPAGNE, 'bold').pack(anchor='w', padx=26)
        ui_label(sidebar, 'S T U D I O', 10, DIM_GOLD, 'bold').pack(anchor='w', padx=28, pady=(0, 30))
        ui_label(sidebar, 'THE COLLECTION', 9, MUTED, 'bold').pack(anchor='w', padx=26, pady=(0, 12))
        self.nav = {}
        for page, title in [('analyze', '✦   Sentiment Studio'),
                            ('history', '▤   My Collection'),
                            ('dashboard', '◫   Mood Insights')]:
            item = tk.Label(sidebar, text=title, anchor='w', bg=SIDEBAR, fg=MUTED,
                            padx=26, pady=17, cursor='hand2', font=(FONT, 11, 'bold'))
            item.pack(fill='x', pady=3)
            item.bind('<Button-1>', lambda event, key=page: self.show(key))
            self.nav[page] = item
        tk.Frame(sidebar, bg=STROKE, height=1).pack(fill='x', padx=22, pady=30)
        ui_label(sidebar, 'PRIVATE BY DESIGN', 9, GOLD, 'bold').pack(anchor='w', padx=26)
        ui_label(sidebar, 'No cloud. No account.\nYour words stay with you.',
                 10, MUTED, justify='left').pack(anchor='w', padx=26, pady=(9, 0))
        ui_label(sidebar, '✦  NOIR / GOLD  ·  2026', 9, DIM_GOLD).pack(side='bottom', padx=26, pady=25)

        main = tk.Frame(frame, bg=BLACK)
        main.pack(side='left', fill='both', expand=True)
        header = tk.Frame(main, bg=BLACK, padx=30, pady=21)
        header.pack(fill='x')
        ui_label(header, 'THE ART OF EMOTION', 10, GOLD, 'bold').pack(anchor='w')
        ui_label(header, 'Every message has a mood.', 23, TEXT, 'bold').pack(anchor='w', pady=(6, 2))
        ui_label(header, 'A refined space to understand your words and express them beautifully.',
                 10, MUTED).pack(anchor='w')
        tk.Frame(main, bg=GOLD, height=1).pack(fill='x', padx=30)
        self.content = tk.Frame(main, bg=BLACK, padx=30, pady=20)
        self.content.pack(fill='both', expand=True)
        self.pages = {name: tk.Frame(self.content, bg=BLACK)
                      for name in ('analyze', 'history', 'dashboard')}
        self._build_analyze()
        self._build_history()
        self._build_dashboard()
        footer = tk.Frame(main, bg=SIDEBAR, padx=30, pady=10)
        footer.pack(fill='x')
        tk.Label(footer, textvariable=self.status, fg=MUTED, bg=SIDEBAR,
                 font=(FONT, 9)).pack(anchor='w')
        self.show('analyze')

    def show(self, name):
        for key, page in self.pages.items():
            page.pack_forget()
            self.nav[key].configure(bg=PANEL2 if key == name else SIDEBAR,
                                    fg=CHAMPAGNE if key == name else MUTED)
        self.pages[name].pack(fill='both', expand=True)
        if name == 'history':
            self.refresh_history()
        if name == 'dashboard':
            self.refresh_dashboard()

    def _build_analyze(self):
        page = self.pages['analyze']
        card = panel(page, pad=22)
        card.pack(fill='x', pady=(0, 14))
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill='x')
        ui_label(head, '01  /  WRITE YOUR MESSAGE', 11, GOLD, 'bold').pack(side='left')
        ui_label(head, '✦    💌    ✨', 17, DIM_GOLD).pack(side='right')
        ui_label(card, 'What is on your mind?', 18, TEXT, 'bold').pack(anchor='w', pady=(8, 11))
        self.input = tk.Text(card, height=4, bg=FIELD, fg=TEXT, insertbackground=GOLD,
                             selectbackground='#6E5837', font=(FONT, 12),
                             relief='flat', wrap='word', padx=14, pady=12,
                             highlightbackground=STROKE, highlightthickness=1)
        self.input.pack(fill='x')
        self.input.bind('<KeyRelease>', self._count)
        controls = tk.Frame(card, bg=PANEL)
        controls.pack(fill='x', pady=(13, 0))
        GoldButton(controls, '✦   ANALYZE TONE', self.analyze,
                   filled=True, width=175, bg=PANEL).pack(side='left')
        GoldButton(controls, 'CLEAR', self.clear, width=95,
                   bg=PANEL).pack(side='left', padx=9)
        self.counter = ui_label(controls, '0 / 2000', 10, MUTED)
        self.counter.pack(side='right')

        result = panel(page, pad=22)
        result.pack(fill='both', expand=True)
        header = tk.Frame(result, bg=PANEL)
        header.pack(fill='x')
        ui_label(header, '02  /  THE VERDICT', 11, GOLD, 'bold').pack(side='left')
        ui_label(header, '✧  MOOD READING', 9, DIM_GOLD, 'bold').pack(side='right')
        top = tk.Frame(result, bg=PANEL)
        top.pack(fill='x', pady=(12, 0))
        self.mood = ui_label(top, 'AWAITING YOUR WORDS', 20, CHAMPAGNE, 'bold')
        self.mood.pack(side='left')
        self.score = ui_label(top, '—', 18, GOLD, 'bold')
        self.score.pack(side='right')
        self.explanation = ui_label(result, 'Enter a message above to reveal its sentiment.',
                                    10, MUTED)
        self.explanation.pack(anchor='w', pady=(5, 12))
        self.gauge = tk.Canvas(result, height=51, bg=PANEL, highlightthickness=0)
        self.gauge.pack(fill='x', pady=(0, 8))
        self.gauge.bind('<Configure>', lambda event: self._draw_gauge())
        tk.Frame(result, bg=STROKE, height=1).pack(fill='x', pady=(6, 14))
        ui_label(result, '03  /  THE PERFECT EMOJI', 11, GOLD, 'bold').pack(anchor='w')
        self.emoji_row = tk.Frame(result, bg=PANEL)
        self.emoji_row.pack(anchor='w', pady=(10, 8))
        ui_label(self.emoji_row, 'Your emoji collection will appear here.', 10, MUTED).pack()
        bottom = tk.Frame(result, bg=PANEL)
        bottom.pack(fill='x', pady=(7, 0))
        GoldButton(bottom, '♡   SAVE TO COLLECTION', self.save,
                   filled=True, width=225, bg=PANEL).pack(side='left')
        self.emoji_info = ui_label(bottom, '', 11, CHAMPAGNE)
        self.emoji_info.pack(side='left', padx=18)
        ui_label(result, 'Sentiment is an estimate; sarcasm and context can be misread.',
                 9, MUTED).pack(anchor='w', pady=(12, 0))
        self._draw_gauge()

    def _count(self, event=None):
        size = len(self.input.get('1.0', 'end-1c'))
        self.counter.configure(text=f'{size} / 2000',
                               fg=RED if size > MAX_LENGTH else MUTED)

    def analyze(self):
        try:
            result = self.analyzer.analyze(self.input.get('1.0', 'end-1c'))
        except ValueError as error:
            messagebox.showwarning('Check message', str(error), parent=self.root)
            return
        except Exception as error:
            messagebox.showerror('Analysis error', str(error), parent=self.root)
            return
        self.current = result
        tint = {'Positive': GREEN, 'Neutral': NEUTRAL, 'Negative': RED}[result.category]
        self.mood.configure(text=result.category.upper() + '  ✦', fg=tint)
        self.score.configure(text=f'{result.score:+.4f}', fg=tint)
        self.explanation.configure(text=result.explanation)
        self.suggestions = self.recommender.suggest(result)
        self.select_emoji(self.suggestions[0])
        self._draw_gauge()
        self.status.set('●  Analysis complete  ·  Select your emoji')

    def select_emoji(self, emoji):
        self.emoji = emoji
        for child in self.emoji_row.winfo_children():
            child.destroy()
        for item in self.suggestions:
            selected = item == emoji
            bg = GOLD if selected else PANEL2
            fg = BLACK if selected else TEXT
            tile = tk.Label(self.emoji_row, text=item, bg=bg, fg=fg,
                            font=(FONT, 24), padx=12, pady=9,
                            cursor='hand2', highlightthickness=1,
                            highlightbackground=GOLD if selected else STROKE)
            tile.pack(side='left', padx=(0, 12))
            tile.bind('<Button-1>', lambda event, value=item: self.select_emoji(value))
        self.emoji_info.configure(text=f'Selected  {emoji}')

    def _draw_gauge(self):
        c = self.gauge
        c.delete('all')
        width = max(c.winfo_width(), 240)
        x0, x1 = 12, width-12
        middle = (x0+x1)/2
        c.create_rectangle(x0, 9, middle, 25, fill='#61343D', outline='')
        c.create_rectangle(middle, 9, x1, 25, fill='#255B4D', outline='')
        score = self.current.score if self.current else 0
        x = x0 + (score+1)/2*(x1-x0)
        c.create_oval(x-8, 5, x+8, 29, fill=GOLD, outline=CHAMPAGNE, width=2)
        for position, caption, anchor in [(x0, '−1  NEGATIVE', 'w'),
                                           (middle, 'NEUTRAL', 'center'),
                                           (x1, 'POSITIVE  +1', 'e')]:
            c.create_text(position, 41, text=caption, anchor=anchor,
                          fill=MUTED, font=(FONT, 9, 'bold'))

    def clear(self):
        self.input.delete('1.0', 'end')
        self._count()
        self.current = None
        self.suggestions = []
        self.emoji = ''
        self.mood.configure(text='AWAITING YOUR WORDS', fg=CHAMPAGNE)
        self.score.configure(text='—', fg=GOLD)
        self.explanation.configure(text='Enter a message above to reveal its sentiment.')
        self.emoji_info.configure(text='')
        for child in self.emoji_row.winfo_children():
            child.destroy()
        ui_label(self.emoji_row, 'Your emoji collection will appear here.', 10, MUTED).pack()
        self._draw_gauge()
        self.status.set('●  Cleared  ·  Ready for a new message')

    def save(self):
        if self.current is None:
            messagebox.showinfo('Analyze first', 'Analyze your message before saving.', parent=self.root)
            return
        if self.input.get('1.0', 'end-1c').strip() != self.current.text:
            messagebox.showwarning('Message changed', 'Analyze the edited message before saving.',
                                   parent=self.root)
            return
        try:
            item_id = self.history.save(replace(self.current, emoji=self.emoji))
            self.refresh_history()
            self.refresh_dashboard()
        except sqlite3.Error as error:
            messagebox.showerror('Database error', str(error), parent=self.root)
            return
        self.status.set(f'●  Saved in your private collection  ·  #{item_id}')
        messagebox.showinfo('Saved', 'Added to your private collection.', parent=self.root)

    def _build_history(self):
        parent = self.pages['history']
        card = panel(parent, pad=22)
        card.pack(fill='both', expand=True)
        ui_label(card, 'YOUR PRIVATE COLLECTION', 18, CHAMPAGNE, 'bold').pack(anchor='w')
        ui_label(card, 'Messages, moods and moments — all saved locally.',
                 10, MUTED).pack(anchor='w', pady=(5, 16))
        bar = tk.Frame(card, bg=PANEL)
        bar.pack(fill='x', pady=(0, 15))
        search = tk.Entry(bar, textvariable=self.search_value, font=(FONT, 11),
                          bg=FIELD, fg=TEXT, insertbackground=GOLD,
                          highlightbackground=STROKE, highlightthickness=1, relief='flat')
        search.pack(side='left', fill='x', expand=True, ipady=10)
        search.bind('<Return>', lambda event: self.refresh_history())
        GoldButton(bar, 'SEARCH', self.refresh_history, filled=True,
                   width=110, bg=PANEL).pack(side='left', padx=(9, 0))
        GoldButton(bar, 'SHOW ALL', self.show_all, width=110,
                   bg=PANEL).pack(side='left', padx=(9, 0))
        holder = tk.Frame(card, bg=PANEL)
        holder.pack(fill='both', expand=True)
        columns = ('date', 'message', 'category', 'score', 'emoji')
        self.tree = ttk.Treeview(holder, columns=columns, show='headings',
                                 style='Gold.Treeview', selectmode='browse')
        for name, caption, size in [('date', 'DATE', 150), ('message', 'MESSAGE', 310),
                                    ('category', 'TONE', 90), ('score', 'SCORE', 85),
                                    ('emoji', 'EMOJI', 70)]:
            self.tree.heading(name, text=caption)
            self.tree.column(name, width=size, minwidth=65,
                             stretch=(name == 'message'))
        scroll = ttk.Scrollbar(holder, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda event: self.view_selected())
        actions = tk.Frame(card, bg=PANEL)
        actions.pack(fill='x', pady=(14, 0))
        GoldButton(actions, 'VIEW DETAILS', self.view_selected, width=130,
                   bg=PANEL).pack(side='left')
        GoldButton(actions, 'DELETE SELECTED', self.delete_selected,
                   danger=True, width=165, bg=PANEL).pack(side='left', padx=10)
        GoldButton(actions, 'CLEAR ALL', self.clear_history,
                   danger=True, width=105, bg=PANEL).pack(side='left')
        self.record_count = ui_label(actions, '0 RECORDS', 9, GOLD)
        self.record_count.pack(side='right')

    def refresh_history(self):
        try:
            results = self.history.find(self.search_value.get())
        except sqlite3.Error as error:
            messagebox.showerror('Database error', str(error), parent=self.root)
            return
        self.records = {item.record_id: item for item in results}
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in results:
            preview = item.text.replace('\n', ' ')
            if len(preview) > 75:
                preview = preview[:72] + '...'
            self.tree.insert('', 'end', iid=str(item.record_id), values=(
                item.created_at[:16].replace('T', ' '), preview, item.category,
                f'{item.score:+.4f}', item.emoji))
        self.record_count.configure(text=f'{len(results)} RECORD(S)')

    def show_all(self):
        self.search_value.set('')
        self.refresh_history()

    def _selected(self):
        chosen = self.tree.selection()
        if not chosen:
            messagebox.showinfo('Select a message', 'Select a history row first.', parent=self.root)
            return None
        return self.records.get(int(chosen[0]))

    def view_selected(self):
        item = self._selected()
        if item:
            messagebox.showinfo('Saved message',
                                f'{item.text}\n\nTone: {item.category}\nScore: {item.score:+.4f}'
                                f'\nEmoji: {item.emoji}\n\n{item.explanation}'
                                f'\n\nSaved: {item.created_at[:19]}', parent=self.root)

    def delete_selected(self):
        item = self._selected()
        if item is None or not messagebox.askyesno('Delete message',
                                                    'Delete this saved analysis?', parent=self.root):
            return
        try:
            self.history.delete(item.record_id)
            self.refresh_history()
            self.refresh_dashboard()
        except sqlite3.Error as error:
            messagebox.showerror('Database error', str(error), parent=self.root)

    def clear_history(self):
        if not messagebox.askyesno('Clear collection',
                                   'Permanently remove EVERY saved analysis?',
                                   icon='warning', parent=self.root):
            return
        try:
            self.history.clear()
            self.refresh_history()
            self.refresh_dashboard()
        except sqlite3.Error as error:
            messagebox.showerror('Database error', str(error), parent=self.root)

    def _build_dashboard(self):
        page = self.pages['dashboard']
        card = panel(page, pad=22)
        card.pack(fill='both', expand=True)
        ui_label(card, 'THE MOOD EDIT', 18, CHAMPAGNE, 'bold').pack(anchor='w')
        ui_label(card, 'Your private sentiment analytics, beautifully presented.',
                 10, MUTED).pack(anchor='w', pady=(5, 16))
        bar = tk.Frame(card, bg=PANEL)
        bar.pack(fill='x')
        ui_label(bar, 'TIMEFRAME', 10, GOLD, 'bold').pack(side='left', padx=(0, 13))
        option = tk.OptionMenu(bar, self.period_value, 'All time', 'Last 7 days',
                               'Last 30 days', command=lambda value: self.refresh_dashboard())
        option.configure(bg=PANEL2, fg=CHAMPAGNE, activebackground=PANEL2,
                         activeforeground=CHAMPAGNE, relief='flat',
                         highlightthickness=0, width=14, font=(FONT, 10))
        option['menu'].configure(bg=PANEL2, fg=TEXT)
        option.pack(side='left')
        GoldButton(bar, 'REFRESH', self.refresh_dashboard, width=110,
                   filled=True, bg=PANEL).pack(side='left', padx=13)
        self.total = ui_label(card, '0 SAVED MESSAGES', 20, CHAMPAGNE, 'bold')
        self.total.pack(anchor='w', pady=(27, 9))
        self.chart = tk.Canvas(card, bg=PANEL, highlightthickness=0, height=300)
        self.chart.pack(fill='both', expand=True)
        self.chart.bind('<Configure>', lambda event: self._draw_chart())
        ui_label(card, 'Only messages you choose to save appear here.',
                 9, MUTED).pack(anchor='w', pady=(8, 0))

    def refresh_dashboard(self):
        days = {'All time': None, 'Last 7 days': 7, 'Last 30 days': 30}[self.period_value.get()]
        try:
            self.counts = self.history.summary(days)
        except sqlite3.Error as error:
            messagebox.showerror('Database error', str(error), parent=self.root)
            return
        self.total.configure(text=f"{sum(self.counts.values())}  SAVED MESSAGES")
        self._draw_chart()

    def _draw_chart(self):
        c = self.chart
        c.delete('all')
        w, h = max(400, c.winfo_width()), max(270, c.winfo_height())
        maximum = max(1, *self.counts.values())
        chart_left = 135
        chart_width = max(130, w-chart_left-65)
        colors = {'Positive': GREEN, 'Neutral': NEUTRAL, 'Negative': RED}
        for index, name in enumerate(('Positive', 'Neutral', 'Negative')):
            y = 52 + index * min(90, (h-60)/3)
            count = self.counts[name]
            c.create_text(10, y, text=name.upper(), fill=CHAMPAGNE,
                          anchor='w', font=(FONT, 11, 'bold'))
            c.create_rectangle(chart_left, y-15, chart_left+chart_width,
                               y+15, fill=FIELD, outline=STROKE)
            if count:
                c.create_rectangle(chart_left, y-15,
                                   chart_left+chart_width*(count/maximum),
                                   y+15, fill=colors[name], outline='')
            c.create_text(chart_left+chart_width+14, y, text=str(count),
                          fill=TEXT, anchor='w', font=(FONT, 12, 'bold'))
        if not sum(self.counts.values()):
            c.create_text(w/2, h-15, text='Your collection is waiting for its first message.',
                          fill=MUTED, font=(FONT, 10))


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        analyzer = VaderSentimentAnalyzer()
        history = HistoryRepository()
        TextToneApp(root, analyzer, EmojiRecommender(), history)
    except Exception as error:
        messagebox.showerror('Could not start TextTone Studio', str(error), parent=root)
        root.destroy()
        return
    root.deiconify()
    root.mainloop()


if __name__ == '__main__':
    main()
