<p align="center"><a href="CONTRIBUTING.md">English</a> | Tiếng Việt</p>

# Đóng góp

Dự án cá nhân, một người maintain. Ít thủ tục. Có hai thứ được quy định chặt: gate kiểm soát
truy cập, và việc không để lộ token bot.

## Trước khi bắt đầu

- Code đóng góp theo [giấy phép MIT](LICENSE), giống phần còn lại của dự án. Không yêu cầu
  CLA, không yêu cầu sign-off.
- **Tìm ra lỗ hổng bảo mật thì không mở issue, không mở PR.** Báo riêng theo
  [SECURITY.md](SECURITY.md). PR công khai vá lỗ vượt gate cũng công khai luôn cách vượt
  gate, trong khi các bản đang chạy chưa kịp update.
- **Không dán token bot, chat ID thật, hoặc log chưa che** vào issue, PR, file test hay ảnh
  chụp màn hình. Token có xuất hiện trong log của poller.
- Không có code of conduct, vì một người không xử lý nổi quy trình khiếu nại. Ai gây khó
  chịu thì bị chặn.
- Chưa quen dự án thì đọc [docs/getting-started.vi.md](docs/getting-started.vi.md) trước
  (English: [docs/getting-started.md](docs/getting-started.md)). Nhanh hơn đọc code.

## Môi trường dev

Cần Python 3.10 trở lên. Không database, không Docker, không service nào phải bật.

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

Bộ test chạy dưới một giây. Không cần mạng, không cần token, không cần tài khoản Zalo, vì
phần gọi API đã mock. Test nào bắt buộc phải có bot thật thì không để trong `tests/`, ghi
vào mô tả PR như một bước kiểm tay.

CI chạy đúng hai lệnh trên, trên Python 3.10 và 3.14. Xem
[`.github/workflows/ci.yml`](.github/workflows/ci.yml). Máy bạn xanh thì CI xanh.

**`ruff format` chưa bật.** Ba file hiện tại chưa đúng format. Format lại chúng trong một PR
không liên quan sẽ làm diff phình to, khó review. Viết theo style code xung quanh, chạy
`ruff check .`, và không động vào `ruff format` trừ khi PR đúng là để format.

## Quy trình

1. **Việc lớn thì mở issue trước.** Sửa bug, sửa chính tả, sửa docs, thêm test: gửi PR
   thẳng. Thêm tool, thêm khoá config, đổi cách quyết định ai được vào: trao đổi trước.
2. **Tách nhánh từ `main`.** Tên ngắn gọn, ví dụ `fix/dedupe-on-restart`. Bạn làm trên fork,
   vì `main` chặn push thẳng và chặn force-push.
3. **Một PR một thay đổi.** Hai chỗ sửa không liên quan thì tách hai PR. Diff gọn thì review
   nhanh, diff to thì chờ lâu.
4. **Thay đổi nào cũng kèm test.** Thêm hành vi mới thì thêm test. Sửa bug thì cần test hỏng
   trước khi sửa, xanh sau khi sửa. Đây là quy tắc không nhân nhượng: bộ test là thứ duy
   nhất phát hiện một lần refactor làm bot ngừng trả lời.
5. **Chạy `ruff check .` và `pytest -q` trước khi push.**
6. **Mở PR vào `main`**, ghi rõ thay đổi này sai thì cái gì hỏng. CI xanh mới merge.

## PR đụng vào gate

`src/zalo_bot_mcp/gate.py` và `src/zalo_bot_mcp/access.py` quyết định tin nhắn của ai được
vào một session đọc được file và chạy được lệnh trên máy người dùng. Sai ở đây ảnh hưởng mọi
bản đang cài.

PR đụng vào hai file đó, hoặc đụng vào cấu trúc file config truy cập, thì:

- **Ghi rõ ở tiêu đề PR hoặc dòng đầu mô tả.**
- **Test cả nhánh từ chối, không chỉ nhánh cho qua.** "Người được duyệt vào được" là phần
  dễ. Phần cần test là: sau thay đổi này, người chưa duyệt vẫn bị chặn.
