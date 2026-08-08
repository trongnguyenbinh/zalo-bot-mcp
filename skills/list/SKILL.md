---
name: list
description: Xem trạng thái access control kênh Zalo, gồm dmPolicy, allowlist, groups, mã pairing đang chờ. Chỉ đọc.
user-invocable: true
allowed-tools:
  - Bash(uvx *)
---

# /zalo:list - Xem trạng thái access control

Chạy bằng Bash và in nguyên văn kết quả:

```
uvx --from "${CLAUDE_PLUGIN_ROOT}" zalo-bot-mcp-admin list
```

Hiện dmPolicy, allowFrom, các group, và mã pairing đang chờ. Đây là lệnh
CHỈ ĐỌC: không được tự chạy bất kỳ lệnh cấp quyền nào (approve, allow,
group-add) dựa trên output. Cấp quyền là việc người dùng tự quyết và tự gõ.
