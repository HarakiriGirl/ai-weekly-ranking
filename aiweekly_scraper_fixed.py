#!/usr/bin/env python3
"""
AI-Weekly専用スクレイピングシステム
毎週火曜日にAI-weeklyの新記事を取得
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

def get_aiweekly_rss():
    """AI-WeeklyのRSS URL"""
    return "https://ai-weekly.ai/feed/"

def fetch_new_articles():
    """AI-WeeklyのRSSから新記事URLを取得"""
    print("📡 AI-Weekly RSS取得開始")
    
    try:
        # RSS取得
        feed = feedparser.parse(get_aiweekly_rss())
        
        if feed.bozo:
            print(f"⚠️  RSS解析警告: {feed.bozo_exception}")
        
        articles = []
        print(f"📰 RSS記事数: {len(feed.entries)}件")
        
        # 各記事のURLを収集
        for entry in feed.entries[:1]:  # 最新1件のみ処理
            article_info = {
                "title": entry.get('title', ''),
                "link": entry.get('link', ''),
                "published": entry.get('published', ''),
                "description": entry.get('description', '')
            }
            
            if article_info['link']:
                articles.append(article_info)
                print(f"  📄 {article_info['title']}")
        
        return articles
        
    except Exception as e:
        print(f"❌ RSS取得エラー: {str(e)}")
        return []

def scrape_article_content(url):
    """個別記事ページから本文を取得"""
    print(f"🔍 スクレイピング開始: {url}")
    
    try:
        # User-Agentを設定してアクセス
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # BeautifulSoupで解析
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # WordPressの記事コンテンツを探す
        content_selectors = [
            '.entry-content',           # 一般的なWordPressテーマ
            '.post-content',            # 別パターン
            'article .content',         # article内のcontent
            '.content',                 # シンプルなcontent
            'main',                     # メインコンテンツ
        ]
        
        content_text = ""
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # テキストのみ抽出（HTMLタグ除去）
                content_text = content_elem.get_text(separator='\n', strip=True)
                print(f"  ✅ コンテンツ取得成功: {len(content_text)}文字")
                break
        
        if not content_text:
            # フォールバック: body全体からテキスト抽出
            body = soup.find('body')
            if body:
                content_text = body.get_text(separator='\n', strip=True)
                print(f"  ⚠️  フォールバック取得: {len(content_text)}文字")
        
        # 空白行の整理
        lines = [line.strip() for line in content_text.split('\n') if line.strip()]
        content_text = '\n'.join(lines)
        
        return {
            "url": url,
            "content": content_text,
            "content_length": len(content_text),
            "scraped_at": datetime.now().isoformat(),
            "status": "success"
        }
        
    except requests.RequestException as e:
        print(f"  ❌ HTTP エラー: {str(e)}")
        return {"url": url, "content": "", "status": "http_error", "error": str(e)}
    
    except Exception as e:
        print(f"  ❌ 解析エラー: {str(e)}")
        return {"url": url, "content": "", "status": "parse_error", "error": str(e)}

def process_aiweekly_articles():
    """AI-Weeklyの記事を処理してJSONに保存"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    result = {
        "collection_date": today,
        "source": "AI-Weekly",
        "rss_url": get_aiweekly_rss(),
        "articles": []
    }
    
    print(f"🤖 AI-Weekly記事収集開始: {today}")
    print("-" * 50)
    
    # RSS記事一覧取得
    rss_articles = fetch_new_articles()
    
    if not rss_articles:
        print("❌ RSS記事が取得できませんでした")
        return result
    
    # 各記事をスクレイピング
    for i, article_info in enumerate(rss_articles, 1):
        print(f"\n📖 記事 {i}/{len(rss_articles)}")
        
        # 本文取得
        scraped_content = scrape_article_content(article_info['link'])
        
        # 記事データ統合
        article_data = {
            "title": article_info['title'],
            "link": article_info['link'],
            "published": article_info['published'],
            "description": article_info['description'],
            "content": scraped_content['content'],
            "content_length": scraped_content['content_length'],
            "scraping_status": scraped_content['status']
        }
        
        if scraped_content['status'] != 'success':
            article_data['error'] = scraped_content.get('error', '')
        
        result['articles'].append(article_data)
        
        # サーバー負荷軽減
        time.sleep(2)
    
    # 統計情報
    successful_scrapes = sum(1 for a in result['articles'] if a['scraping_status'] == 'success')
    total_content_length = sum(a['content_length'] for a in result['articles'])
    
    result['summary'] = {
        "total_articles": len(result['articles']),
        "successful_scrapes": successful_scrapes,
        "failed_scrapes": len(result['articles']) - successful_scrapes,
        "total_content_length": total_content_length
    }
    
    print("-" * 50)
    print(f"📊 処理完了:")
    print(f"  記事数: {len(result['articles'])}件")
    print(f"  成功: {successful_scrapes}件")
    print(f"  失敗: {len(result['articles']) - successful_scrapes}件")
    print(f"  総文字数: {total_content_length:,}文字")
    
    return result

def save_aiweekly_data(data):
    """AI-Weeklyのデータを保存"""
    # データディレクトリ作成
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    # ファイル名生成（JST基準）
    jst_time = datetime.utcnow() + timedelta(hours=9)
    today = jst_time.strftime('%Y%m%d')
    filename = f"{data_dir}/aiweekly_{today}.json"
    
    # JSON保存
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 ファイル保存: {filename}")
    return filename

def test_single_article():
    """テスト用: 1記事のみスクレイピング"""
    test_url = "https://ai-weekly.ai/newsletter-06-10-2025/"
    print(f"🧪 テスト実行: {test_url}")
    
    result = scrape_article_content(test_url)
    
    print(f"\n📊 テスト結果:")
    print(f"  ステータス: {result['status']}")
    print(f"  文字数: {result['content_length']:,}文字")
    
    if result['content']:
        # 最初の500文字を表示
        preview = result['content'][:500] + "..." if len(result['content']) > 500 else result['content']
        print(f"\n📄 コンテンツプレビュー:")
        print(preview)
    
    return result

def main():
    """メイン実行関数"""
    try:
        import sys
        
        # テストモード
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            print("🧪 テストモード実行")
            test_single_article()
            return
        
        # 通常モード
        print("🤖 AI-Weekly収集モード")
        data = process_aiweekly_articles()
        save_aiweekly_data(data)
        
        print("✅ 処理完了")
        
    except Exception as e:
        print(f"💥 実行エラー: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
