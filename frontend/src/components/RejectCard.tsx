import { Space } from 'antd';
import { WarningOutlined, StopOutlined, ArrowRightOutlined } from '@ant-design/icons';
import type { Reject } from '../types';
import { useChatStore } from '../store/chatStore';

interface Props {
  reject: Reject;
}

const TECH_CODES = new Set([
  'intent_parse_failed',
  'sql_generate_failed',
  'sql_execute_failed',
  'timeout',
]);

// 拒答卡：技术类有重试，业务类无重试只给替代问法
export default function RejectCard({ reject }: Props) {
  const ask = useChatStore((s) => s.ask);
  const isTech = TECH_CODES.has(reject.reason_code);
  const title = isTech ? '这次没查出来' : '这个问题我没法回答';

  return (
    <div>
      <div className="result-card-head" style={{ marginBottom: 10 }}>
        <div className="result-head-left">
          <span
            className="result-head-icon"
            style={
              isTech
                ? { background: '#fffbeb', color: '#b45309' }
                : { background: '#fff1f2', color: '#e11d48' }
            }
          >
            {isTech ? <WarningOutlined /> : <StopOutlined />}
          </span>
          <span>{title}</span>
          <span className={`chip ${isTech ? 'chip-warn' : 'chip-danger'}`}>
            {reject.reason_code}
          </span>
        </div>
      </div>

      <div style={{ fontSize: 13, color: '#334155', lineHeight: 1.8 }}>{reject.message}</div>

      {reject.suggestions.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="result-section-title" style={{ margin: '0 0 8px' }}>
            换个问法试试
          </div>
          <Space wrap>
            {reject.suggestions.map((s) => (
              <button
                key={s.question}
                className="btn-ghost"
                style={{ width: 'auto', padding: '6px 12px', borderRadius: 999 }}
                onClick={() => ask(s.question)}
              >
                {s.label}
                <ArrowRightOutlined style={{ fontSize: 10, opacity: 0.45 }} />
              </button>
            ))}
          </Space>
        </div>
      )}
    </div>
  );
}
