import { Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/AppLayout';
import ChatPage from './pages/ChatPage';
import ReportsPage from './pages/ReportsPage';
import ReportViewPage from './pages/ReportViewPage';
import LoginPage from './pages/LoginPage';

// 全局主题：对齐 prismbi 的浅 slate + 青色强调
const theme = {
  token: {
    colorPrimary: '#0891b2',
    colorInfo: '#0891b2',
    colorSuccess: '#059669',
    colorWarning: '#d97706',
    colorError: '#e11d48',
    colorText: '#334155',
    colorTextHeading: '#0f172a',
    colorBorder: '#e2e8f0',
    colorBorderSecondary: '#f1f5f9',
    borderRadius: 10,
    borderRadiusLG: 12,
    fontFamily:
      "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    fontSize: 13,
    controlHeight: 34,
    boxShadowSecondary: '0 6px 18px rgba(15, 23, 42, 0.08)',
  },
  components: {
    Table: {
      headerBg: '#f8fafc',
      headerColor: '#475569',
      headerSplitColor: 'transparent',
      rowHoverBg: '#f8fafc',
      cellPaddingBlockSM: 8,
      borderColor: '#f1f5f9',
    },
    Button: {
      fontWeight: 500,
      defaultShadow: 'none',
      primaryShadow: 'none',
    },
    Input: {
      activeShadow: '0 0 0 3px rgba(8, 145, 178, 0.1)',
    },
    Modal: {
      borderRadiusLG: 16,
    },
    Pagination: {
      itemSize: 26,
    },
  },
};

export default function App() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:id" element={<ReportViewPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Route>
      </Routes>
    </ConfigProvider>
  );
}
