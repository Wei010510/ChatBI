# 前端页面 - 产品需求规格（Spec）

## 概述

- **摘要**：基于 `docs/SDD-前端.md`（v3.0），落地 ChatBI 前端 SPA：对话页（消息流 + 输入框）、报表列表页、报表查看页，三个页面共用左侧栏；用 AntD 5 组件 + ECharts 5（仅 bar/line）按后端 `ChainResult` 渲染，不做智能选图、不拼 SQL、不判口径。
- **目的**：让用户在浏览器里问数、看表看图看解读、存报表、回看历史会话。
- **目标用户**：业务同学（直接使用浏览器页面）。

## 目标

- 三个页面路由可用（/、/reports、/reports/:id），左侧栏常驻。
- 对话问数完整闭环：提问 → loading → 结果卡（表+图+解读）/ 澄清卡 / 拒答卡。
- 报表 CRUD：存为报表、列表、打开快照、改名、删除。
- 对话记录：列表、回看、新对话。
- 图表严格按后端 `result.chart` 渲染，只认 bar/line，不做智能选图。
- 接口字段与后端 §2 / 算法 §7.4 完全一致，不另发明字段。

## 非目标

- ❌ 不直连算法、不直连数据库，只调后端 API。
- ❌ 不在前端做 SQL 拼接、数据过滤、口径推断。
- ❌ 不在前端判断问题是否超范围（算法 S1 职责）。
- ❌ 不在前端决定图表类型（只按 `result.chart.type` 映射）。
- ❌ 不展示 SQL、不做查询条件复述（F9 暂缓）。
- ❌ 不做流式打字机效果。
- ❌ 不做移动端适配、用户可切换主题、国际化（允许统一设计令牌，不做主题切换开关）。
- ❌ 不做登录鉴权/权限中台（仅固定「用户」占位 + 预留 hook）。
- ❌ 不做跨端同步、跨用户共享会话。
- ❌ SDD 明确「不做」的内容一律不做。

## 背景与上下文

- 技术栈：React 18 + TypeScript + Vite + Ant Design 5 + ECharts 5 + Zustand + fetch 封装。
- 接口契约以后端 SDD §2 为准；`ChatAnswer` = `ChainResult`（算法 §7.4）+ message_id + session_id。
- 前端代码落点：`frontend/`（Vite 项目）；构建产物 `dist/` 由 nginx 托管，`/api` 反向代理到后端。
- 修改顺序：算法 → 后端 → 前端 → 总览；本 Spec 只动前端。

## 功能需求

### 页面与布局
- **FR-1 路由与 AppLayout**：三个路由 `/`（对话页）、`/reports`（报表列表）、`/reports/:id`（报表查看）；`AppLayout` 含可折叠左侧栏（品牌区 + NewChatButton + 会话搜索 + 对话/报表导航 + SessionList + 数据仓库状态与固定「用户」位）+ 主区 Outlet；左侧栏常驻。
- **FR-2 对话页 ChatPage**：ChatHeader（标题 + 数据仓库在线）+ MessageList（消息流，带角色/时间 meta）+ 空会话欢迎态（QuickAskBar）+ ChatInput（底部输入框）。
- **FR-3 报表列表页 ReportsPage**：ReportTable（名称/来源问题/保存时间，分页 20，空态 Empty + 去提问）。
- **FR-4 报表查看页 ReportViewPage**：ResultBody（表+图+解读，无提问动作，无刷新按钮）。
- **FR-35 视觉规范**：颜色/圆角/阴影/字体统一由 `styles/index.css` 的 `:root` 令牌驱动，AntD 通过 `ConfigProvider` 对齐；侧栏 280px（折叠 64px），对话内容 860px 居中；用户消息深色气泡、助手消息白色卡片；可点击元素统一手型光标、禁用态 `not-allowed`；卡片入场从下方 28px 上浮（快捷卡错峰 70ms），动效遵循 `prefers-reduced-motion`。

### 对话问数（F1）
- **FR-5 ChatInput**：原生 textarea，回车发送（Shift+回车换行），空内容发送置灰，请求中按钮变「停止」；已有对话时上方显示 4 个联想 chip，点击填入草稿。
- **FR-6 QuickAskBar**：4 张快捷卡（标签 + 完整问题），点击把问题填入输入框，不自动发送。
- **FR-7 过程提示与取消**：发送后本地插入 UserBubble + loading 占位气泡；loading 内「取消」调 AbortController.abort() 移除占位。
- **FR-8 ResultCard（answer）**：ResultBody 顺序 = 表格 → 图表 → 解读；表格 AntD Table 列由 result.columns 动态生成，size=small，超 10 行滚动；图表 ChartView 按 result.chart.type 选 bar/line，chart=null 不渲染；narrative 为空不渲染该行。
- **FR-9 空数据与截断**：rows=[] → 表头 + Alert「该条件下暂无数据」+ 调整建议；truncated=true → 表格上方 Alert「结果超过 1000 行，仅展示前 1000 行」。
- **FR-10 多轮追问**：同一 session_id 继续发问，不重置消息数组，旧卡片保留。
- **FR-11 HTTP 失败**：ErrorBubble + 重试。

