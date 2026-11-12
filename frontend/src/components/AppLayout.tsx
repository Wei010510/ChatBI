import { useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Popconfirm } from 'antd';
import {
  PlusOutlined,
  BarChartOutlined,
  MessageOutlined,
  DeleteOutlined,
  SearchOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DatabaseOutlined,
  BookOutlined,
  ThunderboltOutlined,
  AimOutlined,
} from '@ant-design/icons';
import { useChatStore } from '../store/chatStore';
import SmartCursor from './SmartCursor';
import { sessionApi } from '../api/session';
import { handleApiError } from '../api/client';
import type { SessionItem } from '../types';

// 会话时间：今天只显示时分，往前带日期
function formatSessionTime(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === new Date().toDateString()) return time;
  const date = d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
  return `${date} ${time}`;
}

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const newSession = useChatStore((s) => s.newSession);
  const loadSession = useChatStore((s) => s.loadSession);
  const sessionId = useChatStore((s) => s.sessionId);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [smartCursorEnabled, setSmartCursorEnabled] = useState(
    () => window.localStorage.getItem('smart_cursor_enabled') === 'true',
  );

  const handleSmartCursorToggle = () => {
    const next = !smartCursorEnabled;
    setSmartCursorEnabled(next);
    window.localStorage.setItem('smart_cursor_enabled', String(next));
  };

  const loadSessions = async () => {
    try {
      const resp = await sessionApi.list(30);
      setSessions(resp.items);
    } catch {
      setSessions([]);
    }
  };

  // sessionId 变化时刷新列表，新建的会话能立刻出现在历史里
  useEffect(() => {
    loadSessions();
  }, [sessionId]);

  const handleNewChat = () => {
    newSession();
    navigate('/');
  };

  const handleOpenSession = (id: string) => {
    navigate('/');
    loadSession(id);
  };

  const handleDelete = async (id: string) => {
    try {
      await sessionApi.remove(id);
      if (sessionId === id) newSession();
      await loadSessions();
    } catch (e) {
      handleApiError(e);
    }
  };

  const handleClearAll = async () => {
    try {
      await sessionApi.removeAll();
      newSession();
      await loadSessions();
    } catch (e) {
      handleApiError(e);
    }
  };

  const current = location.pathname.startsWith('/reports') ? 'reports' : 'chat';
  const filtered = sessions.filter((s) => s.title.toLowerCase().includes(keyword.trim().toLowerCase()));

  return (
    <div className="app-layout">
      <aside className={`app-sidebar${collapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-left">
            <div className="brand-badge">
              <BarChartOutlined />
            </div>
            {!collapsed && (
              <div style={{ minWidth: 0 }}>
                <div className="brand-name">
                  Chat<em>BI</em>
                  <span className="brand-chip">问数</span>
                </div>
              </div>
            )}
          </div>
          <button
            className="collapse-btn"
            title={collapsed ? '展开侧边栏' : '折叠侧边栏'}
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
        </div>

        {!collapsed && (
          <>
            <div className="sidebar-actions">
              <button className="btn-new-chat" onClick={handleNewChat}>
                <PlusOutlined /> 新建对话
              </button>
            </div>

            <div className="sidebar-search">
              <SearchOutlined />
              <input
                placeholder="搜索历史对话..."
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
            </div>
          </>
        )}

        <div className="sidebar-nav">
          <button
            className={`nav-pill${current === 'chat' ? ' active' : ''}`}
            onClick={() => navigate('/')}
          >
            <MessageOutlined /> {!collapsed && '对话'}
          </button>
          <button
            className={`nav-pill${current === 'reports' ? ' active' : ''}`}
            onClick={() => navigate('/reports')}
          >
            <BookOutlined /> {!collapsed && '报表'}
          </button>
        </div>

        <div className="sidebar-list">
          {!collapsed && (
            <div className="sidebar-section-title">
              <span>历史会话</span>
              {sessions.length > 0 && (
                <Popconfirm
                  title="清空全部会话？"
                  description="所有会话及其消息都会删除，不可恢复。"
                  okText="清空"
                  cancelText="取消"
                  onConfirm={handleClearAll}
                >
                  <span className="section-action">清空</span>
                </Popconfirm>
              )}
            </div>
          )}

          {filtered.map((s) => (
            <div
              key={s.id}
              className={`session-item${sessionId === s.id ? ' active' : ''}`}
              onClick={() => handleOpenSession(s.id)}
              title={s.title}
            >
              <MessageOutlined style={{ fontSize: 12, opacity: 0.75, flexShrink: 0 }} />
              {!collapsed && (
                <span className="session-text">
                  <span className="session-title">{s.title}</span>
                  <span className="session-time">{formatSessionTime(s.updated_at)}</span>
                </span>
              )}
              {!collapsed && (
                <span onClick={(e) => e.stopPropagation()} style={{ display: 'inline-flex' }}>
                  <Popconfirm
                    title="删除这个会话？"
                    description="会话内的消息会一起删除，不可恢复。"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={() => handleDelete(s.id)}
                  >
                    <DeleteOutlined className="session-del" />
                  </Popconfirm>
                </span>
              )}
            </div>
          ))}

          {!collapsed && filtered.length === 0 && (
            <div style={{ padding: '24px 8px', textAlign: 'center', fontSize: 12, color: '#94a3b8' }}>
              暂无匹配对话
            </div>
          )}
        </div>

        <div className="sidebar-foot">
          {collapsed ? (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <div className="user-avatar">用</div>
            </div>
          ) : (
            <>
              <div className="foot-status">
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <DatabaseOutlined style={{ color: '#059669' }} />
                  <span style={{ fontFamily: 'var(--font-mono)' }}>数据仓库</span>
                </span>
                <span className="chip chip-ok" style={{ fontSize: 10, padding: '0 6px' }}>
                  已连接
                </span>
              </div>
              <button
                type="button"
                className={`cursor-toggle${smartCursorEnabled ? ' active' : ''}`}
                role="switch"
                aria-checked={smartCursorEnabled}
                aria-label="智能悬浮标"
                title="开启后显示圆形悬浮标与浅色辉光"
                onClick={handleSmartCursorToggle}
              >
                <AimOutlined />
                <span>智能悬浮标</span>
                <span className="cursor-toggle-state">{smartCursorEnabled ? '开启' : '关闭'}</span>
              </button>
              <div className="foot-user">
                <div className="user-avatar">用</div>
                <span style={{ flex: 1 }}>用户</span>
                <ThunderboltOutlined style={{ color: '#0891b2', fontSize: 12 }} />
              </div>
            </>
          )}
        </div>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
      <SmartCursor enabled={smartCursorEnabled} />
    </div>
  );
}
