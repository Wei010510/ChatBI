# 前端页面 - 验收清单（checklist.md）

> 对应 [spec.md](./spec.md) 的 17 条验收标准（AC-1 ~ AC-17）。实现完成后逐条勾选，全部通过才算本 Spec 验收完成。

---

## 一、页面与布局

- [x] **AC-1 三个页面路由与布局** 〔rule〕
  - /、/reports、/reports/:id 三个路由可访问
  - 左侧栏常驻：NewChatButton + 会话搜索 + 对话/报表导航 + SessionList + 固定「用户」位
  - **证据**：页面渲染截图

- [x] **AC-2 对话问数完整闭环** 〔rule〕
  - 提问 → UserBubble + loading 占位 → 结果卡
  - answer → ResultCard（表+图+解读）
  - clarify → ClarifyCard
  - reject → RejectCard
  - **证据**：对话流程测试

- [x] **AC-3 ChatAnswer 字段一致性** 〔rule〕
  - 字段与后端 §5.1 / 算法 §7.4 完全一致
  - result = {columns, rows, chart, narrative, truncated}
  - chart.type 仅 bar | line
  - **证据**：类型定义对照

---

## 二、交互

- [x] **AC-4 澄清交互** 〔rule〕
  - 点选项 / 自由输入 → POST /api/chat/clarify
  - 提交后卡片只读态
  - 卡片内不渲染数字
  - **证据**：澄清交互测试

- [x] **AC-5 拒答交互** 〔rule〕
  - 技术类（intent_parse_failed/sql_generate_failed/sql_execute_failed/timeout）→「这次没查出来」+ 重试
  - 业务类（out_of_scope/detail_export/no_data/write_op）→ 无重试，只给替代问法
  - **证据**：拒答卡渲染测试

- [x] **AC-6 存报表** 〔rule〕
  - rows 非空才可点存为报表
  - 报表名 + 图表类型（bar/line）
  - 409 同名 → 改名 / 覆盖
  - **证据**：存报表流程测试

- [x] **AC-7 报表管理** 〔rule〕
  - 列表按 created_at 倒序，分页 20
  - 打开 → 渲染快照，不重查
  - 改名 PATCH，删除 DELETE + Popconfirm
  - 失败回滚
  - **证据**：报表管理测试

- [x] **AC-8 对话记录** 〔rule〕
  - SessionList 按 updated_at 倒序
  - 回看按原序渲染消息
  - 新对话清空 store
  - **证据**：会话记录测试

---

## 三、图表与数据

- [x] **AC-9 图表映射** 〔rule〕
  - bar / line 按 result.chart.type 渲染
  - chart=null 不渲染
  - x_field=null 时用 ['当前值']
  - 渲染异常降级为表格
  - **证据**：图表渲染测试

- [x] **AC-10 空数据与截断提示** 〔rule〕
  - rows=[] → 表头 + Alert「该条件下暂无数据」
  - truncated=true → Alert「结果超过 1000 行，仅展示前 1000 行」
  - **证据**：空数据/截断测试

- [x] **AC-11 错误码映射** 〔rule〕
  - 400 INVALID_ARGUMENT → message.error
  - 404 SESSION_NOT_FOUND → 回新对话
  - 409 REPORT_NAME_EXISTS → 弹窗改名/覆盖
  - 409 CLARIFY_EXPIRED → 澄清卡置灰
  - 422 MESSAGE_NOT_QUERYABLE → 不可存提示
  - 500 INTERNAL → 重试
  - **证据**：错误码映射测试

---

## 四、边界与占位

- [x] **AC-12 鉴权占位** 〔rule〕
  - /login 占位路由
  - attachAuthHeader() 空实现
  - 左侧栏固定「用户」位
  - usePermission() 返回 true
  - **证据**：代码审查

- [x] **AC-13 不做的事** 〔rule〕
  - 无 SQL 拼接
  - 无图表类型推断
  - 无 SQL 展示
  - 无流式打字机
  - 无移动端适配
  - **证据**：grep 输出

- [x] **AC-14 构建产物** 〔rule〕
  - npm run build 成功
  - dist/ 可被 nginx 托管
  - **证据**：构建日志

- [x] **AC-15 可取消请求** 〔rubric〕
  - 维度：请求可取消与状态一致性
  - 阈值：>= 4 / 5
  - 所有 API 请求支持 AbortController，取消后 loading 移除、store 一致
  - **证据**：api/client.ts 与 store 审查 + 取消交互测试

- [x] **AC-16 会话生命周期与删除** 〔rule〕
  - 刷新页面自动恢复上次会话
  - 删除单条 / 清空全部均有二次确认，删除后回到空对话页
  - **证据**：浏览器操作 + 接口日志

- [x] **AC-17 视觉一致性** 〔rubric〕
  - 维度：三个页面的视觉统一度
  - 阈值：>= 4 / 5
  - 全部由 `:root` 令牌驱动，侧栏/消息/结果卡/图表/表格观感一致，可点击元素有手型光标
  - **证据**：页面截图对照 + `tsc --noEmit` + console 无 error

---

## 验收结论

- [x] 15 条 rule 全部通过，2 条 rubric ≥ 4 → 本 Spec 验收 **通过**
- 否则 → 退回实现阶段修复
