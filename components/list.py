import os
from PyQt5.QtWidgets import (QPushButton,
                             QVBoxLayout, QWidget, QLabel,

                             QListWidget, QListWidgetItem,
                             QHBoxLayout,  QAction,
                             QMenu)
from PyQt5.QtCore import Qt, pyqtSignal
import logging

log = logging.getLogger(__name__)


class MusicListWidget(QWidget):
    shortcutRequested = pyqtSignal(str, str)  # music_path, current_hotkey
    deleteRequested = pyqtSignal(str)
    moveRequested = pyqtSignal(str)
    playRequested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.music_files = []
        self.hotkeys = {}  # {hotkey: music_path}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.music_list = QListWidget()
        self.music_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.music_list.customContextMenuRequested.connect(
            self.show_music_context_menu)
        self.music_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.music_list)

    def on_item_double_clicked(self, item):
        '''双击播放'''
        index = self.music_list.row(item)
        music_path = self.music_files[index]
        self.playRequested.emit(music_path)

    def show_music_context_menu(self, pos):
        item = self.music_list.itemAt(pos)
        if item:
            index = self.music_list.row(item)
            music_path = self.music_files[index]

            menu = QMenu()

            delete_action = QAction("删除音乐", self)
            delete_action.triggered.connect(
                lambda: self.delete_music(music_path))

            move_action = QAction("移动到其他分组", self)
            move_action.triggered.connect(lambda: self.move_music(music_path))

            menu.addAction(delete_action)
            menu.addAction(move_action)
            menu.exec_(self.music_list.mapToGlobal(pos))

    def delete_music(self, music_path):
        self.deleteRequested.emit(music_path)

    def move_music(self, music_path):
        self.moveRequested.emit(music_path)

    def set_music_files(self, music_files):
        self.music_files = music_files
        self.update_list()

    def update_list(self):
        self.music_list.clear()

        for music_path in self.music_files:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QHBoxLayout()
            widget.setLayout(layout)

            music_name = os.path.basename(music_path)
            label = QLabel(music_name)

            # 查找当前音乐是否有快捷键
            current_hotkey = None
            for hotkey, path in self.hotkeys.items():
                if path == music_path:
                    current_hotkey = hotkey
                    break

            btn = QPushButton(
                "快捷键" + (f" ({current_hotkey})" if current_hotkey else ""))
            btn.clicked.connect(
                lambda _, mp=music_path, hk=current_hotkey: self.shortcutRequested.emit(mp, hk))
            layout.addWidget(label)
            layout.addWidget(btn)
            layout.setStretch(0, 1)

            item.setSizeHint(widget.sizeHint())
            self.music_list.addItem(item)
            self.music_list.setItemWidget(item, widget)

    def set_hotkey(self, music_path, hotkey):
        # 先移除任何现有的相同快捷键
        if hotkey in self.hotkeys:
            del self.hotkeys[hotkey]

        # 移除该音乐的任何现有快捷键
        for h, path in list(self.hotkeys.items()):
            if path == music_path:
                del self.hotkeys[h]

        if hotkey:  # 如果hotkey不是None或空字符串
            self.hotkeys[hotkey] = music_path

        self.update_list()

    def get_hotkey_for_music(self, music_path):
        for hotkey, path in self.hotkeys.items():
            if path == music_path:
                return hotkey
        return None

    def save_hotkeys(self, settings):
        settings.beginWriteArray("hotkeys")
        for i, (hotkey, music_path) in enumerate(self.hotkeys.items()):
            settings.setArrayIndex(i)
            settings.setValue("hotkey", hotkey)
            settings.setValue("music_path", music_path)
        settings.endArray()

    def load_hotkeys(self, settings):
        self.hotkeys.clear()
        size = settings.beginReadArray("hotkeys")
        for i in range(size):
            settings.setArrayIndex(i)
            hotkey = settings.value("hotkey")
            music_path = settings.value("music_path")
            self.hotkeys[hotkey] = music_path
        settings.endArray()
