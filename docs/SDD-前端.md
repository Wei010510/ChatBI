# ChatBI 平台 · SDD 前端技术方案

> 版本 v3.1（2026-11 视觉改版：统一设计令牌 / 侧栏重构 / 结果卡与图表主题化）｜ 关联 `docs/PRD.md` v0.6 ｜ 关联 `docs/SDD-总览.md` §2、§9 ｜ 关联 `docs/SDD-算法应用.md` v3.0
> **视觉与交互细则（令牌、尺寸、组件状态、动效、图表样式）以 [`docs/前端页面交互.md`](./前端页面交互.md) 为准**；本文只保留页面职责、数据流与实现原则。
> **接口契约以后端文档（`docs/SDD-后端.md` §2）为准。** 若与算法/后端冲突，按「算法 → 后端 → 前端 → PRD → Spec」顺序对齐，不得反向修改后端。
> 本文件只写「页面怎么落地、交互怎么实现、数据怎么渲染」。前端**不直连算法、不直连数据库**，只和后端 API 通信；不感知 S1~S8 的内部过程。

---

## 1. 技术栈与选型理由

| 项 | 选型 | 理由 |
| :--- | :--- | :--- |
| 框架 | React 18 + TypeScript | 对话流本质是消息数组渲染；TS 保证与 `ChainResult` 字段对齐 |
| 构建 | Vite | 冷启动快，Compose 镜像构建简单 |
| 组件库 | Ant Design 5 | 输入框、列表、Modal、Popconfirm、Empty、Result、Alert 现成 |
| 图表 | ECharts 5（按需引入 bar / line） | 后端给 `result.chart`，前端只做适配层 |
| 状态 | Zustand | 全局只有「当前会话 + 报表列表」两块状态 |
| 请求 | fetch 封装（`api/client.ts`） | 统一错误码、超时、`AbortController` |
| 样式 | 全局 CSS 设计令牌（`:root` 变量，单文件 `styles/index.css`）+ AntD `ConfigProvider` 主题 | 一套令牌贯穿全部页面；视觉改版只改令牌与类名，不动业务逻辑。不使用 CSS Modules |

---

## 2. 页面与信息架构

```
/                    对话页（默认）
  ├─ 左侧栏：历史会话列表 + 报表入口 + 新对话按钮
  └─ 主区：消息流 + 底部输入框
/reports             已存报表列表
/reports/:id         报表查看页（直接出表 / 图 / 解读）
```

| 页面 | 进入方式 | 返回方式 |
| :--- | :--- | :--- |
| 对话页 | 打开站点默认落地；点「新对话」清空当前会话 | — |
| 报表列表 | 左侧栏「报表」 | 点左侧栏「对话」 |
| 报表查看 | 报表列表点某一行 | 面包屑「报表」返回列表 |

左侧栏常驻（280px，可折叠为 64px 图标栏），三个页面共用 `AppLayout`；窄屏（≤900px）只收窄侧栏与快捷卡，不做完整移动端适配（本版非目标）。

### 2.1 会话的生命周期

- **一个会话就是一个持续上下文**：同一会话内可以无限追问，每次提问都带同一个 `session_id`，算法侧按最近 6 轮历史接续。
- **刷新/重开浏览器不丢**：当前 `session_id` 写入 `localStorage`（key `current_session_id`），对话页挂载时若有值则自动拉取该会话消息。
- **只有两种情况结束会话**：① 点「新对话」（清空当前会话指针，下一次提问新建）；② 在左侧栏手动删除某条会话（连带删除该会话全部消息，正在查看的被删则回到空对话页）。
- **清空全部会话**：左侧栏「历史会话」右侧提供一键清空入口（二次确认），调 `DELETE /api/sessions`，成功后回到空对话页并清空本地会话指针。
- **点左侧历史会话**＝切换当前会话并加载其消息，不会新建会话。
- **切换反馈**：点击即刻高亮目标会话并显示骨架屏（`sessionLoading`），不做「静默等接口」；连续快速切换时按请求序号丢弃过期响应，避免慢请求覆盖新会话。
- **远程库感知延迟**：消息与列表接口的耗时主要来自数据库往返（实测暖连接 0.6~2s），前端不阻塞输入，加载态与列表刷新并行进行。

