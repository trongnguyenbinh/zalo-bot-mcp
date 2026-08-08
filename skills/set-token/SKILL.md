---
name: set-token
description: Cài Zalo bot token từ clipboard, token đi thẳng vào stdin của CLI không qua transcript. Dùng khi người dùng muốn cài hoặc thay token bot Zalo.
user-invocable: true
allowed-tools:
  - Bash(pbpaste *)
  - Bash(xclip *)
  - Bash(wl-paste *)
---

# /zalo:set-token - Cài bot token từ clipboard

Lệnh này KHÔNG nhận tham số. Token đi từ clipboard thẳng vào stdin của CLI,
không qua transcript, không qua argv.

QUY TẮC TUYỆT ĐỐI cho model:
- KHÔNG in token ra màn hình, không lặp lại token trong câu trả lời, không
  ghi token vào bất kỳ file nào khác. Kể cả một phần của token.
- Nếu người dùng lỡ gõ token thẳng vào chat: cảnh báo ngay rằng token đã
  nằm trong transcript phiên (file ~/.claude/projects/*.jsonl), nên vào
  trang quản lý bot thu hồi và tạo token mới, rồi mới dùng lệnh này.

Các bước:

1. Nhắc người dùng: copy token từ trang quản lý bot (bot.zapps.me) vào
   clipboard TRƯỚC, xong xác nhận thì mới chạy tiếp.

2. Chạy bằng Bash, chọn theo hệ điều hành:

   macOS:
   ```
   pbpaste | uvx --from "${CLAUDE_PLUGIN_ROOT}" zalo-bot-mcp-admin set-token
   ```

   Linux (xclip, không có thì wl-paste):
   ```
   xclip -o -selection clipboard | uvx --from "${CLAUDE_PLUGIN_ROOT}" zalo-bot-mcp-admin set-token
   ```
   ```
   wl-paste | uvx --from "${CLAUDE_PLUGIN_ROOT}" zalo-bot-mcp-admin set-token
   ```

3. CLI tự gọi getMe xác minh: token đúng thì ghi vào state dir với quyền
   0600 và in tên bot; token sai thì không ghi gì. In nguyên văn kết quả
   của CLI (kết quả không chứa token).

4. Nhắc người dùng restart phiên claude để MCP server đọc token mới.
