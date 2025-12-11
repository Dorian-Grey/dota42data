"""
数据库模型和操作
使用JSON文件存储数据，简单高效

积分规则：
- 胜方每人+1分，MVP额外+0.5分
- 负方每人-1分，SVP额外+0.5分，僵-0.5分
- 马匹分类：特等(前20%,价值1)、中等(60%,价值0)、自动(后20%,价值-1)
- 补分：阵容差距1分时失败弱方每人补偿0.5分，差距>=2分成绩无效

积分模式：
- 赛事模式：打满10局按积分排名，至少8局才能上排名
- 长期模式：所有比赛计入长期积分排名，用于马匹分类
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

DATA_FILE = "game_data.json"

# 马匹等级定义
HORSE_LEVELS = {
    "特等": 1,    # 前20%，价值1
    "中等": 0,    # 中间60%，价值0
    "自动": -1    # 后20%，价值-1
}

def init_database():
    """初始化数据库文件"""
    if not os.path.exists(DATA_FILE):
        data = {
            "matches": [],          # 比赛记录
            "players": {},          # 玩家统计
            "horse_overrides": {},  # 手动设置的马匹等级（未满20场时使用）
            "seasons": [],          # 赛事记录
            "current_season": None  # 当前赛事ID
        }
        save_data(data)
    else:
        # 确保数据文件包含新字段
        data = load_data()
        if "horse_overrides" not in data:
            data["horse_overrides"] = {}
        if "seasons" not in data:
            data["seasons"] = []
        if "current_season" not in data:
            data["current_season"] = None
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

def get_player_horse_level(data: dict, player_name: str) -> str:
    """
    获取玩家的马匹等级
    
    规则：
    - 打满20场后自动分类：特等(前20%)、中等(60%)、自动(后20%)
    - 未打满20场按手动设置（horse_overrides），未设置则返回空
    """
    # 检查是否有手动设置
    horse_overrides = data.get("horse_overrides", {})
    if player_name in horse_overrides:
        return horse_overrides[player_name]
    
    # 检查是否打满20场
    player = data.get("players", {}).get(player_name)
    if not player or player.get("total_games", 0) < 20:
        # 未打满20场且无手动设置，返回空字符串
        return ""
    
    # 打满20场，自动计算分类
    return calculate_auto_horse_level(data, player_name)


def calculate_auto_horse_level(data: dict, player_name: str) -> str:
    """
    自动计算马匹等级（基于长期积分排名）
    前20%为特等，中间60%为中等，后20%为自动
    """
    # 获取所有打满20场的玩家
    qualified_players = []
    for name, player in data.get("players", {}).items():
        if player.get("total_games", 0) >= 20:
            qualified_players.append({
                "name": name,
                "score": player.get("score", 0)
            })
    
    if not qualified_players:
        return "中等"
    
    # 按积分排序
    qualified_players.sort(key=lambda x: x["score"], reverse=True)
    total = len(qualified_players)
    
    # 找到当前玩家的排名
    rank = -1
    for i, p in enumerate(qualified_players):
        if p["name"] == player_name:
            rank = i + 1
            break
    
    if rank == -1:
        return "中等"
    
    # 计算百分比
    percentile = rank / total
    
    if percentile <= 0.2:
        return "特等"
    elif percentile <= 0.8:
        return "中等"
    else:
        return "自动"


def get_horse_value(horse_level: str):
    """获取马匹等级对应的价值，未分类返回None"""
    if not horse_level:
        return None
    return HORSE_LEVELS.get(horse_level, 0)


def calculate_team_score(data: dict, players: list) -> int:
    """
    计算阵容总分
    根据每个玩家的马匹等级计算阵容价值
    未分类的玩家按0计算
    """
    total = 0
    for player in players:
        name = player.get("name", "")
        if name:
            horse_level = get_player_horse_level(data, name)
            value = get_horse_value(horse_level)
            total += value if value is not None else 0
    return total


def calculate_compensation(data: dict, winner_players: list, loser_players: list) -> dict:
    """
    计算阵容补分
    
    规则：
    - 补分规则只有在所有选手都分类后才会启用
    - 阵容分数差距1分，失败弱者阵容每人补偿0.5分
    - 差距>=2分，成绩无效
    
    返回: {
        "winner_score": 胜方阵容分,
        "loser_score": 败方阵容分,
        "difference": 分差,
        "compensation": 补分数（败方弱者补偿）,
        "invalid": 是否无效（差距>=2分）,
        "all_classified": 是否所有选手都已分类
    }
    """
    # 检查是否所有玩家都有马匹分类
    all_classified = True
    all_players = winner_players + loser_players
    for player in all_players:
        name = player.get("name", "")
        if name:
            horse_level = get_player_horse_level(data, name)
            if not horse_level:  # 空字符串表示未分类
                all_classified = False
                break
    
    result = {
        "winner_score": 0,
        "loser_score": 0,
        "difference": 0,
        "compensation": 0,
        "invalid": False,
        "all_classified": all_classified
    }
    
    # 如果有玩家未分类，不计算补分
    if not all_classified:
        return result
    
    winner_score = calculate_team_score(data, winner_players)
    loser_score = calculate_team_score(data, loser_players)
    difference = winner_score - loser_score
    
    result["winner_score"] = winner_score
    result["loser_score"] = loser_score
    result["difference"] = difference
    
    # 如果胜方阵容更强，败方可能获得补分
    if difference > 0:
        if difference >= 2:
            # 差距>=2分，成绩无效
            result["invalid"] = True
        else:
            # 差距1分，败方每人补偿0.5分
            result["compensation"] = 0.5
    
    return result


def add_match(match_data: dict) -> dict:
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
    
    返回: {
        "match_id": 比赛ID,
        "compensation_info": 补分信息,
        "invalid": 是否无效
    }
    """
    data = load_data()
    
    match_id = len(data["matches"]) + 1
    match_data["id"] = match_id
    match_data["timestamp"] = datetime.now().isoformat()
    
    # 更新玩家统计
    winner = match_data.get("winner", "")
    radiant_players = match_data.get("radiant_players", [])
    dire_players = match_data.get("dire_players", [])
    
    radiant_won = (winner == "天辉")
    dire_won = (winner == "夜魔")
    
    # 计算阵容补分
    winner_players = radiant_players if radiant_won else dire_players
    loser_players = dire_players if radiant_won else radiant_players
    
    comp_info = calculate_compensation(data, winner_players, loser_players)
    match_data["compensation_info"] = comp_info
    
    # 处理天辉队
    bonus_radiant = comp_info["compensation"] if not radiant_won and comp_info["compensation"] > 0 else 0
    for player in radiant_players:
        update_player_stats(data, player, radiant_won, dire_players, bonus_radiant)
    
    # 处理夜魔队
    bonus_dire = comp_info["compensation"] if not dire_won and comp_info["compensation"] > 0 else 0
    for player in dire_players:
        update_player_stats(data, player, dire_won, radiant_players, bonus_dire)
    
    # 记录队友和对手关系
    update_teammate_opponent_stats(data, match_data)
    
    data["matches"].append(match_data)
    save_data(data)
    
    return {
        "match_id": match_id,
        "compensation_info": comp_info,
        "invalid": comp_info["invalid"]
    }