---

## 3. 组件结构

```
App
└─ AppLayout（左侧栏 + 主区 Outlet）
   ├─ Sidebar
   │  ├─ BrandBar        （渐变品牌徽标 + 折叠按钮）
   │  ├─ NewChatButton
   │  ├─ SessionSearch   （按标题本地过滤）
   │  ├─ NavPills        （对话 / 报表）
   │  ├─ SessionList     （F7 对话记录；hover 出删除，顶部「清空」）
   │  └─ SidebarFoot     （数据仓库状态 + 智能悬浮标开关 + 固定用户位）
   ├─ SmartCursor        （可选全局圆形悬浮标 + 浅色跟随辉光）
   ├─ ChatPage
   │  ├─ ChatHeader      （标题 + 「数据仓库在线」状态）
   │  ├─ WelcomeState    （空会话：欢迎语 + 快捷提问卡）
   │  ├─ MessageList
   │  │  ├─ MessageMeta  （我 / ChatBI + 时间）
   │  │  ├─ UserBubble
   │  │  ├─ ResultCard   （action=answer：表 + 图 + 解读 / 空态）
   │  │  ├─ ClarifyCard  （action=clarify）
   │  │  ├─ RejectCard   （action=reject）
   │  │  └─ ErrorBubble  （HTTP 层失败 + 重试）
   │  ├─ LoadingBubble   （思考中 + 取消）
   │  └─ ChatInput
   ├─ ReportsPage
   │  └─ ReportTable     （F6：列表 / 打开 / 改名 / 删除）
   └─ ReportViewPage
      └─ ResultBody      （表 + 图 + 解读，无提问动作）
```

`ResultCard`（对话内）与 `ReportViewPage`（报表查看页）共用 `ResultBody`（表 + `ChartView` + 解读行），差异只在 `ResultCard` 多一个「存为报表」按钮和结果头（行数 / 图表类型 chip）。

### 3.1 视觉规范（设计令牌）

颜色 / 圆角 / 阴影 / 字体只在 `styles/index.css` 的 `:root` 定义一次，组件内不写死色值；AntD 组件通过 `App.tsx` 的 `ConfigProvider` 对齐同一套令牌。完整令牌表、尺寸、状态与动效清单见 [`docs/前端页面交互.md`](./前端页面交互.md) §1~§6，本节只保留原则。

| 令牌 | 值 | 用途 |
| :--- | :--- | :--- |
| `--ink` / `--ink-2` / `--text` / `--muted` / `--faint` | `#0f172a` / `#1e293b` / `#334155` / `#64748b` / `#94a3b8` | 文字层级：标题 → 正文 → 辅助 → 占位 |
| `--accent` / `--accent-strong` / `--accent-weak` | `#0891b2` / `#0e7490` / `#ecfeff` | 主强调色（青），对应 AntD `colorPrimary` |
| `--indigo` | `#4f46e5` | 渐变副色（品牌徽标、快捷卡悬停） |
| `--ok` / `--warn` / `--danger` | `#059669` / `#d97706` / `#e11d48` | 成功 / 提示 / 错误，`--danger` 对应 `colorError` |
| `--line` / `--line-soft` | `#e2e8f0` / `#f1f5f9` | 描边 / 弱分隔 |
| `--radius-sm` / `--radius` / `--radius-lg` | 8 / 12 / 16 px | 按钮 / 卡片 / 大卡片 |
| `--shadow-xs` ~ `--shadow-lg` | 四级阴影 | 卡片、悬停、弹层 |
| `--font-sans` / `--font-mono` | Plus Jakarta Sans（中文回退 PingFang / 微软雅黑）/ JetBrains Mono | 正文 / 数字与代码 |