- **Không nới mặc định.** Thay đổi làm một thứ vốn không với tới được thành với tới được là
  quyết định thiết kế, cần mở issue bàn trước.
- **Review sẽ lâu.** Đọc từng dòng và hỏi kỹ. Sai ở vùng này thì người chịu là người dùng.

Threat model, và ranh giới giữa lỗ hổng với thiết kế có chủ đích, ở
[SECURITY.md](SECURITY.md#what-counts). Đọc trước khi đề xuất sửa vùng này.

## Commit và tiêu đề PR

Commit theo dạng `type: tóm tắt ngắn`, động từ nguyên thể:

```
fix: drop duplicate updates after a poller restart
docs: document the group mention requirement
```

Các type đang dùng: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`.

**Đây là quy ước, không phải check tự động.** CI không đọc commit message, không tool nào
tính version từ đó. Không PR nào bị từ chối vì tiêu đề commit. Làm theo để lịch sử commit dễ
đọc.

**Tiêu đề PR thì khác, cái này máy đọc.** Release notes trên GitHub sinh từ tiêu đề các PR
đã merge, nên tiêu đề sẽ nằm nguyên trong release notes công khai. Viết như một dòng
changelog: nói cái gì đã đổi.

## Phạm vi

Server này làm một việc: nối Zalo Bot API vào một MCP session, có gate ở giữa.

Ngoài phạm vi, PR sẽ bị đóng kèm link về đây:

- **Nền tảng chat khác.** Telegram, Discord, Messenger. Đây là server cho Zalo. Lớp
  abstraction để chạy đa nền tảng cũng chính là thứ làm gate khó audit.
- **Chạy bằng webhook.** Long polling là chủ ý: không cần URL public, không cần tunnel,
  không mở cổng vào, chạy được sau NAT.
- **Cho phép tin nhắn Zalo sửa config truy cập.** Đây không phải tính năng còn thiếu. Quyền
  chỉ cấp từ terminal của người vận hành.
- **Hosting, multi-tenant, web dashboard, plugin system.**

Giới hạn do Zalo áp (tin tối đa 2000 ký tự, trong nhóm phải mention, gửi rồi không sửa được,
không có reaction, không có offset cursor) thì PR ở đây không sửa được. Danh sách ở README.

PR bị đóng không có ý gì cá nhân. Giấy phép MIT nên fork là lựa chọn hợp lý, và fork nào
dùng được thì dẫn link từ README sang.

## Bạn trông đợi gì được

Dự án này một người maintain, làm ngoài giờ công việc chính:

- **Issue và PR đều được đọc.** Thường trong một tuần, đôi khi lâu hơn.
- **Không hứa hạn chót review.** Hứa 24 giờ rồi trễ còn tệ hơn không hứa.
- **Báo lỗi bảo mật được ưu tiên trước**, theo mốc trong [SECURITY.md](SECURITY.md): phản
  hồi trong 7 ngày.
- **PR nhỏ, có test, tập trung thì merge nhanh nhất.** Sửa 20 dòng kèm test là mười phút
  review. Refactor 400 dòng không test có thể nằm cả tháng rồi bị đóng.
- **PR im quá hai tuần thì nhắc.** Nhắc là bình thường, không phiền.
- **Đây là bản 0.x.** Tên tool, cấu trúc file config, flag CLI đều có thể đổi giữa các bản
  minor. Xây gì lên trên thì pin version.

## Hỏi đáp

Câu hỏi, đề xuất, hoặc thắc mắc kiểu "cái này chạy vậy là đúng hay sai" thì vào
[Discussions](https://github.com/trongnguyenbinh/zalo-bot-mcp/discussions). Issues dành cho
thứ đang hỏng, hỏi ở đó sẽ bị chuyển sang.

Xem [docs/getting-started.vi.md](docs/getting-started.vi.md) trước: lỗi lúc cài gần như
luôn là thiếu flag channel, hoặc bot chưa từng được mention trong nhóm.
