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

MCP channel server cho [Zalo Bot API](https://bot.zapps.me/docs/). Ai nhắn cho bot Zalo của
bạn thì tin đó vào thẳng session MCP đang chạy, và session trả lời ngược lại bằng một tool
call.

> **Dự án còn mới.** Đã lên PyPI, server chạy thật với bot thật rồi, nhưng MCP channel mà
> nó bám vào vẫn là tính năng thử nghiệm của Claude Code.

## Nó chạy thế nào

```
Nhóm Zalo  ──mention──▶  getUpdates  ──▶  gate  ──▶  MCP session
                                           │             │
                                     (không được phép)  tool reply
                                           │             │
                                         bỏ im  ◀────────┘
                                                    sendMessage
```

Server hỏi Zalo bằng `getUpdates`, tức là nó chủ động gọi ra. Không cần URL public, không
cần webhook, không cần tunnel. Cắm trên laptop sau NAT vẫn chạy.

Tin nào đến cũng phải qua gate trước. Trong hệ thống này không có thứ gì thấy tin trước gate.

## Kiểm soát truy cập

**Tin nhắn riêng** chạy theo một trong ba chính sách:

| Chính sách | Người lạ nhắn vào thì nhận được gì |
| --- | --- |
| `pairing` | Một mã ghép nối ngắn hạn, bạn duyệt bằng đường khác |
| `allowlist` | Không gì cả. Tin bị bỏ, bot im |
| `disabled` | Không gì cả. Mọi tin nhắn riêng đều bị bỏ |

**Nhóm** phải được cấp quyền theo `chat_id`. Kéo bot vào nhóm không có nghĩa là nhóm đó dùng
được. Bạn còn giới hạn được ai trong nhóm mới gọi bot.

Hai điều code không cho phá:

1. Không tin nhắn Zalo nào sửa được cấu hình truy cập. Một tin xin vào allowlist trông y hệt
   một cú chèn lệnh, nên việc cấp quyền luôn nằm ngoài kênh chat.
2. Allowlist mà có wildcard thì server không chịu khởi động. Lúc thử nghiệm ai cũng
   nới allowlist ra cho nhanh, rồi quên thu lại.

Nằm trong allowlist chỉ có nghĩa là bạn nhắn được cho bot. Nó không kèm theo quyền hành gì
khác.

## Zalo giới hạn những gì

Đây là giới hạn của chính Zalo Bot API, bot nào cũng dính. Zalo nắm luật và đổi lúc nào cũng
được, nên <https://bot.zapps.me/> mới là nguồn chuẩn, còn mục này chỉ là bản tóm và có thể
đã cũ:

- **Trong nhóm, bot chỉ nghe khi được gọi tên.** Phải mention hoặc trả lời tin của bot thì
  nó mới nhận được. Bot không ngồi hóng cả cuộc trò chuyện được.
- **Một tin tối đa 2000 ký tự.** Trả lời dài hơn thì bị cắt thành nhiều tin.
- **Không có offset.** `getUpdates` chỉ nhận `timeout`, nên muốn khỏi xử lý trùng thì phải
  tự nhớ `message_id`, không có cursor nào để dời.
- **Gửi rồi không sửa được.** Việc chạy lâu thì tiến độ phải báo bằng tin mới.
- **Không có reaction.** API không có endpoint nào để thả cảm xúc. Bù lại có trạng thái đang
  soạn tin (`sendChatAction`) và sticker.
- **Hạn mức gói miễn phí.** Gói Basic cho 3 bot mỗi tài khoản, 50 người mỗi bot, 3 nhóm chat
  (còn ghi beta), và 3.000 tin gửi đi mỗi tháng. Có gói Pro trả phí. Xem gói và hạn mức hiện
  hành tại <https://bot.zapps.me/>.

## Cài đặt

Hai đường, đường nào cũng cần [uv](https://docs.astral.sh/uv/). Cài dạng **plugin Claude
Code** (`/plugin marketplace add trongnguyenbinh/zalo-bot-mcp`, rồi `/plugin install
zalo@zalo-bot-mcp`), hoặc cài dạng **gói Python** rồi khai trong `.mcp.json`. Cài xong kiểu
nào cũng phải chạy Claude Code kèm flag channel, thiếu flag đó thì tin nhắn không bao giờ
vào tới session.

Hướng dẫn đầy đủ, từ lúc tạo bot cho tới tin trả lời đầu tiên, kèm toàn bộ skill `/zalo:*`
và CLI `zalo-bot-mcp-admin`, nằm ở **[docs/getting-started.vi.md](docs/getting-started.vi.md)**
(English: [docs/getting-started.md](docs/getting-started.md)).

### Nói rõ về cái flag channel

Flag đó tên là `--dangerously-load-development-channels`, và chữ ở giữa không phải để trang
trí. Flag `--channels` thường của Claude Code chỉ nhận plugin nằm trong allowlist nhúng sẵn
bên trong Claude Code, còn entry `server:` thì từ chối thẳng. zalo không có trong allowlist
đó, nên hiện tại flag development là đường duy nhất chạy được.

Nguyên văn Anthropic ghi flag này dành cho việc phát triển channel ở máy mình, không dành
cho channel tải từ internet về. Mà cái này thì đúng là tải từ internet về. Nói thẳng ra vẫn
hơn giấu: bạn đang mở cho một app nhắn tin một đường vào session đọc được file và chạy được
lệnh trên máy bạn, bằng một cửa hậu vốn làm ra cho người đang debug code của chính họ.

Cái đỡ lại là gate, là việc không tin nhắn Zalo nào sửa được danh sách ai được vào, và là
toàn bộ code của hai thứ đó nằm trong repo này. Đọc
[`src/zalo_bot_mcp/gate.py`](src/zalo_bot_mcp/gate.py) và [SECURITY.md](SECURITY.md) trước
khi quyết, đừng đọc sau.

## Chạy thử khi phát triển

```bash
git clone https://github.com/trongnguyenbinh/zalo-bot-mcp.git
cd zalo-bot-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Lúc chạy chỉ cần `httpx` và `mcp`, không thêm gì nữa. Các endpoint Zalo được gọi thẳng, nên
toàn bộ phần nói chuyện với API gói gọn trong một file, đọc một lượt là hiểu.

## Không liên kết với Zalo

Đây là dự án cá nhân, không chính thức. Không do Zalo hay VNG Corporation làm, không được họ
duyệt, không được họ hỗ trợ. "Zalo" là nhãn hiệu của họ, ở đây chỉ dùng để nói rõ phần mềm
này kết nối với dịch vụ nào.

Nó gọi [Zalo Bot API](https://bot.zapps.me/docs/) công khai, đúng như mọi bot bên thứ ba
khác. Bot của bạn, token của bạn, tài khoản của bạn, và trách nhiệm cũng của bạn: đọc điều
khoản của Zalo trước khi cắm nó vào việc gì quan trọng, và cứ xác định là API có thể đổi bất
cứ lúc nào.

Phát hành theo giấy phép MIT, tức là không bảo hành và không chịu trách nhiệm. Hỏng ở máy
bạn thì bạn tự lo.

## Giấy phép

MIT