布局与观感约定：

- 侧栏 280px（折叠 64px），主区自适应；对话内容最大宽度 860px 居中，报表页 960px。
- 页面底色白 + 36px 细网格（双层 `linear-gradient`）；卡片白底 + `--line` 描边 + `--shadow-sm`，不用重投影。
- 角色区分：用户消息深色气泡（`--ink` 底、右下 4px 小圆角），助手消息白色卡片（左上 4px 小圆角），带「我 / ChatBI + 时间」meta 行。
- 可点击元素统一 `cursor: pointer`（含无 `href` 的 `<a>`），禁用态 `cursor: not-allowed`。
- 侧栏数仓状态下方提供「智能悬浮标」开关，默认关闭并以 `localStorage['smart_cursor_enabled']` 持久化；开启后以 `SmartCursor` 渲染不拦截事件的圆环、中心点与浅青色辉光。仅精细指针设备启用跟随，指针移动通过 `requestAnimationFrame` 写 `transform`，不触发 React 高频重渲染。
- 微动效只用于反馈，不做页面级转场：
  - 卡片入场统一「从下往上浮入」：`translateY(28px) → 0` + 透明度 0 → 1 + 轻微放大 0.985 → 1，用带轻微回弹的缓动（`--ease-spring`）。
  - 快捷提问卡 4 张错峰 70ms 依次入场；用户气泡、助手结果卡、等待卡各自挂载时入场一次。
  - 空会话欢迎徽标：渐变描边（青→靛）圆角方 + 白色内衬 + 青色火花描线图标，3.4s 上下浮动 6px。
  - 入场动画用 `animation-fill-mode: backwards`，结束后不占用 `transform`，保证 hover 上浮/按下缩放不被覆盖。
  - 交互反馈：会话项 hover 右移 2px + 图标变色、选中项左侧 3px 青色竖条；输入框聚焦上浮 1px + 4px 青色光晕；按钮 hover 上浮、按下 `scale(.94~.98)`。
  - 等待态：渐变图标脉冲 + 流光进度条 + 「约需 40~90 秒」等宽提示，保留取消。
  - 无障碍：仅在 `:focus-visible` 时出键盘焦点环；`prefers-reduced-motion: reduce` 时关闭所有动画与过渡。


---

## 4. 各功能的前端实现

### 4.1 对话问数（F1）

| 环节 | 实现 |
| :--- | :--- |
| 输入框 | `ChatInput`：原生 `textarea`（单行起步，超出在框内滚动），回车发送、Shift+回车换行；空内容时发送按钮置灰；请求中按钮变为「停止」，点击等同取消 |
| 智能联想 | 已有对话且未在等待时，输入框上方出现 chip 行（复用 4 个快捷问题），点击只填入输入框 |
| 提问参考 | `QuickAskBar` 前端内置 4 张快捷卡（渠道表现 / 转化效率 / 商品退货 / 用户结构，卡内是标签 + 完整问题），点击只把问题**填入输入框**，不自动发送；4 张卡错峰上浮入场 |
| 过程提示 | 发送后本地插入 `UserBubble` + 等待卡（渐变图标脉冲 + 流光进度条 + 「约需 40~90 秒」提示 + 取消），直到响应返回 |
| 超时 | `ask` / `clarify` 前端超时 300s（模型单次 40~90s）；超时提示「请求超时」并保留用户气泡，**不当作取消**、不静默移除消息 |
| 取消 | `loading` 气泡内「取消」按钮，调用 `AbortController.abort()`，移除占位气泡 |
| 结果渲染 | `action=answer` → `ResultCard`：`ResultBody` 顺序为表格 → 图表 → 一句解读 |
| 表格 | AntD `Table`，列由 `result.columns` 动态生成，`size="small"`，超过 10 行滚动；`type=number` 的单元格千分位、最多两位小数，键名或标题含 `rate` / `ratio` / `share` / `growth` / `yoy` / `增长` / `占比` / `同比` 且 `|v| ≤ 1` 时按百分比（两位小数）渲染，空值显示 `—` |
| 图表 | `ChartView` 按 `result.chart.type` 选 `bar` / `line`；`chart=null` 时不渲染 |
| 解读 | 单行文本，最大宽度限制，`narrative` 为空则不渲染该行 |
| 多轮追问 | 同一 `session_id` 继续发问；前端不重置消息数组，旧卡片保留 |
| 空数据 | `action=answer` 且 `result.rows.length === 0` → 表头照常渲染 + `Alert`「该条件下暂无数据」+ 提示调整时间窗或维度 |
| 截断 | `result.truncated=true` → 表格上方 `Alert`「结果超过 1000 行，仅展示前 1000 行」 |
| 失败 | HTTP 层失败 → `ErrorBubble` + 「重试」；`action=reject` 且 `retryable=true` → 走 4.3 的可重试态 |

