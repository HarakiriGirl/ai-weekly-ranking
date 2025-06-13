#!/usr/bin/env python3
"""
スコア計算・ランキング生成スクリプト
- processed/*.parquet からデータ読み込み
- ツール別スコア計算（前週 × 0.3 + 今週）
- ジャンル別TOP3ランキング生成
- weekly/*.parquet として保存
"""

import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import argparse

# 設定
DECAY_FACTOR = 0.0  # 前週スコア減衰係数

def get_current_week():
    """現在の週番号取得 (ISO週番号)"""
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"

def get_previous_week(current_week):
    """前週の週番号取得"""
    year, week = current_week.split('-W')
    year, week = int(year), int(week)
    
    # 前週計算
    current_date = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w")
    previous_date = current_date - timedelta(weeks=1)
    
    prev_year, prev_week, _ = previous_date.isocalendar()
    return f"{prev_year}-W{prev_week:02d}"

def load_genres():
    """ジャンル定義読み込み"""
    genres_path = Path("dataproc/config/genres.yml")
    
    if not genres_path.exists():
        print(f"Warning: {genres_path} not found. Using default genres.")
        return ['multi-ai', 'image', 'video', 'music', 'voice', 'research', 'coding', 'agent-workflow']
    
    with open(genres_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or []

def load_tools_dict():
    """ツール辞書読み込み（aggregate: true のみ）"""
    dict_path = Path("dataproc/dict/tools.yml")
    
    if not dict_path.exists():
        print(f"Warning: {dict_path} not found.")
        return {}
    
    with open(dict_path, 'r', encoding='utf-8') as f:
        tools_list = yaml.safe_load(f) or []
    
    # canonical name -> genre のマッピング作成（aggregate: true のみ）
    tools_map = {}
    for tool in tools_list:
        if tool.get('aggregate', True):  # デフォルトはTrue
            tools_map[tool['canonical']] = tool['genre']
    
    return tools_map

def load_current_week_data():
    """今週のprocessedデータ読み込み"""
    processed_dir = Path("dataproc/processed")
    
    # 最新のprocessedファイル検索（pending以外）
    parquet_files = [f for f in processed_dir.glob("*.parquet") if "pending" not in f.name]
    
    if not parquet_files:
        print("No processed data files found")
        return pd.DataFrame()
    
    # 最新ファイル使用
    latest_file = max(parquet_files, key=lambda x: x.stat().st_mtime)
    print(f"Reading current week data: {latest_file}")
    
    return pd.read_parquet(latest_file)

def load_previous_week_scores(previous_week):
    """前週のスコアデータ読み込み"""
    weekly_dir = Path("dataproc/aggregated")
    previous_file = weekly_dir / f"{previous_week}.parquet"
    
    if not previous_file.exists():
        print(f"No previous week data found: {previous_file}")
        return pd.DataFrame()
    
    print(f"Reading previous week scores: {previous_file}")
    return pd.read_parquet(previous_file)

def calculate_current_scores(df, tools_map):
    """今週のスコア計算"""
    current_scores = defaultdict(float)
    
    for _, row in df.iterrows():
        weight = row.get('weight', 1.0)
        matched_tools = row.get('matched_tools', {})
        
        if isinstance(matched_tools, dict):
            for tool, count in matched_tools.items():
                if tool in tools_map and count is not None:  # aggregate対象のツールのみ
                    current_scores[tool] += count * weight
    
    return dict(current_scores)

def merge_scores(current_scores, previous_df, tools_map):
    """今週・前週スコアを統合"""
    final_scores = defaultdict(float)
    
    # 今週のスコア追加
    for tool, score in current_scores.items():
        final_scores[tool] += score
    
    # 前週のスコア（減衰）追加
    if not previous_df.empty:
        for _, row in previous_df.iterrows():
            tool = row['tool']
            previous_score = row['score']
            
            if tool in tools_map:  # aggregate対象のツールのみ
                final_scores[tool] += previous_score * DECAY_FACTOR
    
    return dict(final_scores)

def create_rankings(scores, tools_map, genres):
    """ジャンル別ランキング作成"""
    # ツール別スコアデータ作成
    tools_data = []
    
    for tool, score in scores.items():
        if tool in tools_map and score > 0:
            tools_data.append({
                'tool': tool,
                'genre': tools_map[tool],
                'score': score
            })
    
    if not tools_data:
        print("No tools with scores found")
        return pd.DataFrame()
    
    tools_df = pd.DataFrame(tools_data)
    
    # ジャンル別TOP3作成
    rankings = []
    
    for genre in genres:
        genre_tools = tools_df[tools_df['genre'] == genre]
        
        if genre_tools.empty:
            print(f"No tools found for genre: {genre}")
            continue
        
        # スコア順でソート、TOP3取得
        top_tools = genre_tools.nlargest(3, 'score')
        
        for rank, (_, row) in enumerate(top_tools.iterrows(), 1):
            rankings.append({
                'genre': genre,
                'rank': rank,
                'tool': row['tool'],
                'score': row['score']
            })
    
    return pd.DataFrame(rankings)

def check_new_tools(current_scores, previous_df):
    """新規ツール判定"""
    if previous_df.empty:
        return set(current_scores.keys())
    
    previous_tools = set(previous_df['tool'].unique())
    current_tools = set(current_scores.keys())
    
    return current_tools - previous_tools

def generate_ranking(week=None):
    """ランキング生成メイン処理"""
    
    if week is None:
        week = get_current_week()
    
    print(f"Generating ranking for week: {week}")
    
    # 設定読み込み
    genres = load_genres()
    tools_map = load_tools_dict()
    
    print(f"Loaded {len(genres)} genres")
    print(f"Loaded {len(tools_map)} aggregate tools")
    
    # データ読み込み
    current_df = load_current_week_data()
    
    if current_df.empty:
        print("No current week data available")
        return
    
    previous_week = get_previous_week(week)
    previous_df = load_previous_week_scores(previous_week)
    
    # スコア計算
    current_scores = calculate_current_scores(current_df, tools_map)
    print(f"Calculated scores for {len(current_scores)} tools this week")
    
    final_scores = merge_scores(current_scores, previous_df, tools_map)
    print(f"Final scores for {len(final_scores)} tools")
    
    # 新規ツール検出
    new_tools = check_new_tools(current_scores, previous_df)
    if new_tools:
        print(f"New tools detected: {', '.join(new_tools)}")
    
    # ランキング作成
    rankings_df = create_rankings(final_scores, tools_map, genres)
    
    if rankings_df.empty:
        print("No rankings generated")
        return
    
    # 新規フラグ追加
    rankings_df['is_new'] = rankings_df['tool'].isin(new_tools)
    
    # 結果保存
    weekly_dir = Path("dataproc/aggregated")
    weekly_dir.mkdir(exist_ok=True)
    
    output_path = weekly_dir / f"{week}.parquet"
    rankings_df.to_parquet(output_path, index=False)
    
    print(f"\nRanking saved: {output_path}")
    print(f"Total rankings: {len(rankings_df)}")
    
    # サマリー表示
    print(f"\nRanking summary:")
    for genre in genres:
        genre_rankings = rankings_df[rankings_df['genre'] == genre]
        if not genre_rankings.empty:
            print(f"\n{genre}:")
            for _, row in genre_rankings.iterrows():
                new_marker = " (NEW)" if row['is_new'] else ""
                print(f"  {row['rank']}. {row['tool']}: {row['score']:.1f}{new_marker}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate weekly AI tools ranking')
    parser.add_argument('--week', type=str, help='Week in YYYY-WXX format (default: current week)')
    
    args = parser.parse_args()
    generate_ranking(args.week)