def update_player_stats(data: dict, player: dict, won: bool, opponents: list, bonus_score: float = 0):
    """
    更新单个玩家的统计数据
    
    积分规则：
    - 胜方每人+1分，MVP额外+0.5分
    - 负方每人-1分，SVP额外+0.5分，僵-0.5分
    - bonus_score: 补分（阵容差距补偿）
    """
    name = player.get("name", "")
    if not name:
        return
    
    tags = player.get("tags", [])
    is_mvp = "MVP" in tags
    is_svp = "SVP" in tags
    is_jiang = "僵" in tags  # 僵标签，负方僵-0.5分
    
    if name not in data["players"]:
        data["players"][name] = {
            "name": name,
            "total_games": 0,
            "wins": 0,
            "losses": 0,
            "score": 0,              # 长期积分
            "season_score": 0,       # 赛事积分
            "season_games": 0,       # 赛事场次
            "mvp_count": 0,
            "svp_count": 0,
            "jiang_count": 0,
            "teammates": {},         # 队友胜率统计
            "opponents": {}          # 对手胜率统计
        }
    
    p = data["players"][name]
    p["total_games"] += 1
    
    # 基础积分
    if won:
        p["wins"] += 1
        p["score"] += 1  # 胜方+1分
        # MVP额外+0.5分（仅胜方有MVP）
        if is_mvp:
            p["score"] += 0.5
    else:
        p["losses"] += 1
        p["score"] -= 1  # 负方-1分
        # SVP额外+0.5分（仅负方有SVP）
        if is_svp:
            p["score"] += 0.5
        # 僵-0.5分（仅负方有僵）
        if is_jiang:
            p["score"] -= 0.5
    
    # 补分（阵容差距补偿，仅负方可能获得）
    if bonus_score > 0:
        p["score"] += bonus_score
    
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

