[English](getting-started.md) | Tiếng Việt

# Bắt đầu

Tạo bot Zalo, rồi chọn một trong hai đường cài và làm hết đường đó. Mỗi đường
đi đủ tới lúc nhận được tin đầu tiên, gồm cả flag channel là bước ai cũng
quên.

## 1. Tạo bot Zalo

Bot được tạo ngay trong ứng dụng Zalo, qua tài khoản chính thức tên
**Zalo Bot Manager** (tài liệu: <https://bot.zapps.me/docs/create-bot/>):

1. Trong ứng dụng Zalo, tìm OA **Zalo Bot Manager** và mở khung chat.
2. Trong menu của khung chat, chọn **Tạo bot**. Mini app **Zalo Bot Creator**
   sẽ mở ra.
3. Đặt tên cho bot. Tên bắt buộc bắt đầu bằng chữ `Bot`, ví dụ `Bot MyShop`.
4. Bấm **Tạo Bot** để xác nhận. Token của bot được gửi về tài khoản Zalo của
   bạn dưới dạng tin nhắn. Hãy coi nó như mật khẩu: đừng dán vào chat, vào
   file, hay vào tham số dòng lệnh. Bước 2 bên dưới có cách nạp token an toàn.
5. Trên <https://bot.zapps.me/> chọn gói. Gói miễn phí **Basic** có nút
   **Đăng ký gói**; gói Pro trả phí đang ghi là sắp ra mắt. Hạn mức gói Basic:

![Hạn mức gói Basic](assets/quota-basic.vi.png)

## 2. Cài và chạy

Có hai đường. **Chọn một đường và làm hết đường đó.** Mỗi đường bên dưới là
một luồng đầy đủ, từ lúc cài tới lúc nhận được tin đầu tiên. Hai đường khác
nhau nhiều hơn mỗi lệnh cài, nên đừng lắp lẫn bước của đường này sang đường
kia.

| | Đường A: plugin | Đường B: gói Python |
| --- | --- | --- |
| Cài từ | Claude Code | terminal |
| Quản lý access bằng | skill `/zalo:*` | CLI `zalo-bot-mcp-admin` |
| Cần `.mcp.json` | không | có, mỗi thư mục dự án một file |
| Entry channel | `plugin:zalo@zalo-bot-mcp` | `server:zalo` |
| Chạy được ở mọi thư mục | có | chỉ ở nơi có `.mcp.json` |

Cả hai đều cần cài sẵn [uv](https://docs.astral.sh/uv/), và đều lưu state ở
`~/.zalo-bot-mcp/`, nên sau này đổi đường vẫn giữ nguyên token và allowlist.

---

### Đường A: plugin Claude Code

**A1. Cài plugin.** Trong Claude Code:

```
/plugin marketplace add trongnguyenbinh/zalo-bot-mcp
/plugin install zalo@zalo-bot-mcp
```

Lệnh này đăng ký MCP server và các skill `/zalo:*`.

**A2. Nạp token.** Copy token của bot vào clipboard rồi chạy:

```
/zalo:set-token
```

Token đi thẳng từ clipboard vào `~/.zalo-bot-mcp/.env`, quyền `0600`, không
nằm lại trong nội dung hội thoại. Đó là lý do skill này không nhận token gõ
tay: đừng dán token vào khung chat.

**A3. Khởi động lại Claude Code kèm flag channel.** Ngoài terminal:

```bash
claude --dangerously-load-development-channels plugin:zalo@zalo-bot-mcp
```

Thiếu flag này thì server vẫn kết nối, tool `reply` vẫn có, nhưng không tin
Zalo nào vào tới session. Lý do tên flag như vậy xem ở
[Về cái flag đó](#về-cái-flag-đó).

**A4. Gửi tin đầu tiên.** Nhắn cho bot trên Zalo, bạn nhận lại một mã pairing.
Duyệt mã trong Claude Code:

```
/zalo:approve a1b2c3
```

Nhắn lại lần nữa: tin sẽ vào session.

**A5. Khoá lại.** Khi policy còn là `pairing`, người lạ nào tìm ra bot cũng xin
được mã pairing. Duyệt xong cho mình rồi thì khoá:

```
/zalo:list
/zalo:policy allowlist
```

**Gỡ cài đặt:** `/plugin uninstall zalo@zalo-bot-mcp`. Lệnh này không đụng tới
`~/.zalo-bot-mcp/`, nên token và allowlist còn nguyên. Muốn sạch hẳn thì xoá
thêm thư mục đó.

---

### Đường B: gói Python

**B1. Cài.** Ngoài terminal:

```bash
uv tool install zalo-bot-mcp
```

Hoặc cài từ source, nếu muốn lấy commit chưa release:

```bash
uv tool install git+https://github.com/trongnguyenbinh/zalo-bot-mcp
```

**B2. Kiểm tra `PATH`.**

```bash
which zalo-bot-mcp
```

Không in ra gì tức là `~/.local/bin` chưa có trong `PATH`. Chạy
`uv tool update-shell` rồi mở shell mới.

**B3. Tạo `.mcp.json`.** Lệnh cài KHÔNG tạo file này, và Claude Code chỉ tìm
nó trong đúng thư mục bạn chạy lệnh. Bạn tự tạo, trong thư mục dự án định
dùng:

```bash
cat > .mcp.json <<'EOF'
{ "mcpServers": { "zalo": { "command": "zalo-bot-mcp" } } }
EOF
```

**B4. Nạp token.** Chạy trên terminal thì lệnh hiện prompt và ẩn ký tự nhập,
bạn paste token vào rồi bấm Enter:

```bash
zalo-bot-mcp-admin set-token
```

Pipe cũng được (lệnh macOS; trên Linux thay `pbpaste` bằng
`xclip -o -selection clipboard` hoặc `wl-paste`):

```bash
pbpaste | zalo-bot-mcp-admin set-token
```

Đừng truyền token làm tham số dòng lệnh: nó nằm lại trong shell history và
hiện trong danh sách process. CLI gọi `getMe` hỏi API thật xem token đúng
không rồi mới ghi, đúng thì in tên bot ra. Cách khác: đặt biến môi trường
`ZALO_BOT_TOKEN`.

**B5. Chạy Claude Code kèm flag channel**, đứng trong thư mục có `.mcp.json`:

```bash
claude --dangerously-load-development-channels server:zalo
```

Thiếu flag này thì server vẫn kết nối, tool `reply` vẫn có, nhưng không tin
Zalo nào vào tới session. Lý do tên flag như vậy xem ở
[Về cái flag đó](#về-cái-flag-đó).

**B6. Gửi tin đầu tiên.** Nhắn cho bot trên Zalo, bạn nhận lại một mã pairing.
Duyệt mã ngoài terminal:

```bash
zalo-bot-mcp-admin approve a1b2c3
```

Nhắn lại lần nữa: tin sẽ vào session.

**B7. Khoá lại.** Khi policy còn là `pairing`, người lạ nào tìm ra bot cũng xin
được mã pairing. Duyệt xong cho mình rồi thì khoá:

```bash
zalo-bot-mcp-admin list               # kiểm id của bạn có trong allowFrom
zalo-bot-mcp-admin policy allowlist
```

Lệnh từ chối chuyển sang `allowlist` khi `allowFrom` còn rỗng, vì như vậy là
khoá tất cả ra ngoài, kể cả bạn, mà cũng không còn đường xin mã pairing.

**Gỡ cài đặt:**

```bash
uv tool uninstall zalo-bot-mcp
rm .mcp.json
```

Hai lệnh này không đụng tới `~/.zalo-bot-mcp/`, nên token và allowlist còn
nguyên. Muốn sạch hẳn thì xoá thêm thư mục đó.

---

### Về cái flag đó

MCP channel là tính năng thử nghiệm của Claude Code, mặc định tắt.

Flag là `--dangerously-load-development-channels`, không phải `--channels`.
Flag `--channels` chỉ nhận plugin nằm trong allowlist mà Claude Code nhúng
sẵn, và từ chối thẳng entry `server:`. zalo không có trong allowlist đó, nên
flag development là đường duy nhất hiện tại.

Prefix là bắt buộc, và dùng prefix nào thì tuỳ đường bạn cài. Claude Code tìm
tên `server:` trong scope enterprise, user, project, local; server của một
plugin không nằm trong bốn scope đó, nên đường A phải dùng `plugin:`. Gõ trống
trơn `zalo` thì cả hai đường đều không nhận.

Anthropic ghi rõ flag này để phát triển channel của chính mình trên máy mình,
không dùng cho channel tải từ internet. Repo này tải từ internet. Cái hạn chế
rủi ro là gate, và quy tắc không tin nhắn Zalo nào sửa được danh sách người
được vào. Code cả hai ở
[`src/zalo_bot_mcp/gate.py`](../src/zalo_bot_mcp/gate.py) và
[SECURITY.md](../SECURITY.md).

## 3. Danh sách lệnh

### Skill `/zalo:*` (trong Claude Code)

| Skill | Công dụng |
| --- | --- |
| `/zalo:set-token` | Nạp token bot từ clipboard. Ví dụ: copy token xong gõ `/zalo:set-token` |
| `/zalo:list` | Xem trạng thái access: policy DM, allowlist, nhóm, mã đang chờ |
| `/zalo:policy` | Đổi policy tin nhắn riêng. Ví dụ: `/zalo:policy allowlist` |
| `/zalo:pending-chats` | Xem các chat bị gate chặn, kèm sẵn lệnh cấp quyền |
| `/zalo:approve` | Duyệt mã pairing. Ví dụ: `/zalo:approve a1b2c3` |
| `/zalo:allow` | Thêm thẳng một user_id vào allowlist. Ví dụ: `/zalo:allow 1234abcd` |
| `/zalo:revoke` | Gỡ một user_id khỏi allowlist. Ví dụ: `/zalo:revoke 1234abcd` |
| `/zalo:group-add` | Cấp quyền một nhóm theo chat_id. Ví dụ: `/zalo:group-add zgr-1a2b3c` |
| `/zalo:group-remove` | Gỡ quyền một nhóm. Ví dụ: `/zalo:group-remove zgr-1a2b3c` |

Mọi skill cấp quyền đều từ chối chạy khi yêu cầu đến từ một tin nhắn Zalo
thay vì từ chính bạn. Đó đúng là cách một cú chèn lệnh sẽ diễn ra.

### CLI `zalo-bot-mcp-admin` (ngoài terminal)

Đúng các thao tác trên, không cần Claude Code:

```bash
zalo-bot-mcp-admin list                      # xem trạng thái access
zalo-bot-mcp-admin pending-chats             # chat bị chặn + lệnh gợi ý
zalo-bot-mcp-admin policy allowlist          # đổi policy tin nhắn riêng
zalo-bot-mcp-admin approve a1b2c3            # duyệt mã pairing
zalo-bot-mcp-admin allow 1234abcd            # thêm thẳng user vào allowlist
zalo-bot-mcp-admin revoke 1234abcd           # gỡ user
zalo-bot-mcp-admin group-add zgr-1a2b3c      # cấp quyền nhóm
zalo-bot-mcp-admin group-remove zgr-1a2b3c   # gỡ quyền nhóm
pbpaste | zalo-bot-mcp-admin set-token       # nạp token từ clipboard
```

State nằm ở `~/.zalo-bot-mcp/` (đổi bằng biến `ZALO_MCP_STATE_DIR`).

## Xử lý sự cố

**Bot im hoàn toàn.** Khả năng cao bot đang gắn webhook: Zalo từ chối
`getUpdates` khi webhook còn đó, và server thoát ngay lúc khởi động kèm URL
webhook trong thông báo lỗi. Xoá webhook (`deleteWebhook` trong Bot API) rồi
chạy lại.

**Khởi động báo "another poller (pid N) holds the lock".** Hai tiến trình
đang cùng poll một token: mỗi bot chỉ được đúng một tiến trình gọi `getUpdates`,
nếu không hai bên giật tin của nhau. Tìm xem tiến trình kia chạy ở đâu và tắt
ở đó; tiến trình mới cố tình từ chối chứ không bao giờ tự giết ai.

**MCP kết nối được mà tin không vào session.** Lỗi hay gặp nhất, và cả bốn
trường hợp đều nhìn giống hệt nhau: server khoẻ, channel chết.

- Thiếu hẳn flag channel (bước A3 / B5).
- Gõ `--channels` thay vì `--dangerously-load-development-channels`.
- Sai entry so với đường đã cài: dùng `server:zalo` khi cài plugin, hoặc
  `plugin:zalo@zalo-bot-mcp` khi cài gói Python.
- Riêng đường B: mở Claude Code ngoài thư mục chứa `.mcp.json`.

**Báo `invalid choice: 'policy'`** nghĩa là bản đang cài cũ hơn bản có lệnh
này. Nâng cấp bằng `uv tool upgrade zalo-bot-mcp`, hoặc
`/plugin update zalo@zalo-bot-mcp`.

**Báo `cannot read ~/.zalo-bot-mcp/access.json`** nghĩa là file không còn là
JSON hợp lệ, gần như luôn do sửa tay. Sửa lại cú pháp, hoặc xoá file để chạy
lại từ mặc định (`pairing`, chưa ai được vào) rồi duyệt lại cho mình. Nên đổi
policy bằng `zalo-bot-mcp-admin policy` thay vì sửa file tay.