> 本版结果卡片中**不展示 SQL、不展示查询条件复述**（F9 暂缓）。前端不感知是否命中语义缓存。

### 4.2 澄清（F2）

| 环节 | 实现 |
| :--- | :--- |
| 展示 | `action=clarify` → `ClarifyCard`：`clarify.question` + 选项按钮组（`options`）+ 可选自由输入（`allow_free_text`） |
| 交互 | 点任一选项 → 立即调用 `/api/chat/clarify`，`answer={value}`；自由输入则 `answer={text}` |
| 状态 | 提交后卡片置为「已选择 XXX」只读态，等待结果 |
| 约束 | 卡片内不渲染任何数字（前端只读 `clarify` 字段，`result` 必为 null） |
| 放弃 | 用户直接在输入框发新问题即可，前端不发放弃请求，后端清空 `clarify_state` |
| 过期 | `409 CLARIFY_EXPIRED` → 卡片置灰 + 提示「该问题已失效，请重新提问」 |

### 4.3 拒答（F3）

| 环节 | 实现 |
| :--- | :--- |
| 展示 | `action=reject` → `RejectCard`：`reject.message` + 替代问法按钮（`suggestions`） |
| 交互 | 点替代问法 → 作为新问题调用 `/api/chat/ask` |
| 技术失败态 | `reason_code` ∈ `intent_parse_failed` / `sql_generate_failed` / `sql_execute_failed` / `timeout` 时，标题改为「这次没查出来」，并显示「重试」按钮（`retryable=true`） |
| 业务拒答态 | `out_of_scope` / `detail_export` / `no_data` / `write_op` 时不显示重试，只给替代问法 |
| 约束 | 不渲染「估算」「约」类数字；只展示 `message` 与 `suggestions` |

### 4.4 对比分析（F4）

前端不做特殊处理：对比结果同样走 `ResultCard`。对比类固定为 `period` + 指标列的**两行**结果，`chart` 为 `bar`、`x_field="period"`；后端若已算好增长额 / 增长率，按普通列透传（只在第 1 行有值，第 2 行为空），前端照常渲染、不计算、不猜列。**对比逻辑全在算法与后端，前端只按固定 key 渲染。**

### 4.5 一键存成报表（F5）

| 环节 | 实现 |
| :--- | :--- |
| 入口 | `ResultCard` 右上角「存为报表」按钮；`rows` 为空时禁用（后端也会拒） |
| 弹窗 | `SaveReportModal`：报表名（默认取该卡片的用户问题）+ 图表类型单选（柱 / 线，默认跟当前 `chart.type`） |
| 提交 | `POST /api/reports`，成功后 `message.success` 并关闭弹窗 |
| 同名 | 后端 `409 REPORT_NAME_EXISTS` → 弹窗内提示「已存在同名报表」，给「改名」与「覆盖」两个按钮，覆盖时带 `overwrite: true` 重发 |
| 取消 | 关闭弹窗，不发请求 |
| 失败 | 弹窗内红字提示，输入内容保留，可重试 |

