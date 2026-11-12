import { useState } from 'react';
import { Button } from 'antd';
import { SaveOutlined, TableOutlined } from '@ant-design/icons';
import type { AssistantMessage } from '../types';
import ResultBody from './ResultBody';
import ClarifyCard from './ClarifyCard';
import RejectCard from './RejectCard';
import SaveReportModal from './SaveReportModal';

interface Props {
  message: AssistantMessage;
}

// 按 action 分支渲染结果卡 / 澄清卡 / 拒答卡
export default function ResultCard({ message }: Props) {
  const [saveOpen, setSaveOpen] = useState(false);

  if (message.action === 'clarify' && message.clarify) {
    return (
      <div className="assistant-card">
        <ClarifyCard
          clarify={message.clarify}
          sessionId={message.session_id}
          messageId={message.message_id}
        />
      </div>
    );
  }

  if (message.action === 'reject' && message.reject) {
    return (
      <div className="assistant-card">
        <RejectCard reject={message.reject} />
      </div>
    );
  }

  // answer
  const result = message.result;
  if (!result) return null;
  const hasRows = result.rows.length > 0;

  return (
    <div className="assistant-card">
      <div className="result-card-head">
        <div className="result-head-left">
          <span className="result-head-icon">
            <TableOutlined />
          </span>
          <span>查询结果</span>
          <span className="chip">{result.rows.length} 行</span>
          {result.chart && (
            <span className="chip chip-accent">{result.chart.type === 'bar' ? '柱状图' : '折线图'}</span>
          )}
        </div>
        <Button
          size="small"
          icon={<SaveOutlined />}
          disabled={!hasRows}
          onClick={() => setSaveOpen(true)}
          style={{ borderRadius: 8 }}
        >
          存为报表
        </Button>
      </div>
      <ResultBody result={result} />
      {saveOpen && (
        <SaveReportModal
          open={saveOpen}
          onClose={() => setSaveOpen(false)}
          messageId={message.message_id}
          defaultName={message.content || '未命名报表'}
          chartType={result.chart?.type}
        />
      )}
    </div>
  );
}
