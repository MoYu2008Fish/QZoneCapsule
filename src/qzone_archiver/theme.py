"""Shared blue-and-white space tokens for Qt, painted cards and offline HTML."""

from pathlib import Path

TOKENS = {
    "bg": "#eef4fd",
    "panel": "#ffffff",
    "panel_2": "#f7faff",
    "line": "#e6eefb",
    "text": "#1b2440",
    "muted": "#8a99ba",
    "accent": "#3a6bff",
    "accent_hover": "#2a5af0",
    "navy": "#243150",
    "soft": "#eef3ff",
    "radius": 14,
    "control_radius": 9,
    "font": 13,
    "small": 12,
    "title": 26,
    "weight": 600,
    "space": 8,
    "motion": 160,
    "shadow": "0 6px 22px #173f6510",
    "shadow_color": "#0d1c3f1c",
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
QWidget#appShell {background:#eef4fd;}
QFrame#sidebar {background:qlineargradient(x1:0,y1:0,x2:0.7,y2:1,stop:0 #f7f4ff,stop:0.52 #e9f0ff,stop:1 #e7f2ff);border-right:1px solid #e4ecfa;}
QPushButton#navItem {background:transparent;border:1px solid transparent;border-radius:10px;color:#4d5d80;text-align:left;padding:10px 14px;font-size:14px;}
QPushButton#navItem:hover {background:rgba(255,255,255,160);color:#33447a;}
QPushButton#navItem:checked {background:#dbe6ff;color:#2a5cf0;font-weight:600;}
QPushButton#navItem:focus {border:1px solid #b6cbfa;}
QLabel#sidebarTitle {color:#2f3f66;font-size:17px;font-weight:700;}
QLabel#tagline {background:rgba(255,255,255,175);border:1px solid #eef2fb;border-radius:16px;padding:8px 16px;color:#8090b2;font-size:12px;}
QLabel#avatar {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #8acfff,stop:1 #a18aff);color:white;font-size:25px;font-weight:700;border-radius:35px;}
QLabel#accountName {font-size:19px;font-weight:600;color:#232d4a;}
QLabel#accountId {color:#8290b2;font-size:12px;}
QFrame#accountSummary {border-left:1px solid #e7eefb;}
QLabel#metricValue {font-size:15px;font-weight:700;color:#243150;}
QLabel#tileTitle {font-weight:600;color:#243150;font-size:13px;}
QFrame#contentTile {background:#ffffff;border:1px solid #e2ecfb;border-radius:12px;}
QFrame#contentTile:hover {background:#fafcff;border-color:#bcd0fa;}
QFrame#unavailableTile {background:#f9fbff;border:1px dashed #e4ebf8;border-radius:12px;}
QFrame#unavailableTile QLabel#tileTitle {color:#8491b0;}
QLabel#tileCount {color:#93a1be;font-size:10px;}
QFrame#contentTile QCheckBox {padding:0;}
QFrame#unavailableTile QLabel#muted {color:#a8b3ca;font-size:11px;}
QFrame#formatTile {background:#f8fbff;border:1px solid #e6eefb;border-radius:10px;}
QLabel#formatName {color:#33436d;font-size:12px;font-weight:600;}
QLabel#formatCaption {color:#93a1be;font-size:10px;}
QLabel#formatBadge {border-radius:9px;font-size:9px;font-weight:700;}
QLabel#fieldLabel {font-weight:600;color:#54628a;font-size:12px;}
QLabel#pill {background:#f3f7ff;border:1px solid #e9f0fb;border-radius:10px;padding:3px 10px;color:#7d8db0;font-size:11px;}
QFrame#tileDivider {background:#eef3fc;border:none;max-height:1px;min-height:1px;}
QLabel#taskThumb {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #e6f0ff,stop:1 #efe6ff);border:1px solid #e2ebfb;border-radius:12px;}
QPushButton#mastheadAction {background:rgba(255,255,255,190);border:1px solid #e8eefb;border-radius:16px;color:#7c8bad;font-size:15px;padding:0;min-width:32px;max-width:32px;min-height:32px;max-height:32px;}
QPushButton#mastheadAction:hover {background:#ffffff;color:#3a6bff;border-color:#cddcfb;}
QLabel#bigNumber {font-size:27px;font-weight:700;color:#2f5cf5;}
QLabel#bigNumberCaption {font-size:11px;color:#93a1be;}
QPushButton#stopButton {border:1px solid #ffc9d5;background:#fff7fa;color:#ec7394;border-radius:16px;padding:6px 15px;font-size:12px;}
QPushButton#stopButton:hover {background:#fff0f5;border-color:#ffb3c6;}
QPushButton#stopButton:disabled {color:#b7c0d4;border-color:#e8edf6;background:#f7f9fd;}
QCheckBox::indicator {border:1.5px solid #cbd8f2;border-radius:5px;background:white;}
QCheckBox::indicator:hover {border-color:#9fb9f0;}
QCheckBox::indicator:checked {background:#3a6bff;border:1px solid #3a6bff;image:url("@check");}
QCheckBox::indicator:disabled {background:#eff3fa;border-color:#dde5f2;}

QWidget { color:@text; font-size:@fontpx; }
QMainWindow, QDialog, QScrollArea, QWidget#exportContent { background:@bg; }
QLabel { background:transparent; }
QScrollArea#photoStage {background:@panel;border:1px solid @line;border-radius:@radiuspx;}
QFrame#masthead {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #faf7ff,stop:0.42 #fbfdff,stop:1 #eef5ff);border-bottom:1px solid #e8effb;}
QFrame#masthead QLabel {color:@muted;}
QFrame#masthead QLabel#brand {color:#1f2942;font-size:21px;font-weight:700;}
QLabel#eyebrow {color:@accent;font-size:@smallpx;font-weight:@weight;}
QLabel#title {color:@navy;font-size:@titlepx;font-weight:700;}
QLabel#muted {color:@muted;font-size:@smallpx;}
QLabel#cardtitle {font-size:15px;font-weight:@weight;color:@navy;}
QLabel#step {background:@soft;color:@accent;border-radius:14px;font-size:12px;font-weight:700;}
QFrame#card, QFrame#statCard, QFrame#filters {background:#ffffff;border:1px solid #e9f0fb;border-radius:@radiuspx;}
QFrame#statCard QLabel#statValue {font-size:23px;font-weight:700;color:@navy;}
QFrame#spaceHero {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #e0edff,stop:1 #ebe1ff);border:1px solid @line;border-radius:@radiuspx;}
QFrame#spaceHero QLabel {color:@navy;}
QLabel#spaceTitle {font-size:@titlepx;font-weight:700;}
QPushButton {background:@panel;border:1px solid #e2eaf9;border-radius:@control_radiuspx;padding:7px 12px;color:#3f5b96;font-size:12px;}
QPushButton:hover {background:#f5f9ff;border-color:#c8d9f8;color:#2f4f92;}
QPushButton:pressed {background:#e9f1ff;}
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QCheckBox:focus {border:1px solid @accent;}
QPushButton:disabled {color:#a2aec6;background:#f4f7fc;border-color:#e8edf6;}
QPushButton#primary {background:@accent;color:white;border:1px solid @accent;font-weight:@weight;padding:8px 14px;}
QPushButton#primary:hover {background:@accent_hover;border-color:@accent_hover;}
QPushButton#primary:disabled {background:#cfdcf7;border-color:#cfdcf7;color:#f7faff;}
QLineEdit, QComboBox {background:#fbfdff;border:1px solid #e3ecfa;border-radius:@control_radiuspx;padding:6px 10px;min-height:16px;font-size:12px;color:#33415f;selection-background-color:@soft;selection-color:@navy;}
QLineEdit:hover, QComboBox:hover {border-color:#c8d9f8;}
QLineEdit:disabled, QComboBox:disabled {background:#f2f6fc;color:#a2aec6;}
QComboBox::drop-down {border:none;width:26px;}
QComboBox::down-arrow {image:url("@chevron");width:11px;height:7px;}
QComboBox QAbstractItemView {background:white;selection-background-color:@soft;selection-color:@navy;border:1px solid @line;padding:5px;}
QListWidget, QTextBrowser, QTextEdit, QTreeWidget {background:@panel;border:1px solid @line;border-radius:@control_radiuspx;padding:@spacepx;selection-background-color:@soft;selection-color:@navy;}
QTextBrowser {font-size:14px;}
QListWidget::item {padding:10px;border-bottom:1px solid @line;}
QListWidget::item:selected {background:@soft;color:@navy;}
QListWidget::item:hover {background:@panel_2;}
QTreeWidget#taskTable {background:transparent;border:none;border-radius:0;padding:0;font-size:12px;}
QTreeWidget#taskTable::item {padding:8px 4px;border-bottom:1px solid #f1f5fc;}
QTreeWidget#taskTable::item:selected {background:#f2f6ff;color:@navy;}
QTextEdit#taskLog {background:#f8faff;border:1px solid #e6edfc;font-size:12px;padding:6px;border-radius:8px;}
QTabBar {background:@navy;}
QTabWidget::pane {border:none;background:@bg;}
QTabBar::tab {background:@navy;color:#c5d9ed;padding:13px 24px;border-bottom:3px solid @navy;}
QTabBar::tab:selected {color:white;border-bottom:3px solid #77c6ff;font-weight:@weight;}
QTabBar::tab:hover {background:#23527b;}
QCheckBox {spacing:7px;padding:3px 0;border:1px solid transparent;font-size:12px;color:#5a6786;}
QCheckBox::indicator {width:16px;height:16px;}
QTreeWidget::item {padding:7px 3px;}
QHeaderView::section {background:@panel_2;color:#94a1bd;border:none;border-bottom:1px solid #eef3fc;padding:8px 6px;font-size:11px;font-weight:@weight;}
QProgressBar {border:none;background:#e8eefb;border-radius:5px;min-height:10px;max-height:10px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #45a8ff,stop:1 #7d6bff);border-radius:5px;}
QScrollBar:vertical {background:transparent;width:8px;margin:4px 2px;}
QScrollBar::handle:vertical {background:#c3d0e6;border-radius:4px;min-height:36px;}
QScrollBar::handle:vertical:hover {background:#9fb3d1;}
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