### 澄清（F2）
- **FR-12 ClarifyCard**：clarify.question + 选项按钮组 + 可选自由输入（allow_free_text）；点选项立即调 /api/chat/clarify，answer={value}；自由输入 answer={text}。
- **FR-13 澄清状态与过期**：提交后卡片置「已选择 XXX」只读态；卡片内不渲染数字；409 CLARIFY_EXPIRED → 卡片置灰 + 提示重新提问；放弃澄清直接发新问题即可。

### 拒答（F3）
- **FR-14 RejectCard**：reject.message + 替代问法按钮（suggestions）；点替代问法作为新问题调 /api/chat/ask。
- **FR-15 技术失败 vs 业务拒答**：reason_code ∈ {intent_parse_failed, sql_generate_failed, sql_execute_failed, timeout} → 标题「这次没查出来」+ 重试按钮（retryable=true）；业务类（out_of_scope/detail_export/no_data/write_op）→ 不显示重试，只给替代问法；不渲染「估算」「约」类数字。

### 对比分析（F4）
- **FR-16 对比结果渲染**：对比类走 ResultCard，固定为 period + 指标列两行，chart 为 bar 且 x_field="period"；差值/变化率只在 narrative，前端不计算不猜列。

### 存报表（F5）
- **FR-17 存报表入口与弹窗**：ResultCard 右上角「存为报表」按钮，rows 为空禁用；SaveReportModal（报表名默认取用户问题 + 图表类型单选 bar/line 默认跟当前 chart.type）。
- **FR-18 存报表提交与冲突**：POST /api/reports；成功 message.success 并关闭弹窗；409 REPORT_NAME_EXISTS → 弹窗提示同名 + 改名/覆盖（overwrite:true 重发）；失败弹窗内红字提示，输入保留。

### 报表管理（F6）
- **FR-19 报表列表**：ReportTable 名称/来源问题/created_at 倒序，分页 20；空态 Empty + 去提问。
- **FR-20 打开报表**：行点击 → /reports/:id，直接渲染后端快照，不重新提问不重新查询。
- **FR-21 改名与删除**：行内编辑改名（Enter 确认/Esc 取消）调 PATCH；删除 Popconfirm「删除后不可恢复」调 DELETE；失败 message.error + 列表回滚。

### 对话记录（F7）
- **FR-22 会话列表**：左侧栏 SessionList 按 updated_at 倒序，显示会话标题；sessionId 变化后自动刷新；顶部搜索框按标题本地过滤（不发请求）；切换会话时即时高亮 + 骨架屏，过期响应按序号丢弃。
- **FR-23 回看会话**：点击 → sessionStorage['open_session_id'] 传参 → GET /api/sessions/{id}/messages → 按原顺序渲染消息。
- **FR-24 新对话**：点击 → 清空 chatStore 与本地会话指针，session_id 置空，首次发送后端创建。
- **FR-32 会话生命周期**：当前 session_id 存 localStorage['current_session_id']，刷新页面自动恢复；只有「新对话」和手动删除会结束会话。
- **FR-33 删除会话**：hover 会话项右侧删除图标 → Popconfirm → DELETE /api/sessions/{id}（删当前会话则回空对话页）；「清空」→ DELETE /api/sessions 清空全部。

### 部署（F8）
- **FR-25 构建产物**：npm run build 产出 dist/，由 web 容器 nginx 托管，/api 反向代理到 api 容器。

### 接口与状态
- **FR-26 统一响应与错误码映射**：ApiResponse<T>={code,message,data,trace_id}；错误码表与前端展示映射（400/404/409/422/500）。
- **FR-27 类型定义**：ChatAnswer / ChatMessage（UserMessage | AssistantMessage）/ ReportListItem / ReportDetail / ResultBody，字段与后端 §5 完全一致。
- **FR-28 Zustand 状态**：chatStore（sessionId/messages/loading/error/abortController/draft + ask/submitClarify/loadSession/newSession/cancel/setDraft/setError）；reportStore（list/total + fetchList/remove/rename）。
- **FR-29 数据流原则**：服务端为唯一事实来源，不缓存答案不做本地合并，每次提问以响应为准追加消息，报表列表每次进入重新拉取。

