<p align="center"><a href="CONTRIBUTING.md">English</a> | Tiếng Việt</p>

# Đóng góp

Dự án một người làm, nên ở đây ít thủ tục. Chỉ có hai thứ tôi nói kỹ: cái gate chặn truy
cập, và chuyện đừng để lộ token bot.

## Đọc trước khi bắt tay

- Code bạn gửi đi theo [giấy phép MIT](LICENSE) như phần còn lại của dự án. Không CLA, không
  bắt ký sign-off.
- **Tìm ra lỗ hổng bảo mật thì đừng mở issue, cũng đừng mở PR.** Báo riêng, cách làm ở
  [SECURITY.md](SECURITY.md). Một PR công khai vá lỗ vượt gate cũng là công khai luôn cách
  vượt gate, trong khi máy người dùng vẫn đang chạy bản cũ.
- **Đừng dán token bot, chat ID thật, hay log chưa che** vào issue, PR, file test hay ảnh
  chụp màn hình. Token có nằm trong log của poller. Soi lại trước khi đăng.
- Ăn nói tử tế với nhau. Tôi không viết code of conduct vì một mình tôi không xử lý nổi thủ
  tục khiếu nại. Ai làm chỗ này khó chịu thì tôi chặn, vậy thôi.
- Mới vào dự án thì đọc [docs/getting-started.vi.md](docs/getting-started.vi.md) trước
  (English: [docs/getting-started.md](docs/getting-started.md)), nhanh hơn đọc code.

## Dựng môi trường

Cần Python 3.10 trở lên. Không database, không Docker, không phải bật service nào.

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

144 test, chạy chưa tới một giây. Không cần mạng, không cần token, không cần tài khoản Zalo,
vì phần gọi API đã mock hết. Test nào bắt buộc phải có bot thật mới chạy được thì đừng để
trong `tests/`, ghi vào mô tả PR như một bước kiểm tay.

CI chạy đúng hai lệnh trên, trên Python 3.10 và 3.14, xem
[`.github/workflows/ci.yml`](.github/workflows/ci.yml). Máy bạn xanh thì CI cũng xanh.

Một lưu ý: **`ruff format` chưa bật.** Ba file hiện tại chưa đúng format. Format lại chúng
trong một PR không liên quan sẽ biến sửa năm dòng thành cái diff không ai soi nổi. Cứ viết
theo style của code xung quanh, chạy `ruff check .`, và đừng động vào `ruff format` trừ khi
PR của bạn đúng là để làm việc đó.

## Quy trình

1. **Việc không nhỏ thì mở issue hỏi trước.** Sửa bug, sửa chính tả, sửa docs, thêm test thì
   cứ gửi PR thẳng. Còn thêm tool mới, thêm khoá config, đổi cách quyết định ai được vào thì
   nói với tôi trước. Tôi nói "hướng này không đi" trong một comment vẫn hơn nói sau khi bạn
   đã đổ cả cuối tuần vào đó.
2. **Tách nhánh từ `main`.** Đặt tên gọn, kiểu `fix/dedupe-on-restart`. Bạn làm trên fork của
   mình, vì `main` ở đây chặn push thẳng và chặn force-push.
3. **Một PR một thay đổi.** Hai chỗ sửa không liên quan thì tách hai PR. Không phải tôi làm
   khó. Tôi review buổi tối, diff gọn thì tối nay merge, diff to thì có khi ba tuần nữa.
4. **Sửa gì cũng phải có test.** Thêm hành vi mới thì thêm test. Sửa bug thì cần một test
   hỏng trước khi sửa và xanh sau khi sửa. Điều này tôi không nhân nhượng, vì bộ test là thứ
   duy nhất chặn giữa một lần refactor và một con bot lặng lẽ ngừng trả lời.
5. **Chạy `ruff check .` với `pytest -q` trước khi push.**
6. **Mở PR vào `main`**, ghi rõ nếu thay đổi này sai thì cái gì hỏng. CI xanh tôi mới merge.

## PR đụng vào gate

`src/zalo_bot_mcp/gate.py` và `src/zalo_bot_mcp/access.py` quyết định tin nhắn của ai được
vào tới một session đọc được file và chạy được lệnh trên máy người ta. Sai ở đây không phải
một cái bug, mà là cửa không khoá trên mọi máy đang cài.

PR của bạn động vào hai file đó, hoặc động vào cấu trúc file config truy cập, thì:

- **Ghi rõ ngay ở tiêu đề PR hoặc dòng đầu mô tả.** Tôi cần biết trước khi bắt đầu đọc.
- **Test cả nhánh TỪ CHỐI, đừng chỉ test nhánh cho qua.** "Người được duyệt thì vào được" là
  nửa dễ. Nửa còn lại mới quan trọng: sau thay đổi này, người chưa duyệt vẫn phải bị chặn.
