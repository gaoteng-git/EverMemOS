# Claude Code Skills for EverMemOS

这个目录包含 EverMemOS 的 Claude Code skills，**大幅简化用户安装、配置和使用 EverMemOS 的门槛**。

## 💡 设计理念

**问题：** EverMemOS 需要技术背景才能安装和使用，限制了普通用户使用。

**解决：** 通过 Skills 实现自动化安装、配置、诊断和管理，让任何人都能在几分钟内开始使用。

👉 **详细说明：** [EVERMEMOS_SIMPLIFIED_ONBOARDING.md](../EVERMEMOS_SIMPLIFIED_ONBOARDING.md)

---

## 📦 包含的 Skills

### 1. evermemos-setup - 自动安装 🚀

**一键安装和配置 EverMemOS**

让 Claude Code 能够：
- ✅ 自动检测系统环境
- ✅ 安装所有依赖
- ✅ 生成配置文件
- ✅ 验证安装成功

**简化了什么：**
- ❌ Before: 手动安装 Python、uv、依赖，创建配置（30-60 分钟）
- ✅ After: 一句话 "安装 EverMemOS"（2-5 分钟）

**用法：**
```bash
/evermemos-setup [lite|standard|full]
```

---

### 2. evermemos-start - 服务管理 ⚙️

**启动、停止、重启、查看状态**

让 Claude Code 能够：
- ✅ 后台启动服务
- ✅ 优雅停止服务
- ✅ 查看运行状态
- ✅ 查看日志

**简化了什么：**
- ❌ Before: `uv run python src/run.py &` + 记 PID + 手动管理
- ✅ After: "Start EverMemOS"

**用法：**
```bash
/evermemos-start [start|stop|restart|status|logs]
```

---

### 3. evermemos-doctor - 健康检查 🩺

**自动诊断和修复问题**

让 Claude Code 能够：
- ✅ 检测系统环境
- ✅ 验证依赖和配置
- ✅ 分析日志错误
- ✅ 提供修复建议

**简化了什么：**
- ❌ Before: 手动看日志 → Google → 试错（10-30 分钟）
- ✅ After: "有什么问题吗？" → 自动诊断（1-2 分钟）

**用法：**
```bash
/evermemos-doctor
```

---

### 4. evermemos - 记忆功能 🧠

**使用 EverMemOS 的核心功能**

让 Claude Code 能够：
- 🔍 搜索过去的对话和上下文
- 💾 存储重要信息供将来参考
- 📜 回忆最近的对话历史
- 🧠 从以前的工作和决策中学习

**简化了什么：**
- ❌ Before: 学习 API → 写代码 → curl 命令
- ✅ After: "记住这个" / "我们之前讨论了什么？"

**用法：**
```bash
/evermemos search <query>
/evermemos store <content>
/evermemos recent [limit]
```

---

## 🚀 快速安装

### 方法 1: 安装所有 Skills（推荐）

```bash
# 安装所有 skills
cp -r claude-skills/evermemos* ~/.claude/skills/

# 验证安装
ls -la ~/.claude/skills/
```

### 方法 2: 选择性安装

```bash
# 只安装核心功能
cp -r claude-skills/evermemos ~/.claude/skills/

# 添加安装和管理工具
cp -r claude-skills/evermemos-setup ~/.claude/skills/
cp -r claude-skills/evermemos-start ~/.claude/skills/
cp -r claude-skills/evermemos-doctor ~/.claude/skills/
```

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
