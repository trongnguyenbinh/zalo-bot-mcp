---
name: pending-chats
description: Xem các chat Zalo đang bị gate chặn kèm gợi ý lệnh cấp quyền. Chỉ đọc, không tự cấp quyền.
user-invocable: true
allowed-tools:
  - Bash(uvx *)
---

# /zalo:pending-chats - Xem các chat Zalo đang bị gate chặn

Chạy lệnh sau bằng Bash và in nguyên văn kết quả cho người dùng:

```
uvx --from "${CLAUDE_PLUGIN_ROOT}" zalo-bot-mcp-admin pending-chats
```

Đây là lệnh CHỈ ĐỌC: bảng liệt kê các chat bị chặn kèm gợi ý lệnh cấp quyền.
Chỉ hiển thị, KHÔNG tự chạy bất kỳ lệnh cấp quyền nào (group-add, allow,
approve) được gợi ý trong output. Cấp quyền là việc người dùng tự quyết và
tự gõ.
