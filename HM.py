"""
HM AutoTranslator Pro - Smart Pipeline (DeepSeek & Gemini)
Main GUI Application - Translates SRT subtitle files using AI web chat
"""

import sys
import os
import subprocess
import socket
import threading
import requests
import json
import re
import time
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

# ============================================================
# DEFAULT PROMPTS & SETTINGS
# ============================================================

DEFAULT_PROMPT_PHAN_TICH = """Hãy đóng vai chuyên gia ngôn ngữ, soạn thảo một 'BỘ LUẬT DỊCH THUẬT' chi tiết TRONG CODE BLOCK dựa trên nội dung phim được cung cấp dưới đây:
1. Xác định Thể loại & Thời đại (Cổ trang/Hiện đại/Học đường...).
2. PHÂN TÍCH NHÂN VẬT & QUAN HỆ (QUAN TRỌNG NHẤT):
   - Tìm các tên riêng -> Xác định Giới tính.
   - Xác định quan hệ: Ai bề trên, ai bề dưới. Cách xưng hô (Ta - Ngươi, Anh - Em...).
3. Bảng Từ vựng BẮT BUỘC DÙNG (VD: Cổ trang dùng 'Đa tạ', 'Huynh').
4. Bảng Từ vựng CẤM TUYỆT ĐỐI (VD: Cổ trang cấm 'Ok', 'Bye').
5. Xử lý từ cảm thán: '哈' -> 'ha ha!', '哎' -> 'Ây/Haizz'."""

DEFAULT_PROMPT_DICH = """DỊCH CÁC DÒNG DƯỚI ĐÂY SANG TIẾNG VIỆT (DỊCH NGHĨA, KHÔNG PHIÊN ÂM).
YÊU CẦU CỐT LÕI:
1. Giữ nguyên ID [số]. Trả về dạng Code Block.
2. DỊCH NGHĨA tự nhiên sang tiếng Việt. TUYỆT ĐỐI KHÔNG phiên âm Hán Việt nguyên văn. Phải dịch thành câu tiếng Việt có nghĩa, dễ hiểu.
3. XỬ LÝ CHÚ THÍCH: (nhạc), (vỗ tay)... -> Giữ ID, trả nội dung rỗng. Ví dụ: '[1] '.
4. Mỗi dòng dịch phải là tiếng Việt thuần túy, mạch lạc, đúng ngữ cảnh phim."""

DEFAULT_PROMPT_CONTENT = """Dựa vào TOÀN BỘ nội dung phụ đề phim dưới đây, hãy trở thành một chuyên gia Marketing và viết giúp tôi:
1. 05 Tiêu đề giật tít, thu hút người xem (phù hợp làm mồi câu view).
2. Một đoạn mô tả ngắn gọn, tóm tắt sự kịch tính của video.
3. Một bộ hashtag xu hướng để đăng TikTok, YouTube Shorts, Facebook Reels.
YÊU CẦU: TRẢ KẾT QUẢ VỀ TRONG 1 CODE BLOCK DUY NHẤT ĐỂ TÔI DỄ SAO CHÉP."""

DEFAULT_FUNCTIONS = {
    'dubbing': '- NHẬN DIỆN LỒNG TIẾNG: Nhận diện câu nói là của Nam hay Nữ, từ đó thêm tag [NAM] hoặc [NỮ] vào ngay sau ID. Ví dụ: [1] [NAM] Xin chào.',
    'no_punct': '- BỎ DẤU CÂU: Bản dịch tuyệt đối không được chứa bất kỳ dấu câu nào (chấm, phẩy, chấm than, hỏi chấm...).',
    'force_id': '- FORCE BẢO TOÀN ID: Bắt buộc trả về ĐẦY ĐỦ các ID có trong dữ liệu gốc, cấm gộp dòng, cấm bỏ sót.',
    'overlap': 'Dưới đây là {N} câu đã được dịch ở phiên trước. Hãy đọc để NẮM RÕ NGỮ CẢNH (TUYỆT ĐỐI KHÔNG DỊCH LẠI PHẦN NÀY, CHỈ DÙNG ĐỂ THAM KHẢO):',
    'context': 'ÁP DỤNG NGHIÊM NGẶT BỘ LUẬT DỊCH SAU:'
}

