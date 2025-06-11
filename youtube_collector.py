#!/usr/bin/env python3
"""
YouTube Data API 週間収集システム (GitHub Actions用)
60チャンネルから週間動画を取得してAIツールランキング作成
"""

import requests
import json
import datetime
import os
from typing import Dict, List, Optional

class YouTubeDataCollector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
    def get_channel_id_from_handle(self, handle: str) -> Optional[str]:
        """
        チャンネルハンドル（@username）からチャンネルIDを取得
        """
        # ハンドルから@を除去
        handle_clean = handle.replace('@', '') if handle.startswith('@') else handle
        
        url = f"{self.base_url}/channels"
        params = {
            'part': 'id,snippet',
            'forHandle': handle_clean,
            'key': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('items'):
                channel_id = data['items'][0]['id']
                channel_name = data['items'][0]['snippet']['title']
                print(f"✓ {handle} → {channel_id} ({channel_name})")
                return channel_id
            else:
                print(f"✗ チャンネルが見つかりません: {handle}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"✗ API エラー ({handle}): {e}")
            return None
    
    def get_weekly_videos(self, channel_id: str, channel_name: str) -> List[Dict]:
        """
        指定チャンネルの過去7日間の動画を取得
        """
        # 7日前の日付を計算
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        published_after = week_ago.isoformat() + 'Z'
        
        url = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',
            'order': 'date',
            'publishedAfter': published_after,
            'maxResults': 50,
            'key': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for item in data.get('items', []):
                video = {
                    'title': item['snippet']['title'],
                    'published': item['snippet']['publishedAt'],
                    'tags': item['snippet'].get('tags', []),
                    'url': f"https://youtube.com/watch?v={item['id']['videoId']}"
                }
                videos.append(video)
            
            print(f"✓ {channel_name}: {len(videos)}本の動画を取得")
            return videos
            
        except requests.exceptions.RequestException as e:
            print(f"✗ 動画取得エラー ({channel_name}): {e}")
            return []

def get_test_channels():
    """テスト用5チャンネル"""
    return [
        ("webshokutv", "ウェブ職TV"),
        ("iketomo-ch", "いけともch_旧リモ研"),
        ("AIAIChatGPT-cj4sh", "AI大学【AI&ChatGPT最新情報】"),
        ("TwoMinutePapers", "Two Minute Papers"),
        ("la_inteligencia_artificial", "Inteligencia Artificial")
    ]

def extract_ai_tools(data):
    """動画データからAIツール名を抽出してランキング作成"""
    # よく出てくるAIツール名
    ai_tools = [
        'ChatGPT', 'Claude', 'Gemini', 'OpenAI', 'Anthropic',
        'NotebookLM', 'Cursor', 'Suno', 'Heygen', 'Midjourney',
        'DALL-E', 'Stable Diffusion', 'Perplexity', 'Google',
        'Microsoft', 'NVIDIA', 'Copilot', 'Udio', 'Flux',
        'RunwayML', 'Luma', 'Pika', 'Meta', 'LLaMA'
    ]
    
    tool_counts = {}
    tool_videos = {}  # どの動画で言及されたかの記録
    
    for channel_name, channel_data in data['channels'].items():
        for video in channel_data['videos']:
            title = video['title'].lower()
            tags = [tag.lower() for tag in video.get('tags', [])]
            
            # タイトルからツール名抽出
            for tool in ai_tools:
                if tool.lower() in title:
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1
                    if tool not in tool_videos:
                        tool_videos[tool] = []
                    tool_videos[tool].append({
                        'channel': channel_name,
                        'title': video['title'],
                        'url': video['url']
                    })
            
            # タグからツール名抽出
            for tag in tags:
                for tool in ai_tools:
                    if tool.lower() in tag and tool not in [t.lower() for t in title.split()]:
                        # タイトルで既にカウント済みでなければ追加
                        tool_counts[tool] = tool_counts.get(tool, 0) + 1
                        if tool not in tool_videos:
                            tool_videos[tool] = []
                        tool_videos[tool].append({
                            'channel': channel_name,
                            'title': video['title'],
                            'url': video['url'],
                            'from': 'tag'
                        })
    
    return tool_counts, tool_videos

def main():
    """メイン実行関数"""
    # APIキーを環境変数から取得
    API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    if not API_KEY:
        print("❌ エラー: YOUTUBE_API_KEY 環境変数が設定されていません")
        return
    
    collector = YouTubeDataCollector(API_KEY)
    
    # テスト用チャンネルリスト
    test_channels = get_test_channels()
    
    # 結果を格納する辞書
    result = {
        "collection_date": datetime.datetime.now().isoformat(),
        "source": "YouTube Data API",
        "channels": {}
    }
    
    print("=== YouTube Data API 週間収集開始 ===\n")
    
    # 各チャンネルを処理
    for handle, display_name in test_channels:
        print(f"処理中: {display_name} (@{handle})")
        
        # Step 1: チャンネルIDを取得
        channel_id = collector.get_channel_id_from_handle(handle)
        if not channel_id:
            continue
            
        # Step 2: 週間動画を取得
        videos = collector.get_weekly_videos(channel_id, display_name)
        
        # Step 3: 結果に追加
        result["channels"][display_name] = {
            "channel_id": channel_id,
            "videos": videos
        }
        
        print(f"完了: {display_name}\n")
    
    # AIツール出現頻度分析
    print("=== AIツール分析開始 ===")
    tool_counts, tool_videos = extract_ai_tools(result)
    
    # ランキング作成
    ranking = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
    
    result["ai_tools_ranking"] = {
        "ranking": ranking,
        "details": tool_videos
    }
    
    # 結果をJSONファイルに保存
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    output_file = f"{data_dir}/youtube_weekly_{datetime.datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"=== 完了 ===")
    print(f"結果ファイル: {output_file}")
    
    # 簡単な統計を表示
    total_videos = sum(len(ch['videos']) for ch in result['channels'].values())
    print(f"総動画数: {total_videos}本")
    print(f"チャンネル数: {len(result['channels'])}個")
    
    if ranking:
        print(f"\n=== AIツールランキング TOP5 ===")
        for i, (tool, count) in enumerate(ranking[:5], 1):
            print(f"{i}. {tool}: {count}回")

if __name__ == "__main__":
    main()
