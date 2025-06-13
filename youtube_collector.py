#!/usr/bin/env python3
"""
YouTube週次収集システム
毎週指定チャンネルの新着動画を収集
"""

import requests
import json
import csv
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
from pathlib import Path
import time

def load_channel_list(csv_file: str) -> List[Tuple[str, str, str]]:
    """
    CSVファイルからチャンネル情報を読み込み
    戻り値: [(channel_id, name, handle), ...]
    """
    channels = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('status') == '成功':  # 成功ステータスのみ処理
                    channels.append((
                        row['channel_id'].strip(),
                        row['name'].strip(),
                        row['handle'].strip()
                    ))
        print(f"📋 {len(channels)}チャンネルをCSVから読み込み")
        return channels
    except Exception as e:
        print(f"❌ CSVファイル読み込みエラー: {e}")
        return []

def fetch_weekly_videos(api_key: str, channel_id: str, channel_name: str) -> Dict:
    """
    指定チャンネルの過去7日間の動画を取得
    """
    print(f"🔍 動画取得開始: {channel_name}")
    
    # 7日前の日付を計算（UTC）
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    published_after = week_ago.isoformat()
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'channelId': channel_id,
        'type': 'video',
        'order': 'date',
        'publishedAfter': published_after,
        'maxResults': 50,
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # エラー応答チェック
        if 'error' in data:
            print(f"  ❌ API エラー: {data['error']['message']}")
            return {
                "channel_id": channel_id,
                "videos": [],
                "status": "api_error",
                "error": data['error']['message']
            }
        
        videos = []
        for item in data.get('items', []):
            video = {
                'title': item['snippet']['title'],
                'tags': item['snippet'].get('tags', []),  # タグ配列（なければ空配列）
                'published_at': item['snippet']['publishedAt']
            }
            videos.append(video)
        
        print(f"  ✅ {len(videos)}本の動画を取得")
        return {
            "channel_id": channel_id,
            "videos": videos,
            "status": "success"
        }
        
    except requests.exceptions.Timeout:
        print(f"  ❌ タイムアウト")
        return {"channel_id": channel_id, "videos": [], "status": "timeout"}
    except requests.exceptions.RequestException as e:
        print(f"  ❌ ネットワークエラー: {e}")
        return {"channel_id": channel_id, "videos": [], "status": "network_error", "error": str(e)}
    except Exception as e:
        print(f"  ❌ 予期しないエラー: {e}")
        return {"channel_id": channel_id, "videos": [], "status": "unexpected_error", "error": str(e)}

def get_jst_timestamp() -> str:
    """日本時間でのタイムスタンプを生成（pytz不使用）"""
    jst_offset = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst_offset)
    return now_jst.strftime('%Y%m%d_%H%M%S')

def process_youtube_channels(api_key: str, csv_file: str):
    """YouTubeチャンネルを処理してJSONに保存"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    result = {
        "collection_date": today,
        "collection_date_jst": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "source": "YouTube Data API v3",
        "total_channels": 0,
        "successful_channels": 0,
        "failed_channels": 0,
        "total_videos": 0,
        "channels": {}
    }
    
    print(f"🎥 YouTube週次収集開始: {today}")
    print("-" * 50)
    
    # チャンネルリストを読み込み
    channels = load_channel_list(csv_file)
    if not channels:
        print("❌ 処理対象のチャンネルがありません")
        return result
    
    result["total_channels"] = len(channels)
    
    # 各チャンネルを処理
    for i, (channel_id, channel_name, handle) in enumerate(channels, 1):
        print(f"\n📺 チャンネル {i}/{len(channels)}: {channel_name} (@{handle})")
        
        # 週間動画を取得
        channel_data = fetch_weekly_videos(api_key, channel_id, channel_name)
        
        if channel_data["status"] == "success":
            result["successful_channels"] += 1
            result["total_videos"] += len(channel_data["videos"])
        else:
            result["failed_channels"] += 1
        
        # チャンネルデータを追加
        result["channels"][channel_name] = {
            "channel_id": channel_id,
            "handle": handle,
            "video_count": len(channel_data["videos"]),
            "videos": channel_data["videos"],
            "collection_status": channel_data["status"]
        }
        
        if channel_data["status"] != "success":
            result["channels"][channel_name]["error"] = channel_data.get("error", "")
        
        # レート制限対策（1秒待機）
        if i < len(channels):
            time.sleep(1)
    
    # 統計情報
    result["summary"] = {
        "total_channels": result["total_channels"],
        "successful_channels": result["successful_channels"],
        "failed_channels": result["failed_channels"],
        "total_videos": result["total_videos"],
        "success_rate": f"{(result['successful_channels'] / result['total_channels'] * 100):.1f}%" if result["total_channels"] > 0 else "0%"
    }
    
    print("-" * 50)
    print(f"📊 処理完了:")
    print(f"  チャンネル数: {result['total_channels']}個")
    print(f"  成功: {result['successful_channels']}個")
    print(f"  失敗: {result['failed_channels']}個")
    print(f"  総動画数: {result['total_videos']:,}本")
    print(f"  成功率: {result['summary']['success_rate']}")
    
    return result

def save_youtube_data(data):
    """YouTubeのデータを保存"""
    # データディレクトリ作成
    data_dir = Path("data/youtube/weekly")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # ファイル名生成（JST時刻）
    jst_timestamp = get_jst_timestamp()
    filename = data_dir / f"youtube_weekly_{jst_timestamp}.json"
    
    # JSON保存
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 ファイル保存: {filename}")
    return str(filename)

def test_single_channel():
    """テスト用: 1チャンネルのみ収集"""
    api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print("❌ YOUTUBE_API_KEY 環境変数が設定されていません")
        return
    
    # テスト用チャンネル（ウェブ職TV）
    test_channel_id = "UClNZUVnSFRKKUfJYarEUqdA"
    test_channel_name = "ウェブ職TV"
    
    print(f"🧪 テスト実行: {test_channel_name}")
    
    result = fetch_weekly_videos(api_key, test_channel_id, test_channel_name)
    
    print(f"\n📊 テスト結果:")
    print(f"  ステータス: {result['status']}")
    print(f"  動画数: {len(result['videos'])}本")
    
    if result['videos']:
        print(f"\n📄 最新動画:")
        latest_video = result['videos'][0]
        print(f"  タイトル: {latest_video['title']}")
        print(f"  タグ: {latest_video['tags']}")
        print(f"  公開日: {latest_video['published_at']}")
    
    return result

def main():
    """メイン実行関数"""
    try:
        import sys
        
        # APIキーチェック
        api_key = os.environ.get('YOUTUBE_API_KEY')
        if not api_key:
            print("❌ エラー: YOUTUBE_API_KEY 環境変数が設定されていません")
            print("ローカル実行の場合:")
            print("  Windows: set YOUTUBE_API_KEY=あなたのAPIキー")
            print("  Mac/Linux: export YOUTUBE_API_KEY=あなたのAPIキー")
            return
        
        # テストモード
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            print("🧪 テストモード実行")
            test_single_channel()
            return
        
        # 通常モード
        csv_file = 'youtube_channel_ids.csv'
        if not os.path.exists(csv_file):
            print(f"❌ エラー: {csv_file} が見つかりません")
            return
        
        print("🎥 YouTube収集モード")
        data = process_youtube_channels(api_key, csv_file)
        save_youtube_data(data)
        
        print("✅ 処理完了")
        
    except Exception as e:
        print(f"💥 実行エラー: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()