### 4.6 已存报表管理（F6）

| 环节 | 实现 |
| :--- | :--- |
| 列表 | `ReportTable`：名称 / 来源问题 / 保存时间（`created_at`），按 `created_at` 倒序；分页 20 条 |
| 空态 | AntD `Empty` + 「去提问」按钮跳回对话页 |
| 打开 | 行点击 → `/reports/:id`；直接渲染后端返回的快照，**不重新提问、不重新查询** |
| 改名 | 行内编辑（铅笔 → Input → Enter 确认 / Esc 取消），调 `PATCH /api/reports/{id}` |
| 删除 | 行尾删除图标 → `Popconfirm`「删除后不可恢复」→ `DELETE /api/reports/{id}` |
| 失败 | `message.error`，列表回滚原状（先乐观更新再失败回滚） |

### 4.7 对话记录（F7）

| 环节 | 实现 |
| :--- | :--- |
| 列表 | 左侧栏 `SessionList`，按 `updated_at` 倒序，显示会话标题（首条问题摘要）；`sessionId` 变化后自动刷新列表 |
| 搜索 | 侧栏搜索框按标题做**本地**过滤，不发请求；无匹配显示「暂无匹配对话」 |
| 回看 | 点击 → `sessionStorage['open_session_id']` 传参 → `GET /api/sessions/{id}/messages` → 按原顺序渲染消息（结果卡保持当时内容） |
| 新对话 | 点击 → 清空 `chatStore` 与本地会话指针，`session_id` 置空，首次发送时后端创建 |
| 删除单条 | hover 会话项右侧出现删除图标 → `Popconfirm` → `DELETE /api/sessions/{id}`；删的是当前会话则回到空对话页 |
| 清空全部 | 「历史会话」右侧「清空」→ `Popconfirm` → `DELETE /api/sessions`，成功后回到空对话页 |
| 持久化 | 当前 `session_id` 存 `localStorage['current_session_id']`，刷新后自动恢复（详见 §2.1） |
| 本版边界 | 不做跨端同步、不做跨用户共享 |

### 4.8 一键部署（F8）

前端只负责构建产物被 nginx 托管，无运行时配置：`npm run build` 产出 `dist/`，由 `web` 容器提供；`/api` 由 nginx 反向代理到 `api` 容器。部署说明见 `docs/SDD-后端.md` §6。

---

## 5. 接口契约（前端调用视图）

> 完整定义与错误码见 `docs/SDD-后端.md` §2。此处只写前端关心的入参与渲染依赖字段。

统一响应包：

```ts
type ApiResponse<T> = {
  code: number;          // 0 = 成功
  message: string;
  data: T;
  trace_id: string;
};
```

### 5.1 提问

```
POST /api/chat/ask
body: { session_id?: string; question: string }
```

`data` 关键字段：

> `ChatAnswer` = 后端在 `ChainResult` 外层补 `message_id` / `session_id` 后的结果（`ChainResult` 定义见 `docs/SDD-算法应用.md` §7.4）。前端不新增字段，只按 `action` 分支渲染。

```ts
type ChatAnswer = {
  message_id: string;
  session_id: string;
  action: 'answer' | 'clarify' | 'reject';

  result: {
    columns: { key: string; title: string; type: 'number' | 'string' | 'date' }[];
    rows: Record<string, string | number | null>[];
    chart: {
      type: 'bar' | 'line';
      x_field: string | null;
      series: { key: string; name: string }[];
    } | null;
    narrative: string;
    truncated: boolean;
  } | null;

  clarify: {
    clarify_id: string;
    question: string;
    options: { label: string; value: string }[];
    allow_free_text: boolean;
    missing: ('metric' | 'time_range' | 'baseline' | 'caliber')[];
  } | null;

  reject: {
    reason_code:
      | 'out_of_scope'
      | 'detail_export'
      | 'no_data'
      | 'write_op'
      | 'intent_parse_failed'
      | 'sql_generate_failed'
      | 'sql_execute_failed'
      | 'timeout';
    message: string;
    suggestions: { label: string; question: string }[];
    retryable: boolean;
  } | null;
};
```

