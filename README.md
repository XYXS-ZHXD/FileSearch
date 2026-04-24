# FileSearch — 便携式文件搜索工具

Windows 平台便携文件搜索工具，基于 Python + Tkinter 编写，PyInstaller 打包为单文件 EXE，不依赖 Everything，可直接放在 U 盘运行。

## 功能特性

- 🔍 **模糊搜索**：支持多关键词 OR 匹配，按匹配度排序
- 📂 **双击打开**：双击或回车直接打开文件
- 📋 **右键菜单**：打开文件、打开所在文件夹、复制文件名/路径、复制文件到剪贴板
- 📊 **按列排序**：文件名、类型、大小、修改时间、相对路径
- 🎨 **深色主题**：Catppuccin Macchiato 配色
- ⚡ **流式显示**：边搜边显示，实时更新结果
- 💾 **便携设计**：不写注册表，不依赖系统环境，放 U 盘即用

## 运行方式

### 直接运行 EXE（推荐）
下载 [FileSearch.exe](https://github.com/XYXS-ZHXD/FileSearch/releases) 双击运行。

### 从源码运行
```bash
python filesearch.py
```

## 依赖

- Python 3.8+
- 仅使用 Python 标准库（tkinter、ctypes、os、subprocess 等），**无需安装任何第三方包**

## 构建 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --console --name "FileSearch" --icon icon.svg filesearch.py
```

## 项目结构

```
FileSearch/
├── filesearch.py      # 主程序源代码
├── icon.svg           # 程序图标（SVG 格式）
├── FileSearch.spec    # PyInstaller 构建配置
└── README.md
```

## License

MIT