def set_horse_level(player_name: str, level: str) -> bool:
    """
    手动设置玩家的马匹等级（用于未满20场的玩家）
    level: "特等" / "中等" / "自动"
    """
    if level not in HORSE_LEVELS:
        return False
    
    data = load_data()
    if "horse_overrides" not in data:
        data["horse_overrides"] = {}
    
    data["horse_overrides"][player_name] = level
    save_data(data)
    return True


def remove_horse_override(player_name: str) -> bool:
    """移除玩家的手动马匹等级设置"""
    data = load_data()
    if player_name in data.get("horse_overrides", {}):
        del data["horse_overrides"][player_name]
        save_data(data)
        return True
    return False


def get_all_horse_levels() -> Dict[str, str]:
    """获取所有玩家的马匹等级"""
    data = load_data()
    result = {}
    
    for name in data.get("players", {}).keys():
        result[name] = get_player_horse_level(data, name)
    
    return result


def get_all_players() -> List[dict]:
    """获取所有玩家统计（含马匹等级）"""
    data = load_data()
    players = list(data["players"].values())
    
    # 计算胜率和马匹等级
    for p in players:
        name = p["name"]
        if p["total_games"] > 0:
            p["win_rate"] = round(p["wins"] / p["total_games"] * 100, 1)
        else:
            p["win_rate"] = 0
        
        # 添加马匹等级信息
        p["horse_level"] = get_player_horse_level(data, name)
        p["horse_value"] = get_horse_value(p["horse_level"])
        p["is_horse_auto"] = p["total_games"] >= 20 and name not in data.get("horse_overrides", {})
    
    # 按积分排序
    players.sort(key=lambda x: x["score"], reverse=True)
    return players

def get_player_detail(name: str) -> Optional[dict]:
    """获取玩家详细信息，包括队友和对手胜率及马匹等级"""
    data = load_data()
    if name not in data["players"]:
        return None
    
    player = data["players"][name].copy()
    
    # 计算总胜率
    if player["total_games"] > 0:
        player["win_rate"] = round(player["wins"] / player["total_games"] * 100, 1)
    else:
        player["win_rate"] = 0
    
    # 添加马匹等级信息
    player["horse_level"] = get_player_horse_level(data, name)
    player["horse_value"] = get_horse_value(player["horse_level"])
    player["is_horse_auto"] = player["total_games"] >= 20 and name not in data.get("horse_overrides", {})
    
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
               "win_rate", "mvp_count", "svp_count", "jiang_count", 
               "horse_level", "horse_value"]
    df = df[[c for c in columns if c in df.columns]]
    
    # 重命名列
    df.columns = ["玩家", "总场次", "胜场", "负场", "积分", 
                  "胜率%", "MVP次数", "SVP次数", "僵次数",
                  "马匹等级", "马匹价值"]
    
    df.to_excel(filename, index=False)
    return filename


