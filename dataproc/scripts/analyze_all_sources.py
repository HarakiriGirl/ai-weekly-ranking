#!/usr/bin/env python3
"""
全データソース分析：RSS、YouTube、AI-Weekly の貢献度比較
"""

import json
import pandas as pd
from pathlib import Path
from collections import Counter
import re
from datetime import datetime, timedelta

def load_rss_data():
    """RSSデータ読み込み"""
    weekly_file = Path("data/rss/weekly/weekly_summary_20250613.json")
    
    if not weekly_file.exists():
        return None, "RSS週次データなし"
    
    with open(weekly_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    articles = []
    for site_name, site_articles in data['sites'].items():
        for article in site_articles:
            articles.append({
                'source_type': 'RSS',
                'source_name': site_name,
                'title': article['title'],
                'summary': article.get('summary', ''),
                'published': article.get('published', '')
            })
    
    return articles, f"RSS: {len(articles)}件"

def load_youtube_data():
    """YouTubeデータ読み込み"""
    youtube_dir = Path("data/youtube/weekly")
    youtube_files = list(youtube_dir.glob("youtube_weekly_*.json"))
    
    if not youtube_files:
        return None, "YouTube週次データなし"
    
    # 最新ファイル取得
    latest_file = max(youtube_files, key=lambda x: x.stat().st_mtime)
    print(f"  読み込み: {latest_file.name}")
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"  データ構造確認: {list(data.keys())}")
        
        articles = []
        for video in data.get('videos', []):
            articles.append({
                'source_type': 'YouTube',
                'source_name': video.get('channel_title', 'Unknown'),
                'title': video.get('title', ''),
                'summary': video.get('description', '')[:500],  # 最初の500文字
                'published': video.get('published_at', '')
            })
        
        print(f"  処理後記事数: {len(articles)}件")
        return articles, f"YouTube: {len(articles)}件"
    
    except Exception as e:
        print(f"  YouTubeデータ処理エラー: {e}")
        return None, f"YouTube処理エラー: {e}"

