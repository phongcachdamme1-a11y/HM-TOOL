#!/usr/bin/env python3
"""
🔥 DONGHUA KEYWORD FINDER - Tool Tìm Kiếm Kênh Hoạt Hình Dong Hua Hot
========================================================================
Tìm kiếm kênh Việt Nam đang up video Dong Hua (2D/3D) có view cao.
Lọc kênh hot, không trùng lặp, chỉ hiển thị kênh Việt Nam.
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tabulate import tabulate
from colorama import init, Fore, Style, Back

# Khởi tạo colorama
init(autoreset=True)

# Load .env
load_dotenv()

# ============================================================
# CẤU HÌNH TÌM KIẾM
# ============================================================

# Danh sách keyword tìm kiếm Dong Hua (tiếng Việt - kênh VN)
DONGHUA_KEYWORDS = [
    "dong hua vietsub",
    "donghua vietsub 2024",
    "donghua vietsub 2025",
    "hoạt hình trung quốc vietsub",
    "phim hoạt hình 3d vietsub",
    "phim hoạt hình 3D trung quốc",
    "donghua hay nhất",
    "dong hua mới nhất",
    "hoạt hình 3d hay",
    "donghua thuyết minh",
    "phim anime trung quốc vietsub",
    "donghua hành động vietsub",
    "donghua tu tiên vietsub",
    "donghua kiếm hiệp vietsub",
    "donghua 2D vietsub",
    "donghua 3D vietsub mới nhất",
    "phim hoạt hình trung quốc mới nhất",
    "donghua full vietsub",
    "donghua tập mới",
    "hoạt hình dong hua hay",
]

# Keyword phụ để mở rộng tìm kiếm
EXTRA_KEYWORDS = [
    "đấu phá thương khung",
    "tiên nghịch",
    "phàm nhân tu tiên",
    "vũ động càn khôn",
    "thôn phệ tinh không",
    "đấu la đại lục",
    "tuyệt thế vũ thần",
    "vạn giới tiên tung",
    "già thiên",
    "linh kiếm tôn",
]

# Từ khóa để nhận diện kênh Trung Quốc (loại bỏ)
CHINESE_CHANNEL_INDICATORS = [
    "官方", "频道", "动漫", "动画", "官网", "中文",
    "bilibili", "哔哩哔哩", "腾讯", "优酷", "爱奇艺",
]

# Từ khóa nhận diện kênh Việt Nam
VIETNAM_CHANNEL_INDICATORS = [
    "vietsub", "việt", "viet", "thuyết minh", "lồng tiếng",
    "sub việt", "phụ đề", "VN", "vietnam", "việt nam",
]


class DonghuaFinder:
    """Tool tìm kiếm kênh Dong Hua hot trên YouTube."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            print(f"{Fore.RED}❌ Lỗi: Chưa cấu hình YOUTUBE_API_KEY!")
            print(f"{Fore.YELLOW}   Hãy tạo file .env với nội dung: YOUTUBE_API_KEY=your_key")
            print(f"{Fore.CYAN}   Lấy key tại: https://console.cloud.google.com/apis/credentials")
            sys.exit(1)

        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        self.found_channels = {}  # channel_id -> channel_info (đảm bảo không trùng)
        self.api_calls = 0

    def print_banner(self):
        """In banner tool."""
        print(f"""
{Fore.CYAN}{'='*70}
{Fore.YELLOW}🐉 DONGHUA KEYWORD FINDER v2.0
{Fore.GREEN}   Tool Tìm Kiếm Kênh Hoạt Hình Dong Hua Hot - Kênh Việt Nam
{Fore.CYAN}{'='*70}
{Fore.WHITE}   ✅ Lọc kênh Việt Nam (loại bỏ kênh Trung Quốc gốc)
   ✅ Lọc kênh HOT - video view cao
   ✅ Không trùng lặp - mỗi kênh chỉ hiển thị 1 lần
   ✅ Sắp xếp theo lượt xem & subscriber
{Fore.CYAN}{'='*70}
""")

    def search_videos(self, keyword, max_results=50, published_after=None):
        """Tìm kiếm video theo keyword."""
        try:
            params = {
                "q": keyword,
                "part": "snippet",
                "type": "video",
                "maxResults": min(max_results, 50),
                "order": "viewCount",
                "relevanceLanguage": "vi",
                "regionCode": "VN",
            }

            if published_after:
                params["publishedAfter"] = published_after

            self.api_calls += 1
            request = self.youtube.search().list(**params)
            response = request.execute()
            return response.get("items", [])

        except HttpError as e:
            if e.resp.status == 403:
                print(f"{Fore.RED}   ⚠️  API quota exceeded! Đã dùng hết quota.")
                return []
            print(f"{Fore.RED}   ❌ Lỗi API: {e}")
            return []
        except Exception as e:
            print(f"{Fore.RED}   ❌ Lỗi: {e}")
            return []

    def get_video_details(self, video_ids):
        """Lấy chi tiết video (view count, like count)."""
        if not video_ids:
            return {}

        try:
            self.api_calls += 1
            request = self.youtube.videos().list(
                part="statistics,snippet,contentDetails",
                id=",".join(video_ids)
            )
            response = request.execute()

            details = {}
            for item in response.get("items", []):
                vid_id = item["id"]
                stats = item.get("statistics", {})
                details[vid_id] = {
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "title": item["snippet"]["title"],
                    "published_at": item["snippet"]["publishedAt"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"],
                }
            return details

        except HttpError as e:
            print(f"{Fore.RED}   ❌ Lỗi lấy chi tiết video: {e}")
            return {}

    def get_channel_details(self, channel_ids):
        """Lấy thông tin chi tiết kênh."""
        if not channel_ids:
            return {}

        # Chia thành batch 50 kênh
        results = {}
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i+50]
            try:
                self.api_calls += 1
                request = self.youtube.channels().list(
                    part="snippet,statistics,brandingSettings",
                    id=",".join(batch)
                )
                response = request.execute()

                for item in response.get("items", []):
                    ch_id = item["id"]
                    stats = item.get("statistics", {})
                    snippet = item.get("snippet", {})
                    branding = item.get("brandingSettings", {}).get("channel", {})

                    results[ch_id] = {
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "country": snippet.get("country", ""),
                        "subscriber_count": int(stats.get("subscriberCount", 0)),
                        "video_count": int(stats.get("videoCount", 0)),
                        "view_count": int(stats.get("viewCount", 0)),
                        "custom_url": snippet.get("customUrl", ""),
                        "keywords": branding.get("keywords", ""),
                        "published_at": snippet.get("publishedAt", ""),
                    }

            except HttpError as e:
                print(f"{Fore.RED}   ❌ Lỗi lấy thông tin kênh: {e}")

        return results

    def is_vietnamese_channel(self, channel_info):
        """Kiểm tra xem kênh có phải kênh Việt Nam không."""
        # Kiểm tra country code
        country = channel_info.get("country", "").upper()
        if country == "VN":
            return True

        # Kiểm tra tên kênh và mô tả
        title = channel_info.get("title", "").lower()
        description = channel_info.get("description", "").lower()
        keywords = channel_info.get("keywords", "").lower()
        combined = f"{title} {description} {keywords}"

        # Loại bỏ kênh Trung Quốc
        for indicator in CHINESE_CHANNEL_INDICATORS:
            if indicator.lower() in combined:
                # Nếu kênh có cả chỉ dấu TQ lẫn VN thì vẫn giữ
                has_vn = any(vn.lower() in combined for vn in VIETNAM_CHANNEL_INDICATORS)
                if not has_vn:
                    return False

        # Kiểm tra chỉ dấu Việt Nam
        for indicator in VIETNAM_CHANNEL_INDICATORS:
            if indicator.lower() in combined:
                return True

        # Nếu không rõ ràng, kiểm tra regionCode từ kết quả tìm kiếm
        # Mặc định giữ lại nếu tìm thấy qua regionCode=VN
        return True

    def is_hot_channel(self, channel_info, min_views=10000, min_subscribers=100):
        """Kiểm tra kênh có đang hot không."""
        subscriber_count = channel_info.get("subscriber_count", 0)
        total_views = channel_info.get("view_count", 0)
        video_count = channel_info.get("video_count", 0)

        # Tính trung bình view/video
        avg_views = total_views / max(video_count, 1)

        # Kênh hot: subscriber >= ngưỡng HOẶC avg view cao
        if subscriber_count >= min_subscribers:
            return True
        if avg_views >= min_views:
            return True
        if total_views >= min_views * 10:
            return True

        return False

    def calculate_hot_score(self, channel_info, recent_video_views=0):
        """Tính điểm HOT cho kênh."""
        subscribers = channel_info.get("subscriber_count", 0)
        total_views = channel_info.get("view_count", 0)
        video_count = channel_info.get("video_count", 0)
        avg_views = total_views / max(video_count, 1)

        # Công thức tính điểm hot
        score = 0
        score += min(subscribers / 1000, 100) * 2  # Max 200 điểm từ subscriber
        score += min(avg_views / 1000, 50) * 3     # Max 150 điểm từ avg view
        score += min(recent_video_views / 10000, 100)  # Max 100 điểm từ video gần đây
        score += min(video_count / 10, 50)         # Max 50 điểm từ số video

        return round(score, 1)

    def search_donghua_channels(self, keywords=None, days_back=30,
                                 min_views=5000, min_subscribers=100,
                                 max_results_per_keyword=25, use_extra=False):
        """
        Tìm kiếm kênh Dong Hua hot.
        
        Args:
            keywords: Danh sách keyword (None = dùng mặc định)
            days_back: Tìm video trong N ngày gần đây
            min_views: Lượt xem tối thiểu để coi là "hot"
            min_subscribers: Subscriber tối thiểu
            max_results_per_keyword: Số kết quả mỗi keyword
            use_extra: Sử dụng thêm keyword tên phim cụ thể
        """
        self.print_banner()

        if keywords is None:
            keywords = DONGHUA_KEYWORDS.copy()
            if use_extra:
                keywords.extend(EXTRA_KEYWORDS)

        # Tính thời gian published_after
        published_after = None
        if days_back:
            after_date = datetime.utcnow() - timedelta(days=days_back)
            published_after = after_date.strftime("%Y-%m-%dT00:00:00Z")

        print(f"{Fore.CYAN}📋 Cấu hình tìm kiếm:")
        print(f"   • Số keyword: {len(keywords)}")
        print(f"   • Thời gian: {days_back} ngày gần đây")
        print(f"   • View tối thiểu: {min_views:,}")
        print(f"   • Subscriber tối thiểu: {min_subscribers:,}")
        print(f"   • Kết quả/keyword: {max_results_per_keyword}")
        print()

        all_video_ids = []
        video_to_channel = {}

        # Bước 1: Tìm kiếm video theo từng keyword
        print(f"{Fore.YELLOW}🔍 Bước 1: Tìm kiếm video Dong Hua...")
        print(f"{'─'*50}")

        for i, keyword in enumerate(keywords, 1):
            print(f"   [{i}/{len(keywords)}] Tìm: \"{keyword}\"", end="")
            
            videos = self.search_videos(
                keyword,
                max_results=max_results_per_keyword,
                published_after=published_after
            )

            new_count = 0
            for video in videos:
                vid_id = video["id"]["videoId"]
                ch_id = video["snippet"]["channelId"]

                if vid_id not in video_to_channel:
                    video_to_channel[vid_id] = ch_id
                    all_video_ids.append(vid_id)
                    new_count += 1

            print(f" → {Fore.GREEN}{len(videos)} video, {new_count} mới")
            time.sleep(0.1)  # Rate limiting

        print(f"\n   {Fore.GREEN}✓ Tổng: {len(all_video_ids)} video unique")

        # Bước 2: Lấy chi tiết video (view count)
        print(f"\n{Fore.YELLOW}📊 Bước 2: Phân tích lượt xem video...")
        print(f"{'─'*50}")

        video_details = {}
        for i in range(0, len(all_video_ids), 50):
            batch = all_video_ids[i:i+50]
            details = self.get_video_details(batch)
            video_details.update(details)
            print(f"   Đã phân tích {min(i+50, len(all_video_ids))}/{len(all_video_ids)} video")

        # Bước 3: Nhóm theo kênh & lọc
        print(f"\n{Fore.YELLOW}📡 Bước 3: Nhóm video theo kênh & lọc trùng lặp...")
        print(f"{'─'*50}")

        channel_videos = {}  # channel_id -> list of video details
        for vid_id, details in video_details.items():
            ch_id = details["channel_id"]
            if ch_id not in channel_videos:
                channel_videos[ch_id] = []
            channel_videos[ch_id].append(details)

        print(f"   Tìm thấy {len(channel_videos)} kênh unique")

        # Bước 4: Lấy thông tin kênh
        print(f"\n{Fore.YELLOW}📋 Bước 4: Lấy thông tin chi tiết kênh...")
        print(f"{'─'*50}")

        channel_ids = list(channel_videos.keys())
        channel_details = self.get_channel_details(channel_ids)
        print(f"   Đã lấy thông tin {len(channel_details)} kênh")

        # Bước 5: Lọc kênh Việt Nam & kênh hot
        print(f"\n{Fore.YELLOW}🇻🇳 Bước 5: Lọc kênh Việt Nam & kênh Hot...")
        print(f"{'─'*50}")

        hot_channels = []
        rejected_chinese = 0
        rejected_not_hot = 0

        for ch_id, ch_info in channel_details.items():
            # Kiểm tra kênh Việt Nam
            if not self.is_vietnamese_channel(ch_info):
                rejected_chinese += 1
                continue

            # Kiểm tra kênh hot
            if not self.is_hot_channel(ch_info, min_views, min_subscribers):
                rejected_not_hot += 1
                continue

            # Tính video có view cao nhất
            videos = channel_videos.get(ch_id, [])
            max_video_views = max((v["view_count"] for v in videos), default=0)
            best_video = max(videos, key=lambda v: v["view_count"]) if videos else None

            # Tính điểm hot
            hot_score = self.calculate_hot_score(ch_info, max_video_views)

            hot_channels.append({
                "channel_id": ch_id,
                "channel_info": ch_info,
                "hot_score": hot_score,
                "best_video": best_video,
                "max_video_views": max_video_views,
                "video_count_found": len(videos),
            })

        print(f"   ❌ Loại bỏ {rejected_chinese} kênh Trung Quốc")
        print(f"   ❌ Loại bỏ {rejected_not_hot} kênh không đủ hot")
        print(f"   {Fore.GREEN}✅ Còn lại {len(hot_channels)} kênh Việt Nam HOT")

        # Bước 6: Sắp xếp & hiển thị kết quả
        hot_channels.sort(key=lambda x: x["hot_score"], reverse=True)

        self.display_results(hot_channels)
        self.export_results(hot_channels)

        print(f"\n{Fore.CYAN}📊 Thống kê API: {self.api_calls} calls đã sử dụng")

        return hot_channels

    def display_results(self, channels):
        """Hiển thị kết quả dạng bảng."""
        print(f"\n{'='*70}")
        print(f"{Fore.YELLOW}🏆 KẾT QUẢ: TOP KÊNH DONG HUA VIỆT NAM HOT")
        print(f"{'='*70}\n")

        if not channels:
            print(f"{Fore.RED}   Không tìm thấy kênh nào phù hợp!")
            return

        table_data = []
        for i, ch in enumerate(channels[:50], 1):  # Top 50
            info = ch["channel_info"]
            best = ch["best_video"]

            # Format số
            subs = self._format_number(info["subscriber_count"])
            views = self._format_number(info["view_count"])
            best_views = self._format_number(ch["max_video_views"])

            # Rút gọn tên video
            video_title = ""
            if best:
                video_title = best["title"][:40] + "..." if len(best.get("title", "")) > 40 else best.get("title", "")

            table_data.append([
                i,
                info["title"][:30],
                subs,
                views,
                info["video_count"],
                best_views,
                ch["hot_score"],
                video_title,
            ])

        headers = ["#", "Kênh", "Subs", "Tổng View", "Videos", "Max View", "Score", "Video Hot Nhất"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

        # In chi tiết top 10
        print(f"\n{'='*70}")
        print(f"{Fore.GREEN}📌 CHI TIẾT TOP 10 KÊNH HOT NHẤT:")
        print(f"{'='*70}\n")

        for i, ch in enumerate(channels[:10], 1):
            info = ch["channel_info"]
            best = ch["best_video"]
            channel_url = f"https://www.youtube.com/channel/{ch['channel_id']}"

            print(f"{Fore.YELLOW}{'─'*60}")
            print(f"{Fore.GREEN} #{i} | {Fore.WHITE}{info['title']}")
            print(f"{Fore.CYAN}     🔗 {channel_url}")
            print(f"     📊 Subscribers: {info['subscriber_count']:,}")
            print(f"     👁️  Tổng view: {info['view_count']:,}")
            print(f"     🎬 Số video: {info['video_count']}")
            print(f"     🔥 Hot Score: {ch['hot_score']}")
            print(f"     🌍 Quốc gia: {info.get('country', 'N/A')}")
            if best:
                print(f"     🏆 Video hot nhất: {best['title']}")
                print(f"        Views: {best['view_count']:,} | Likes: {best['like_count']:,}")
            print()

    def export_results(self, channels, filename="donghua_results.txt"):
        """Xuất kết quả ra file."""
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("DONGHUA KEYWORD FINDER - KẾT QUẢ TÌM KIẾM\n")
            f.write(f"Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Tổng kênh tìm thấy: {len(channels)}\n")
            f.write("=" * 70 + "\n\n")

            for i, ch in enumerate(channels, 1):
                info = ch["channel_info"]
                best = ch["best_video"]
                channel_url = f"https://www.youtube.com/channel/{ch['channel_id']}"

                f.write(f"#{i} | {info['title']}\n")
                f.write(f"    URL: {channel_url}\n")
                f.write(f"    Subscribers: {info['subscriber_count']:,}\n")
                f.write(f"    Tổng view: {info['view_count']:,}\n")
                f.write(f"    Số video: {info['video_count']}\n")
                f.write(f"    Hot Score: {ch['hot_score']}\n")
                f.write(f"    Quốc gia: {info.get('country', 'N/A')}\n")
                if best:
                    f.write(f"    Video hot nhất: {best['title']}\n")
                    f.write(f"    Views video hot: {best['view_count']:,}\n")
                f.write(f"{'─'*50}\n")

        print(f"\n{Fore.GREEN}💾 Đã lưu kết quả vào: {filepath}")

    def _format_number(self, num):
        """Format số cho dễ đọc."""
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)

    def quick_search(self, custom_keyword=None):
        """Tìm kiếm nhanh với 1 keyword."""
        keyword = custom_keyword or "donghua vietsub mới nhất"
        print(f"{Fore.CYAN}⚡ Tìm kiếm nhanh: \"{keyword}\"")
        return self.search_donghua_channels(
            keywords=[keyword],
            days_back=7,
            min_views=1000,
            min_subscribers=50,
            max_results_per_keyword=50
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="🐉 Donghua Keyword Finder - Tìm kênh Dong Hua Việt Nam Hot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python donghua_finder.py                     # Tìm kiếm đầy đủ
  python donghua_finder.py --quick             # Tìm kiếm nhanh
  python donghua_finder.py --days 7            # Video 7 ngày gần đây
  python donghua_finder.py --min-views 50000   # View tối thiểu 50K
  python donghua_finder.py --keyword "đấu phá thương khung"  # Keyword riêng
  python donghua_finder.py --extra             # Thêm keyword tên phim nổi tiếng
        """
    )

    parser.add_argument("--quick", "-q", action="store_true",
                       help="Tìm kiếm nhanh (1 keyword, 7 ngày)")
    parser.add_argument("--keyword", "-k", type=str, default=None,
                       help="Keyword tùy chỉnh để tìm kiếm")
    parser.add_argument("--days", "-d", type=int, default=30,
                       help="Tìm video trong N ngày gần đây (mặc định: 30)")
    parser.add_argument("--min-views", "-v", type=int, default=5000,
                       help="Lượt xem tối thiểu (mặc định: 5000)")
    parser.add_argument("--min-subs", "-s", type=int, default=100,
                       help="Subscriber tối thiểu (mặc định: 100)")
    parser.add_argument("--results", "-r", type=int, default=25,
                       help="Số kết quả mỗi keyword (mặc định: 25)")
    parser.add_argument("--extra", "-e", action="store_true",
                       help="Sử dụng thêm keyword tên phim nổi tiếng")
    parser.add_argument("--api-key", type=str, default=None,
                       help="YouTube API Key (hoặc đặt trong .env)")

    args = parser.parse_args()

    # Khởi tạo finder
    finder = DonghuaFinder(api_key=args.api_key)

    if args.quick:
        # Tìm kiếm nhanh
        finder.quick_search(custom_keyword=args.keyword)
    elif args.keyword:
        # Tìm kiếm với keyword tùy chỉnh
        finder.search_donghua_channels(
            keywords=[args.keyword],
            days_back=args.days,
            min_views=args.min_views,
            min_subscribers=args.min_subs,
            max_results_per_keyword=args.results,
        )
    else:
        # Tìm kiếm đầy đủ
        finder.search_donghua_channels(
            days_back=args.days,
            min_views=args.min_views,
            min_subscribers=args.min_subs,
            max_results_per_keyword=args.results,
            use_extra=args.extra,
        )


if __name__ == "__main__":
    main()
