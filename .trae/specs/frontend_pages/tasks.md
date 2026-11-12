# 前端页面 - 实现计划（tasks.md）

> 依赖：[spec.md](./spec.md)。每个任务含测试要求，完成前自验通过。

## Task 1：工程脚手架
- **Status**：`completed`
- **Priority**：high
- **Depends On**：None
- **Description**：
  - `frontend/` 目录用 Vite 建 React + TS 项目。
  - 安装依赖：antd、echarts、zustand、react-router-dom。
  - 目录结构：src/{components,pages,store,api,types,hooks,styles}。
  - Vite 配置代理 `/api` → 后端。
- **Acceptance Criteria Addressed**：AC-14
- **Test Requirements**：
  - `rule` TR-1.1：`npm run build` 成功产出 dist/。

## Task 2：类型定义（types/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - `types/index.ts`：ApiResponse<T>、ChatAnswer、ResultBody、ChartSpec、Clarify、Reject、RejectCode、UserMessage、AssistantMessage、ChatMessage、ReportListItem、ReportDetail。
  - 字段与后端 SDD §5 完全一致。
- **Acceptance Criteria Addressed**：AC-3
- **Test Requirements**：
  - `rule` TR-2.1：ChatAnswer 字段与后端 §5.1 diff 为零。

## Task 3：API 封装（api/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2
- **Description**：
  - `api/client.ts`：fetch 封装，统一 ApiResponse 解包、超时、AbortController、错误码映射、attachAuthHeader() 空实现。
  - `api/chat.ts`：ask、clarify。
  - `api/session.ts`：listSessions、getMessages。
  - `api/report.ts`：create、list、get、rename、remove。
  - 错误码 → 前端表现映射。
- **Acceptance Criteria Addressed**：AC-11, AC-15
- **Test Requirements**：
  - `rule` TR-3.1：6 种错误码各触发对应前端表现。
  - `rule` TR-3.2：abort 后 Promise reject 且不更新 store。

## Task 4：Zustand Store（store/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 3
- **Description**：
  - `store/chatStore.ts`：sessionId/messages/loading/pendingClarify + ask/submitClarify/loadSession/newSession。
  - `store/reportStore.ts`：list/total + fetchList/remove/rename。
  - 服务端为唯一事实来源，不缓存答案。
- **Acceptance Criteria Addressed**：AC-2, AC-8
- **Test Requirements**：
  - `rule` TR-4.1：ask 成功后 messages 追加 user + assistant 两条。
  - `rule` TR-4.2：newSession 清空 messages 且 sessionId=null。

## Task 5：布局与路由（AppLayout + Router）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1, Task 4
- **Description**：
  - `App.tsx` + `AppLayout.tsx`：可折叠左侧栏（品牌区、NewChatButton、会话搜索、对话/报表导航、SessionList、数据仓库状态与固定「用户」位）+ 主区 Outlet。
  - 路由：/ → ChatPage，/reports → ReportsPage，/reports/:id → ReportViewPage，/login → LoginPage 占位。
  - `hooks/usePermission.ts`：恒返回 true。
- **Acceptance Criteria Addressed**：AC-1, AC-12
- **Test Requirements**：
  - `rule` TR-5.1：三个路由可访问，左侧栏元素齐全。
  - `rule` TR-5.2：/login 占位路由存在。

## Task 6：通用结果体 ResultBody
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2
- **Description**：
  - `components/ResultBody.tsx`：表格（AntD Table 动态列）+ ChartView + NarrativeLine。
  - `components/ChartView.tsx`：按 result.chart 渲染 bar/line，x_field=null 用 ['当前值']，null 不渲染，异常降级表格。
  - 空数据 Alert、截断 Alert。
- **Acceptance Criteria Addressed**：AC-9, AC-10
- **Test Requirements**：
  - `rule` TR-6.1：bar/line/null 三种 chart 状态正确渲染。
  - `rule` TR-6.2：rows=[] 显示暂无数据 Alert；truncated 显示截断 Alert。
  - `rule` TR-6.3：图表渲染异常时只显示表格。

## Task 7：对话页组件
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 4, Task 6
- **Description**：
  - `pages/ChatPage.tsx` + MessageList。
  - `components/UserBubble.tsx`、`components/ResultCard.tsx`（含存报表按钮）、`components/ClarifyCard.tsx`、`components/RejectCard.tsx`、`components/ErrorBubble.tsx`。
  - `components/QuickAskBar.tsx`（4 张快捷卡）、`components/ChatInput.tsx`（原生 textarea，回车发送/Shift 换行/空内容置灰/请求中变停止）。
  - 按 action 分支渲染对应卡片。
- **Acceptance Criteria Addressed**：AC-2, AC-4, AC-5
- **Test Requirements**：
  - `rule` TR-7.1：answer/clarify/reject 三种 action 渲染对应卡片。
  - `rule` TR-7.2：ClarifyCard 点选项调 clarify，提交后只读，无数字。
  - `rule` TR-7.3：RejectCard 技术类有重试、业务类无重试。
  - `rule` TR-7.4：loading 取消调 abort 并移除占位。

## Task 8：存报表弹窗
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 7
- **Description**：
  - `components/SaveReportModal.tsx`：报表名（默认用户问题）+ 图表类型单选（bar/line 默认 chart.type）。
  - 提交 POST /api/reports；409 给改名/覆盖；rows 空时 ResultCard 按钮禁用。
- **Acceptance Criteria Addressed**：AC-6
- **Test Requirements**：
  - `rule` TR-8.1：rows 空时存报表按钮 disabled。
  - `rule` TR-8.2：409 时弹窗显示改名/覆盖选项。

