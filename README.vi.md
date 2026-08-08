<p align="center"><a href="README.md">English</a> | Tiếng Việt</p>

<h1 align="center">zalo-bot-mcp</h1>

<p align="center">
  Nói chuyện với AI agent của bạn từ một nhóm Zalo.
</p>

<p align="center">
  <a href="#giấy-phép"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/status-early%20development-orange.svg" alt="Đang phát triển">
</p>

Một MCP channel server cho [Zalo Bot API](https://bot.zapps.me/docs/). Tin nhắn
gửi tới bot Zalo của bạn sẽ xuất hiện trong phiên MCP client; phiên trả lời
lại qua một tool call.

> **Còn sớm.** Server chạy được và đã thử với bot thật, nhưng chưa lên PyPI,
> và MCP channel mà nó nhắm tới vẫn là tính năng thử nghiệm của Claude Code.

## Cách hoạt động

```
Nhóm Zalo  ──mention──▶  getUpdates  ──▶  gate  ──▶  phiên MCP
                                           │             │
                                     (không được phép)  tool reply
                                           │             │
                                        bỏ qua  ◀────────┘
                                                    sendMessage
```

Server poll Zalo bằng `getUpdates` nên không cần URL công khai, không cần
webhook, không cần tunnel. Chạy được trên laptop sau NAT.

Mọi tin nhắn đến đều phải qua gate trước khi bất kỳ thứ gì khác nhìn thấy nó.
Gate là cánh cửa duy nhất.

## Kiểm soát truy cập

**Tin nhắn riêng (DM)** theo một trong ba chính sách:

| Chính sách | Người lạ nhắn tin sẽ nhận được |
| --- | --- |
| `pairing` | Một mã ngắn hạn, bạn duyệt qua kênh khác |
| `allowlist` | Không gì cả. Tin bị bỏ qua trong im lặng |
| `disabled` | Không gì cả. Mọi DM đều bị bỏ qua |

**Nhóm** phải được cấp quyền theo ID. Kéo bot vào nhóm không có nghĩa nhóm đó
được bật. Bạn còn có thể giới hạn thành viên nào được phép gọi bot.

Hai quy tắc mà code cưỡng chế:

1. Không tin nhắn Zalo nào thay đổi được cấu hình truy cập. Một tin nhắn xin
   được thêm vào allowlist trông y hệt một cú tấn công chèn lệnh, nên mọi
   phê duyệt diễn ra bên ngoài kênh chat.
2. Server từ chối khởi động nếu allowlist chứa ký tự đại diện. Lúc thử nghiệm
   người ta hay mở rộng allowlist rồi quên thu hẹp lại.

Có mặt trong allowlist nghĩa là bạn nói chuyện được với bot. Nó không trao
quyền hành động lên bất cứ thứ gì.

## Ràng buộc từ nền tảng Zalo

Những điều dưới đây đến từ chính Zalo Bot API và định hình mọi bot Zalo. Zalo
sở hữu các quy tắc này và đổi chúng không cần báo trước, nên hãy coi
<https://bot.zapps.me/> là nguồn chuẩn, còn mục này chỉ là bản tóm tắt có thể
đã cũ:

- **Nhóm bị chặn theo mention.** Bot chỉ nhận tin nhắn nhóm khi được mention
  hoặc khi có người trả lời tin của nó. Bot không nghe lén cuộc trò chuyện
  được.
- **Tin nhắn tối đa 2000 ký tự.** Trả lời dài hơn sẽ bị tách thành nhiều tin.
- **Không có con trỏ offset.** `getUpdates` chỉ nhận `timeout`, nên việc khử
  trùng lặp dựa vào `message_id` chứ không phải dịch con trỏ.
- **Không sửa được tin đã gửi.** Không có chỉnh sửa tin nhắn, nên tiến độ của
  một việc dài sẽ đến dưới dạng các tin mới.
- **Không có reaction.** API không có endpoint reaction, bot không thả emoji
  xác nhận được. Nó gửi được trạng thái đang gõ (`sendChatAction`) và sticker.
- **Hạn mức gói miễn phí.** Gói Basic (miễn phí) của Zalo cho 3 bot mỗi tài
  khoản, 50 người dùng mỗi bot, 3 nhóm chat (đánh dấu beta), và 3.000 tin gửi
  đi mỗi tháng. Có gói Pro trả phí. Gói và hạn mức hiện hành:
  <https://bot.zapps.me/>.

## Cài đặt

Hai đường vào, đều cần [uv](https://docs.astral.sh/uv/): cài dạng **plugin
Claude Code** (`/plugin marketplace add trongnguyenbinh/zalo-bot-mcp`, rồi
`/plugin install zalo@zalo-bot-mcp`), hoặc cài dạng **gói Python** khai trong
`.mcp.json`. Đường nào thì sau đó cũng phải khởi động Claude Code với cờ
channel, không thì tin nhắn không bao giờ vào phiên.

Hướng dẫn đầy đủ, từ lúc tạo bot trên Zalo tới tin nhắn được trả lời đầu
tiên, cùng toàn bộ skill `/zalo:*` và CLI `zalo-bot-mcp-admin`, nằm ở
**[docs/getting-started.vi.md](docs/getting-started.vi.md)**
(English: [docs/getting-started.md](docs/getting-started.md)).

## Phát triển

```bash
git clone https://github.com/trongnguyenbinh/zalo-bot-mcp.git
cd zalo-bot-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Phụ thuộc lúc chạy là `httpx` và `mcp`. Không gì khác. Các endpoint của Zalo
được gọi trực tiếp, nên toàn bộ bề mặt API đọc được trong một file.

## Không liên kết với Zalo

Đây là dự án cá nhân, không chính thức. Nó không do Zalo, VNG Corporation hay
bất kỳ đơn vị liên kết nào của họ xây dựng, chứng thực, thẩm định hay hỗ trợ.
"Zalo" là nhãn hiệu của họ, ở đây chỉ dùng để nói phần mềm này nói chuyện với
dịch vụ nào.

Nó gọi [Zalo Bot API](https://bot.zapps.me/docs/) công khai theo đúng cách
mọi bot bên thứ ba khác gọi. Bot của bạn, token của bạn, tài khoản của bạn,
trách nhiệm của bạn: hãy đọc điều khoản của chính Zalo trước khi trỏ phần mềm
này vào bất cứ thứ gì quan trọng, và hãy lường trước việc API thay đổi không
báo trước.

Phần mềm phát hành theo giấy phép MIT, nghĩa là không kèm bất kỳ bảo hành nào
và không ai chịu trách nhiệm pháp lý. Nếu có gì đổ vỡ trong hệ thống của bạn,
đổ vỡ đó thuộc về bạn.

## Giấy phép

MIT