def preview_team_balance(radiant_names: List[str], dire_names: List[str]) -> dict:
    """
    预览两队阵容平衡情况（用于录入前检查）
    
    返回: {
        "radiant_score": 天辉阵容分,
        "dire_score": 夜魔阵容分,
        "difference": 分差,
        "radiant_players": [{"name": xx, "horse_level": xx, "horse_value": xx}, ...],
        "dire_players": [...],
        "warning": 警告信息,
        "all_classified": 是否所有选手都已分类
    }
    """
    data = load_data()
    
    all_classified = True
    radiant_info = []
    radiant_total = 0
    for name in radiant_names:
        if name:
            level = get_player_horse_level(data, name)
            value = get_horse_value(level)
            if not level:
                all_classified = False
            radiant_info.append({
                "name": name,
                "horse_level": level,
                "horse_value": value if value is not None else 0
            })
            radiant_total += value if value is not None else 0
    
    dire_info = []
    dire_total = 0
    for name in dire_names:
        if name:
            level = get_player_horse_level(data, name)
            value = get_horse_value(level)
            if not level:
                all_classified = False
            dire_info.append({
                "name": name,
                "horse_level": level,
                "horse_value": value if value is not None else 0
            })
            dire_total += value if value is not None else 0
    
    difference = abs(radiant_total - dire_total)
    
    warning = ""
    if not all_classified:
        warning = "ℹ️ 有选手未分类马匹，补分规则暂不启用"
    elif difference >= 2:
        warning = f"⚠️ 阵容差距{difference}分（>=2分），若比赛完成成绩将无效！"
    elif difference == 1:
        weak_team = "天辉" if radiant_total < dire_total else "夜魔"
        warning = f"阵容差距{difference}分，若{weak_team}失败每人可获得0.5分补偿"
    
    return {
        "radiant_score": radiant_total,
        "dire_score": dire_total,
        "difference": difference,
        "radiant_players": radiant_info,
        "dire_players": dire_info,
        "warning": warning,
        "all_classified": all_classified
    }

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
    recalculate_all_stats(data)
    
    save_data(data)
    return True

def get_match(match_id: int) -> Optional[dict]:
    """获取指定比赛记录"""
    data = load_data()
    for match in data["matches"]:
        if match.get("id") == match_id:
            return match
    return None

def update_match(match_id: int, match_data: dict) -> bool:
    """更新指定比赛记录并重新计算统计"""
    data = load_data()
    
    # 找到要更新的比赛
    match_index = None
    for i, match in enumerate(data["matches"]):
        if match.get("id") == match_id:
            match_index = i
            break
    
    if match_index is None:
        return False
    
    # 保留原有的id和timestamp
    original_id = data["matches"][match_index].get("id")
    original_timestamp = data["matches"][match_index].get("timestamp")
    
    # 更新比赛数据
    match_data["id"] = original_id
    match_data["timestamp"] = original_timestamp
    data["matches"][match_index] = match_data
    
    # 重新计算所有玩家统计
    recalculate_all_stats(data)
    
    save_data(data)
    return True

def recalculate_all_stats(data: dict):
    """重新计算所有玩家统计（使用新积分规则）"""
    data["players"] = {}
    
    for match in data["matches"]:
        winner = match.get("winner", "")
        radiant_players = match.get("radiant_players", [])
        dire_players = match.get("dire_players", [])
        radiant_won = (winner == "天辉")
        dire_won = (winner == "夜魔")
        
        # 获取补分信息（如果有的话）
        comp_info = match.get("compensation_info", {})
        compensation = comp_info.get("compensation", 0)
        
        # 处理天辉队
        bonus_radiant = compensation if not radiant_won and compensation > 0 else 0
        for player in radiant_players:
            update_player_stats(data, player, radiant_won, dire_players, bonus_radiant)
        
        # 处理夜魔队
        bonus_dire = compensation if not dire_won and compensation > 0 else 0
        for player in dire_players:
            update_player_stats(data, player, dire_won, radiant_players, bonus_dire)
        
        update_teammate_opponent_stats(data, match)

# 初始化数据库
init_database()

