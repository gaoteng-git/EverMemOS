# Claude Code Skills for EverMemOS

这个目录包含 EverMemOS 的 Claude Code skills，让 Claude Code 拥有持久化记忆能力。

## 📦 包含的 Skills

### evermemos - EverMemOS Memory Integration

让 Claude Code 能够：
- 🔍 搜索过去的对话和上下文
- 💾 存储重要信息供将来参考
- 📜 回忆最近的对话历史
- 🧠 从以前的工作和决策中学习

## 🚀 快速安装

```bash
# 安装 evermemos skill 到个人目录
cp -r claude-skills/evermemos ~/.claude/skills/

# 验证安装
ls -la ~/.claude/skills/evermemos/
```

详细说明请查看：`evermemos/INSTALL.md`

## 📁 目录结构

```
claude-skills/
├── README.md              # 本文件
└── evermemos/             # EverMemOS memory skill
    ├── INSTALL.md         # 安装指南
    ├── SKILL.md           # Skill 定义
    ├── examples.md        # 详细使用示例
    └── scripts/
        └── evermemos_client.py  # Python API 客户端
```

## 📖 完整文档

- **快速开始**: `evermemos/INSTALL.md`
- **详细指南**: `../CLAUDE_CODE_SKILL_GUIDE.md`（项目根目录）
- **使用示例**: `evermemos/examples.md`

## 🎯 Skills vs 项目的 .claude/ 目录

| 目录 | 用途 | Git 管理 |
|------|------|----------|
| `claude-skills/` | 可分发的 skill 源文件 | ✅ 版本控制 |
| `.claude/` | 项目本地配置和状态 | ❌ 已忽略 |
| `~/.claude/skills/` | 用户实际使用的 skills | ❌ 本地 |

**工作流：**
1. 修改 `claude-skills/evermemos/` 中的源文件
2. Commit 到 Git 版本控制
3. 用户从这里安装到 `~/.claude/skills/`

## ⚙️ 配置

Skills 使用环境变量配置（可选）：

```bash
export EVERMEMOS_BASE_URL="http://localhost:1995"
export EVERMEMOS_USER_ID="your_username"
export EVERMEMOS_GROUP_ID="your_project_name"
```

## 🔄 更新 Skills

当 skills 更新时，重新执行安装命令：

```bash
cp -r claude-skills/evermemos ~/.claude/skills/
```

## 📋 前置条件

1. **Claude Code** 已安装
2. **Python 3.7+** 已安装
3. **EverMemOS 后端** 运行中

## 💡 使用示例

```
用户: "我们之前讨论的那个 ES 同步 bug 是什么？"

Claude: [自动使用 /evermemos search]
找到了！2026-02-03 发现 elasticsearch 的 async_streaming_bulk
有一个 bug，会在 bulk 操作完成后挂起...
```

## 📞 支持

遇到问题请查看：
1. `evermemos/INSTALL.md` - 安装和故障排除
2. `CLAUDE_CODE_SKILL_GUIDE.md` - 完整集成指南
3. `evermemos/examples.md` - 使用示例

## 📄 License

MIT License - 与 EverMemOS 项目相同
