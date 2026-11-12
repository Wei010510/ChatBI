import { useEffect, useRef } from 'react';
import { Button } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import { useChatStore, getStoredSessionId } from '../store/chatStore';
import type { AssistantMessage, UserMessage } from '../types';
import UserBubble from '../components/UserBubble';
import ResultCard from '../components/ResultCard';
import QuickAskBar from '../components/QuickAskBar';
import ChatInput from '../components/ChatInput';

export default function ChatPage() {
  const messages = useChatStore((s) => s.messages);
  const loading = useChatStore((s) => s.loading);
  const sessionLoading = useChatStore((s) => s.sessionLoading);
  const loadSession = useChatStore((s) => s.loadSession);
  const setDraft = useChatStore((s) => s.setDraft);
  const cancel = useChatStore((s) => s.cancel);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 优先用左侧栏点选的会话；否则恢复上次的会话（刷新不丢）
    const openId = sessionStorage.getItem('open_session_id');
    if (openId) {
      sessionStorage.removeItem('open_session_id');
      loadSession(openId);
      return;
    }
    const storedId = getStoredSessionId();
    if (storedId && !useChatStore.getState().sessionId) {
      loadSession(storedId);
    }
  }, [loadSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, loading]);

  const handlePick = (q: string) => {
    setDraft(q);
  };

  return (
    <div className="chat-page">
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'baseline', minWidth: 0 }}>
          <span className="chat-title">智能问数</span>
          <span className="chat-subtitle">自然语言查询 · 自动出表出图</span>
        </div>
        <div className="status-pill">
          <span className="status-dot" />
          数据仓库在线
        </div>
      </div>

      <div className="message-list">
        {messages.length === 0 && !loading && !sessionLoading && (
          <div className="welcome-wrap">
            <div className="welcome-logo">
              <span className="welcome-logo-inner">
                <svg viewBox="0 0 32 32" aria-hidden="true">
                  <path
                    d="M16 5.2c.7 4.8 3 7.1 7.8 7.8-4.8.7-7.1 3-7.8 7.8-.7-4.8-3-7.1-7.8-7.8 4.8-.7 7.1-3 7.8-7.8Z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M23.6 22.2v4.2M21.5 24.3h4.2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                  <circle cx="8.6" cy="23.4" r="1.7" fill="none" stroke="currentColor" strokeWidth="2" />
                </svg>
              </span>
            </div>
            <div className="welcome-title">今天想了解什么数据？</div>
            <div className="welcome-sub">
              直接用中文提问，我会自动选表、生成 SQL、出表出图，并给一句解读。
              <br />
              不用记字段名，也不用写 SQL。
            </div>
            <QuickAskBar onPick={handlePick} />
          </div>
        )}

        {sessionLoading && messages.length === 0 && (
          <div className="msg-row assistant">
            <div className="msg-meta">
              <span className="who">ChatBI</span>
              <span>正在加载会话…</span>
            </div>
            <div className="session-skeleton">
              <span className="sk-line" style={{ width: '42%' }} />
              <span className="sk-line" style={{ width: '92%' }} />
              <span className="sk-line" style={{ width: '76%' }} />
              <span className="sk-block" />
            </div>
          </div>
        )}

        {messages.map((m: UserMessage | AssistantMessage) => (
          <div key={m.message_id} className={`msg-row ${m.role === 'user' ? 'user' : 'assistant'}`}>
            <div className="msg-meta">
              <span className="who">{m.role === 'user' ? '我' : 'ChatBI'}</span>
              <span className="mono">
                {new Date(m.created_at).toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
            {m.role === 'user' ? (
              <UserBubble content={m.content} />
            ) : (
              <ResultCard message={m} />
            )}
          </div>
        ))}

        {loading && (
          <div className="msg-row assistant">
            <div className="msg-meta">
              <span className="who">ChatBI</span>
              <span>正在思考</span>
            </div>
            <div className="loading-bubble">
              <span className="loading-orb">
                <LoadingOutlined />
              </span>
              <div className="loading-body">
                <div className="loading-title">正在理解问题、生成 SQL 并执行…</div>
                <div className="loading-track">
                  <span className="loading-bar" />
                </div>
                <div className="loading-hint">复杂问题约需 40~90 秒，结果会自动出现</div>
              </div>
              <Button size="small" type="text" onClick={cancel}>
                取消
              </Button>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <ChatInput />
    </div>
  );
}
