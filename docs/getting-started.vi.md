[English](getting-started.md) | Tiếng Việt

# Bắt đầu từ đầu

Ba bước: tạo bot Zalo, cài server này, chạy Claude Code với cờ channel. Bước
cuối là bước ai cũng quên.

## 1. Tạo bot Zalo

Bot được tạo ngay trong ứng dụng Zalo, qua tài khoản chính thức tên
**Zalo Bot Manager** (tài liệu: <https://bot.zapps.me/docs/create-bot/>):

1. Trong ứng dụng Zalo, tìm OA **Zalo Bot Manager** và mở khung chat.
2. Trong menu của khung chat, chọn **Tạo bot**. Ứng dụng nhỏ
   **Zalo Bot Creator** sẽ mở ra.
3. Đặt tên cho bot. Tên bắt buộc bắt đầu bằng chữ `Bot`, ví dụ `Bot MyShop`.
4. Bấm **Tạo Bot** để xác nhận. Token của bot được gửi về tài khoản Zalo của
   bạn dưới dạng tin nhắn. Hãy coi nó như mật khẩu: đừng dán vào chat, vào
   file, hay vào tham số dòng lệnh. Bước 2 bên dưới có cách nạp token an toàn.
5. Trên <https://bot.zapps.me/> chọn gói. Gói miễn phí **Basic** có nút
   **Đăng ký gói**; gói Pro trả phí đang ghi là sắp ra mắt. Hạn mức gói Basic:

![Hạn mức gói Basic](assets/quota-basic.vi.png)

## 2. Cài server

Cả hai đường đều cần cài sẵn [uv](https://docs.astral.sh/uv/).

### Đường A: plugin Claude Code (khuyên dùng)

Trong Claude Code:

```
/plugin marketplace add trongnguyenbinh/zalo-bot-mcp
/plugin install zalo@zalo-bot-mcp
```

Lệnh này đăng ký MCP server và tám skill `/zalo:*`. Sau đó copy token của bot
vào clipboard rồi chạy:

```
/zalo:set-token
```

Token đi từ clipboard thẳng vào `~/.zalo-bot-mcp/.env` với quyền `0600`,
không đi qua transcript hội thoại, không đi qua tham số lệnh. Skill từ chối
nhận token dạng chữ cũng vì lý do đó.

### Đường B: gói Python

Chưa lên PyPI, cài từ source:

```bash
uv tool install git+https://github.com/trongnguyenbinh/zalo-bot-mcp
```

Khai báo server trong `.mcp.json` của thư mục dự án:

```json
{ "mcpServers": { "zalo": { "command": "zalo-bot-mcp" } } }
```

Nạp token từ clipboard (lệnh macOS; trên Linux thay `pbpaste` bằng
`xclip -o -selection clipboard` hoặc `wl-paste`):

```bash
pbpaste | zalo-bot-mcp-admin set-token
```

CLI gọi `getMe` kiểm tra token với API thật trước khi ghi, thành công thì in
tên bot ra. Cách khác: đặt biến môi trường `ZALO_BOT_TOKEN`.

## 3. Chạy Claude Code với cờ channel

**Thiếu bước này thì mọi thứ chết im lặng.** MCP channel là tính năng thử
nghiệm của Claude Code, mặc định tắt. Không có cờ thì MCP server vẫn nối
được, tool `reply` vẫn có, nhưng tin nhắn Zalo không bao giờ vào phiên.

```bash
claude --dangerously-load-development-channels server:zalo
```

Hai chi tiết quan trọng:

- Bắt buộc có tiền tố `server:`. Viết
  `--dangerously-load-development-channels zalo` là không nhận.
- Chạy trong thư mục có `.mcp.json` khai server `zalo` (đường B), hoặc đã cài
  plugin (đường A). Bộ phân giải channel phải tìm thấy server đúng tên đó.

Claude Code sẽ hỏi xác nhận về development channels, rồi hiện banner báo tin
nhắn từ `server:zalo` sẽ vào thẳng phiên. Nhắn thử cho bot trên Zalo: tin DM
đầu tiên nhận được mã pairing, bạn duyệt mã (`/zalo:approve <mã>`) xong thì
tin bắt đầu vào phiên.

## 4. Danh sách lệnh

### Skill `/zalo:*` (trong Claude Code)

| Skill | Công dụng |
| --- | --- |
| `/zalo:set-token` | Nạp token bot từ clipboard. Ví dụ: copy token xong gõ `/zalo:set-token` |
| `/zalo:list` | Xem trạng thái access: chính sách DM, allowlist, nhóm, mã đang chờ |
| `/zalo:pending-chats` | Xem các chat bị gate chặn, kèm sẵn lệnh cấp quyền |
| `/zalo:approve` | Duyệt mã pairing. Ví dụ: `/zalo:approve a1b2c3` |
| `/zalo:allow` | Thêm thẳng một user_id vào allowlist. Ví dụ: `/zalo:allow 1234abcd` |
| `/zalo:revoke` | Gỡ một user_id khỏi allowlist. Ví dụ: `/zalo:revoke 1234abcd` |
| `/zalo:group-add` | Cấp quyền một nhóm theo chat_id. Ví dụ: `/zalo:group-add zgr-1a2b3c` |
| `/zalo:group-remove` | Gỡ quyền một nhóm. Ví dụ: `/zalo:group-remove zgr-1a2b3c` |

Mọi skill cấp quyền đều từ chối chạy khi yêu cầu đến từ một tin nhắn Zalo
thay vì từ chính bạn: kịch bản đó chính là hình dáng của tấn công chèn lệnh.

### CLI `zalo-bot-mcp-admin` (ngoài terminal)

Đúng các thao tác trên, không cần Claude Code:

```bash
zalo-bot-mcp-admin list                      # xem trạng thái access
zalo-bot-mcp-admin pending-chats             # chat bị chặn + lệnh gợi ý
zalo-bot-mcp-admin approve a1b2c3            # duyệt mã pairing
zalo-bot-mcp-admin allow 1234abcd            # thêm thẳng user vào allowlist
zalo-bot-mcp-admin revoke 1234abcd           # gỡ user
zalo-bot-mcp-admin group-add zgr-1a2b3c      # cấp quyền nhóm
zalo-bot-mcp-admin group-remove zgr-1a2b3c   # gỡ quyền nhóm
pbpaste | zalo-bot-mcp-admin set-token       # nạp token từ clipboard
```

Trạng thái nằm ở `~/.zalo-bot-mcp/` (đổi bằng biến `ZALO_MCP_STATE_DIR`).

## Xử lý sự cố

**Bot im hoàn toàn.** Khả năng cao bot đang gắn webhook: Zalo từ chối
`getUpdates` khi webhook còn đó, và server thoát ngay lúc khởi động kèm URL
webhook trong thông báo lỗi. Xoá webhook (`deleteWebhook` trong Bot API) rồi
chạy lại.

**Khởi động báo "another poller (pid N) holds the lock".** Hai tiến trình
đang cùng poll một token: mỗi bot chỉ được một người tiêu thụ `getUpdates`,
không thì chúng giật tin của nhau. Tìm xem tiến trình kia chạy ở đâu và tắt
ở đó; tiến trình mới cố tình từ chối chứ không bao giờ tự giết ai.

**MCP nối được mà tin không vào phiên.** Hoặc thiếu cờ channel (xem bước 3),
hoặc Claude Code được mở ở thư mục không khai server `zalo`. Hai lỗi nhìn
giống hệt nhau: server khỏe, channel chết.
