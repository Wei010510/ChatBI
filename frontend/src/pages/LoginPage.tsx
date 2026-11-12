import { Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import { MessageOutlined } from '@ant-design/icons';

export default function LoginPage() {
  const navigate = useNavigate();
  return (
    <div className="welcome-wrap" style={{ minHeight: '100vh' }}>
      <div className="welcome-logo">
        <span className="welcome-logo-inner">
          <MessageOutlined />
        </span>
      </div>
      <div className="welcome-title">本版无需登录</div>
      <div className="welcome-sub">
        直接进入对话即可使用。当前环境以固定用户身份访问数据仓库。
      </div>
      <Button
        type="primary"
        size="large"
        style={{ marginTop: 12, borderRadius: 10 }}
        onClick={() => navigate('/')}
      >
        进入对话
      </Button>
    </div>
  );
}
