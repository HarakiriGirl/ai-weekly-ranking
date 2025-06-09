#!/usr/bin/env python3
"""
GitHub Actions対応RSS収集システム
毎日自動実行で21サイトからRSS収集し、JSONファイルに保存
"""

import feedparser
import json
import os
from datetime import datetime, timedelta
import time
import hashlib

def get_rss_feeds():
    """19サイトのRSS URL一覧"""
    return {
        # 超大手
        "TechCrunch": "https://techcrunch.com/feed/",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Wired": "https://www.wired.com/feed/rss",
        "Engadget": "https://www.engadget.com/rss.xml",
        "ITmedia": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
        
        # 大手
        "ZDNet": "https://www.zdnet.com/news/rss.xml",
        "CNET Japan": "https://www.cnet.com/rss/news/",
        "日経XTECH": "https://xtech.nikkei.com/rss/xtech-it.rdf",
        "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
        "VentureBeat": "https://venturebeat.com/feed/",
        "Mashable": "https://mashable.com/feeds/rss/all",
        "Impress Watch": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf",
        "マイナビニュース": "https://news.mynavi.jp/rss/index",
        
        # 中堅
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
        "ASCII.jp": "https://ascii.jp/rss.xml",

        "ReadWrite": "https://readwrite.com/feed/",
        "The Next Web": "https://thenextweb.com/feed",
        
        # 専門・中小
        "Gigazine": "https://gigazine.net/news/rss_2.0/",
        "Publickey": "https://www.publickey1.jp/atom.xml",
        
        # 追加サイト（必要に応じてコメントアウト解除）
        # "PC Watch": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
        # "ケータイWatch": "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf",
        # "INTERNET Watch": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf",
        
        # 除外サイト（アクセス制限等でエラーが発生）
        # "The Next Web": "https://thenextweb.com/feed",  # アクセス制限によりエラー
    }

def clean_text(text):
    """HTMLタグや余分な空白を除去"""
    import re
    if not text:
        return ""
    
    # HTMLタグ除去
    text = re.sub(r'<[^>]*>', '', str(text))
    # 余分な空白除去
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def collect_daily_rss():
    """当日のRSS記事を収集"""
    rss_feeds = get_rss_feeds()
    today = datetime.now().strftime('%Y-%m-%d')
    
    result = {
        "collection_date": today,
        "total_sites": len(rss_feeds),
        "sites": {}
    }
    
    successful_sites = 0
    total_articles = 0
    
    print(f"📡 RSS収集開始: {today}")
    print(f"📊 対象サイト: {len(rss_feeds)}サイト")
    print("-" * 50)
    
    for site_name, rss_url in rss_feeds.items():
        print(f"🔄 処理中: {site_name}")
        
        try:
            # RSS取得
            feed = feedparser.parse(rss_url)
            
            # エラーチェック
            if feed.bozo:
                print(f"  ⚠️  警告: RSS解析エラー（続行）")
            
            articles = []
            
            # 各記事を処理
            for entry in feed.entries:
                try:
                    # 記事情報抽出
                    article = {
                        "title": clean_text(entry.get('title', '')),
                        "summary": clean_text(entry.get('summary', ''))[:500],  # 500文字まで
                        "link": entry.get('link', ''),
                        "published": entry.get('published', ''),
                    }
                    
                    # 記事ID生成（重複チェック用）
                    article_id = hashlib.md5(
                        (article['title'] + article['link']).encode('utf-8')
                    ).hexdigest()[:8]
                    
                    article['id'] = article_id
                    
                    # 空のタイトルは除外
                    if article['title']:
                        articles.append(article)
                
                except Exception as e:
                    print(f"    ❌ 記事処理エラー: {str(e)}")
                    continue
            
            result["sites"][site_name] = {
                "url": rss_url,
                "articles_count": len(articles),
                "articles": articles,
                "status": "success"
            }
            
            successful_sites += 1
            total_articles += len(articles)
            print(f"  ✅ 完了: {len(articles)}件取得")
            
            # サーバー負荷軽減
            time.sleep(1)
            
        except Exception as e:
            result["sites"][site_name] = {
                "url": rss_url,
                "articles_count": 0,
                "articles": [],
                "status": "error",
                "error": str(e)
            }
            print(f"  ❌ エラー: {str(e)}")
    
    # サマリー情報追加
    result["summary"] = {
        "successful_sites": successful_sites,
        "failed_sites": len(rss_feeds) - successful_sites,
        "total_articles": total_articles
    }
    
    print("-" * 50)
    print(f"📈 収集完了サマリー:")
    print(f"  成功: {successful_sites}/{len(rss_feeds)}サイト")
    print(f"  総記事数: {total_articles}件")
    
    return result