- **Đừng nới mặc định cho rộng ra.** Thay đổi làm một thứ vốn không với tới được thành với
  tới được thì đó là quyết định thiết kế, phải mở issue bàn trước chứ không gửi PR luôn.
- **Chuẩn bị tinh thần bị soi lâu.** Tôi sẽ đọc từng dòng và hỏi những câu nghe rất bắt bẻ.
  Không phải nhắm vào bạn. Chỗ này mà sai thì người lãnh đủ là người dùng, mà họ có ngồi đây
  đâu.

Threat model, và ranh giới giữa "lỗ hổng" với "thiết kế nó vậy", nằm trong
[SECURITY.md](SECURITY.md#what-counts). Đọc trước khi đề xuất sửa ở vùng này.

## Commit và tiêu đề PR

Commit viết dạng `type: tóm tắt ngắn`, động từ để nguyên thể:

```
fix: drop duplicate updates after a poller restart
docs: document the group mention requirement
```

Các type đang dùng: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`.

**Đây là quy ước, không phải check tự động.** CI không đọc commit message, cũng không tool
nào tính version từ đó. Sẽ không có PR nào bị từ chối vì một dòng tiêu đề. Làm theo cho lịch
sử commit dễ đọc thôi.

**Tiêu đề PR thì khác, cái đó máy đọc thật.** Release notes trên GitHub sinh ra từ tiêu đề
các PR đã merge, nên tiêu đề bạn viết sẽ nằm nguyên si trong release notes công khai. Viết
như một dòng changelog: nói cái gì đã đổi, đừng kể bạn đã làm gì.

## Phạm vi

Server này làm đúng một việc: nối Zalo Bot API vào một MCP session, có cái gate đứng chắn ở
giữa.

Mấy thứ nằm ngoài phạm vi, gửi PR tôi sẽ đóng kèm link về đây:

- **Nền tảng chat khác.** Telegram, Discord, Messenger. Đây là server cho Zalo. Muốn chạy đa
  nền tảng thì phải thêm một lớp abstraction, mà chính lớp đó làm cái gate khó soát.
- **Chạy bằng webhook.** Long polling là chủ ý, không phải giới hạn cần đi vòng: không cần
  URL public, không cần tunnel, không mở cổng vào, cắm laptop sau NAT là chạy.
- **Bất cứ thứ gì cho phép tin nhắn Zalo sửa được config truy cập.** Đây không phải tính năng
  còn thiếu. Quyền chỉ cấp từ terminal của người vận hành, không từ đâu khác, cả thiết kế
  chịu lực ở chỗ đó.
- **Hosting, multi-tenant, web dashboard, plugin system.**

Mấy giới hạn do chính Zalo áp (tin tối đa 2000 ký tự, trong nhóm phải mention mới nghe, gửi
rồi không sửa được, không có reaction, không có offset cursor) thì PR ở đây không sửa nổi.
Danh sách đang có trong README.

Tôi đóng PR không có ý gì cá nhân đâu. Giấy phép MIT nên fork là một lựa chọn hoàn toàn hợp
lý, và bạn dựng fork thì tôi dẫn link từ README sang.

## Bạn trông đợi gì được ở tôi

Tôi làm dự án này một mình, xen giữa công việc chính. Nên nói thẳng:

- **Issue nào PR nào tôi cũng đọc.** Thường trong một tuần. Đôi khi trễ.
- **Tôi không hứa hạn chót review.** Hứa 24 giờ rồi trễ còn tệ hơn không hứa, vì bạn cứ ngồi
  bấm tải lại thay vì đi làm việc khác.
- **Báo lỗi bảo mật được ưu tiên trước hết**, theo mốc trong [SECURITY.md](SECURITY.md), phản
  hồi trong 7 ngày.
- **PR nhỏ gọn có test thì merge nhanh nhất**, nhanh hơn hẳn. Sửa 20 dòng kèm test là mười
  phút review xong. Refactor 400 dòng không test có thể nằm đó cả tháng rồi bị đóng, mà cái
  đó phí thời gian của bạn hơn của tôi.
- **PR im hơn hai tuần thì cứ nhắc tôi.** Không phải tôi lơ bạn, nó trôi khỏi trang thôi.
  Nhắc là chuyện nên làm, không có gì bất lịch sự.
- **Đây mới là bản 0.x.** Tên tool, cấu trúc file config, flag CLI đều có thể đổi giữa các
  bản minor. Xây gì lên trên thì nhớ pin version.

## Hỏi han

Hỏi gì, góp ý gì, hay thắc mắc kiểu "cái này chạy vậy là đúng hay sai" thì vào
[Discussions](https://github.com/trongnguyenbinh/zalo-bot-mcp/discussions). Issues để dành
cho thứ đang hỏng, hỏi ở đó rồi cũng bị chuyển sang.

Xem [docs/getting-started.vi.md](docs/getting-started.vi.md) trước đã: trục trặc lúc cài gần
như lúc nào cũng là thiếu flag channel, hoặc con bot chưa từng được mention trong nhóm.
