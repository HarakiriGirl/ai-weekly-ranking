#!/usr/bin/env python3
"""
GitHub Actions対応RSS収集システム
毎日自動実行で22サイトからRSS収集し、JSONファイルに保存
"""

import feedparser
import json
import os
import re
from datetime import datetime, timedelta
import time
import hashlib

def get_rss_feeds():
    """22サイトのRSS URL一覧"""
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
        "ReadWrite": "https://readwrite.com/feed/",# エラー頻発なら削除
        "The Next Web": "https://thenextweb.com/feed",
        
        # 専門・中小
        "Gigazine": "https://gigazine.net/news/rss_2.0/",
        "Publickey": "https://www.publickey1.jp/atom.xml",

        # アジア・EU
        "TechEU": "https://tech.eu/feed/",
        "TechRadar": "https://www.techradar.com/rss",
        "Tech Advisor": "https://www.techadvisor.com/feed/",
        
        # 追加サイト（必要に応じてコメントアウト解除）
        # "PC Watch": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
        # "ケータイWatch": "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf",
        # "INTERNET Watch": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf",
        
        # 除外サイト（アクセス制限等でエラーが発生）
        # "The Next Web": "https://thenextweb.com/feed",  # アクセス制限によりエラー
    }

def clean_text(text):
    """HTMLタグや余分な空白を除去"""
    if not text:
        return ""
    
    # HTMLタグ除去
    text = re.sub(r'<[^>]*>', '', str(text))
    # 余分な空白除去
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_published_date(published_str):
    """published文字列を日付オブジェクトに変換"""
    if not published_str:
        return None
    
    # タイムゾーン付きISO形式の特別処理（The Verge等）
    if 'T' in published_str and ('+' in published_str or '-' in published_str[-6:]):
        try:
            # 2025-06-09T11:24:23-04:00 形式
            # タイムゾーン部分を除去
            clean_str = re.sub(r'[+-]\d{2}:\d{2}$', '', published_str)
            return datetime.strptime(clean_str, '%Y-%m-%dT%H:%M:%S')
        except:
            pass
    
    # 標準的な日付形式を試行
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',     # Mon, 09 Jun 2025 09:35:00 +0000
        '%a, %d %b %Y %H:%M:%S',        # Mon, 09 Jun 2025 09:35:00
        '%Y-%m-%dT%H:%M:%S%z',          # 2025-06-09T09:35:00+00:00
        '%Y-%m-%dT%H:%M:%S',            # 2025-06-09T09:35:00
        '%Y-%m-%d %H:%M:%S',            # 2025-06-09 09:35:00
        '%Y-%m-%d',                     # 2025-06-09
    ]
    
    for fmt in formats:
        try:
            # タイムゾーン情報があれば除去して処理
            clean_str = published_str.replace(' +0000', '').replace(' +0900', '').replace(' GMT', '').replace('Z', '')
            return datetime.strptime(clean_str, fmt.replace('%z', ''))
        except:
            continue
    
    # 全形式で失敗した場合はNone
    return None

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
                    
                    # 記事ID生成（重複チェック用）- サイト名を含める
                    article_id = hashlib.md5(
                        (site_name + article['title'] + article['link']).encode('utf-8')
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
    
    daily_files_list = []  # ログ用に保持
    
    print(f"🗓️  7日間データ統合: {weekly_data['week_start']} ～ {weekly_data['week_end']}")
    
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        filename = f"{data_dir}/rss_{date.strftime('%Y%m%d')}.json"
        
        if os.path.exists(filename):
            print(f"📁 読み込み: {filename}")
            daily_files_list.append(filename)  # ログ用リストに追加
            
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    daily_data = json.load(f)
                
                # 全記事を統合
                for site_name, site_data in daily_data.get("sites", {}).items():
                    if site_data.get("status") == "success":
                        for article in site_data.get("articles", []):
                            article["site"] = site_name
                            article["collection_date"] = date.strftime('%Y-%m-%d')
                            weekly_data["all_articles"].append(article)
                
            except Exception as e:
                print(f"❌ ファイル読み込みエラー: {filename} - {str(e)}")
    
    print(f"📊 統合前記事数: {len(weekly_data['all_articles'])}件")
    
    # 📅 日付フィルタリング（7日以内の記事のみ保持）
    seven_days_ago = datetime.now() - timedelta(days=7)
    filtered_articles = []
    
    date_parse_success = 0
    date_parse_failed = 0
    filtered_out = 0
    
    print(f"📅 日付フィルタリング実行（基準: {seven_days_ago.strftime('%Y-%m-%d %H:%M')}）")
    
    for article in weekly_data["all_articles"]:
        published = article.get('published', '')
        parsed_date = parse_published_date(published)
        
        if parsed_date is None:
            # 日付不明の記事は7日以内として扱う（保持）
            filtered_articles.append(article)
            date_parse_failed += 1
        elif parsed_date >= seven_days_ago:
            # 7日以内の記事は保持
            filtered_articles.append(article)
            date_parse_success += 1
        else:
            # 7日より古い記事は除外
            filtered_out += 1
    
    weekly_data["all_articles"] = filtered_articles
    
    print(f"📈 日付フィルタリング結果:")
    print(f"  日付解析成功: {date_parse_success}件")
    print(f"  日付不明（保持）: {date_parse_failed}件")
    print(f"  7日より古い（除外）: {filtered_out}件")
    print(f"  フィルタリング後: {len(filtered_articles)}件")
    
    # 重複記事除去
    unique_articles = {}
    for article in weekly_data["all_articles"]:
        article_id = article.get("id")
        if article_id and article_id not in unique_articles:
            unique_articles[article_id] = article
    
    weekly_data["all_articles"] = list(unique_articles.values())
    weekly_data["total_unique_articles"] = len(unique_articles)
    
    print(f"🔄 重複除去後: {len(unique_articles)}件")
    
    # サイト別グループ化（スリム化された出力形式）
    sites_grouped = {}
    for article in weekly_data["all_articles"]:
        site = article["site"]
        if site not in sites_grouped:
            sites_grouped[site] = []
        
        # 日付を簡潔な形式に変換
        published_date = ""
        if article.get("published"):
            parsed = parse_published_date(article["published"])
            if parsed:
                published_date = parsed.strftime("%Y-%m-%d")
            else:
                # 日付解析失敗時は元の文字列の日付部分を抽出
                try:
                    if len(article["published"]) >= 10:
                        published_date = article["published"][:10]
                except:
                    published_date = ""
        
        # スリム化された記事データ
        slim_article = {
            "title": article["title"],
            "summary": article["summary"],
            "published": published_date
        }
        sites_grouped[site].append(slim_article)
    
    # フィルタリング統計を追加
    filter_ratio = len(weekly_data["all_articles"]) / (len(weekly_data["all_articles"]) + filtered_out) * 100 if len(weekly_data["all_articles"]) + filtered_out > 0 else 0
    
    # o3専用のスリム化された出力のみ作成
    final_output = {
        "week_start": weekly_data["week_start"],
        "week_end": weekly_data["week_end"],
        "total_articles": len(weekly_data["all_articles"]),
        "sites": sites_grouped
    }
    
    weekly_data = final_output
    
    # 週間サマリー保存
    week_filename = f"{data_dir}/weekly_summary_{datetime.now().strftime('%Y%m%d')}.json"
    with open(week_filename, 'w', encoding='utf-8') as f:
        json.dump(weekly_data, f, ensure_ascii=False, indent=2)
    
    print(f"📊 週間サマリー保存: {week_filename}")
    print(f"📈 最終統計: {len(daily_files_list)}日分、{weekly_data['total_articles']}件")
    print(f"🎯 保持率: {filter_ratio:.1f}%")
    print(f"🗂️  サイト別グループ: {len(sites_grouped)}サイト")
    
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
