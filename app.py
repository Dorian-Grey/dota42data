"""
DOTA2积分系统 - Flask后端
使用 Google Gemini API 进行图片识别
"""
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

import database as db
from ocr_parser import get_parser, create_match_from_manual_input, is_api_available, set_api_key

app = Flask(__name__, static_folder='static')
CORS(app)

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== API路由 ====================

@app.route('/api/status', methods=['GET'])
def api_status():
    """系统状态"""
    return jsonify({
        "status": "running",
        "api_available": is_api_available(),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/set_api_key', methods=['POST'])
def set_gemini_api_key():
    """设置 Gemini API Key"""
    data = request.json
    api_key = data.get("api_key", "").strip()
    
    if not api_key:
        return jsonify({"error": "API Key不能为空"}), 400
    
    set_api_key(api_key)
    
    # 保存到配置文件
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")
    except:
        pass
    
    return jsonify({
        "success": True,
        "message": "API Key已设置"
    })


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """上传图片并解析"""
    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "没有选择文件"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "不支持的文件格式"}), 400
    
    # 保存文件
    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # 检查API是否可用
    if not is_api_available():
        return jsonify({
            "error": "请先设置 Gemini API Key",
            "image_path": filepath,
            "filename": filename,
            "api_available": False
        })
    
    # 使用 DeepSeek API 解析
    parser = get_parser()
    result = parser.parse_image(filepath)
    result["image_path"] = filepath
    result["filename"] = filename
    
    return jsonify(result)


@app.route('/api/match', methods=['POST'])
def add_match():
    """添加比赛记录"""
    data = request.json
    if not data:
        return jsonify({"error": "无效的数据"}), 400
    
    # 验证必要字段
    if not data.get("winner"):
        return jsonify({"error": "请指定获胜方"}), 400
    
    if not data.get("radiant_players") and not data.get("dire_players"):
        return jsonify({"error": "请添加玩家信息"}), 400
    
    # 创建比赛数据
    match_data = create_match_from_manual_input(data)
    match_data["date"] = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # 保存到数据库
    match_id = db.add_match(match_data)
    
    return jsonify({
        "success": True,
        "match_id": match_id,
        "message": "比赛记录已添加"
    })


@app.route('/api/match/<int:match_id>', methods=['DELETE'])
def delete_match(match_id):
    """删除比赛记录"""
    success = db.delete_match(match_id)
    if success:
        return jsonify({"success": True, "message": "比赛记录已删除"})
    else:
        return jsonify({"error": "比赛记录不存在"}), 404


@app.route('/api/matches', methods=['GET'])
def get_matches():
    """获取所有比赛记录"""
    matches = db.get_all_matches()
    return jsonify(matches)


@app.route('/api/players', methods=['GET'])
def get_players():
    """获取所有玩家"""
    players = db.get_all_players()
    return jsonify(players)


@app.route('/api/player/<name>', methods=['GET'])
def get_player(name):
    """获取玩家详情"""
    player = db.get_player_detail(name)
    if player:
        return jsonify(player)
    else:
        return jsonify({"error": "玩家不存在"}), 404


@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """获取排行榜"""
    leaderboard = db.get_leaderboard()
    return jsonify(leaderboard)


@app.route('/api/export', methods=['GET'])
def export_data():
    """导出数据到Excel"""
    try:
        filename = db.export_to_excel()
        return jsonify({
            "success": True,
            "filename": filename,
            "message": "数据已导出"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """下载文件"""
    return send_from_directory('.', filename, as_attachment=True)


# ==================== 前端页面 ====================

@app.route('/')
def index():
    """主页"""
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """静态文件"""
    return send_from_directory('static', filename)


# 启动时尝试加载环境变量中的API Key
def load_api_key():
    """从环境变量或.env文件加载API Key"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not api_key:
        try:
            if os.path.exists(".env"):
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
        except:
            pass
    
    if api_key:
        set_api_key(api_key)
        return True
    return False


if __name__ == '__main__':
    print("=" * 50)
    print("DOTA2 积分系统启动中...")
    
    has_key = load_api_key()
    print(f"Gemini API: {'已配置' if has_key else '未配置（请在界面中设置）'}")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