def load_aiweekly_data():
    """AI-Weeklyデータ読み込み"""
    aiweekly_dir = Path("data/aiweekly/weekly")
    aiweekly_files = list(aiweekly_dir.glob("aiweekly_*.json"))
    
    if not aiweekly_files:
        return None, "AI-Weekly週次データなし"
    
    # 最新ファイル取得
    latest_file = max(aiweekly_files, key=lambda x: x.stat().st_mtime)
    print(f"  読み込み: {latest_file.name}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    articles = []
    
    # セクションごとに記事を抽出
    for section_name, section_data in data.get('sections', {}).items():
        if isinstance(section_data, list):
            for item in section_data:
                if isinstance(item, dict):
                    articles.append({
                        'source_type': 'AI-Weekly',
                        'source_name': f"AI-Weekly/{section_name}",
                        'title': item.get('title', ''),
                        'summary': item.get('description', ''),
                        'published': data.get('date', '')
                    })
    
    return articles, f"AI-Weekly: {len(articles)}件"

def detect_ai_keywords(text):
    """AI関連キーワード検出（改良版）"""
    if not text:
        return []
    
    text_lower = text.lower()
    
    # AI関連キーワード辞書
    ai_keywords = {
        'ai_general': ['ai', 'artificial intelligence', 'machine intelligence'],
        'ml_dl': ['machine learning', 'ml', 'deep learning', 'neural network', 'neural', 'cnn', 'rnn', 'lstm'],
        'models': ['gpt', 'llm', 'bert', 'transformer', 'diffusion', 'gan', 'vae'],
        'companies': ['openai', 'anthropic', 'meta ai', 'google ai', 'mistral', 'claude', 'chatgpt'],
        'applications': ['copilot', 'agent', 'automation', 'reasoning', 'computer vision', 'nlp'],
        'tools': ['stable diffusion', 'midjourney', 'dall-e', 'whisper', 'codex'],
        'techniques': ['fine-tuning', 'rag', 'prompt engineering', 'few-shot', 'zero-shot'],
        'models_specific': ['o1', 'o3', 'claude-3', 'gemini', 'palm', 'llama']
    }
    
    detected = []
    for category, keywords in ai_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                detected.append((category, keyword))
    
    return detected

def analyze_source_data(articles, source_type):
    """ソース別データ分析"""
    if not articles:
        return None
    
    print(f"\n{'='*20} {source_type} 分析 {'='*20}")
    print(f"総記事数: {len(articles)}件")
    
    # ソース名別統計
    source_counts = Counter(article['source_name'] for article in articles)
    print(f"\n📊 {source_type}内訳:")
    for source_name, count in source_counts.most_common(10):
        print(f"  {source_name}: {count}件")
    if len(source_counts) > 10:
        print(f"  ... 他{len(source_counts)-10}ソース")
    
    # AI関連記事検出
    ai_articles = []
    ai_keyword_stats = Counter()
    
    for article in articles:
        text_to_check = (article['title'] + ' ' + article['summary'])
        detected_keywords = detect_ai_keywords(text_to_check)
        
        if detected_keywords:
            ai_articles.append({
                **article,
                'ai_keywords': detected_keywords
            })
            
            # キーワード統計
            for category, keyword in detected_keywords:
                ai_keyword_stats[keyword] += 1
    
    ai_rate = len(ai_articles) / len(articles) * 100
    print(f"\n🤖 AI関連分析:")
    print(f"  AI記事数: {len(ai_articles)}件")
    print(f"  AI率: {ai_rate:.1f}%")
    
    # 人気AIキーワード
    if ai_keyword_stats:
        print(f"\n🔥 人気AIキーワード Top10:")
        for keyword, count in ai_keyword_stats.most_common(10):
            print(f"  {keyword}: {count}回")
    
    # AI記事サンプル表示
    if ai_articles:
        print(f"\n📰 AI記事サンプル:")
        for i, article in enumerate(ai_articles[:5], 1):
            keywords = [kw for _, kw in article['ai_keywords'][:3]]
            keywords_str = ', '.join(keywords) if keywords else 'AI関連'
            print(f"  {i}. [{keywords_str}] {article['title'][:50]}...")
    
    return {
        'source_type': source_type,
        'total_articles': len(articles),
        'ai_articles': len(ai_articles),
        'ai_rate': ai_rate,
        'top_keywords': dict(ai_keyword_stats.most_common(10)),
        'sources_count': len(source_counts)
    }

def save_analysis_results(results):
    """分析結果をJSONファイルに保存"""
    # 保存ディレクトリ作成
    analyze_dir = Path("dataproc/analyze")
    analyze_dir.mkdir(parents=True, exist_ok=True)
    
    # 分析結果データ構築
    analysis_data = {
        "analysis_date": datetime.now().isoformat(),
        "week_period": f"{(datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
        "sources": [],
        "summary": {}
    }
    
    # 全体統計計算
    total_articles = sum(r['total_articles'] for r in results if r)
    total_ai = sum(r['ai_articles'] for r in results if r)
    
    analysis_data["summary"] = {
        "total_articles": total_articles,
        "total_ai_articles": total_ai,
        "overall_ai_rate": total_ai/total_articles*100 if total_articles > 0 else 0,
        "active_sources": len([r for r in results if r])
    }
    
    # ソース別データ
    for result in results:
        if result:
            volume_share = result['total_articles'] / total_articles * 100 if total_articles > 0 else 0
            ai_share = result['ai_articles'] / total_ai * 100 if total_ai > 0 else 0
            efficiency_index = ai_share / volume_share if volume_share > 0 else 0
            
            source_data = {
                "source_type": result['source_type'],
                "total_articles": result['total_articles'],
                "ai_articles": result['ai_articles'],
                "ai_rate": result['ai_rate'],
                "volume_share": volume_share,
                "ai_contribution": ai_share,
                "efficiency_index": efficiency_index,
                "top_keywords": result['top_keywords'],
                "sources_count": result['sources_count']
            }
            analysis_data["sources"].append(source_data)
    
    # ファイル保存
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    week_id = datetime.now().strftime('%Y-W%U')
    filename = analyze_dir / f"sources_analysis_{week_id}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 分析結果保存: {filename}")
    return str(filename)

