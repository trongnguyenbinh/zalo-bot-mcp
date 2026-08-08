<p align="center"><a href="README.md">English</a> | Tiếng Việt</p>

<h1 align="center">zalo-bot-mcp</h1>

<p align="center">
  Nhắn Zalo, AI agent của bạn làm việc.
</p>

<p align="center">
  <a href="https://pypi.org/project/zalo-bot-mcp/"><img src="https://img.shields.io/pypi/v/zalo-bot-mcp.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/zalo-bot-mcp/"><img src="https://img.shields.io/pypi/pyversions/zalo-bot-mcp.svg" alt="Python versions"></a>
  <a href="#giấy-phép"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/status-early%20development-orange.svg" alt="Đang phát triển">
</p>

MCP channel server cho [Zalo Bot API](https://bot.zapps.me/docs/). Tin nhắn gửi tới bot Zalo
của bạn sẽ vào session MCP đang chạy. Session trả lời lại bằng một tool call.

> **Dự án còn mới.** Đã lên PyPI và đã chạy thật với bot thật. MCP channel thì vẫn là tính
> năng thử nghiệm của Claude Code.

## Cách hoạt động

```
Nhóm Zalo  ──mention──▶  getUpdates  ──▶  gate  ──▶  MCP session
                                           │             │
                                     (không cho qua)  tool reply
                                           │             │
                                          bỏ    ◀────────┘
                                                    sendMessage
```

Server gọi `getUpdates` để lấy tin, tức là kết nối đi ra. Không cần URL public, không cần
webhook, không cần tunnel. Chạy được trên laptop sau NAT.

Mọi tin đến đều đi qua gate trước. Không thành phần nào thấy tin trước gate.

## Kiểm soát truy cập

**Tin nhắn riêng** theo một trong ba policy:

| Policy | Người lạ nhắn tới thì nhận được gì |
| --- | --- |
| `pairing` | Một mã pairing ngắn hạn, bạn duyệt bằng đường khác |
| `allowlist` | Không nhận được gì. Tin bị bỏ |
| `disabled` | Không nhận được gì. Mọi tin nhắn riêng đều bị bỏ |

**Nhóm** phải được cấp quyền theo `chat_id`. Thêm bot vào nhóm không đồng nghĩa nhóm đó dùng
được. Bạn cũng giới hạn được ai trong nhóm gọi được bot.

Hai ràng buộc code không cho phá:

1. Không tin nhắn Zalo nào sửa được config truy cập. Tin xin vào allowlist trông giống hệt
   một cú prompt injection, nên việc cấp quyền nằm ngoài kênh chat.
2. Allowlist có wildcard thì server không khởi động. Lúc test hay nới allowlist cho nhanh
   rồi quên thu lại.

Nằm trong allowlist chỉ có nghĩa là nhắn được cho bot. Không kèm quyền nào khác.

## Giới hạn từ phía Zalo

Đây là giới hạn của Zalo Bot API, bot nào cũng chịu. Zalo có thể đổi bất cứ lúc nào, nên
<https://bot.zapps.me/> mới là nguồn chuẩn. Mục này là bản tóm và có thể đã cũ.

- **Trong nhóm, bot chỉ nhận tin khi được mention hoặc được reply.** Không đọc được toàn bộ
  cuộc trò chuyện.
- **Một tin tối đa 2000 ký tự.** Dài hơn thì bị cắt thành nhiều tin.
- **Không có offset.** `getUpdates` chỉ nhận `timeout`. Muốn tránh xử lý trùng thì phải tự
  lưu `message_id`.
- **Gửi rồi không sửa được.** Việc chạy lâu thì báo tiến độ bằng tin mới.
- **Không có reaction.** API không có endpoint thả cảm xúc. Có `sendChatAction` (trạng thái
  đang soạn tin) và sticker.
- **Hạn mức gói miễn phí.** Gói Basic: 3 bot mỗi tài khoản, 50 người mỗi bot, 3 nhóm chat
  (ghi beta), 3.000 tin gửi đi mỗi tháng. Có gói Pro trả phí. Xem mức hiện hành tại
  <https://bot.zapps.me/>.

## Cài đặt

Hai đường, đều cần [uv](https://docs.astral.sh/uv/):

- **Plugin Claude Code**: `/plugin marketplace add trongnguyenbinh/zalo-bot-mcp` rồi
  `/plugin install zalo@zalo-bot-mcp`
- **Gói Python**: `uv tool install zalo-bot-mcp` rồi khai server trong `.mcp.json`

Cài xong phải chạy Claude Code kèm flag channel. Thiếu flag đó thì tin nhắn không vào tới
session.

Hướng dẫn đầy đủ, từ tạo bot tới tin trả lời đầu tiên, kèm toàn bộ skill `/zalo:*` và CLI
`zalo-bot-mcp-admin`: **[docs/getting-started.vi.md](docs/getting-started.vi.md)**
(English: [docs/getting-started.md](docs/getting-started.md)).

### Về flag channel

Flag là `--dangerously-load-development-channels`.

Flag `--channels` thường không dùng được. Nó chỉ nhận plugin nằm trong allowlist có sẵn của
Claude Code, và không nhận entry `server:`. zalo chưa có trong allowlist đó.

Anthropic ghi rõ flag development chỉ để phát triển channel trên máy mình, không dùng cho
channel tải từ internet. Repo này tải từ internet.

Rủi ro: bạn cho một app nhắn tin đi vào session đọc được file và chạy được lệnh trên máy.

Cái hạn chế rủi ro: gate chặn ở đầu vào, và tin nhắn Zalo không sửa được allowlist. Code của
cả hai ở [`src/zalo_bot_mcp/gate.py`](src/zalo_bot_mcp/gate.py) và [SECURITY.md](SECURITY.md).

## Chạy thử khi phát triển

```bash
git clone https://github.com/trongnguyenbinh/zalo-bot-mcp.git
cd zalo-bot-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Lúc chạy chỉ cần `httpx` và `mcp`. Các endpoint Zalo được gọi trực tiếp, nên toàn bộ phần
gọi API nằm trong một file.

## Không liên kết với Zalo

Đây là dự án cá nhân, không phải sản phẩm chính thức. Không do Zalo hay VNG Corporation phát
triển, không được họ duyệt, không được họ hỗ trợ. "Zalo" là nhãn hiệu của họ, ở đây dùng để
chỉ rõ phần mềm này kết nối với dịch vụ nào.

Phần mềm gọi [Zalo Bot API](https://bot.zapps.me/docs/) công khai, như mọi bot bên thứ ba
khác. Bot, token và tài khoản là của bạn, trách nhiệm cũng vậy. Đọc điều khoản của Zalo
trước khi dùng cho việc quan trọng. API có thể đổi bất cứ lúc nào.

Phát hành theo giấy phép MIT: không bảo hành, không chịu trách nhiệm.

## Giấy phép

MIT
