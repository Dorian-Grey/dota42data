# DOTA2 积分系统

一个用于记录和统计DOTA2比赛数据的积分系统，支持截图OCR识别和手动录入。

## 功能特点

- 📤 **截图上传**: 支持上传小黑盒比赛截图，使用 Gemini AI 自动识别玩家信息
- ✏️ **手动录入**: 当OCR识别不准确时，支持手动录入比赛数据
- 🏆 **积分系统**: 
  - 胜利 +1分
  - 失败 -1分
  - MVP 额外 +0.5分
  - SVP 不扣分
  - 僵 额外 -0.5分
- 📊 **数据统计**:
  - 总场次、胜场、负场
  - 胜率统计
  - 称号统计（MVP、SVP、僵）
- 👥 **关系统计**:
  - 作为队友的胜率
  - 作为对手的胜率
- 📈 **积分排行榜**: 实时积分排名
- 📥 **数据导出**: 支持导出Excel文件

## 安装和运行

### 环境要求

- Python 3.8+
- uv (Python包管理器)

### 安装步骤

1. 创建虚拟环境：

```bash
uv venv
```

2. 激活虚拟环境并安装依赖：

```bash
# Windows PowerShell
.venv\Scripts\activate
uv pip install -r requirements.txt

# 或者一行命令
.venv\Scripts\activate; uv pip install flask flask-cors requests pillow pandas openpyxl werkzeug
```

3. 运行应用：

```bash
# 确保已激活虚拟环境
.venv\Scripts\activate; python app.py
```

4. 打开浏览器访问：

```
http://localhost:5000
```

5. 首次使用需要设置 Gemini API Key：
   - 点击右上角 **⚙️ 设置** 按钮
   - 输入你的 Gemini API Key
   - API Key 获取地址：https://aistudio.google.com/apikey

## 使用说明

### 录入比赛

1. **上传截图**（可选）：
   - 点击上传区域或拖拽截图文件
   - 系统会尝试OCR识别玩家信息
   - 识别结果会自动填充到表单

2. **选择获胜方**：
   - 点击"天辉"或"夜魔"按钮

3. **填写玩家信息**：
   - 输入玩家名称
   - 点击选择称号标签（MVP、SVP、僵等）

4. **提交记录**：
   - 点击"提交比赛记录"保存

### 查看积分榜

- 点击导航栏"积分榜"查看排名
- 点击玩家名称查看详细统计

### 查看比赛记录

- 点击导航栏"比赛记录"查看历史比赛
- 可以删除错误的比赛记录

### 导出数据

- 点击导航栏"导出数据"生成Excel文件

## 称号说明

| 称号 | 说明 |
|------|------|
| MVP | 最有价值玩家 |
| SVP | 最无价值玩家（失败不扣分） |
| 僵 | 僵尸 |


## 数据存储

- 比赛数据存储在 `game_data.json` 文件中
- 上传的截图保存在 `uploads/` 目录

## 项目结构

```
dota积分系统/
├── app.py              # Flask主应用
├── database.py         # 数据库操作
├── ocr_parser.py       # Gemini AI图片识别
├── requirements.txt    # Python依赖
├── game_data.json      # 数据存储文件（自动生成）
├── .env                # API Key配置（自动生成）
├── .venv/              # Python虚拟环境
├── static/
│   └── index.html      # 前端页面
├── uploads/            # 截图上传目录
└── README.md           # 说明文档
```

## 技术栈

- **后端**: Python + Flask
- **前端**: HTML + CSS + JavaScript
- **AI识别**: Google Gemini 2.5 Flash
- **数据存储**: JSON文件

## 注意事项

1. AI识别可能不完全准确，请在提交前核对玩家信息
2. 如果识别的阵营错误，可点击"一键交换阵营"按钮
3. 删除比赛记录会重新计算所有玩家的统计数据
4. 建议定期备份 `game_data.json` 文件

