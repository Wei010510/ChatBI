// 类型定义：与后端 SDD §5 / 算法 §7.4 完全一致，不增删字段。

// 统一响应包
export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T;
  trace_id: string;
}

// 后端错误码
export type ErrorCode =
  | 'INVALID_ARGUMENT'
  | 'SESSION_NOT_FOUND'
  | 'REPORT_NOT_FOUND'
  | 'REPORT_NAME_EXISTS'
  | 'CLARIFY_EXPIRED'
  | 'MESSAGE_NOT_QUERYABLE'
  | 'INTERNAL';

// 图表规格
export interface ChartSpec {
  type: 'bar' | 'line';
  x_field: string | null;
  series: { key: string; name: string }[];
}

// 结果体
export interface ResultBody {
  columns: { key: string; title: string; type: 'number' | 'string' | 'date' }[];
  rows: Record<string, string | number | null>[];
  chart: ChartSpec | null;
  narrative: string;
  truncated: boolean;
}

// 澄清
export interface Clarify {
  clarify_id: string;
  question: string;
  options: { label: string; value: string }[];
  allow_free_text: boolean;
  missing: ('metric' | 'time_range' | 'baseline' | 'caliber')[];
}

// 拒答
export type RejectCode =
  | 'out_of_scope'
  | 'detail_export'
  | 'no_data'
  | 'write_op'
  | 'intent_parse_failed'
  | 'sql_generate_failed'
  | 'sql_execute_failed'
  | 'timeout';

export interface Reject {
  reason_code: RejectCode;
  message: string;
  suggestions: { label: string; question: string }[];
  retryable: boolean;
}

// 问数返回 = ChainResult + message_id + session_id
export interface ChatAnswer {
  message_id: string;
  session_id: string;
  action: 'answer' | 'clarify' | 'reject';
  result: ResultBody | null;
  clarify: Clarify | null;
  reject: Reject | null;
}

// 用户消息
export interface UserMessage {
  message_id: string;
  session_id: string;
  role: 'user';
  content: string;
  created_at: string;
}

// 助手消息
export type AssistantMessage = ChatAnswer & {
  role: 'assistant';
  content: string;
  created_at: string;
};

export type ChatMessage = UserMessage | AssistantMessage;

// 会话
export interface SessionItem {
  id: string;
  title: string;
  updated_at: string;
}

// 报表
export interface ReportListItem {
  id: string;
  name: string;
  question: string;
  created_at: string;
  updated_at: string;
}

export interface ReportDetail {
  id: string;
  name: string;
  question: string;
  result: ResultBody;
  created_at: string;
}
