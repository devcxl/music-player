import sys
import os
import sounddevice as sd
import soundfile as sf
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                            QVBoxLayout, QWidget, QLabel, QComboBox, 
                            QFileDialog, QMessageBox, QShortcut, 
                            QInputDialog, QListWidget, QListWidgetItem,
                            QHBoxLayout, QMenuBar, QAction, QSplitter,
                            QAbstractItemView, QSizePolicy, QMenu)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QKeySequence

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
        self.group_list.customContextMenuRequested.connect(self.show_group_context_menu)
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
            delete_action.triggered.connect(lambda: self.delete_group(group_name))
            
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
            settings.beginWriteArray("music_files", len(self.groups[group_name]))
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

class MusicListWidget(QWidget):
    shortcutRequested = pyqtSignal(str, str)  # music_path, current_hotkey
    deleteRequested = pyqtSignal(str)
    moveRequested = pyqtSignal(str)
    
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
        self.music_list.customContextMenuRequested.connect(self.show_music_context_menu)
        self.music_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.music_list)
    
    def on_item_double_clicked(self, item):
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
            delete_action.triggered.connect(lambda: self.delete_music(music_path))
            
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
            
            btn = QPushButton("快捷键" + (f" ({current_hotkey})" if current_hotkey else ""))
            btn.clicked.connect(lambda : self.shortcutRequested.emit(music_path, hotkey))
            
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

class MusicPlayerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化设置
        self.settings = QSettings("MusicPlayer", "HotkeyMusicPlayer")
        self.last_device_id = self.settings.value("last_device_id", sd.default.device[0], type=int)
        self.stream = None
        self.current_frame = 0
        self.data = None
        self.samplerate = None
        self.current_playing = None  # 当前正在播放的音乐路径
        self.current_group = None    # 当前选中的分组
        
        # 初始化UI
        self.init_ui()
        # 初始化快捷键字典
        self.shortcuts = {}
        # 加载上次的设置
        self.load_settings()
        
    def init_ui(self):
        self.setWindowTitle("音乐播放器 (soundfree)")
        self.setGeometry(100, 100, 800, 600)
        # 创建菜单栏
        self.create_menu_bar()
        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # 使用QSplitter分割左右布局
        splitter = QSplitter(Qt.Horizontal)
        # 左侧分组列表
        self.group_widget = MusicGroupWidget()
        self.group_widget.groupSelected.connect(self.on_group_selected)
        self.group_widget.groupDeleted.connect(self.on_group_deleted)
        self.group_widget.requestMoveMusic.connect(self.on_move_music_requested)
        # 右侧音乐列表
        self.music_list_widget = MusicListWidget()
        self.music_list_widget.shortcutRequested.connect(self.set_music_hotkey)
        self.music_list_widget.deleteRequested.connect(self.on_delete_music_requested)
        self.music_list_widget.moveRequested.connect(self.on_move_music_requested)
        # self.music_list_widget.playRequested.connect(self.play_music)
        
        # 添加默认分组
        if not self.group_widget.get_all_groups():
            self.group_widget.add_group("默认分组")

        splitter.addWidget(self.group_widget)
        splitter.addWidget(self.music_list_widget)
        splitter.setStretchFactor(1, 3)  # 右侧占3/4宽度
        
        # 底部控制面板
        control_panel = QWidget()
        control_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)  # 限制高度
        control_layout = QHBoxLayout()
        control_panel.setLayout(control_layout)
        
        # 播放设备选择
        self.device_combo = QComboBox()
        self.refresh_audio_devices()
        
        # 播放/停止按钮
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self.play_selected_music)
        
        control_layout.addWidget(QLabel("播放设备:"))
        control_layout.addWidget(self.device_combo)
        control_layout.addWidget(self.play_btn)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_layout.addWidget(control_panel)
        central_widget.setLayout(main_layout)
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        import_music_action = QAction("导入音乐", self)
        import_music_dir_action = QAction("导入文件夹", self)
        import_music_action.triggered.connect(self.import_music)
        import_music_dir_action.triggered.connect(self.import_music_dir)
        file_menu.addAction(import_music_action)
        file_menu.addAction(import_music_dir_action)
        
    def import_music(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音乐文件", "", 
            "音频文件 (*.mp3 *.wav *.flac *.ogg *.aiff)", 
            options=options
        )
        
        if files:
            if not self.current_group:
                self.group_widget.add_group("默认分组")
                self.current_group = "默认分组"
            self.group_widget.groups[self.current_group].extend(files)
            self.music_list_widget.set_music_files(self.group_widget.groups[self.current_group])
    
    def import_music_dir(self):
        # 导入文件夹
        dir_path = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if dir_path:
            group_name = os.path.basename(dir_path)
            music_files = []
            
            # 扫描文件夹中的音乐文件
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.aiff')):
                        music_files.append(os.path.join(root, file))
            
            if music_files:
                self.group_widget.add_group(group_name, music_files)
                self.on_group_selected(group_name)
    
    def on_group_selected(self, group_name):
        self.current_group = group_name
        music_files = self.group_widget.get_music_files(group_name)
        self.music_list_widget.set_music_files(music_files)
    
    def on_group_deleted(self, group_name):
        if self.current_group == group_name:
            self.current_group = None
            self.music_list_widget.set_music_files([])
    
    def on_delete_music_requested(self, music_path):
        if self.current_group:
            if music_path in self.group_widget.groups[self.current_group]:
                self.group_widget.groups[self.current_group].remove(music_path)
                self.music_list_widget.set_music_files(self.group_widget.groups[self.current_group])
                
                # 如果这个音乐有快捷键，移除它
                hotkey = self.music_list_widget.get_hotkey_for_music(music_path)
                if hotkey and hotkey in self.shortcuts:
                    self.shortcuts[hotkey][1].deleteLater()
                    del self.shortcuts[hotkey]
    
    def on_move_music_requested(self, music_path):
        if not self.current_group:
            return
            
        # 获取所有分组，排除当前分组
        groups = [g for g in self.group_widget.get_all_groups() if g != self.current_group]
        
        if not groups:
            QMessageBox.information(self, "提示", "没有其他分组可供移动")
            return
            
        # 让用户选择目标分组
        group_name, ok = QInputDialog.getItem(
            self, "移动到分组", 
            "选择目标分组:", 
            groups, 0, False
        )
        
        if ok and group_name:
            # 从当前分组移除
            self.group_widget.groups[self.current_group].remove(music_path)
            # 添加到目标分组
            self.group_widget.groups[group_name].append(music_path)
            # 更新当前列表
            self.music_list_widget.set_music_files(self.group_widget.groups[self.current_group])
    
    def set_music_hotkey(self, music_path, current_hotkey):
        hotkey, ok = QInputDialog.getText(
            self, "设置快捷键", 
            f"为 {os.path.basename(music_path)} 设置快捷键组合 (如 Ctrl+P):", 
            text=current_hotkey if current_hotkey else ""
        )
        
        if ok:
            # 检查快捷键是否已被占用
            if hotkey and hotkey in self.shortcuts and self.shortcuts[hotkey][0] != music_path:
                QMessageBox.warning(self, "警告", f"快捷键 {hotkey} 已被 {os.path.basename(self.shortcuts[hotkey][0])} 占用!")
                return
                
            # 移除旧的快捷键
            if current_hotkey in self.shortcuts:
                self.shortcuts[current_hotkey][1].deleteLater()
                del self.shortcuts[current_hotkey]
            
            # 设置新的快捷键
            if hotkey:
                shortcut = QShortcut(QKeySequence(hotkey), self)
                shortcut.activated.connect(lambda : self.toggle_play_music(music_path))
                self.shortcuts[hotkey] = (music_path, shortcut)
                # 保存到列表显示
                self.music_list_widget.set_hotkey(music_path, hotkey)
            else:
                # 清除快捷键
                self.music_list_widget.set_hotkey(music_path, "")
    
    def toggle_play_music(self, music_path):
        if self.current_playing == music_path and self.stream is not None:
            self.stop_music()
        else:
            self.play_music(music_path)
    
    def play_selected_music(self):
        selected_items = self.music_list_widget.music_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要播放的音乐!")
            return
            
        item = selected_items[0]
        index = self.music_list_widget.music_list.row(item)
        music_path = self.music_list_widget.music_files[index]
        self.play_music(music_path)
    
    def play_music(self, music_path):
        try:
            # 如果已经在播放其他音乐，先停止
            if self.stream is not None:
                self.stop_music()
            
            # 获取选择的设备
            device_id = self.device_combo.currentData()
            self.last_device_id = device_id
            self.settings.setValue("last_device_id", device_id)
            
            # 读取音频文件
            self.data, self.samplerate = sf.read(music_path, dtype='float32')
            self.current_frame = 0
            self.current_playing = music_path
            
            # 确保数据是二维的 (frames, channels)
            if len(self.data.shape) == 1:
                self.data = self.data.reshape(-1, 1)
            
            # 定义回调函数
            def callback(outdata, frames, time, status):
                if status:
                    print(status)
                
                chunksize = min(len(self.data) - self.current_frame, frames)
                outdata[:chunksize] = self.data[self.current_frame:self.current_frame + chunksize]
                
                if chunksize < frames:
                    outdata[chunksize:] = 0
                    raise sd.CallbackStop
                
                self.current_frame += chunksize
            
            # 开始播放
            self.stream = sd.OutputStream(
                device=device_id,
                samplerate=self.samplerate,
                channels=self.data.shape[1],
                callback=callback,
                finished_callback=self.playback_finished
            )
            
            self.stream.start()
            
            # 更新按钮状态
            self.play_btn.setText("停止")
            self.play_btn.clicked.disconnect()
            self.play_btn.clicked.connect(self.stop_music)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"播放音乐时出错:\n{str(e)}")
            self.current_playing = None
    
    def playback_finished(self):
        # 播放完成后的回调
        print("播放完成")
        self.current_frame = 0
        self.current_playing = None
        self.play_btn.setText("播放")
        self.play_btn.clicked.disconnect()
        self.play_btn.clicked.connect(self.play_selected_music)
    
    def stop_music(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.current_frame = 0
            self.current_playing = None
            
            # 更新按钮状态
            self.play_btn.setText("播放")
            self.play_btn.clicked.disconnect()
            self.play_btn.clicked.connect(self.play_selected_music)
    
    def refresh_audio_devices(self):
        self.device_combo.clear()
        devices = sd.query_devices()
        default_output = sd.default.device[1]  # 默认输出设备
        
        for i, device in enumerate(devices):
            # 只显示输出设备
            if device['max_output_channels'] > 0:
                is_default = "(默认设备)" if i == default_output else ""
                self.device_combo.addItem(f"{device['name']} {is_default}", i)
                
                # 如果是上次选择的设备，设置为选中
                if i == self.last_device_id:
                    self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
    
    def load_settings(self):
        # 加载设备选择
        for i in range(self.device_combo.count()):
            if self.device_combo.itemData(i) == self.last_device_id:
                self.device_combo.setCurrentIndex(i)
                break
        
        # 加载分组和音乐文件
        self.group_widget.load_groups(self.settings)
        
        # 加载快捷键设置
        self.music_list_widget.load_hotkeys(self.settings)
        
        # 重新创建快捷键
        for hotkey, music_path in self.music_list_widget.hotkeys.items():
            shortcut = QShortcut(QKeySequence(hotkey), self)
            shortcut.activated.connect(lambda: self.toggle_play_music(music_path))
            self.shortcuts[hotkey] = (music_path, shortcut)
        
        # 选择第一个分组
        groups = self.group_widget.get_all_groups()
        if groups:
            self.group_widget.group_list.setCurrentRow(0)
            self.on_group_selected(groups[0])
    
    def save_settings(self):
        # 保存设备设置
        self.settings.setValue("last_device_id", self.last_device_id)
        
        # 保存分组和音乐文件
        self.group_widget.save_groups(self.settings)
        
        # 保存快捷键设置
        self.music_list_widget.save_hotkeys(self.settings)
    
    def closeEvent(self, event):
        # 保存设置
        self.save_settings()
        
        # 停止播放并退出
        self.stop_music()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MusicPlayerApp()
    player.show()
    sys.exit(app.exec_())