前端渲染规则：`action` 三选一，**互斥**——`answer` 时 `result` 非空；`clarify` / `reject` 时 `result` 必为 null。空结果是 `answer` 的一种形态（`rows.length === 0`），不是独立分支。

### 5.2 澄清确认

```
POST /api/chat/clarify
body: { session_id: string; clarify_id: string; answer: { value?: string; text?: string } }
```

返回同 `ChatAnswer`（通常为 `action=answer`）。

### 5.3 会话

```
GET    /api/sessions?limit=30        → { items: { id, title, updated_at }[] }
GET    /api/sessions/{id}/messages   → { items: ChatMessage[] }
DELETE /api/sessions/{id}            → { deleted: true }（会话不存在 → 404 SESSION_NOT_FOUND）
DELETE /api/sessions                 → { deleted_count: number }（清空当前用户全部会话）
```

```ts
type UserMessage = {
  message_id: string;
  session_id: string;
  role: 'user';
  content: string;
  created_at: string;
};

type AssistantMessage = ChatAnswer & {
  role: 'assistant';
  content: string;
  created_at: string;
};

type ChatMessage = UserMessage | AssistantMessage;
```

> 会话由首次 `/api/chat/ask` 自动创建，前端不单独调新建会话接口。

### 5.4 报表

```ts
type ResultBody = NonNullable<ChatAnswer['result']>;

type ReportListItem = {
  id: string; name: string; question: string;
  created_at: string; updated_at: string;
};

type ReportDetail = {
  id: string; name: string; question: string;
  result: ResultBody;   // 保存时的快照：columns / rows / chart / narrative / truncated
  created_at: string;
};
```

```
POST   /api/reports        body: { message_id, name, chart_type, overwrite?: boolean }
GET    /api/reports?page=1&size=20  → { items: ReportListItem[], total: number }
GET    /api/reports/{id}   → ReportDetail
PATCH  /api/reports/{id}   body: { name }
DELETE /api/reports/{id}
```

错误码与前端展示的映射：

| HTTP | code | 前端表现 |
| :--- | :--- | :--- |
| 400 | `INVALID_ARGUMENT` | `message.error`，提示参数不合法 |
| 404 | `SESSION_NOT_FOUND` | 回看会话失败，提示并回到新对话 |
| 409 | `REPORT_NAME_EXISTS` | 弹窗内提示同名，给改名 / 覆盖 |
| 409 | `CLARIFY_EXPIRED` | 澄清卡置灰，提示重新提问 |
| 404 | `REPORT_NOT_FOUND` | `Result` 页提示并给返回列表按钮 |
| 422 | `MESSAGE_NOT_QUERYABLE` | 「这次结果不能存为报表」提示 |
| 500 | `INTERNAL` | `message.error` + 可重试 |

---

## 6. 图表怎么出

**结论：图表类型和坐标轴由后端 `chart` 决定，前端只做映射，不判断。**

```ts
// components/ChartView.tsx
const option = {
  xAxis: {
    type: 'category',
    data: spec.x_field ? rows.map(r => r[spec.x_field]) : ['当前值'],
  },
  yAxis: { type: 'value' },
  series: spec.series.map(s => ({
    name: s.name,
    type: spec.type,          // 'bar' | 'line'
    data: rows.map(r => r[s.key]),
  })),
  tooltip: { trigger: 'axis' },
  grid: { left: 48, right: 24, top: 32, bottom: 40 },
};
```

