<p align="center"><a href="CONTRIBUTING.md">English</a> | Tiếng Việt</p>

# Đóng góp

Cảm ơn bạn đã ghé. Đây là dự án cá nhân do một người làm, nên tài liệu này ít thủ tục và nói
kỹ đúng hai thứ thật sự quan trọng ở đây: cái gate chặn truy cập, và chuyện không để lộ token
bot.

## Trước khi bắt đầu

- Đóng góp được cấp phép theo [giấy phép MIT](LICENSE), giống phần còn lại của dự án. Không
  có CLA, không bắt ký sign-off.
- **Phát hiện lỗ hổng bảo mật? Đừng mở issue, đừng mở PR.** Hãy báo riêng tư, xem
  [SECURITY.md](SECURITY.md). Một PR công khai vá lỗi vượt gate cũng công bố luôn cách vượt
  gate, và mọi bản đang chạy sẽ phơi ra cho tới khi người ta kịp nâng cấp.
- **Đừng bao giờ dán token bot, chat ID thật, hay log thô chưa che** vào issue, PR, file test,
  hay ảnh chụp màn hình. Token bot có xuất hiện trong log của poller. Rà sạch trước khi đăng.
- Cư xử tử tế. Không có quy tắc ứng xử chính thức vì tôi không đủ người để vận hành một quy
  trình xử lý vi phạm. Ai làm chỗ này khó chịu thì tôi chặn, chính sách chỉ có vậy.
- Mới tới dự án? Đọc [docs/getting-started.vi.md](docs/getting-started.vi.md) trước
  (English: [docs/getting-started.md](docs/getting-started.md)). Nhanh hơn đọc mã nguồn.

## Dựng môi trường

Python 3.10 trở lên. Không cần database, không cần Docker, không phải khởi động dịch vụ nào.

```bash
git clone https://github.com/trongnguyenbinh/zalo-bot-mcp.git
cd zalo-bot-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Chạy kiểm tra:

```bash
ruff check .
pytest -q
```

Bộ test có 144 bài, chạy chưa tới một giây. Nó không cần mạng, không cần token, không cần tài
khoản Zalo: phần gọi API được test bằng đối tượng giả. Nếu test của bạn cần một bot thật mới
chạy được thì nó thuộc về phần ghi chú thủ công trong mô tả PR, không thuộc về `tests/`.

CI chạy đúng hai lệnh trên, với Python 3.10 và 3.14
(xem [`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Xanh ở máy bạn là xanh trên CI.

Một điểm cần biết: **`ruff format` chưa được bắt buộc.** Ba file hiện có chưa đúng định dạng,
và định dạng lại chúng bên trong một PR không liên quan sẽ biến một thay đổi năm dòng thành
một diff không ai review nổi. Hãy viết theo phong cách của đoạn mã xung quanh, chạy
`ruff check .`, và đừng đụng vào `ruff format` trừ khi PR của bạn đúng là về định dạng.

## Quy trình

1. **Việc gì không nhỏ thì mở issue trước.** Sửa lỗi, sửa chính tả, sửa tài liệu, thêm test:
   gửi PR thẳng. Thêm tool mới, thêm khoá cấu hình mới, đổi cách quyết định truy cập: nói với
   tôi trước đã. Tôi thà nói "không đi đường này" trong một comment còn hơn nói khi bạn đã bỏ
   cả cuối tuần vào một nhánh.
2. **Tách nhánh từ `main`.** Tên ngắn gọn dễ hiểu, kiểu `fix/dedupe-on-restart`. Bạn sẽ làm
   trên bản fork; nhánh `main` ở đây chặn đẩy thẳng và chặn force-push.
3. **Mỗi PR một thay đổi logic.** Hai chỗ sửa không liên quan là hai PR. Không phải làm khó,
   mà vì tôi review vào buổi tối, và một diff gọn là khác biệt giữa merge tối nay và merge sau
   ba tuần.
4. **Thay đổi phải đi kèm test.** Hành vi mới cần test. Sửa lỗi cần một test hỏng trước khi
   sửa và xanh sau khi sửa. Đây là quy tắc duy nhất tôi không nhân nhượng, vì bộ test là thứ
   duy nhất đứng giữa một lần refactor và một con bot lặng lẽ ngừng trả lời.
5. **Chạy `ruff check .` và `pytest -q` trước khi push.**
6. **Mở PR vào `main`** và mô tả rõ cái gì sẽ hỏng nếu thay đổi này sai. CI phải xanh thì tôi
   mới merge.

## Thay đổi chạm vào gate

`src/zalo_bot_mcp/gate.py` và `src/zalo_bot_mcp/access.py` quyết định tin nhắn của ai được
vào tới một phiên có quyền đọc file và chạy lệnh trên máy người khác. Sai ở đó không phải là
một cái bug, mà là một cánh cửa không khoá trên mọi bản cài.

Nếu PR của bạn động vào hai file đó, hoặc động vào định dạng file cấu hình truy cập:

- **Nói rõ ngay ở tiêu đề PR hoặc dòng đầu phần mô tả.** Tôi muốn biết trước khi bắt đầu đọc.
- **Kèm test cho nhánh TỪ CHỐI, không chỉ nhánh cho qua.** "Người được phép thì vào được" là
  nửa dễ. Nửa quan trọng là "người chưa được duyệt vẫn không vào được, sau thay đổi này".