### 图表
- **FR-30 ChartView 映射**：按 result.chart 渲染，x_field 取行值（null 时 ['当前值']），series 映射；chart=null 或 rows 空时不渲染；捕获异常只显示表格。
- **FR-34 图表主题**：统一调色板（青/靛/琥珀/翠/玫红），柱体圆角与最大宽度、折线平滑与渐变面积、深色 tooltip、浅色网格线；多系列才出图例；容器 resize 时重绘。

### 鉴权预留
- **FR-31 鉴权占位**：/login 路由与 LoginPage 占位；api/client.ts 预留 attachAuthHeader() 空实现；左侧栏底部显示固定「用户」；usePermission() 恒返回 true。

## 非功能需求

- **NFR-1 接口字段零偏差**：ChatAnswer/ChatMessage/Report 类型与后端 §5 完全一致，不增删字段。
- **NFR-2 不做智能选图**：chart.type 仅 bar/line，前端不推断图表类型。
- **NFR-3 不展示 SQL**：结果卡不展示 SQL、不展示查询条件复述。
- **NFR-4 图表异常降级**：ECharts 渲染失败时只显示表格 + 提示，不白屏。
- **NFR-5 可取消请求**：所有 API 请求支持 AbortController。
- **NFR-6 无空白页**：网络失败/5xx 有 ErrorBubble + 重试。

## 约束

- **技术**：React 18、TypeScript、Vite、AntD 5、ECharts 5（仅 bar/line）、Zustand；不引入其他 UI 库或图表库。
- **业务**：不做算法、不做后端、不做鉴权、不做流式、不做移动端/主题/i18n。
- **依赖**：后端 API 已就绪（由后端 Spec 交付）；本步可用 Mock API 测试。

## 假设

- 后端接口路径与返回体与 SDD §2 一致；本步可写 Mock 层联调。
- 后端启动在 `http://localhost:8000` 或经 nginx 反代 `/api`；前端用相对路径 `/api`。
- 前端项目根目录 `frontend/`，独立于 `backend/`。

## 验收标准

### AC-1：三个页面路由与布局
- **Type**: `rule`
- **Given**: 前端 dev server 启动
- **When**: 访问 /、/reports、/reports/:id
- **Then**: 三个页面正确渲染；左侧栏常驻含 NewChatButton/会话搜索/SessionList/「用户」位
- **Pass Condition**: 三个路由可访问，左侧栏元素齐全
- **Evidence**: 页面渲染截图 / 路由测试

### AC-2：对话问数完整闭环
- **Type**: `rule`
- **Given**: 后端 /api/chat/ask 可用
- **When**: 用户输入问题并发送
- **Then**: 出现 UserBubble + loading 占位 → 返回后渲染 ResultCard（表+图+解读）或 ClarifyCard 或 RejectCard
- **Pass Condition**: 三种 action 各自渲染对应卡片
- **Evidence**: 对话流程测试

### AC-3：ChatAnswer 字段一致性
- **Type**: `rule`
- **Given**: 前端 ChatAnswer 类型定义
- **When**: 对照后端 §5.1 与算法 §7.4
- **Then**: 字段完全一致（message_id/session_id/action/result/clarify/reject），result 内部 columns/rows/chart/narrative/truncated，chart 仅 bar/line
- **Pass Condition**: 类型定义 diff 为零
- **Evidence**: 类型定义对照

### AC-4：澄清交互
- **Type**: `rule`
- **Given**: action=clarify 的消息
- **When**: 点击选项或输入自由文本
- **Then**: 调 /api/chat/clarify，提交后卡片只读；卡片内无数字
- **Pass Condition**: 澄清提交流程正确
- **Evidence**: 澄清交互测试

### AC-5：拒答交互
- **Type**: `rule`
- **Given**: action=reject 的消息
- **When**: reason_code 为技术类
- **Then**: 显示「这次没查出来」+ 重试按钮；业务类不显示重试
- **Pass Condition**: 技术类有重试、业务类无重试
- **Evidence**: 拒答卡渲染测试

### AC-6：存报表
- **Type**: `rule`
- **Given**: answer 且 rows 非空的 ResultCard
- **When**: 点击存为报表 → 填写 → 提交
- **Then**: POST /api/reports 成功；409 时给改名/覆盖；rows 空时按钮禁用
- **Pass Condition**: 存报表成功与冲突处理正确
- **Evidence**: 存报表流程测试

