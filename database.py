"""
数据库模型和操作
使用JSON文件存储数据，简单高效
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

DATA_FILE = "game_data.json"

def init_database():
    """初始化数据库文件"""
    if not os.path.exists(DATA_FILE):
        data = {
            "matches": [],  # 比赛记录
            "players": {}   # 玩家统计
        }
        save_data(data)
    return load_data()

def load_data() -> dict:
    """加载数据"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"matches": [], "players": {}}

def save_data(data: dict):
    """保存数据"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_match(match_data: dict) -> int:
    """
    添加一场比赛记录
    match_data: {
        "date": "2025-12-02",
        "winner": "夜魔",  # 或 "天辉"
        "radiant_players": [...],  # 天辉队玩家列表
        "dire_players": [...],     # 夜魔队玩家列表
    }
    每个玩家: {
        "name": "玩家名",
        "hero": "英雄名",
        "level": 28,
        "kda": "15/4/13",
        "participation": "50.0%",
        "damage": "19.7%",
        "economy": 3936,
        "tags": ["MVP", "稳", "壕"]  # 称号标签
    }
    """
    data = load_data()
    
    match_id = len(data["matches"]) + 1
    match_data["id"] = match_id
    match_data["timestamp"] = datetime.now().isoformat()
    
    # 更新玩家统计
    winner = match_data.get("winner", "")
    
    # 处理天辉队
    radiant_won = (winner == "天辉")
    for player in match_data.get("radiant_players", []):
        update_player_stats(data, player, radiant_won, match_data.get("dire_players", []))
    
    # 处理夜魔队
    dire_won = (winner == "夜魔")
    for player in match_data.get("dire_players", []):
        update_player_stats(data, player, dire_won, match_data.get("radiant_players", []))
    
    # 记录队友和对手关系
    update_teammate_opponent_stats(data, match_data)
    
    data["matches"].append(match_data)
    save_data(data)
    
    return match_id

def update_player_stats(data: dict, player: dict, won: bool, opponents: list):
    """更新单个玩家的统计数据"""
    name = player.get("name", "")
    if not name:
        return
    
    tags = player.get("tags", [])
    is_mvp = "MVP" in tags
    is_svp = "SVP" in tags
    is_jiang = "僵" in tags  # 僵尸标签
    
    if name not in data["players"]:
        data["players"][name] = {
            "name": name,
            "total_games": 0,
            "wins": 0,
            "losses": 0,
            "score": 0,
            "mvp_count": 0,
            "svp_count": 0,
            "jiang_count": 0,
            "teammates": {},    # 队友胜率统计
            "opponents": {}     # 对手胜率统计
        }
    
    p = data["players"][name]
    p["total_games"] += 1
    
    if won:
        p["wins"] += 1
        p["score"] += 1
    else:
        p["losses"] += 1
        # SVP不扣分
        if not is_svp:
            p["score"] -= 1
    
    # 更新称号统计
    if is_mvp:
        p["mvp_count"] += 1
    if is_svp:
        p["svp_count"] += 1
    if is_jiang:
        p["jiang_count"] += 1

def update_teammate_opponent_stats(data: dict, match_data: dict):
    """更新队友和对手统计"""
    winner = match_data.get("winner", "")
    radiant_players = [p["name"] for p in match_data.get("radiant_players", []) if p.get("name")]
    dire_players = [p["name"] for p in match_data.get("dire_players", []) if p.get("name")]
    
    radiant_won = (winner == "天辉")
    dire_won = (winner == "夜魔")
    
    # 更新天辉队内部队友关系
    for i, name1 in enumerate(radiant_players):
        if name1 not in data["players"]:
            continue
        p1 = data["players"][name1]
        
        # 队友关系
        for j, name2 in enumerate(radiant_players):
            if i != j:
                if name2 not in p1["teammates"]:
                    p1["teammates"][name2] = {"games": 0, "wins": 0}
                p1["teammates"][name2]["games"] += 1
                if radiant_won:
                    p1["teammates"][name2]["wins"] += 1
        
        # 对手关系
        for name2 in dire_players:
            if name2 not in p1["opponents"]:
                p1["opponents"][name2] = {"games": 0, "wins": 0}
            p1["opponents"][name2]["games"] += 1
            if radiant_won:
                p1["opponents"][name2]["wins"] += 1
    
    # 更新夜魔队内部队友关系
    for i, name1 in enumerate(dire_players):
        if name1 not in data["players"]:
            continue
        p1 = data["players"][name1]
        
        # 队友关系
        for j, name2 in enumerate(dire_players):
            if i != j:
                if name2 not in p1["teammates"]:
                    p1["teammates"][name2] = {"games": 0, "wins": 0}
                p1["teammates"][name2]["games"] += 1
                if dire_won:
                    p1["teammates"][name2]["wins"] += 1
        
        # 对手关系
        for name2 in radiant_players:
            if name2 not in p1["opponents"]:
                p1["opponents"][name2] = {"games": 0, "wins": 0}
            p1["opponents"][name2]["games"] += 1
            if dire_won:
                p1["opponents"][name2]["wins"] += 1

def get_all_players() -> List[dict]:
    """获取所有玩家统计"""
    data = load_data()
    players = list(data["players"].values())
    
    # 计算胜率
    for p in players:
        if p["total_games"] > 0:
            p["win_rate"] = round(p["wins"] / p["total_games"] * 100, 1)
        else:
            p["win_rate"] = 0
    
    # 按积分排序
    players.sort(key=lambda x: x["score"], reverse=True)
    return players

def get_player_detail(name: str) -> Optional[dict]:
    """获取玩家详细信息，包括队友和对手胜率"""
    data = load_data()
    if name not in data["players"]:
        return None
    
    player = data["players"][name].copy()
    
    # 计算总胜率
    if player["total_games"] > 0:
        player["win_rate"] = round(player["wins"] / player["total_games"] * 100, 1)
    else:
        player["win_rate"] = 0
    
    # 计算队友胜率（和谁一起时胜率从高到低）
    teammate_stats = []
    for teammate, stats in player.get("teammates", {}).items():
        if stats["games"] > 0:
            win_rate = round(stats["wins"] / stats["games"] * 100, 1)
            teammate_stats.append({
                "name": teammate,
                "games": stats["games"],
                "wins": stats["wins"],
                "win_rate": win_rate
            })
    # 按胜率从高到低排序（和谁一起赢得最多）
    teammate_stats.sort(key=lambda x: (-x["win_rate"], -x["games"]))
    player["teammate_stats"] = teammate_stats
    
    # 计算对手胜率（对面赢我的胜率，从高到低 = 我输得最多的对手）
    opponent_stats = []
    for opponent, stats in player.get("opponents", {}).items():
        if stats["games"] > 0:
            # 我的胜场
            my_wins = stats["wins"]
            # 对手的胜场 = 总场次 - 我的胜场
            opponent_wins = stats["games"] - my_wins
            # 对手赢我的胜率
            opponent_win_rate = round(opponent_wins / stats["games"] * 100, 1)
            opponent_stats.append({
                "name": opponent,
                "games": stats["games"],
                "wins": opponent_wins,  # 对手赢的场次
                "my_wins": my_wins,     # 我赢的场次
                "win_rate": opponent_win_rate  # 对手的胜率
            })
    # 按对手胜率从高到低排序（遇到谁输得最多）
    opponent_stats.sort(key=lambda x: (-x["win_rate"], -x["games"]))
    player["opponent_stats"] = opponent_stats
    
    return player

def get_all_matches() -> List[dict]:
    """获取所有比赛记录"""
    data = load_data()
    matches = data["matches"]
    matches.reverse()  # 最新的在前
    return matches

def get_leaderboard() -> List[dict]:
    """获取积分排行榜"""
    players = get_all_players()
    for i, p in enumerate(players):
        p["rank"] = i + 1
    return players

def export_to_excel(filename: str = "dota_stats.xlsx"):
    """导出数据到Excel"""
    players = get_all_players()
    df = pd.DataFrame(players)
    
    # 选择要导出的列
    columns = ["name", "total_games", "wins", "losses", "score", 
               "win_rate", "mvp_count", "svp_count", "jiang_count"]
    df = df[[c for c in columns if c in df.columns]]
    
    # 重命名列
    df.columns = ["玩家", "总场次", "胜场", "负场", "积分", 
                  "胜率%", "MVP次数", "SVP次数", "僵次数"]
    
    df.to_excel(filename, index=False)
    return filename

def delete_match(match_id: int) -> bool:
    """删除指定比赛记录并重新计算统计"""
    data = load_data()
    
    # 找到要删除的比赛
    match_to_delete = None
    for match in data["matches"]:
        if match.get("id") == match_id:
            match_to_delete = match
            break
    
    if not match_to_delete:
        return False
    
    # 删除比赛
    data["matches"] = [m for m in data["matches"] if m.get("id") != match_id]
    
    # 重新计算所有玩家统计
    data["players"] = {}
    for match in data["matches"]:
        winner = match.get("winner", "")
        radiant_won = (winner == "天辉")
        dire_won = (winner == "夜魔")
        
        for player in match.get("radiant_players", []):
            update_player_stats(data, player, radiant_won, match.get("dire_players", []))
        
        for player in match.get("dire_players", []):
            update_player_stats(data, player, dire_won, match.get("radiant_players", []))
        
        update_teammate_opponent_stats(data, match)
    
    save_data(data)
    return True

# 初始化数据库
init_database()

