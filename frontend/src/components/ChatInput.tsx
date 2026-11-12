import { useChatStore } from '../store/chatStore';
import { ArrowUpOutlined, StopOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { QUICK_QUESTIONS } from './QuickAskBar';

// 多行输入，回车发送，Shift+回车换行，发送中禁用
export default function ChatInput() {
  const ask = useChatStore((s) => s.ask);
  const loading = useChatStore((s) => s.loading);
  const draft = useChatStore((s) => s.draft);
  const setDraft = useChatStore((s) => s.setDraft);
  const cancel = useChatStore((s) => s.cancel);
  const hasMessages = useChatStore((s) => s.messages.length > 0);

  const handleSend = () => {
    const text = draft.trim();
    if (!text || loading) return;
    setDraft('');
    ask(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-input-wrap">
      {hasMessages && !loading && (
        <div className="composer-suggest">
          <span className="composer-suggest-label">
            <ThunderboltOutlined />
            智能联想
          </span>
          {QUICK_QUESTIONS.map((item) => (
            <button
              key={item.q}
              className="composer-chip"
              onClick={() => setDraft(item.q)}
              title={item.q}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      <div className="chat-input-box">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="问点什么，比如：上周各渠道 GMV 是多少"
          rows={1}
          disabled={loading}
          style={{ height: 'auto', minHeight: 24 }}
        />
        {loading ? (
          <button className="chat-send-btn" title="停止" onClick={cancel}>
            <StopOutlined />
          </button>
        ) : (
          <button
            className="chat-send-btn"
            title="发送（回车）"
            onClick={handleSend}
            disabled={!draft.trim()}
          >
            <ArrowUpOutlined />
          </button>
        )}
      </div>
      <div className="input-hint">回车发送 · Shift + 回车换行 · 结果基于真实数据仓库</div>
    </div>
  );
}