# Delay profiles (min_delay, max_delay) in seconds
DELAY_PROFILES = {
    "Nhanh (1-3s)": (1, 3),
    "Bình thường (3-7s)": (3, 7),
    "An toàn (5-12s)": (5, 12),
    "Rất an toàn (10-20s)": (10, 20),
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_free_port():
    """Find a free port on localhost"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def parse_srt(file_path):
    """Parse SRT file into list of subtitle entries"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().replace('\r\n', '\n')
    
    blocks = re.split(r'\n\n+', content.strip())
    subtitles = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            try:
                idx = int(lines[0].strip())
                timestamp = lines[1].strip()
                text = '\n'.join(lines[2:]).strip()
                subtitles.append({
                    'id': idx,
                    'time': timestamp,
                    'text': text
                })
            except ValueError:
                continue
    
    return subtitles


def write_srt(subtitles, file_path):
    """Write subtitles back to SRT format"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(subtitles):
            f.write(f"{sub['id']}\n")
            f.write(f"{sub['time']}\n")
            translated = sub.get('translated', sub['text'])
            f.write(f"{translated}\n\n")


def extract_code_block(text):
    """Extract content from markdown code block"""
    # Try to find code block
    pattern = r'```[\w]*\n?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return text.strip()


def parse_translated_lines(text):
    """Parse AI response into dict {id: translated_text}"""
    result = {}
    # Match patterns like [1] translated text or [1][NAM] text
    pattern = r'\[(\d+)\]\s*(.*?)(?=\[\d+\]|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        idx = int(match[0])
        translated = match[1].strip()
        # Remove trailing newlines
        translated = translated.rstrip('\n').strip()
        result[idx] = translated
    return result


# ============================================================
# PROMPT MANAGER
# ============================================================

class PromptManager:
    PROMPT_DIR = os.path.join(os.path.expanduser("~"), ".hm_translator")
    
    @staticmethod
    def load_prompt(filename, default_text=""):
        os.makedirs(PromptManager.PROMPT_DIR, exist_ok=True)
        filepath = os.path.join(PromptManager.PROMPT_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        return default_text
    
    @staticmethod
    def save_prompt(filename, text):
        os.makedirs(PromptManager.PROMPT_DIR, exist_ok=True)
        filepath = os.path.join(PromptManager.PROMPT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @staticmethod
    def load_funcs():
        filepath = os.path.join(PromptManager.PROMPT_DIR, "functions.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return DEFAULT_FUNCTIONS
    
    @staticmethod
    def save_funcs(data):
        os.makedirs(PromptManager.PROMPT_DIR, exist_ok=True)
        filepath = os.path.join(PromptManager.PROMPT_DIR, "functions.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# MAIN APPLICATION
# ============================================================

class HMAutoTranslator(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("HM AutoTranslator Pro - Smart Pipeline (DeepSeek & Gemini)")
        self.geometry("1400x800")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # State
        self.backend_port = None
        self.backend_process = None
        self.subtitles = []
        self.translated = {}
        self.is_translating = False
        self.context_rules = ""
        self.progress_file = None
        
        # Build UI
        self._build_ui()
        self._log("Tool khởi động thành công!")
        
        # Start backend
        self._start_backend()
    
    def _build_ui(self):
        """Build the main UI"""
        # Main layout: left panel + right table
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Left Panel (controls)
        left_frame = ctk.CTkScrollableFrame(self, width=260)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # === HE THONG ===
        ctk.CTkLabel(left_frame, text="HỆ THỐNG", text_color="#FF6B6B", font=("", 14, "bold")).pack(pady=(10,5))
        
        # AI Selection
        ai_frame = ctk.CTkFrame(left_frame)
        ai_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(ai_frame, text="Lõi AI:").pack(side="left", padx=5)
        self.ai_var = ctk.StringVar(value="DeepSeek")
        self.ai_combo = ctk.CTkComboBox(ai_frame, values=["DeepSeek", "Gemini"], variable=self.ai_var, width=120)
        self.ai_combo.pack(side="right", padx=5)
        
        ctk.CTkButton(left_frame, text="1. Khởi chạy Trình duyệt", command=self._init_browser, fg_color="#4169E1").pack(fill="x", padx=5, pady=3)
        ctk.CTkButton(left_frame, text="2. Tải file SRT", command=self._load_srt, fg_color="#4169E1").pack(fill="x", padx=5, pady=3)
        
        # === PHAN TICH ===
        ctk.CTkLabel(left_frame, text="PHÂN TÍCH & NGỮ CẢNH", text_color="#9B59B6", font=("", 12, "bold")).pack(pady=(15,5))
        ctk.CTkButton(left_frame, text="Mở Bảng Phân Tích", command=self._open_analysis, fg_color="#F39C12").pack(fill="x", padx=5, pady=3)
        ctk.CTkButton(left_frame, text="Sửa Prompt Phân Tích", command=lambda: self._edit_prompt("prompt_analysis.txt", DEFAULT_PROMPT_PHAN_TICH), fg_color="#555").pack(fill="x", padx=5, pady=3)
        
        # === CONTENT ===
        ctk.CTkLabel(left_frame, text="TẠO CONTENT ĐĂNG BÀI", text_color="#E74C3C", font=("", 12, "bold")).pack(pady=(15,5))
        ctk.CTkButton(left_frame, text="Phân tích lấy Tiêu đề / Hashtag", command=self._generate_content, fg_color="#F39C12").pack(fill="x", padx=5, pady=3)
        ctk.CTkButton(left_frame, text="Sửa Prompt Content", command=lambda: self._edit_prompt("prompt_content.txt", DEFAULT_PROMPT_CONTENT), fg_color="#555").pack(fill="x", padx=5, pady=3)
        
        # === CAU HINH DICH ===
        ctk.CTkLabel(left_frame, text="CẤU HÌNH DỊCH THUẬT", text_color="#3498DB", font=("", 12, "bold")).pack(pady=(15,5))
        
        # Checkboxes
        self.chk_dubbing = ctk.BooleanVar(value=False)
        self.chk_no_punct = ctk.BooleanVar(value=False)
        self.chk_force_id = ctk.BooleanVar(value=True)
        self.chk_context = ctk.BooleanVar(value=True)
        self.chk_overlap = ctk.BooleanVar(value=False)
        
        ctk.CTkCheckBox(left_frame, text="Lồng tiếng (Nam/Nữ)", variable=self.chk_dubbing).pack(anchor="w", padx=10, pady=2)
        ctk.CTkCheckBox(left_frame, text="Bỏ dấu câu", variable=self.chk_no_punct).pack(anchor="w", padx=10, pady=2)
        ctk.CTkCheckBox(left_frame, text="Ép Force đủ ID", variable=self.chk_force_id).pack(anchor="w", padx=10, pady=2)
        ctk.CTkCheckBox(left_frame, text="Gửi kèm bộ luật Context", variable=self.chk_context).pack(anchor="w", padx=10, pady=2)
        
        overlap_frame = ctk.CTkFrame(left_frame)
        overlap_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkCheckBox(overlap_frame, text="Gối câu (Context nối):", variable=self.chk_overlap).pack(side="left")
        self.overlap_count = ctk.CTkEntry(overlap_frame, width=40)
        self.overlap_count.insert(0, "5")
        self.overlap_count.pack(side="right", padx=5)
        
        # Delay profile
        delay_frame = ctk.CTkFrame(left_frame)
        delay_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(delay_frame, text="Hạn chế Bot:").pack(side="left", padx=5)
        self.delay_var = ctk.StringVar(value="An toàn (5-12s)")
        self.delay_combo = ctk.CTkComboBox(delay_frame, values=list(DELAY_PROFILES.keys()), variable=self.delay_var, width=150)
        self.delay_combo.pack(side="right", padx=5)
        
        # Lines per batch
        batch_frame = ctk.CTkFrame(left_frame)
        batch_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(batch_frame, text="Số dòng/Lần gửi:").pack(side="left", padx=5)
        self.batch_size_entry = ctk.CTkEntry(batch_frame, width=60)
        self.batch_size_entry.insert(0, "50")
        self.batch_size_entry.pack(side="right", padx=5)
        
        # Translate button
        self.btn_translate = ctk.CTkButton(left_frame, text="BẮT ĐẦU DỊCH", command=self._start_translate, fg_color="#27AE60", font=("", 14, "bold"))
        self.btn_translate.pack(fill="x", padx=5, pady=8)
        
        ctk.CTkButton(left_frame, text="Sửa Prompt Dịch", command=lambda: self._edit_prompt("prompt_dich.txt", DEFAULT_PROMPT_DICH), fg_color="#555").pack(fill="x", padx=5, pady=3)
        
        # Error detection
        self.btn_error = ctk.CTkButton(left_frame, text="KHÔNG PHÁT HIỆN LỖI", fg_color="#27AE60", state="disabled")
        self.btn_error.pack(fill="x", padx=5, pady=8)
        
        # Export
        ctk.CTkButton(left_frame, text="Xuất File SRT", command=self._export_srt, fg_color="#555").pack(fill="x", padx=5, pady=3)
        
        # Right Panel (table + log)
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)
        
        # Table
        table_frame = ctk.CTkFrame(right_frame)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        columns = ("check", "id", "time", "original", "translated")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=25)
        self.tree.heading("check", text="[X]")
        self.tree.heading("id", text="ID")
        self.tree.heading("time", text="Time")
        self.tree.heading("original", text="Bản Gốc")
        self.tree.heading("translated", text="Bản Dịch")
        
        self.tree.column("check", width=30, anchor="center")
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("original", width=350)
        self.tree.column("translated", width=350)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(right_frame)
        self.progress.grid(row=1, column=0, sticky="ew", padx=5, pady=3)
        self.progress.set(0)
        
        # Log area
        self.log_text = ctk.CTkTextbox(right_frame, height=120, fg_color="#1a1a2e")
        self.log_text.grid(row=2, column=0, sticky="ew", padx=2, pady=2)
    
    def _log(self, msg):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")
    
    def _start_backend(self):
        """Start the backend FastAPI server"""
        self.backend_port = get_free_port()
        self._log(f"Khởi động lõi API ngầm trên Port {self.backend_port}...")
        
        # Start backend as subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backend_script = os.path.join(script_dir, "sys_ntm.py")
        
        self.backend_process = subprocess.Popen(
            [sys.executable, backend_script, "--port", str(self.backend_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Wait for backend to be ready
        def wait_ready():
            for _ in range(30):
                try:
                    r = requests.get(f"http://127.0.0.1:{self.backend_port}/health", timeout=2)
                    if r.status_code == 200:
                        self._log("Đã liên kết Backend thành công!")
                        return
                except:
                    pass
                time.sleep(1)
            self._log("CẢNH BÁO: Backend chưa sẵn sàng!")
        
        threading.Thread(target=wait_ready, daemon=True).start()
    
    def _api_call(self, endpoint, method="GET", data=None):
        """Call backend API"""
        url = f"http://127.0.0.1:{self.backend_port}{endpoint}"
        try:
            if method == "GET":
                r = requests.get(url, timeout=1000)
            else:
                r = requests.post(url, json=data, timeout=1000)
            return r.json()
        except Exception as e:
            return {"status": "error", "text": str(e)}
    
    def _init_browser(self):
        """Initialize browser"""
        ai = self.ai_var.get().lower()
        self._log(f"Đang khởi chạy trình duyệt ({ai})...")
        
        def do_init():
            result = self._api_call("/init_browser", "POST", {"target_ai": ai})
            if "error" in str(result.get("status", "")):
                self._log(f"LỖI: {result.get('detail', result.get('text', 'Unknown'))}")
            else:
                self._log(f"Trình duyệt đã sẵn sàng! ({ai})")
        
        threading.Thread(target=do_init, daemon=True).start()
    
    def _load_srt(self):
        """Load SRT file"""
        filepath = filedialog.askopenfilename(
            title="Chọn file SRT",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        self.subtitles = parse_srt(filepath)
        self.srt_path = filepath
        
        # Setup progress file for resume
        self.progress_file = filepath + ".progress.json"
        
        # Check if progress file exists - ask user
        if os.path.exists(self.progress_file):
            answer = messagebox.askyesno(
                "Tìm thấy tiến trình cũ",
                "Đã có tiến trình dịch trước đó.\n\n"
                "• Nhấn CÓ để tiếp tục tiến trình cũ\n"
                "• Nhấn KHÔNG để dịch lại từ đầu"
            )
            if answer:
                self._load_progress()
                self._log(f"Tiếp tục tiến trình cũ: {len(self.translated)}/{len(self.subtitles)} dòng đã dịch")
            else:
                self.translated = {}
                # Delete old progress file
                try:
                    os.remove(self.progress_file)
                except:
                    pass
                self._log("Đã xóa tiến trình cũ, dịch lại từ đầu.")
        else:
            self.translated = {}
        
        # Populate table
        self.tree.delete(*self.tree.get_children())
        for sub in self.subtitles:
            translated = self.translated.get(sub['id'], "")
            self.tree.insert("", "end", values=(
                "✓" if translated else "",
                sub['id'],
                sub['time'],
                sub['text'][:80],
                translated[:80]
            ))
        
        self._log(f"Đã tải {len(self.subtitles)} dòng phụ đề từ: {os.path.basename(filepath)}")
        
        # Update progress bar
        done_count = len(self.translated)
        if done_count > 0:
            self.progress.set(done_count / len(self.subtitles))
        else:
            self.progress.set(0)
    
    def _load_progress(self):
        """Load translation progress from file"""
        if self.progress_file and os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.translated = {int(k): v for k, v in saved.items()}
            except:
                self.translated = {}
        else:
            self.translated = {}
    
    def _save_progress(self):
        """Save translation progress"""
        if self.progress_file:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.translated, f, ensure_ascii=False, indent=2)
    
    def _build_translate_prompt(self, lines, overlap_lines=None):
        """Build the full translation prompt"""
        parts = []
        
        # Load base prompt
        prompt_dich = PromptManager.load_prompt("prompt_dich.txt", DEFAULT_PROMPT_DICH)
        parts.append(prompt_dich)
        
        # Add function flags
        funcs = PromptManager.load_funcs()
        if self.chk_dubbing.get():
            parts.append(funcs.get('dubbing', ''))
        if self.chk_no_punct.get():
            parts.append(funcs.get('no_punct', ''))
        if self.chk_force_id.get():
            parts.append(funcs.get('force_id', ''))
        
        # Add context rules
        if self.chk_context.get() and self.context_rules:
            parts.append(funcs.get('context', 'ÁP DỤNG NGHIÊM NGẶT BỘ LUẬT DỊCH SAU:'))
            parts.append(self.context_rules)
        
        # Add overlap context
        if self.chk_overlap.get() and overlap_lines:
            n = len(overlap_lines)
            overlap_header = funcs.get('overlap', '').replace('{N}', str(n))
            parts.append(overlap_header)
            for ol in overlap_lines:
                parts.append(f"[{ol['id']}] {ol.get('translated', ol['text'])}")
            parts.append("--- HẾT PHẦN THAM KHẢO ---")
        
        # Add lines to translate
        parts.append("\n--- DỮ LIỆU CẦN DỊCH ---")
        for line in lines:
            parts.append(f"[{line['id']}] {line['text']}")
        
        return "\n".join(parts)
    
    def _start_translate(self):
        """Start translation process"""
        if not self.subtitles:
            messagebox.showwarning("Cảnh báo", "Chưa tải file SRT!")
            return
        
        if self.is_translating:
            self.is_translating = False
            self.btn_translate.configure(text="BẮT ĐẦU DỊCH", fg_color="#27AE60")
            self._log("Đã dừng dịch.")
            return
        
        self.is_translating = True
        self.btn_translate.configure(text="DỪNG DỊCH", fg_color="#E74C3C")
        
        threading.Thread(target=self._translate_worker, daemon=True).start()
    
    def _translate_worker(self):
        """Worker thread for translation"""
        batch_size = int(self.batch_size_entry.get() or 50)
        delay_profile = self.delay_var.get()
        min_delay, max_delay = DELAY_PROFILES.get(delay_profile, (5, 12))
        overlap_count = int(self.overlap_count.get() or 5)
        
        # Find untranslated lines
        untranslated = [s for s in self.subtitles if s['id'] not in self.translated]
        
        if not untranslated:
            self._log("Tất cả dòng đã được dịch!")
            self.is_translating = False
            self.btn_translate.configure(text="BẮT ĐẦU DỊCH", fg_color="#27AE60")
            return
        
        total = len(self.subtitles)
        self._log(f"Bắt đầu dịch {len(untranslated)} dòng còn lại (batch={batch_size}, delay={delay_profile})")
        
        # Split into batches
        batches = []
        for i in range(0, len(untranslated), batch_size):
            batches.append(untranslated[i:i+batch_size])
        
        self._log(f"Chia thành {len(batches)} gói để gửi")
        
        error_count = 0
        max_retries = 3
        
        for batch_idx, batch in enumerate(batches):
            if not self.is_translating:
                break
            
            self._log(f"Đang dịch gói {batch_idx+1}/{len(batches)} ({len(batch)} dòng: ID {batch[0]['id']} -> {batch[-1]['id']})...")
            
            # Get overlap lines for context
            overlap_lines = None
            if self.chk_overlap.get() and batch_idx > 0:
                # Get last N translated lines
                first_id = batch[0]['id']
                prev_lines = [s for s in self.subtitles if s['id'] < first_id and s['id'] in self.translated]
                overlap_lines = prev_lines[-overlap_count:]
                for ol in overlap_lines:
                    ol['translated'] = self.translated.get(ol['id'], ol['text'])
            
            # Build prompt
            prompt = self._build_translate_prompt(batch, overlap_lines)
            
            # Send to AI with retry
            success = False
            for retry in range(max_retries):
                if not self.is_translating:
                    break
                
                result = self._api_call("/chat", "POST", {"prompt": prompt})
                
                if result.get("status") == "ok":
                    response_text = result.get("text", "")
                    
                    # Extract from code block
                    clean_text = extract_code_block(response_text)
                    
                    # Parse translated lines
                    parsed = parse_translated_lines(clean_text)
                    
                    if parsed:
                        # Save translations
                        for line_id, trans_text in parsed.items():
                            self.translated[line_id] = trans_text
                        
                        # Update table
                        self._update_table()
                        self._save_progress()
                        
                        # Update progress
                        done = len(self.translated)
                        self.progress.set(done / total)
                        self._log(f"  Gói {batch_idx+1}: Dịch thành công {len(parsed)}/{len(batch)} dòng")
                        
                        # Check for missing IDs
                        missing = [l['id'] for l in batch if l['id'] not in parsed]
                        if missing:
                            self._log(f"  CẢNH BÁO: Thiếu ID: {missing[:10]}...")
                        
                        success = True
                        error_count = 0
                        break
                    else:
                        self._log(f"  Không parse được kết quả, thử lại ({retry+1}/{max_retries})...")
                
                elif result.get("status") == "timeout":
                    self._log(f"  Timeout! Thử lại ({retry+1}/{max_retries})...")
                
                else:
                    error_msg = result.get("text", "Unknown error")
                    self._log(f"  Lỗi: {error_msg}")
                    
                    if "Too many requests" in error_msg or "busy" in error_msg:
                        wait_time = random.randint(30, 60)
                        self._log(f"  Rate limited! Đợi {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        time.sleep(5)
            
            if not success:
                error_count += 1
                self._log(f"  GÓI {batch_idx+1} THẤT BẠI sau {max_retries} lần thử!")
                
                if error_count >= 3:
                    self._log("QUÁ NHIỀU LỖI LIÊN TIẾP - Dừng dịch. Hãy kiểm tra trình duyệt!")
                    break
            
            # Random delay between batches
            if batch_idx < len(batches) - 1 and self.is_translating:
                delay = random.uniform(min_delay, max_delay)
                self._log(f"  Nghỉ {delay:.1f}s trước gói tiếp theo...")
                time.sleep(delay)
        
        # Done
        self.is_translating = False
        self.btn_translate.configure(text="BẮT ĐẦU DỊCH", fg_color="#27AE60")
        
        done = len(self.translated)
        self._log(f"HOÀN TẤT: {done}/{total} dòng đã dịch ({done*100//total}%)")
        
        # Check errors
        missing_ids = [s['id'] for s in self.subtitles if s['id'] not in self.translated]
        if missing_ids:
            self.btn_error.configure(text=f"PHÁT HIỆN {len(missing_ids)} DÒNG THIẾU", fg_color="#E74C3C", state="normal")
            self._log(f"Các dòng chưa dịch: {missing_ids[:20]}...")
        else:
            self.btn_error.configure(text="KHÔNG PHÁT HIỆN LỖI", fg_color="#27AE60")
    
    def _update_table(self):
        """Update treeview with translations"""
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            line_id = int(values[1])
            if line_id in self.translated:
                self.tree.item(item, values=(
                    "✓",
                    values[1],
                    values[2],
                    values[3],
                    self.translated[line_id][:80]
                ))
    
    def _open_analysis(self):
        """Open analysis window"""
        win = ctk.CTkToplevel(self)
        win.title("Phân Tích & Ngữ Cảnh")
        win.geometry("900x600")
        win.attributes("-topmost", True)
        win.after(500, lambda: win.attributes("-topmost", False))
        win.focus_force()
        win.grab_set()
        
        left = ctk.CTkFrame(win, width=250)
        left.pack(side="left", fill="y", padx=5, pady=5)
        
        ctk.CTkLabel(left, text="CẤU HÌNH PHÂN TÍCH", font=("", 14, "bold"), text_color="#3498DB").pack(pady=10)
        
        self.analysis_all = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(left, text="Phân tích toàn bộ SRT", variable=self.analysis_all).pack(anchor="w", padx=10, pady=5)
        
        lines_frame = ctk.CTkFrame(left)
        lines_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(lines_frame, text="Hoặc số dòng:").pack(side="left")
        self.analysis_lines = ctk.CTkEntry(lines_frame, width=60)
        self.analysis_lines.insert(0, "100")
        self.analysis_lines.pack(side="right")
        
        # Result area
        result_text = ctk.CTkTextbox(win, fg_color="#1a1a2e")
        result_text.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        result_text.insert("1.0", "Khu vực này hiển thị kết quả phân tích...")
        
        def do_analysis():
            if not self.subtitles:
                messagebox.showwarning("Cảnh báo", "Chưa tải file SRT!")
                return
            
            num_lines = len(self.subtitles) if self.analysis_all.get() else int(self.analysis_lines.get() or 100)
            lines_to_analyze = self.subtitles[:num_lines]
            
            prompt = PromptManager.load_prompt("prompt_analysis.txt", DEFAULT_PROMPT_PHAN_TICH)
            prompt += "\n\n--- NỘI DUNG PHIM ---\n"
            for line in lines_to_analyze:
                prompt += f"[{line['id']}] {line['text']}\n"
            
            result_text.delete("1.0", "end")
            result_text.insert("1.0", "Đang phân tích...")
            
            def run():
                result = self._api_call("/chat", "POST", {"prompt": prompt})
                text = result.get("text", "Lỗi: không nhận được phản hồi")
                result_text.delete("1.0", "end")
                result_text.insert("1.0", text)
            
            threading.Thread(target=run, daemon=True).start()
        
        ctk.CTkButton(left, text="GỬI AI PHÂN TÍCH", command=do_analysis, fg_color="#27AE60", font=("", 13, "bold")).pack(fill="x", padx=10, pady=10)
        
        def save_rules():
            self.context_rules = result_text.get("1.0", "end").strip()
            self._log("Đã lưu bộ luật dịch vào RAM!")
            win.destroy()
        
        ctk.CTkButton(left, text="LƯU BỘ LUẬT", command=save_rules, fg_color="#27AE60").pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(left, text="* Lưu ý: Nút Lưu ở trên chỉ đưa\nluật vào RAM, tool sẽ tự nạp\nvào prompt khi bạn tích\n'Gửi kèm bộ luật Context'.",
                     font=("", 10), text_color="#888").pack(padx=10, pady=20)
    
    def _generate_content(self):
        """Generate content titles/hashtags"""
        if not self.subtitles:
            messagebox.showwarning("Cảnh báo", "Chưa tải file SRT!")
            return
        
        prompt = PromptManager.load_prompt("prompt_content.txt", DEFAULT_PROMPT_CONTENT)
        prompt += "\n\n--- NỘI DUNG PHỤ ĐỀ ---\n"
        for line in self.subtitles[:200]:
            prompt += f"{line['text']}\n"
        
        self._log("Đang tạo content...")
        
        def run():
            result = self._api_call("/chat", "POST", {"prompt": prompt})
            text = result.get("text", "Lỗi")
            self._log(f"Content đã tạo xong! (Xem trong cửa sổ mới)")
            
            # Show in new window
            win = ctk.CTkToplevel(self)
            win.title("Content Đăng Bài")
            win.geometry("600x400")
            tb = ctk.CTkTextbox(win)
            tb.pack(fill="both", expand=True, padx=10, pady=10)
            tb.insert("1.0", text)
        
        threading.Thread(target=run, daemon=True).start()
    
    def _edit_prompt(self, filename, default):
        """Open prompt editor"""
        win = ctk.CTkToplevel(self)
        win.title(f"Sửa Prompt: {filename}")
        win.geometry("700x500")
        
        text = PromptManager.load_prompt(filename, default)
        
        editor = ctk.CTkTextbox(win, font=("Consolas", 12))
        editor.pack(fill="both", expand=True, padx=10, pady=10)
        editor.insert("1.0", text)
        
        def save():
            PromptManager.save_prompt(filename, editor.get("1.0", "end").strip())
            self._log(f"Đã lưu prompt: {filename}")
            messagebox.showinfo("OK", "Đã lưu!")
        
        ctk.CTkButton(win, text="LƯU", command=save, fg_color="#27AE60").pack(pady=10)
    
    def _export_srt(self):
        """Export translated SRT"""
        if not self.subtitles:
            messagebox.showwarning("Cảnh báo", "Chưa có dữ liệu!")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Lưu file SRT đã dịch",
            defaultextension=".srt",
            filetypes=[("SRT files", "*.srt")]
        )
        if not filepath:
            return
        
        # Build output
        for sub in self.subtitles:
            if sub['id'] in self.translated:
                sub['translated'] = self.translated[sub['id']]
            else:
                sub['translated'] = sub['text']
        
        write_srt(self.subtitles, filepath)
        self._log(f"Đã xuất file: {filepath}")
        messagebox.showinfo("Thành công", f"Đã lưu file SRT!\n{filepath}")
    
    def destroy(self):
        """Cleanup on exit"""
        if self.backend_process:
            self.backend_process.terminate()
        super().destroy()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # Install requirements if needed
    required = ['customtkinter', 'requests', 'playwright', 'fastapi', 'uvicorn', 'pydantic']
    
    try:
        import customtkinter
    except ImportError:
        print("Installing requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + required)
        print("Done! Starting app...")
    
    app = HMAutoTranslator()
    app.mainloop()
