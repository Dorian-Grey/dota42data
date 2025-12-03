"""
OCR图片识别模块
使用 Google Gemini API 解析小黑盒DOTA2比赛截图
"""
import os
import base64
import json
from typing import Dict
import requests

# Gemini API 配置
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# 已知的称号标签（只记录这三个）
KNOWN_TAGS = ["MVP", "SVP", "僵"]

def encode_image_to_base64(image_path: str) -> str:
    """将图片编码为base64"""
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")

def get_image_mime_type(image_path: str) -> str:
    """获取图片MIME类型"""
    ext = image_path.lower().split('.')[-1]
    mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    return mime_types.get(ext, 'image/jpeg')

class MatchParser:
    """比赛截图解析器 - 使用 Google Gemini API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        
    def set_api_key(self, api_key: str):
        """设置API Key"""
        self.api_key = api_key
    
    def parse_image(self, image_path: str) -> Dict:
        """
        使用 Gemini API 解析比赛截图
        返回比赛数据结构
        """
        if not self.api_key:
            return {"error": "请先设置 Gemini API Key"}
        
        if not os.path.exists(image_path):
            return {"error": f"图片不存在: {image_path}"}
        
        try:
            # 编码图片
            base64_image = encode_image_to_base64(image_path)
            mime_type = get_image_mime_type(image_path)
            
            # 构建提示词
            prompt = """这是一张DOTA2游戏比赛结果截图，请帮我识别其中的信息。

请提取：
1. 获胜方是哪一方（天辉或夜魔）
2. 所有玩家的昵称
3. 玩家的称号标签（只关注：MVP、SVP、僵 这三种）

截图说明：
- 图片分上下两部分，有"胜利"文字的是获胜方
- 每方有5个玩家
- 玩家昵称在头像旁边
- 称号标签是玩家名下方的小字

请用以下JSON格式回复：
{"winner":"天辉或夜魔","radiant_players":[{"name":"玩家名","tags":["MVP"]}],"dire_players":[{"name":"玩家名","tags":[]}]}

注意：天辉=Radiant，夜魔=Dire。只返回JSON，不要其他文字。"""

            # 调用 Gemini API
            url = f"{GEMINI_API_URL}?key={self.api_key}"
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": base64_image
                                }
                            },
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 2000
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                timeout=120
            )
            
            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"].get("message", response.text)
                except:
                    pass
                return {"error": f"API请求失败: {response.status_code} - {error_msg}"}
            
            result = response.json()
            
            # 提取响应内容
            candidates = result.get("candidates", [])
            if not candidates:
                # 检查是否有安全过滤
                prompt_feedback = result.get("promptFeedback", {})
                block_reason = prompt_feedback.get("blockReason", "")
                if block_reason:
                    return {"error": f"内容被过滤: {block_reason}"}
                return {"error": f"API未返回有效结果，原始响应: {str(result)[:500]}"}
            
            # 检查是否被安全过滤
            finish_reason = candidates[0].get("finishReason", "")
            if finish_reason == "SAFETY":
                safety_ratings = candidates[0].get("safetyRatings", [])
                return {"error": f"内容被安全过滤: {finish_reason}"}
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return {"error": f"API返回内容为空，finishReason: {finish_reason}，原始响应: {str(candidates[0])[:500]}"}
            
            text_content = parts[0].get("text", "")
            if not text_content:
                return {"error": "API返回文本为空"}
            
            # 解析JSON响应
            return self._parse_api_response(text_content)
            
        except requests.exceptions.Timeout:
            return {"error": "API请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            return {"error": f"网络错误: {str(e)}"}
        except Exception as e:
            return {"error": f"解析错误: {str(e)}"}
    
    def _parse_api_response(self, content: str) -> Dict:
        """解析API返回的内容"""
        try:
            # 尝试直接解析JSON
            # 移除可能的markdown代码块标记
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            # 验证和清理数据
            result = {
                "winner": data.get("winner", ""),
                "radiant_players": [],
                "dire_players": []
            }
            
            # 处理天辉玩家
            for player in data.get("radiant_players", []):
                if isinstance(player, dict) and player.get("name"):
                    cleaned_tags = []
                    for t in player.get("tags", []):
                        # 检查标签是否在已知列表中
                        if t in KNOWN_TAGS:
                            cleaned_tags.append(t)
                        else:
                            # 尝试匹配部分标签
                            for known in KNOWN_TAGS:
                                if known in t:
                                    cleaned_tags.append(known)
                                    break
                    
                    result["radiant_players"].append({
                        "name": player.get("name", "").strip(),
                        "hero": player.get("hero", ""),
                        "level": player.get("level", 0),
                        "kda": player.get("kda", ""),
                        "participation": player.get("participation", ""),
                        "damage": player.get("damage", ""),
                        "economy": player.get("economy", 0),
                        "tags": cleaned_tags
                    })
            
            # 处理夜魔玩家
            for player in data.get("dire_players", []):
                if isinstance(player, dict) and player.get("name"):
                    cleaned_tags = []
                    for t in player.get("tags", []):
                        if t in KNOWN_TAGS:
                            cleaned_tags.append(t)
                        else:
                            for known in KNOWN_TAGS:
                                if known in t:
                                    cleaned_tags.append(known)
                                    break
                    
                    result["dire_players"].append({
                        "name": player.get("name", "").strip(),
                        "hero": player.get("hero", ""),
                        "level": player.get("level", 0),
                        "kda": player.get("kda", ""),
                        "participation": player.get("participation", ""),
                        "damage": player.get("damage", ""),
                        "economy": player.get("economy", 0),
                        "tags": cleaned_tags
                    })
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                "error": f"JSON解析失败: {str(e)}",
                "raw_content": content
            }


def create_match_from_manual_input(data: Dict) -> Dict:
    """
    从手动输入创建比赛数据
    """
    match_data = {
        "winner": data.get("winner", ""),
        "radiant_players": [],
        "dire_players": []
    }
    
    for player in data.get("radiant_players", []):
        match_data["radiant_players"].append({
            "name": player.get("name", ""),
            "hero": player.get("hero", ""),
            "level": player.get("level", 0),
            "kda": player.get("kda", ""),
            "participation": player.get("participation", ""),
            "damage": player.get("damage", ""),
            "economy": player.get("economy", 0),
            "tags": player.get("tags", [])
        })
    
    for player in data.get("dire_players", []):
        match_data["dire_players"].append({
            "name": player.get("name", ""),
            "hero": player.get("hero", ""),
            "level": player.get("level", 0),
            "kda": player.get("kda", ""),
            "participation": player.get("participation", ""),
            "damage": player.get("damage", ""),
            "economy": player.get("economy", 0),
            "tags": player.get("tags", [])
        })
    
    return match_data


# 全局解析器实例
_parser = None

def get_parser() -> MatchParser:
    """获取解析器实例（延迟初始化）"""
    global _parser
    if _parser is None:
        _parser = MatchParser()
    return _parser

def set_api_key(api_key: str):
    """设置全局API Key"""
    get_parser().set_api_key(api_key)

def is_api_available() -> bool:
    """检查Gemini API是否配置"""
    return bool(get_parser().api_key)
