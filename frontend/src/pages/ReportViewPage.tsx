import { useEffect, useState } from 'react';
import { Spin, Result, Button, Breadcrumb } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { FileTextOutlined } from '@ant-design/icons';
import { reportApi } from '../api/report';
import type { ReportDetail } from '../types';
import { ApiError } from '../api/client';
import ResultBody from '../components/ResultBody';

export default function ReportViewPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setNotFound(false);
    reportApi
      .get(id)
      .then((d) => setData(d))
      .catch((e) => {
        if (e instanceof ApiError && e.httpStatus === 404) {
          setNotFound(true);
        }
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} />;

  if (notFound) {
    return (
      <Result
        status="404"
        title="报表不存在"
        extra={
          <Button type="primary" onClick={() => navigate('/reports')}>
            返回列表
          </Button>
        }
      />
    );
  }

  if (!data) return null;

  return (
    <div className="page-wrap">
      <Breadcrumb
        style={{ marginBottom: 14, fontSize: 12 }}
        items={[
          { title: <a onClick={() => navigate('/reports')}>报表</a> },
          { title: data.name },
        ]}
      />

      <div className="assistant-card" style={{ maxWidth: 960 }}>
        <div className="result-card-head">
          <div className="result-head-left">
            <span className="result-head-icon">
              <FileTextOutlined />
            </span>
            <span style={{ fontSize: 15 }}>{data.name}</span>
            <span className="chip chip-accent">只读快照</span>
          </div>
        </div>
        {data.question && (
          <div style={{ color: '#64748b', marginBottom: 12, fontSize: 12 }}>
            来源问题：{data.question}
          </div>
        )}
        <ResultBody result={data.result} />
      </div>
    </div>
  );
}