def compare_sources(results):
    """ソース間比較"""
    print(f"\n{'='*60}")
    print("🎯 全ソース比較サマリー")
    print(f"{'='*60}")
    
    # 全体統計
    total_articles = sum(r['total_articles'] for r in results if r)
    total_ai = sum(r['ai_articles'] for r in results if r)
    
    print(f"📊 全体統計:")
    print(f"  総記事数: {total_articles:,}件")
    print(f"  AI記事数: {total_ai:,}件")
    print(f"  全体AI率: {total_ai/total_articles*100:.1f}%")
    
    # ソース別比較
    print(f"\n📈 ソース別詳細:")
    print(f"{'ソース':<12} {'記事数':<8} {'AI記事':<8} {'AI率':<8} {'効率':<8}")
    print("-" * 50)
    
    for result in results:
        if result:
            efficiency = result['ai_articles'] / result['total_articles'] if result['total_articles'] > 0 else 0
            contribution = result['ai_articles'] / total_ai * 100 if total_ai > 0 else 0
            print(f"{result['source_type']:<12} {result['total_articles']:<8,} {result['ai_articles']:<8} {result['ai_rate']:<7.1f}% {contribution:<7.1f}%")
    
    # 貢献度分析
    print(f"\n💡 貢献度分析:")
    for result in results:
        if result:
            contribution = result['ai_articles'] / total_ai * 100 if total_ai > 0 else 0
            volume_share = result['total_articles'] / total_articles * 100 if total_articles > 0 else 0
            efficiency_ratio = contribution / volume_share if volume_share > 0 else 0
            
            print(f"  {result['source_type']}:")
            print(f"    記事量シェア: {volume_share:.1f}%")
            print(f"    AI記事シェア: {contribution:.1f}%")
            print(f"    効率指数: {efficiency_ratio:.2f} {'⭐' if efficiency_ratio > 1 else ''}")
    
    # 推奨構成
    print(f"\n🎯 データ収集戦略:")
    rss_result = next((r for r in results if r and r['source_type'] == 'RSS'), None)
    youtube_result = next((r for r in results if r and r['source_type'] == 'YouTube'), None)
    aiweekly_result = next((r for r in results if r and r['source_type'] == 'AI-Weekly'), None)
    
    if rss_result:
        print(f"  📡 RSS: 幅広いニュース収集（{rss_result['ai_rate']:.1f}% AI率）")
    if youtube_result:
        print(f"  📺 YouTube: 動画・実演コンテンツ（{youtube_result['ai_rate']:.1f}% AI率）")
    if aiweekly_result:
        print(f"  📰 AI-Weekly: 厳選AI情報（{aiweekly_result['ai_rate']:.1f}% AI率）")

def main():
    print("🔍 全データソース分析システム")
    print("="*60)
    
    results = []
    
    # RSS分析
    rss_articles, rss_status = load_rss_data()
    print(f"📡 RSS読み込み: {rss_status}")
    if rss_articles:
        rss_result = analyze_source_data(rss_articles, "RSS")
        results.append(rss_result)
    
    # YouTube分析
    youtube_articles, youtube_status = load_youtube_data()
    print(f"📺 YouTube読み込み: {youtube_status}")
    if youtube_articles:
        youtube_result = analyze_source_data(youtube_articles, "YouTube")
        results.append(youtube_result)
    
    # AI-Weekly分析
    aiweekly_articles, aiweekly_status = load_aiweekly_data()
    print(f"📰 AI-Weekly読み込み: {aiweekly_status}")
    if aiweekly_articles:
        aiweekly_result = analyze_source_data(aiweekly_articles, "AI-Weekly")
        results.append(aiweekly_result)
    
    # 全体比較
    if results:
        compare_sources(results)
        
        # 分析結果を保存
        saved_file = save_analysis_results(results)
    
    print(f"\n{'='*60}")
    print("✅ 全ソース分析完了")

if __name__ == "__main__":
    main()