## Task 9：报表列表页
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 4
- **Description**：
  - `pages/ReportsPage.tsx` + `components/ReportTable.tsx`。
  - 列表（名称/来源问题/created_at 倒序，分页 20）、空态 Empty + 去提问。
  - 行点击跳 /reports/:id。
  - 改名（行内编辑 PATCH）、删除（Popconfirm DELETE），失败回滚。
- **Acceptance Criteria Addressed**：AC-7
- **Test Requirements**：
  - `rule` TR-9.1：列表按 created_at 倒序，分页 20。
  - `rule` TR-9.2：删除失败时列表回滚原状。

## Task 10：报表查看页
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 6
- **Description**：
  - `pages/ReportViewPage.tsx`（复用 `components/ResultBody.tsx`）。
  - GET /api/reports/{id} 直接渲染快照 result，复用 ResultBody。
  - 无提问动作、无刷新按钮；404 时 Result status=404 + 返回列表。
- **Acceptance Criteria Addressed**：AC-7
- **Test Requirements**：
  - `rule` TR-10.1：打开报表不调 /api/chat/ask（mock 断言）。
  - `rule` TR-10.2：404 显示 Result 404 页。

## Task 11：鉴权占位
- **Status**：`completed`
- **Priority**：low
- **Depends On**：Task 5
- **Description**：
  - `pages/LoginPage.tsx` 占位（提示「本版无需登录」）。
  - 左侧栏底部固定「用户」显示。
  - `api/client.ts` attachAuthHeader() 空实现。
  - `hooks/usePermission.ts` 返回 true。
- **Acceptance Criteria Addressed**：AC-12
- **Test Requirements**：
  - `rule` TR-11.1：四个占位（路由/空实现/「用户」位/usePermission）齐全。

## Task 12：异常与空态
- **Status**：`completed`
- **Priority**：medium
- **Depends On**：Task 7, Task 9, Task 10
- **Description**：
  - ErrorBubble + 重试（网络/5xx）。
  - 会话为空时主区欢迎语 + QuickAskBar（4 张快捷卡）。
  - 报表列表空态 Empty。
  - 报表不存在 Result 404。
  - 所有空态不白屏。
- **Acceptance Criteria Addressed**：AC-10, AC-11
- **Test Requirements**：
  - `rule` TR-12.1：网络失败时显示 ErrorBubble 而非空白。

## Task 13：不做的事自检
- **Status**：`completed`
- **Priority**：medium
- **Depends On**：Task 1-12
- **Description**：
  - grep 检查：无 SQL 拼接、无图表类型推断逻辑、无 SQL 展示组件、无流式打字机、无移动端适配媒体查询。
- **Acceptance Criteria Addressed**：AC-13
- **Test Requirements**：
  - `rule` TR-13.1：grep 相关关键词零匹配。

## Task 14：联调与构建验证
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1-13
- **Description**：
  - 与后端联调（或 Mock API）跑通一次完整问数 + 存报表 + 回看会话。
  - npm run build 验证构建产物。
- **Acceptance Criteria Addressed**：AC-2, AC-14
- **Test Requirements**：
  - `rule` TR-14.1：完整问数流程（提问→结果→存报表→打开报表）走通。
  - `rule` TR-14.2：npm run build 无报错。

## Task 15：会话生命周期与删除
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 5, Task 7
- **Description**：
  - `store/chatStore.ts`：sessionId 写入/清除 `localStorage['current_session_id']`，刷新自动恢复；`sessionStorage['open_session_id']` 承接侧栏点选。
  - `api/session.ts`：`remove(id)` / `removeAll()`。
  - `AppLayout`：会话 hover 删除（Popconfirm）+「清空」全部（Popconfirm）+ 标题搜索（本地过滤）。
- **Acceptance Criteria Addressed**：AC-1
- **Test Requirements**：
  - `rule` TR-15.1：刷新页面后仍停在上次会话。
  - `rule` TR-15.2：删除当前会话后回到空对话页；清空全部后会话列表为空。

## Task 16：视觉改版（设计令牌 + 布局 + 图表）
- **Status**：`completed`
- **Priority**：medium
- **Depends On**：Task 5, Task 6, Task 7, Task 8
- **Description**：
  - `styles/index.css` 重写：`:root` 设计令牌（墨色/青色/靛色/四级阴影/字体）、侧栏与消息类、通用 chip/surface/chart-frame。
  - `App.tsx`：ConfigProvider 主题（colorPrimary/colorError/borderRadius/字体，Table/Button/Input/Modal 覆盖）。
  - `ChatPage`/`ResultCard`/`ResultBody`/`ClarifyCard`/`RejectCard`/`ErrorBubble`/`ReportTable`/`SaveReportModal`/`LoginPage` 按新令牌重排。
  - 卡片入场：快捷卡错峰上浮、用户气泡/结果卡/等待卡从下 28px 浮入（spring 缓动，`fill-mode: backwards` 不干扰 hover）。
  - 等待卡：渐变图标脉冲 + 流光进度条 + 「约需 40~90 秒」提示 + 取消。
  - 欢迎徽标：渐变描边圆角方 + 白色内衬 + 青色火花图标，上下小幅浮动。
  - 可点击元素统一手型光标，禁用态 `not-allowed`。
- **Acceptance Criteria Addressed**：AC-1, AC-9, AC-12
- **Test Requirements**：
  - `rule` TR-16.1：三个页面视觉一致，无硬编码色值散落（除令牌文件）。
  - `rule` TR-16.2：`npx tsc --noEmit` 通过；浏览器无 console error。
  - `rule` TR-16.3：图表按统一调色板渲染，窗口缩放不糊。

