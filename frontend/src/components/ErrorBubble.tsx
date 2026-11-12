import { Button } from 'antd';
import { WarningOutlined, ReloadOutlined } from '@ant-design/icons';

interface Props {
  message: string;
  onRetry: () => void;
}

export default function ErrorBubble({ message, onRetry }: Props) {
  return (
    <div
      className="assistant-card"
      style={{ width: '100%', borderColor: 'rgba(225, 29, 72, 0.24)' }}
    >
      <div className="result-card-head">
        <div className="result-head-left">
          <span
            className="result-head-icon"
            style={{ background: 'rgba(225, 29, 72, 0.1)', color: '#e11d48' }}
          >
            <WarningOutlined />
          </span>
          <span style={{ fontSize: 14, fontWeight: 600 }}>请求失败</span>
        </div>
        <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
          重试
        </Button>
      </div>
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.75,
          color: 'var(--ink-2)',
          wordBreak: 'break-word',
        }}
      >
        {message}
      </div>
    </div>
  );
}
