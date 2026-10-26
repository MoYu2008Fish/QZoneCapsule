"""Shared blue-and-white space tokens for Qt, painted cards and offline HTML."""

from pathlib import Path

TOKENS = {
    "bg": "#edf4ff",
    "panel": "#ffffff",
    "panel_2": "#f5f8ff",
    "line": "#e0eafe",
    "text": "#151c35",
    "muted": "#8290b2",
    "accent": "#356aff",
    "accent_hover": "#2557e8",
    "navy": "#27365a",
    "soft": "#eaf0ff",
    "radius": 12,
    "control_radius": 8,
    "font": 13,
    "small": 12,
    "title": 26,
    "weight": 600,
    "space": 8,
    "motion": 160,
    "shadow": "0 4px 18px #173f6508",
    "shadow_color": "#08173f65",
}


def css_variables():
    return (
        ";".join(
            f"--{key.replace('_', '-')}:{value}{'ms' if key == 'motion' else 'px' if isinstance(value, int) and key != 'weight' else ''}"
            for key, value in TOKENS.items()
        )
        + ";"
    )


_QSS = """
QWidget#appShell {background:#edf4ff;}
QFrame#sidebar {background:qlineargradient(x1:0,y1:0,x2:0.6,y2:1,stop:0 #f5f3ff,stop:0.52 #e4edff,stop:1 #e8f2ff);border-right:1px solid #e0e8fa;}
QPushButton#navItem {background:transparent;border:1px solid transparent;border-radius:8px;color:#465578;text-align:left;padding:12px 16px;font-size:15px;}
QPushButton#navItem:hover {background:#e5eaff;}
QPushButton#navItem:checked {background:#dae3ff;color:#255be6;font-weight:600;}
QPushButton#navItem:focus {border:1px solid @accent;}
QLabel#sidebarTitle {color:#304475;font-size:21px;padding-top:10px;}
QLabel#tagline {background:rgba(255,255,255,155);border-radius:17px;padding:9px 18px;color:#8290b2;}
QFrame#accountSummary {border-left:1px solid #e4eaff;}
QLabel#avatar {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #8acfff,stop:1 #a18aff);color:white;font-size:24px;font-weight:700;border-radius:38px;}
QLabel#accountName {font-size:18px;font-weight:600;color:#252c47;}
QLabel#tileTitle {font-weight:600;color:#202941;font-size:13px;}
QFrame#unavailableTile {background:#f8faff;border:1px solid #e5ebf8;border-radius:9px;}
QFrame#unavailableTile QLabel#tileTitle {color:#7783a4;}
QFrame#unavailableTile QLabel#muted {color:#9aa5bf;font-size:10px;}
QFrame#contentTile QCheckBox {padding:0;}
QFrame#contentTile QLabel#muted {font-size:10px;}
QTreeWidget#taskTable {border:none;border-radius:0;padding:0;font-size:12px;}
QTreeWidget#taskTable::item {padding:5px 1px;}
QTextEdit#taskLog {background:#f8faff;border:1px solid #e6edfc;font-size:12px;padding:5px;}
QFrame#contentTile {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:1 #f6f9ff);border:1px solid #d9e4fc;border-radius:10px;}
QLabel#formatTile {background:#f8faff;border:1px solid #dce5fa;border-radius:8px;padding:7px 4px;color:#43558b;line-height:150%;}
QLabel#fieldLabel {font-weight:600;color:#516080;}
QLabel#taskStatus {font-size:15px;font-weight:600;color:#334168;}
QPushButton#stopButton {border:1px solid #ffc3d0;background:#fff7fa;color:#ec7394;border-radius:17px;padding:7px 14px;}
QPushButton#stopButton:disabled {color:#abb3c9;border-color:#e1e7f3;background:#f6f8fd;}
QPushButton#exportAction, QPushButton#libraryAction {border:none;border-radius:12px;color:white;font-size:14px;font-weight:600;padding:10px;}
QPushButton#exportAction {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #46bdff,stop:1 #5352ff);}
QPushButton#exportAction:hover {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #299fff,stop:1 #4540ee);}
QPushButton#libraryAction {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #bb84f5,stop:1 #6946fb);}
QPushButton#libraryAction:hover {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #a36ae9,stop:1 #5837eb);}
QPushButton#exportAction:disabled {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #b4d8f4,stop:1 #b3b8ed);color:#f6f8ff;}
QPushButton#exportAction:focus, QPushButton#libraryAction:focus {border:2px solid #263a87;}
QCheckBox::indicator {border:1px solid #c7d5f1;border-radius:4px;background:white;}
QCheckBox::indicator:checked {background:@accent;border:1px solid @accent;image:url("@check");}
QCheckBox::indicator:disabled {background:#e8edf7;border-color:#d7dfef;}

QWidget { color:@text; font-size:@fontpx; }
QMainWindow, QDialog, QScrollArea, QWidget#exportContent { background:@bg; }
QLabel { background:transparent; }
QScrollArea#photoStage {background:@panel;border:1px solid @line;border-radius:@radiuspx;}
QFrame#masthead { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #f5f1ff,stop:0.45 #f5f9ff,stop:1 #e6f1ff);border-bottom:1px solid #e0e9fa; }
QFrame#masthead QLabel {color:@muted;}
QFrame#masthead QLabel#brand {color:#202740;font-size:23px;font-weight:700;}
QLabel#eyebrow {color:@accent;font-size:@smallpx;font-weight:@weight;}
QLabel#title {color:@navy;font-size:@titlepx;font-weight:700;}
QLabel#muted {color:@muted;font-size:@smallpx;}
QLabel#cardtitle {font-size:16px;font-weight:@weight;color:@navy;}
QLabel#step {background:@soft;color:@accent;border-radius:14px;font-size:12px;font-weight:700;}
QFrame#card, QFrame#statCard, QFrame#filters {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ffffff,stop:1 #f9fcff);border:1px solid @line;border-radius:@radiuspx;}
QFrame#statCard QLabel#statValue {font-size:23px;font-weight:700;color:@navy;}
QFrame#spaceHero {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #e0edff,stop:1 #ebe1ff);border:1px solid @line;border-radius:@radiuspx;}
QFrame#spaceHero QLabel {color:@navy;}
QLabel#spaceTitle {font-size:@titlepx;font-weight:700;}
QPushButton {background:@panel;border:1px solid @line;border-radius:@control_radiuspx;padding:7px 11px;color:@accent;}
QPushButton:hover {background:@soft;border-color:#a9c9e3;}
QPushButton:pressed {background:#d5e8f7;}
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QCheckBox:focus {border:1px solid @accent;}
QPushButton:disabled {color:#8a9aab;background:#e9eef4;border-color:#e0e7ee;}
QPushButton#primary {background:@accent;color:white;border:1px solid @accent;font-weight:@weight;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:disabled {background:#c8d8e7;border-color:#c8d8e7;color:#5b7389;}
QLineEdit, QComboBox {background:@panel;border:1px solid @line;border-radius:@control_radiuspx;padding:6px 10px;min-height:18px;selection-background-color:@soft;selection-color:@navy;}
QLineEdit:disabled, QComboBox:disabled {background:#e9eef4;color:#8a9aab;}
QComboBox::drop-down {border:none;width:26px;}
QComboBox::down-arrow {image:url("@chevron");width:12px;height:8px;}
QComboBox QAbstractItemView {background:white;selection-background-color:@soft;selection-color:@navy;border:1px solid @line;padding:5px;}
QListWidget, QTextBrowser, QTextEdit, QTreeWidget {background:@panel;border:1px solid @line;border-radius:@control_radiuspx;padding:@spacepx;selection-background-color:@soft;selection-color:@navy;}
QTextBrowser {font-size:14px;}
QListWidget::item {padding:10px;border-bottom:1px solid @line;}
QListWidget::item:selected {background:@soft;color:@navy;}
QListWidget::item:hover {background:@panel_2;}
QTabBar {background:@navy;}
QTabWidget::pane {border:none;background:@bg;}
QTabBar::tab {background:@navy;color:#c5d9ed;padding:13px 24px;border-bottom:3px solid @navy;}
QTabBar::tab:selected {color:white;border-bottom:3px solid #77c6ff;font-weight:@weight;}
QTabBar::tab:hover {background:#23527b;}
QCheckBox {spacing:@spacepx;padding:5px 0;border:1px solid transparent;}
QCheckBox::indicator {width:16px;height:16px;}
QTreeWidget::item {padding:7px 3px;}
QHeaderView::section {background:@panel_2;color:@muted;border:none;padding:8px;}
QProgressBar {border:none;background:#e2eaf3;border-radius:4px;min-height:8px;max-height:8px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #289cff,stop:1 #9d71ff);border-radius:4px;}
QScrollBar:vertical {background:transparent;width:9px;margin:3px 0;}
QScrollBar::handle:vertical {background:#b8c9d8;border-radius:4px;min-height:32px;}
QScrollBar::handle:vertical:hover {background:#819fb8;}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {background:transparent;}
QSplitter::handle {background:@bg;width:10px;}
"""


def stylesheet():
    source = _QSS.replace("@chevron", (Path(__file__).parent / "assets" / "chevron.svg").as_posix())
    source = source.replace("@check", (Path(__file__).parent / "assets" / "check.svg").as_posix())
    for key in sorted(TOKENS, key=len, reverse=True):
        source = source.replace("@" + key, str(TOKENS[key]))
    return source


STYLE = stylesheet()