- **Đừng nới rộng giá trị mặc định.** Nếu thay đổi làm một thứ vốn không với tới được trở nên
  với tới được, đó là quyết định thiết kế, và nó cần một issue trước, không phải một PR.
- **Chuẩn bị tinh thần review chậm.** Tôi sẽ đọc từng dòng và sẽ hỏi những câu nghe rất bắt
  bẻ. Không có gì cá nhân ở đây, đây là phần mã mà sai thì người trả giá là những người không
  có mặt trong cuộc trao đổi này.

Mô hình mối đe doạ, và ranh giới giữa "lỗ hổng" với "thiết kế đúng như vậy", được viết rõ
trong [SECURITY.md](SECURITY.md#what-counts). Đọc nó trước khi đề xuất thay đổi ở đây.

## Commit và tiêu đề PR

Commit dùng dạng `type: tóm tắt ngắn`, động từ ở thể mệnh lệnh:

```
fix: drop duplicate updates after a poller restart
docs: document the group mention requirement
```

Các type đang dùng: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`.

**Đây là quy ước, không phải một cái kiểm tra tự động.** Không có gì trong CI đọc commit
message của bạn, cũng không có công cụ nào tính số phiên bản từ đó, nên sẽ không có PR nào bị
từ chối vì một dòng tiêu đề. Làm theo vì nó giúp lịch sử commit dễ đọc.

**Tiêu đề PR thì khác, và có máy đọc thật.** Ghi chú phát hành trên GitHub được sinh ra từ
tiêu đề các PR đã merge, nên tiêu đề của bạn sẽ nằm nguyên văn trong ghi chú phát hành công
khai. Hãy viết nó như dòng changelog mà chính bạn muốn đọc: cái gì đã đổi, không phải bạn đã
làm gì.

## Phạm vi

Server này làm đúng một việc: nối Zalo Bot API vào một phiên MCP, có một cái gate đứng chắn
phía trước.

Ngoài phạm vi, và tôi sẽ đóng kèm một link về đây:

- **Nền tảng chat khác.** Telegram, Discord, Messenger. Đây là server cho Zalo. Chính lớp
  trừu tượng làm nó chạy được đa nền tảng là lớp trừu tượng khiến cái gate khó soát.
- **Chế độ webhook.** Long polling là thiết kế, không phải giới hạn cần đi vòng: không cần
  URL công khai, không cần tunnel, không cần mở cổng vào, chạy được trên laptop sau NAT.
- **Mọi thứ cho phép một tin nhắn Zalo đổi được cấu hình truy cập.** Không phải tính năng còn
  thiếu. Quyền được cấp từ terminal của người vận hành và không từ đâu khác, và đó là thứ chịu
  lực của cả thiết kế.
- **Hosting, đa người thuê, bảng điều khiển web, hệ thống plugin.**

Những hành vi do chính API của Zalo áp đặt (tin nhắn tối đa 2000 ký tự, nhóm chỉ nhận khi
được nhắc tên, không sửa được tin đã gửi, không có reaction, không có con trỏ offset) thì một
PR ở đây không sửa được. Danh sách hiện tại nằm trong README.

Đóng một PR không có gì cá nhân. Giấy phép MIT nghĩa là fork là một câu trả lời hoàn toàn hợp
lý, và nếu bạn dựng một bản fork thì tôi sẽ dẫn link tới nó từ README.

## Bạn có thể trông đợi gì ở tôi

Tôi duy trì dự án này một mình, xen giữa một công việc toàn thời gian. Nên nói thẳng:

- **Tôi đọc mọi issue và mọi PR.** Thường trong vòng một tuần. Đôi khi không kịp.
- **Tôi không hứa một hạn chót review.** Hứa 24 giờ rồi trễ thì tệ cho bạn hơn là không hứa
  gì, vì bạn sẽ ngồi bấm tải lại thay vì đi làm việc khác.
- **Báo cáo bảo mật được ưu tiên vượt hàng**, theo mốc thời gian trong
  [SECURITY.md](SECURITY.md) (phản hồi trong vòng 7 ngày).
- **PR nhỏ, gọn, có test được merge nhanh nhất**, nhanh hơn hẳn. Một bản sửa 20 dòng kèm test
  hồi quy là mười phút review. Một bản refactor 400 dòng không test có thể nằm đó một tháng
  rồi bị đóng, và cái đó phí thời gian của bạn nhiều hơn của tôi.
- **PR im hơn hai tuần thì cứ nhắc.** Tôi không phớt lờ bạn đâu, nó trôi khỏi trang thôi. Nhắc
  một câu là điều nên làm, không phải bất lịch sự.
- **Đây là bản 0.x.** Tên tool, hình dạng file cấu hình và cờ CLI đều có thể đổi giữa các bản
  minor. Nếu bạn xây thứ gì lên trên nó, hãy ghim phiên bản.

## Hỏi han

Hỏi gì, góp ý gì, hay thắc mắc kiểu "cái này chạy vậy là đúng hay sai" thì vào
[Discussions](https://github.com/trongnguyenbinh/zalo-bot-mcp/discussions). Issues để dành
cho thứ đang hỏng, hỏi ở đó thì cũng bị chuyển sang.

Xem [docs/getting-started.vi.md](docs/getting-started.vi.md) trước đã: trục trặc lúc cài gần
như lúc nào cũng là thiếu cờ channel, hoặc con bot chưa từng được nhắc tên trong nhóm.
