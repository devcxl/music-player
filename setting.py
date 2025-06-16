import os
import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional

class AppSettings:
    def __init__(self, app_name: str, default_settings: Optional[Dict[str, Any]] = None):
        """
        初始化跨平台设置类
        
        :param app_name: 应用程序名称，将作为配置文件夹名
        :param default_settings: 默认配置字典
        """
        self.app_name = app_name
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "settings.json"
        self.settings = default_settings or {}
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 如果配置文件存在，则加载
        if self.config_file.exists():
            self.load()
    
    def _get_config_dir(self) -> Path:
        """根据操作系统返回适当的配置目录"""
        system = platform.system()
        
        if system == "Windows":
            base_dir = Path(os.environ.get("APPDATA", Path.home()))
        elif system == "Darwin":  # macOS
            base_dir = Path.home() / "Library" / "Application Support"
        else:  # Linux和其他Unix-like系统
            base_dir = Path.home()
            # 遵循XDG规范
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                base_dir = Path(xdg_config)
            else:
                base_dir = base_dir / ".config"
        
        return base_dir / self.app_name
    
    def load(self) -> None:
        """从配置文件加载设置"""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.settings.update(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load settings: {e}")
    
    def save(self) -> None:
        """保存当前设置到配置文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Error: Failed to save settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取设置值"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any, save_immediately: bool = False) -> None:
        """设置值"""
        self.settings[key] = value
        if save_immediately:
            self.save()
    
    def update(self, new_settings: Dict[str, Any], save_immediately: bool = False) -> None:
        """批量更新设置"""
        self.settings.update(new_settings)
        if save_immediately:
            self.save()
    
    def reset_to_defaults(self) -> None:
        """重置为默认设置"""
        self.settings = {}
        self.save()
    
    @property
    def config_file_path(self) -> str:
        """返回配置文件完整路径"""
        return str(self.config_file)