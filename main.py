import sys
import os
import sounddevice as sd
import soundfile as sf
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton,
                             QVBoxLayout, QWidget, QLabel, QComboBox,
                             QFileDialog, QMessageBox,
                             QInputDialog,
                             QHBoxLayout, QAction, QSplitter,
                             QSizePolicy, QMenu, QSystemTrayIcon, QDialog)
from PyQt5.QtCore import Qt, QSettings
import sys
from PyQt5.QtGui import QIcon
from pynput import keyboard
import threading
import logging
import utils
from components.group import MusicGroupWidget
from components.list import MusicListWidget

log = logging.getLogger(__name__)


class MusicPlayerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # 初始化设置
        self.settings = QSettings("MusicPlayer", "HotkeyMusicPlayer")
        self.last_device_id = self.settings.value(
            "last_device_id", sd.default.device[0], type=int)
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
        self.hotkey_listener = None
        # 加载上次的设置
        self.load_settings()

        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(utils.resource_path("assert/logo.png")))
        self.tray_icon.setToolTip("MusicPlayer")

        tray_menu = QMenu()
        show_action = QAction("显示窗口", self)
        quit_action = QAction("退出", self)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        # 绑定菜单事件
        show_action.triggered.connect(self.show_window)
        quit_action.triggered.connect(self.quit)
        # 双击托盘图标显示窗口
        self.tray_icon.activated.connect(self.on_tray_activated)
        # 显示托盘图标
        self.tray_icon.show()

    def init_ui(self):
        self.setWindowTitle("音乐播放器")
        # 屏幕居中放置
        screen = QApplication.primaryScreen().geometry()
        window_width, window_height = 800, 600
        x = (screen.width() - window_width) // 2
        y = (screen.height() - window_height) // 2
        self.setGeometry(x, y, window_width, window_height)
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
        self.group_widget.requestMoveMusic.connect(
            self.on_move_music_requested)
        # 右侧音乐列表
        self.music_list_widget = MusicListWidget()
        self.music_list_widget.shortcutRequested.connect(self.set_music_hotkey)
        self.music_list_widget.deleteRequested.connect(
            self.on_delete_music_requested)
        self.music_list_widget.moveRequested.connect(
            self.on_move_music_requested)
        self.music_list_widget.playRequested.connect(self.play_music)

        # 添加默认分组
        if not self.group_widget.get_all_groups():
            self.group_widget.add_group("默认分组")

        splitter.addWidget(self.group_widget)
        splitter.addWidget(self.music_list_widget)
        splitter.setStretchFactor(1, 3)  # 右侧占3/4宽度

        # 底部控制面板
        control_panel = QWidget()
        control_panel.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Maximum)  # 限制高度
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
            self.music_list_widget.set_music_files(
                self.group_widget.groups[self.current_group])
            # 同步更新设置配置
            self.group_widget.save_groups(self.settings)

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
        # 同步更新设置配置
        self.group_widget.save_groups(self.settings)

    def on_group_selected(self, group_name):
        self.current_group = group_name
        music_files = self.group_widget.get_music_files(group_name)
        self.music_list_widget.set_music_files(music_files)

    def on_group_deleted(self, group_name):
        if self.current_group == group_name:
            self.current_group = None
            self.music_list_widget.set_music_files([])

        # 删除分组下的音乐快捷键
        if group_name in self.group_widget.groups:
            for music_path in self.group_widget.groups[group_name]:
                hotkey = self.music_list_widget.get_hotkey_for_music(
                    music_path)
                if hotkey and hotkey in self.shortcuts:
                    self.shortcuts[hotkey][1].deleteLater()
                    del self.shortcuts[hotkey]

        # 同步更新设置配置
        self.group_widget.save_groups(self.settings)
        self.music_list_widget.save_hotkeys(self.settings)

    def on_delete_music_requested(self, music_path):
        if self.current_group:
            if music_path in self.group_widget.groups[self.current_group]:
                self.group_widget.groups[self.current_group].remove(music_path)
                self.music_list_widget.set_music_files(
                    self.group_widget.groups[self.current_group])

                # 如果这个音乐有快捷键，移除它
                hotkey = self.music_list_widget.get_hotkey_for_music(
                    music_path)
                if hotkey and hotkey in self.shortcuts:
                    del self.shortcuts[hotkey]

        self.start_global_hotkey_listener()
        # 同步更新设置配置
        self.group_widget.save_groups(self.settings)

    def on_move_music_requested(self, music_path):
        if not self.current_group:
            return

        # 获取所有分组，排除当前分组
        groups = [g for g in self.group_widget.get_all_groups() if g !=
                  self.current_group]

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
            self.music_list_widget.set_music_files(
                self.group_widget.groups[self.current_group])
        # 同步更新设置配置
        self.group_widget.save_groups(self.settings)

    def record_hotkey_dialog(self, music_path, current_hotkey):
        dialog = QDialog(self)
        dialog.setWindowTitle("录制快捷键")
        layout = QVBoxLayout()

        self.keys_pressed = []
        self.formatted_keys = []

        label = QLabel(
            f"正在录制快捷键...\n请按下任意组合键后点击 确定 或按 Enter 确认\n当前快捷键: {current_hotkey or '无'}")
        layout.addWidget(label)

        confirm_btn = QPushButton("确定")
        confirm_btn.clicked.connect(lambda: dialog.done(QDialog.Accepted))
        layout.addWidget(confirm_btn)

        dialog.setLayout(layout)
        dialog.setModal(True)

        def on_press(key):
            try:
                char_key = key.char.lower()
                if char_key not in self.formatted_keys:
                    self.keys_pressed.append(char_key)
                    self.formatted_keys.append(char_key)
                    label.setText(
                        f"已记录: {'+'.join(self.formatted_keys)}\n点击 确定 或按 Enter 完成")
            except AttributeError:
                # 处理特殊按键
                special_keys = {
                    keyboard.Key.ctrl_l: 'Ctrl',
                    keyboard.Key.ctrl_r: 'Ctrl',
                    keyboard.Key.shift_l: 'Shift',
                    keyboard.Key.shift_r: 'Shift',
                    keyboard.Key.alt_l: 'Alt',
                    keyboard.Key.alt_r: 'Alt',
                    keyboard.Key.cmd_l: 'Cmd',
                    keyboard.Key.cmd_r: 'Cmd',
                    keyboard.Key.enter: 'Enter',
                    keyboard.Key.esc: 'Esc',
                }

                if key in special_keys:
                    k = special_keys[key]
                    if k not in self.formatted_keys:
                        self.formatted_keys.append(k)
                        label.setText(
                            f"已记录: {'+'.join(self.formatted_keys)}\n点击 确定 或按 Enter 完成")
                elif hasattr(key, 'name'):
                    # F1-F12 等功能键
                    k = key.name.capitalize()
                    if k not in self.formatted_keys:
                        self.formatted_keys.append(k)
                        label.setText(
                            f"已记录: {'+'.join(self.formatted_keys)}\n点击 确定 或按 Enter 完成")

        def on_release(key):
            if key == keyboard.Key.enter:
                dialog.accept()
                return False
            elif key == keyboard.Key.esc:
                dialog.reject()
                return False

        listener = keyboard.Listener(
            on_press=on_press, on_release=on_release, daemon=True)
        listener.start()

        result = dialog.exec_()
        listener.stop()

        if result == QDialog.Accepted and self.formatted_keys:
            modifiers = ['Ctrl', 'Shift', 'Alt', 'Cmd']
            modifier_set = set()
            normal_keys = []

            for k in self.formatted_keys:
                if k in modifiers:
                    modifier_set.add(k)
                else:
                    normal_keys.append(k)

            ordered_modifiers = sorted(
                modifier_set, key=lambda x: modifiers.index(x))
            final_keys = ordered_modifiers + normal_keys
            formatted_parts = []
            for k in final_keys:
                if k in ['Enter', 'Ctrl', 'Shift', 'Alt', 'Cmd', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12']:
                    formatted_parts.append(f"<{k}>")
                else:
                    formatted_parts.append(k)
            formatted_string = "+".join(formatted_parts)
            return formatted_string, True
        else:
            return None, False

    def set_music_hotkey(self, music_path, current_hotkey):
        hotkey, ok = self.record_hotkey_dialog(music_path, current_hotkey)

        if ok:
            # 检查快捷键是否已被占用
            if hotkey and hotkey in self.shortcuts and self.shortcuts[hotkey] != music_path:
                QMessageBox.warning(
                    self, "警告", f"快捷键 {hotkey} 已被 {os.path.basename(self.shortcuts[hotkey][0])} 占用!")
                return

            # 移除旧的快捷键
            if current_hotkey in self.shortcuts:
                del self.shortcuts[current_hotkey]

            # 设置新的快捷键
            if hotkey:
                self.shortcuts[hotkey] = music_path
                # 保存到列表显示
                self.music_list_widget.set_hotkey(music_path, hotkey)
                self.start_global_hotkey_listener()
            else:
                # 清除快捷键
                self.music_list_widget.set_hotkey(music_path, "")
            
            # 重新启动全局快捷键监听器
            self.start_global_hotkey_listener()

            # 同步更新设置配置
            self.group_widget.save_groups(self.settings)

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
                    self.device_combo.setCurrentIndex(
                        self.device_combo.count() - 1)

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
            self.shortcuts[hotkey] = music_path

        self.start_global_hotkey_listener()

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
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "程序仍在运行",
            "点击托盘图标可重新打开窗口",
            QSystemTrayIcon.Information,
            3000
        )

    def show_window(self):
        """显示主窗口"""
        self.showNormal()
        self.activateWindow()

    def on_tray_activated(self, reason):
        """托盘图标双击事件"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def start_global_hotkey_listener(self):
        if self.hotkey_listener:
            # 如果已存在监听器，先停止它
            try:
                self.hotkey_listener.stop()
            except:
                pass
            self.hotkey_listener = None

        if self.shortcuts:
            log.info("当前注册的快捷键:", self.shortcuts)
            # 创建新的监听器，并绑定对应的回调函数
            self.hotkey_listener = keyboard.GlobalHotKeys(
                {hotkey: lambda hk=hotkey: self.toggle_play_music(
                    self.shortcuts[hk]) for hotkey in self.shortcuts}
            )
            

            def for_thread():
                with self.hotkey_listener:
                    self.hotkey_listener.join()

            # 设置 daemon=True 表示该线程为守护线程，主程序退出时自动结束
            thread = threading.Thread(target=for_thread, daemon=True)
            thread.start()

    def quit(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        # 保存设置
        self.save_settings()
        # 停止播放并退出
        self.stop_music()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MusicPlayerApp()
    player.show()
    sys.exit(app.exec_())