def save_daily_data(data):
    """当日のデータをJSONファイルに保存"""
    # データディレクトリ作成
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    # ファイル名生成
    today = datetime.now().strftime('%Y%m%d')
    filename = f"{data_dir}/rss_{today}.json"
    
    # JSON保存
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 ファイル保存: {filename}")
    return filename

def create_weekly_summary():
    """過去7日分のデータを統合（週末実行用）"""
    data_dir = "data"
    
    # 過去7日分のファイルを探す
    weekly_data = {
        "week_start": (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d'),
        "week_end": datetime.now().strftime('%Y-%m-%d'),
        "daily_files": [],
        "all_articles": [],
        "site_summary": {}
    }
    
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        filename = f"{data_dir}/rss_{date.strftime('%Y%m%d')}.json"
        
        if os.path.exists(filename):
            print(f"📁 読み込み: {filename}")
            
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    daily_data = json.load(f)
                
                weekly_data["daily_files"].append({
                    "date": date.strftime('%Y-%m-%d'),
                    "filename": filename,
                    "articles_count": daily_data.get("summary", {}).get("total_articles", 0)
                })
                
                # 全記事を統合
                for site_name, site_data in daily_data.get("sites", {}).items():
                    if site_data.get("status") == "success":
                        for article in site_data.get("articles", []):
                            article["site"] = site_name
                            article["collection_date"] = date.strftime('%Y-%m-%d')
                            weekly_data["all_articles"].append(article)
                
            except Exception as e:
                print(f"❌ ファイル読み込みエラー: {filename} - {str(e)}")
    
    # 重複記事除去
    unique_articles = {}
    for article in weekly_data["all_articles"]:
        article_id = article.get("id")
        if article_id and article_id not in unique_articles:
            unique_articles[article_id] = article
    
    weekly_data["all_articles"] = list(unique_articles.values())
    weekly_data["total_unique_articles"] = len(unique_articles)
    
    # サイト別統計
    site_stats = {}
    for article in weekly_data["all_articles"]:
        site = article["site"]
        if site not in site_stats:
            site_stats[site] = 0
        site_stats[site] += 1
    
    weekly_data["site_summary"] = site_stats
    
    # 週間サマリー保存
    week_filename = f"{data_dir}/weekly_summary_{datetime.now().strftime('%Y%m%d')}.json"
    with open(week_filename, 'w', encoding='utf-8') as f:
        json.dump(weekly_data, f, ensure_ascii=False, indent=2)
    
    print(f"📊 週間サマリー保存: {week_filename}")
    print(f"📈 統計: {len(weekly_data['daily_files'])}日分、{weekly_data['total_unique_articles']}件（重複除去後）")
    
    return week_filename

def main():
    """メイン実行関数"""
    try:
        # 引数チェック（GitHub Actionsから渡される）
        import sys
        mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
        
        if mode == "weekly":
            print("🗓️  週間サマリー作成モード")
            create_weekly_summary()
        else:
            print("📅 日次RSS収集モード")
            # 日次RSS収集
            data = collect_daily_rss()
            save_daily_data(data)
        
        print("✅ 処理完了")
        
    except Exception as e:
        print(f"💥 実行エラー: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
