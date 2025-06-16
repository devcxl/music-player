from PyQt5.QtWidgets import (
    QVBoxLayout, QWidget,
    QMessageBox,
    QListWidget,
    QAction,
    QAbstractItemView, QMenu,)
from PyQt5.QtCore import Qt, pyqtSignal
import logging

log = logging.getLogger(__name__)


class MusicGroupWidget(QWidget):
    groupSelected = pyqtSignal(str)
    groupDeleted = pyqtSignal(str)
    requestMoveMusic = pyqtSignal(str, str)  # music_path, target_group

    def __init__(self):
        super().__init__()
        self.groups = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.group_list.itemClicked.connect(self.on_group_selected)
        self.group_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(
            self.show_group_context_menu)
        layout.addWidget(self.group_list)

    def add_group(self, group_name, music_files=None):
        if group_name not in self.groups:
            self.groups[group_name] = music_files if music_files else []
            self.group_list.addItem(group_name)

    def on_group_selected(self, item):
        group_name = item.text()
        self.groupSelected.emit(group_name)

    def show_group_context_menu(self, pos):
        item = self.group_list.itemAt(pos)
        if item:
            group_name = item.text()
            menu = QMenu()

            delete_action = QAction("删除分组", self)
            delete_action.triggered.connect(
                lambda: self.delete_group(group_name))

            menu.addAction(delete_action)
            menu.exec_(self.group_list.mapToGlobal(pos))

    def delete_group(self, group_name):
        if group_name in self.groups:
            reply = QMessageBox.question(
                self, '确认删除',
                f'确定要删除分组 "{group_name}" 及其所有音乐吗?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 从列表中移除
                items = self.group_list.findItems(group_name, Qt.MatchExactly)
                if items:
                    row = self.group_list.row(items[0])
                    self.group_list.takeItem(row)

                # 从字典中移除
                del self.groups[group_name]
                self.groupDeleted.emit(group_name)

    def get_music_files(self, group_name):
        return self.groups.get(group_name, [])

    def get_all_groups(self):
        return list(self.groups.keys())

    def move_music_to_group(self, music_path, target_group):
        # 从所有分组中移除音乐
        for group in self.groups:
            if music_path in self.groups[group]:
                self.groups[group].remove(music_path)
                break

        # 添加到目标分组
        if target_group in self.groups:
            self.groups[target_group].append(music_path)
        else:
            self.groups[target_group] = [music_path]

    def save_groups(self, settings):
        settings.beginWriteArray("groups")
        for i, group_name in enumerate(self.groups.keys()):
            settings.setArrayIndex(i)
            settings.setValue("name", group_name)
            settings.beginWriteArray(
                "music_files", len(self.groups[group_name]))
            for j, music_path in enumerate(self.groups[group_name]):
                settings.setArrayIndex(j)
                settings.setValue("path", music_path)
            settings.endArray()
        settings.endArray()

    def load_groups(self, settings):
        self.groups.clear()
        self.group_list.clear()

        size = settings.beginReadArray("groups")
        for i in range(size):
            settings.setArrayIndex(i)
            group_name = settings.value("name")

            music_files = []
            file_count = settings.beginReadArray("music_files")
            for j in range(file_count):
                settings.setArrayIndex(j)
                music_files.append(settings.value("path"))
            settings.endArray()

            self.add_group(group_name, music_files)
        settings.endArray()