与算法的对应关系：算法 §8 生成 `chart_spec`，组装 `ChainResult` 时写入 `result.chart`（算法 §7.4），后端只透传不改名（类别对比 / 排名 → `bar`，时间序列 → `line`，两期对比 → `bar` 且 `x_field="period"`，单标量 → `bar` 且 `x_field=null`，空结果 → `null`）。**前端不实现「智能选图」。**

图表为空的处理：`chart === null` 或 `rows` 为空时 `ChartView` 不渲染，由 `ResultBody` 走空态。

视觉统一（不读后端颜色，前端固定一套）：调色板 `['#0891b2', '#4f46e5', '#f59e0b', '#10b981', '#f43f5e']`；柱状图圆角 `[6,6,0,0]`、最大宽度 42px；折线图平滑曲线 + 青色渐变面积；tooltip 深色半透明；网格线 `#f1f5f9`；仅多系列时才显示图例；容器尺寸变化时监听 `resize` 重绘。

---

## 7. 鉴权本版怎么处理

| 项 | 本版 | 预留 |
| :--- | :--- | :--- |
| 登录 | 不做，打开即用 | `/login` 路由与 `LoginPage` 占位组件 |
| 身份 | 前端不传 token | `api/client.ts` 预留 `attachAuthHeader()` 空实现 |
| 用户位 | 左侧栏底部显示固定「用户」 | 替换为账号菜单（退出 / 切换） |
| 权限 | 不做按钮级权限判断 | 预留 `usePermission()`，恒返回 `true` |

对应 F11「本版可暂缓」。不假装平台永远不需要鉴权，所以预留位必须有；但本版不做成权限中台。

---

## 8. 前端状态与数据流

```ts
// store/chatStore.ts
{
  sessionId: string | null;
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  abortController: AbortController | null;
  draft: string;               // 输入框草稿；快捷卡点击只写入这里
  ask(question: string): Promise<void>;
  submitClarify(clarifyId: string, answer: { value?: string; text?: string }): Promise<void>;
  loadSession(id: string): Promise<void>;
  newSession(): void;
  cancel(): void;
  setError(err: string | null): void;
  setDraft(text: string): void;
}

// store/reportStore.ts
{
  list: ReportListItem[];
  total: number;
  fetchList(page: number): Promise<void>;
  remove(id: string): Promise<void>;
  rename(id: string, name: string): Promise<void>;
}
```

数据流原则：**服务端为唯一事实来源**。前端不缓存答案、不做本地合并；每次提问后以响应为准追加消息；报表列表每次进入页面重新拉取。

---

## 9. 异常与空态清单

| 场景 | 表现 |
| :--- | :--- |
| 网络失败 / 5xx | `ErrorBubble` + 重试，不出现空白页 |
| `action=reject` 且 `retryable=true` | 「这次没查出来」+ 重试按钮 |
| `action=reject` 业务拒答 | 原因 + 替代问法，无重试 |
| 空结果（`action=answer`、`rows=[]`） | 表头 + 「该条件下暂无数据」+ 调整建议 |
| 结果截断（`result.truncated=true`） | 表格上方 `Alert`「仅展示前 1000 行」 |
| 图表渲染失败 | `ChartView` 捕获异常 → 只显示表格，附一行提示 |
| 会话为空 | 主区欢迎语 + 4 张快捷提问卡 |
| 报表列表为空 | `Empty` + 「去提问」 |
| 报表快照 | 直接展示保存时的 `result`；不提供刷新按钮，不调重新查询 |
| 报表不存在 | `Result status="404"` + 返回列表 |

---

## 10. 前端不做的事（防越界）

- 不直连算法、不直连数据库，只调后端 API
- 不在前端做 SQL 拼接、数据过滤或口径推断
- 不在前端判断问题是否超范围（算法 S1 的职责）
- 不在前端决定图表类型
- 不展示 SQL、不做查询条件复述（F9 暂缓）
- 不做流式打字机效果（总览 §6 非目标）
- 不做移动端适配、主题切换、国际化
