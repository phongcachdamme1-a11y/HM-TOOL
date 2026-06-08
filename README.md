# HM AutoTranslator Pro

Tool dịch phụ đề SRT tự động bằng DeepSeek / Gemini (không cần API, dùng trình duyệt web).

## Cài đặt

```bash
pip install customtkinter requests playwright fastapi uvicorn pydantic
playwright install chromium
```

## Chạy

```bash
python HM.py
```

## Cách dùng

1. Chọn AI (DeepSeek hoặc Gemini)
2. Click "Khởi chạy Trình duyệt" → Đăng nhập vào tài khoản AI
3. Click "Tải file SRT" → Chọn file phụ đề cần dịch
4. (Tùy chọn) Mở "Bảng Phân Tích" để AI phân tích ngữ cảnh phim
5. Cấu hình: số dòng/lần gửi, delay, các tùy chọn
6. Click "BẮT ĐẦU DỊCH"
7. Khi xong, click "Xuất File SRT"

## Cài đặt khuyến nghị cho DeepSeek

| Cài đặt | Giá trị |
|---------|---------|
| Số dòng/Lần gửi | 50-80 |
| Hạn chế Bot | An toàn (5-12s) |
| Ép Force đủ ID | ✓ |
| Gối câu | ✓ (5 câu) |

## Cài đặt cho Gemini (nhanh hơn)

| Cài đặt | Giá trị |
|---------|---------|
| Số dòng/Lần gửi | 200-500 |
| Hạn chế Bot | Nhanh (1-3s) |

## Tính năng

- ✅ Dịch batch (nhiều dòng/lần) 
- ✅ Lưu tiến trình tự động (resume khi bị ngắt)
- ✅ Random delay chống bot
- ✅ Auto retry khi lỗi
- ✅ Hỗ trợ DeepSeek + Gemini
- ✅ Phân tích ngữ cảnh phim
- ✅ Tạo content (tiêu đề, hashtag)
- ✅ Lồng tiếng Nam/Nữ
- ✅ Gối câu (overlap context)