### AC-7：报表管理
- **Type**: `rule`
- **Given**: 报表列表页
- **When**: 打开/改名/删除
- **Then**: 打开渲染快照不重查；改名 PATCH；删除 DELETE + Popconfirm；失败回滚
- **Pass Condition**: 报表 CRUD 正确
- **Evidence**: 报表管理测试

### AC-8：对话记录
- **Type**: `rule`
- **Given**: 有历史会话
- **When**: 点击会话回看
- **Then**: GET /api/sessions/{id}/messages 按序渲染；新对话清空 store
- **Pass Condition**: 回看与新对话正确
- **Evidence**: 会话记录测试

### AC-9：图表映射
- **Type**: `rule`
- **Given**: result.chart 为 bar/line/null
- **When**: ChartView 渲染
- **Then**: bar/line 正确渲染；null 不渲染；x_field=null 时用 ['当前值']；渲染异常降级为表格
- **Pass Condition**: 三种图表状态正确处理
- **Evidence**: 图表渲染测试

### AC-10：空数据与截断提示
- **Type**: `rule`
- **Given**: rows=[] 或 truncated=true
- **When**: ResultCard 渲染
- **Then**: rows=[] → 表头 + Alert 暂无数据；truncated → Alert 仅展示前 1000 行
- **Pass Condition**: 两种提示正确显示
- **Evidence**: 空数据/截断测试

### AC-11：错误码映射
- **Type**: `rule`
- **Given**: 后端返回各错误码
- **When**: 前端处理
- **Then**: 400 message.error；404 SESSION_NOT_FOUND 回新对话；409 REPORT_NAME_EXISTS 弹窗；409 CLARIFY_EXPIRED 置灰；422 不可存提示；500 重试
- **Pass Condition**: 6 种错误码前端表现正确
- **Evidence**: 错误码映射测试

### AC-12：鉴权占位
- **Type**: `rule`
- **Given**: 前端应用
- **When**: 检查鉴权相关
- **Then**: /login 占位路由存在；attachAuthHeader() 空实现；左侧栏显示「用户」；usePermission() 返回 true
- **Pass Condition**: 四个占位齐全
- **Evidence**: 代码审查

### AC-13：不做的事
- **Type**: `rule`
- **Given**: 前端代码
- **When**: grep 检查
- **Then**: 无 SQL 拼接、无图表类型推断、无 SQL 展示、无流式打字机、无移动端适配代码
- **Pass Condition**: grep 相关关键词零匹配
- **Evidence**: grep 输出

### AC-14：构建产物
- **Type**: `rule`
- **Given**: 执行 npm run build
- **When**: 构建完成
- **Then**: dist/ 产出静态文件，可被 nginx 托管
- **Pass Condition**: 构建成功无报错
- **Evidence**: 构建日志

### AC-15：可取消请求
- **Type**: `rubric`
- **Dimension**: 请求可取消与状态一致性
- **Scale**: 1-5
- **Anchors**: 1 = 请求不可取消，取消后状态错乱；3 = 部分请求可取消但状态未清理；5 = 所有 API 请求支持 AbortController，取消后 loading 占位移除、store 状态一致
- **Pass Threshold**: >= 4
- **Evidence**: api/client.ts 与 store 审查 + 取消交互测试

### AC-16：会话生命周期与删除
- **Type**: `rule`
- **Given**: 已有一个进行中的会话
- **When**: 刷新页面 / 删除该会话 / 清空全部
- **Then**: 刷新后自动恢复该会话；删除后回到空对话页；清空后列表为空
- **Pass Condition**: 三种场景均符合，且删除有二次确认
- **Evidence**: 浏览器操作 + 接口日志

### AC-17：视觉一致性
- **Type**: `rubric`
- **Dimension**: 三个页面的视觉统一度
- **Scale**: 1-5
- **Anchors**: 1 = 颜色字体各写各的；3 = 大部分统一但仍有硬编码色值；5 = 全部由 `:root` 令牌驱动，侧栏/消息/结果卡/图表/表格观感一致，可点击元素有手型光标
- **Pass Threshold**: >= 4
- **Evidence**: 页面截图对照 + `tsc --noEmit` + console 无 error

## 开放问题

- [ ] 前端项目目录是 `frontend/` 还是仓库根？（建议 `frontend/`，与 `backend/` 平级）
- [ ] 本步是否搭建 Mock API 层用于无后端联调？（建议用 Vite mock 或 MSW，加速开发）
