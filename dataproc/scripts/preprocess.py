#!/usr/bin/env python3
"""
データ前処理スクリプト（誤検出対策版）
- RAWデータから本文抽出
- 形態素解析・n-gram生成
- AIツール名マッチング（強化版）
- 未知語抽出
"""

import json
import re
import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import fugashi
from rapidfuzz import fuzz, process

# 設定
WEIGHT = {
    "reddit": 1.0,
    "youtube": 1.0, 
    "rss": 1.0,
    "aiweekly": 1.0
}

MIN_FUZZY_SCORE = 90  # 90前後で調整
MIN_WORD_LENGTH = 3   # 最小単語長
MAX_PENDING_WORDS = 150  # 未知語リスト最大数

# 英語ストップワード（一旦全削除）
ENGLISH_STOP_WORDS = set()  # 空にする

class DataProcessor:
    def __init__(self):
        self.tagger = fugashi.Tagger()
        self.tools_dict = self.load_tools_dict()
        self.all_variants = self.build_variants_list()
        
    def load_tools_dict(self):
        """ツール辞書読み込み"""
        dict_path = Path("dataproc/dict/tools.yml")
        if not dict_path.exists():
            return []
        
        with open(dict_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or []
    
    def build_variants_list(self):
        """全ツール名のvariantsリスト構築"""
        variants = []
        for tool in self.tools_dict:
            # canonical name
            variants.append(tool['canonical'])
            
            # variants
            if 'variants' in tool:
                variants.extend(tool['variants'])
                
            # versions
            if 'versions' in tool:
                variants.extend(tool['versions'])
                
            # features
            if 'features' in tool:
                variants.extend(tool['features'])
                
        return list(set(variants))  # 重複除去
    
    def is_valid_candidate(self, word):
        """候補語の妥当性チェック（強化版）"""
        word_clean = word.lower().strip()
        
        # ストップワード除外
        if word_clean in ENGLISH_STOP_WORDS:
            return False
        
        # 長さチェック
        if len(word_clean) < MIN_WORD_LENGTH or len(word_clean) > 25:
            return False
        
        # 数字のみは除外
        if word_clean.isdigit():
            return False
        
        # 1文字の繰り返しは除外（aaa, bbb等）
        if len(set(word_clean)) == 1:
            return False
        
        # 英数字を含まない場合は除外
        if not any(c.isalnum() for c in word_clean):
            return False
        
        return True
    
    def get_latest_weekly_files(self, data_dir):
        """各ソース別の最新週次ファイルを取得"""
        latest_files = []
        
        # RSS週次ファイル
        rss_weekly_dir = data_dir / "rss" / "weekly"
        if rss_weekly_dir.exists():
            rss_files = list(rss_weekly_dir.glob("weekly_summary_*.json"))
            if rss_files:
                latest_rss = max(rss_files, key=lambda x: x.stat().st_mtime)
                latest_files.append(latest_rss)
                print(f"Found latest RSS weekly: {latest_rss}")
        
        # AI-Weekly週次ファイル
        aiweekly_weekly_dir = data_dir / "aiweekly" / "weekly"  
        if aiweekly_weekly_dir.exists():
            aiweekly_files = list(aiweekly_weekly_dir.glob("aiweekly_*.json"))
            if aiweekly_files:
                latest_aiweekly = max(aiweekly_files, key=lambda x: x.stat().st_mtime)
                latest_files.append(latest_aiweekly)
                print(f"Found latest AI-Weekly: {latest_aiweekly}")
        
        # YouTube週次ファイル
        youtube_weekly_dir = data_dir / "youtube" / "weekly"
        if youtube_weekly_dir.exists():
            youtube_files = list(youtube_weekly_dir.glob("youtube_weekly_*.json"))
            if youtube_files:
                latest_youtube = max(youtube_files, key=lambda x: x.stat().st_mtime)
                latest_files.append(latest_youtube)
                print(f"Found latest YouTube: {latest_youtube}")
        
        return latest_files
    
    def extract_content(self, obj, source):
        """ソース別本文抽出（YouTubeタグ対応版）"""
        try:
            if source == "reddit":
                title = obj.get('title', '')
                body = obj.get('selftext', '')
                return f"{title} {body}".strip()
                
            elif source == "youtube":
                # channelsからvideosのtitleとtags抽出
                content_parts = []
                if 'channels' in obj:
                    for channel_name, channel_data in obj['channels'].items():
                        if 'videos' in channel_data:
                            for video in channel_data['videos']:
                                title = video.get('title', '')
                                tags = video.get('tags', [])
                                
                                content_parts.append(title)
                                # タグも追加（重要なAIツール名が含まれる可能性）
                                if tags and isinstance(tags, list):
                                    content_parts.extend(tags)
                                
                return ' '.join(content_parts).strip()
                
            elif source == "rss":
                # 週次RSS集約の場合
                if "sites" in obj:
                    all_content = []
                    for site_name, articles in obj["sites"].items():
                        for article in articles:
                            title = article.get("title", "")
                            summary = article.get("summary", "")
                            all_content.append(f"{title} {summary}")
                    return " ".join(all_content).strip()
                else:
                    # 通常のRSS記事
                    title = obj.get('title', '')
                    summary = obj.get('summary', '')
                    return f"{title} {summary}".strip()
                
            elif source == "aiweekly":
                # articlesの配列から本文抽出
                if 'articles' in obj and obj['articles']:
                    article = obj['articles'][0]  # 最初の記事
                    title = article.get('title', '')
                    content = article.get('content', '')
                    return f"{title} {content}".strip()
                return ""
                
            else:
                return ""
                
        except Exception as e:
            print(f"Content extraction error: {e}")
            return ""
    
    def detect_source(self, obj):
        """JSONオブジェクトからソース判定"""
        if "subreddit" in obj:
            return "reddit"
        elif "channels" in obj and "total_channels" in obj:
            return "youtube"
        elif "articles" in obj and "rss_url" in obj:
            return "aiweekly"
        elif "week_start" in obj and "sites" in obj:
            return "rss"  # 週次RSS集約
        elif "summary" in obj:
            return "rss"
        else:
            raise ValueError(f"Unknown source format: {list(obj.keys())}")
    
    def clean_text(self, text):
        """テキストクレンジング（改良版）"""
        # HTMLタグ除去
        text = re.sub(r'<[^>]+>', '', text)
        
        # URL除去
        text = re.sub(r'https?://\S+', '', text)
        
        # 重要：ハイフンとドットは保持（GPT-4、Claude-3、v6.1等のため）
        # 英数字、ハイフン、ドット、スペース以外を除去
        text = re.sub(r'[^\w\s\-\.]', ' ', text)
        
        # 連続空白を単一に
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def extract_ngrams(self, text, n=3):
        """形態素解析 + n-gram抽出（改良版）"""
        ngrams = []
        
        # 形態素解析
        words = []
        for word in self.tagger(text):
            surface = word.surface
            features = str(word.feature).split(',')
            pos = features[0]
            
            # 改良されたフィルタ：英数字を含む語、または名詞・記号・未知語
            if (any(c.isalnum() for c in surface) or 
                pos in ['名詞', '記号', '未知語']):
                if len(surface) >= MIN_WORD_LENGTH:
                    words.append(surface)
        
        # 1-gram（妥当性チェック付き）
        for word in words:
            if self.is_valid_candidate(word):
                ngrams.append(word)
        
        # 2-gram
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if self.is_valid_candidate(bigram):
                ngrams.append(bigram)
        
        # 3-gram
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            if self.is_valid_candidate(trigram):
                ngrams.append(trigram)
        
        return ngrams
    
    def match_tools(self, ngrams):
        """n-gramをツール辞書とマッチング（ツール別厳格度対応版）"""
        matched_tools = defaultdict(int)
        ngram_counts = Counter(ngrams)  # 頻度をカウント
        
        for ngram, count in ngram_counts.items():
            # 完全一致を優先
            if ngram in self.all_variants:
                canonical = self.find_canonical(ngram)
                if canonical:
                    matched_tools[canonical] += count * 2  # 完全一致はボーナス
                    continue
            
            # Fuzzy マッチング（閾値を厳格化）
            matches = process.extract(
                ngram, 
                self.all_variants, 
                scorer=fuzz.ratio,
                limit=1
            )
            
            if matches and matches[0][1] >= MIN_FUZZY_SCORE:
                # マッチしたvariantから canonical name を逆引き
                matched_variant = matches[0][0]
                canonical = self.find_canonical(matched_variant)
                if canonical:
                    # ツール別厳格度チェック
                    tool_info = self.get_tool_info(canonical)
                    if tool_info.get('match_mode') == 'exact_only':
                        # 完全一致のみ許可
                        if ngram != matched_variant:
                            print(f"  [REJECT] Exact match required: '{ngram}' -> '{matched_variant}' (rejected)")
                            continue
                    
                    # 低信頼度マッチングを警告
                    if matches[0][1] < 95:
                        print(f"  [WARN] Low confidence: '{ngram}' -> '{matched_variant}' ({matches[0][1]:.1f})")
                    
                    matched_tools[canonical] += count
        
        return dict(matched_tools)
    
    def find_canonical(self, variant):
        """variantからcanonical nameを逆引き"""
        for tool in self.tools_dict:
            if variant == tool['canonical']:
                return tool['canonical']
            
            if 'variants' in tool and variant in tool['variants']:
                return tool['canonical']
                
            if 'versions' in tool and variant in tool['versions']:
                return tool['canonical']
                
            if 'features' in tool and variant in tool['features']:
                return tool['canonical']
        
        return None
    
    def get_tool_info(self, canonical):
        """canonical nameからツール情報を取得"""
        for tool in self.tools_dict:
            if tool['canonical'] == canonical:
                return tool
        return {}
    
    def extract_unknown_words(self, ngrams):
        """未知語抽出（ツール辞書にないもの）"""
        unknown = []
        
        for ngram in ngrams:
            # 妥当性チェック
            if not self.is_valid_candidate(ngram):
                continue
            
            # 既知ツールとのマッチング確認
            matches = process.extract(
                ngram,
                self.all_variants,
                scorer=fuzz.ratio,
                limit=1
            )
            
            # マッチしない、または低スコアの場合は未知語候補
            if not matches or matches[0][1] < MIN_FUZZY_SCORE:
                unknown.append(ngram)
        
        return unknown
    
    def process_files(self, debug=False):
        """メイン処理（デバッグ出力制御可能）"""
        data_dir = Path("data")
        processed_dir = Path("dataproc/processed")
        processed_dir.mkdir(exist_ok=True)
        
        # 日付ベースでファイル処理
        today = datetime.now().strftime("%Y-%m-%d")
        
        all_records = []
        all_pending = []
        
        # 最新週次ファイルのみ取得
        latest_files = self.get_latest_weekly_files(data_dir)
        
        if not latest_files:
            print("No weekly files found!")
            return
        
        for json_file in latest_files:
                
            print(f"Processing: {json_file}")
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # リスト形式とオブジェクト形式の両方に対応
                if isinstance(data, list):
                    objects = data
                else:
                    objects = [data]
                
                for obj in objects:
                    try:
                        # ソース判定
                        source = self.detect_source(obj)
                        
                        if debug:
                            print(f"  Source detected: {source} for keys: {list(obj.keys())[:5]}")
                        
                        # 本文抽出
                        content = self.extract_content(obj, source)
                        if not content:
                            continue
                        
                        # テキストクレンジング
                        cleaned = self.clean_text(content)
                        
                        # n-gram抽出
                        ngrams = self.extract_ngrams(cleaned)
                        if not ngrams:
                            continue
                        
                        if debug:
                            print(f"  Extracted {len(ngrams)} n-grams from {source}")
                            print(f"  Sample n-grams: {ngrams[:10]}")
                        
                        # ツールマッチング
                        matched = self.match_tools(ngrams)
                        
                        if debug and matched:
                            print(f"  Matched tools: {matched}")
                        elif debug:
                            print(f"  No tools matched")
                        
                        # 未知語抽出
                        unknown = self.extract_unknown_words(ngrams)
                        
                        # レコード作成
                        record = {
                            'source': source,
                            'weight': WEIGHT.get(source, 1.0),
                            'content': content[:500],  # 500文字まで保存
                            'matched_tools': matched,
                            'file_path': str(json_file)
                        }
                        all_records.append(record)
                        
                        # 未知語リストに追加
                        all_pending.extend(unknown)
                        
                    except Exception as e:
                        print(f"Object processing error: {e}")
                        continue
                        
            except Exception as e:
                print(f"File processing error {json_file}: {e}")
                continue
        
        # データフレーム作成・保存
        if all_records:
            df = pd.DataFrame(all_records)
            output_path = processed_dir / f"{today}.parquet"
            df.to_parquet(output_path, index=False)
            print(f"Saved: {output_path} ({len(df)} records)")
        
        # 未知語リスト作成・保存
        if all_pending:
            # 頻度集計
            pending_counts = Counter(all_pending)
            
            # 頻度上位を選択
            top_pending = pending_counts.most_common(MAX_PENDING_WORDS)
            
            pending_df = pd.DataFrame(top_pending, columns=['word', 'frequency'])
            pending_path = processed_dir / f"{today}_pending.parquet"
            pending_df.to_parquet(pending_path, index=False)
            print(f"Saved pending: {pending_path} ({len(pending_df)} words)")

if __name__ == "__main__":
    processor = DataProcessor()
    
    # デバッグモードで実行する場合
    import sys
    debug_mode = len(sys.argv) > 1 and sys.argv[1] == "--debug"
    
    processor.process_files(debug=debug_mode)
    print("Preprocessing completed!")