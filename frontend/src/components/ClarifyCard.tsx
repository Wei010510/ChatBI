import { useState } from 'react';
import { Input, Alert } from 'antd';
import { QuestionCircleOutlined, CheckCircleFilled, ArrowRightOutlined } from '@ant-design/icons';
import type { Clarify } from '../types';
import { useChatStore } from '../store/chatStore';
import { ApiError } from '../api/client';

interface Props {
  clarify: Clarify;
  sessionId: string;
  messageId: string;
}

// 澄清卡：选项按钮 + 可选自由输入；提交后只读；卡片内不渲染数字
export default function ClarifyCard({ clarify }: Props) {
  const submitClarify = useChatStore((s) => s.submitClarify);
  const [selected, setSelected] = useState<string | null>(null);
  const [freeText, setFreeText] = useState('');
  const [expired, setExpired] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSelect = async (value: string) => {
    if (selected) return;
    setSelected(value);
    setSubmitting(true);
    try {
      await submitClarify(clarify.clarify_id, { value });
    } catch (e) {
      if (e instanceof ApiError && e.code === 'CLARIFY_EXPIRED') {
        setExpired(true);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleFreeSubmit = async () => {
    if (!freeText.trim()) return;
    setSelected(freeText);
    setSubmitting(true);
    try {
      await submitClarify(clarify.clarify_id, { text: freeText.trim() });
    } catch (e) {
      if (e instanceof ApiError && e.code === 'CLARIFY_EXPIRED') {
        setExpired(true);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (expired) {
    return (
      <Alert message="该问题已失效，请重新提问" type="warning" showIcon style={{ borderRadius: 10 }} />
    );
  }

  return (
    <div>
      <div className="result-card-head" style={{ marginBottom: 10 }}>
        <div className="result-head-left">
          <span className="result-head-icon" style={{ background: '#eef2ff', color: '#4f46e5' }}>
            <QuestionCircleOutlined />
          </span>
          <span>需要你确认一下</span>
        </div>
      </div>

      <div style={{ fontSize: 13, color: '#334155', lineHeight: 1.7, marginBottom: 12 }}>
        {clarify.question}
      </div>

      {selected ? (
        <div className="chip chip-ok" style={{ padding: '4px 10px', fontSize: 12 }}>
          <CheckCircleFilled /> 已选择：{selected}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {clarify.options.map((o) => (
              <button
                key={o.value}
                className="btn-ghost"
                style={{ width: 'auto', padding: '7px 12px', borderRadius: 10 }}
                onClick={() => handleSelect(o.value)}
                disabled={submitting}
              >
                {o.label}
                <ArrowRightOutlined style={{ fontSize: 10, opacity: 0.5 }} />
              </button>
            ))}
          </div>
          {clarify.allow_free_text && (
            <div className="chat-input-box" style={{ boxShadow: 'none', maxWidth: '100%' }}>
              <Input
                variant="borderless"
                placeholder="或者直接输入你的答案"
                value={freeText}
                onChange={(e) => setFreeText(e.target.value)}
                onPressEnter={handleFreeSubmit}
                disabled={submitting}
              />
              <button className="chat-send-btn" onClick={handleFreeSubmit} disabled={!freeText.trim()}>
                <ArrowRightOutlined />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
