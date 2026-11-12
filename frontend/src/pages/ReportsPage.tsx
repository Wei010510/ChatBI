import { useEffect, useState } from 'react';
import { Empty, Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import { BookOutlined, PlusOutlined } from '@ant-design/icons';
import { useReportStore } from '../store/reportStore';
import ReportTable from '../components/ReportTable';

export default function ReportsPage() {
  const navigate = useNavigate();
  const list = useReportStore((s) => s.list);
  const total = useReportStore((s) => s.total);
  const loading = useReportStore((s) => s.loading);
  const fetchList = useReportStore((s) => s.fetchList);
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchList(page, 20);
  }, [fetchList, page]);

  return (
    <div className="page-wrap">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className="page-title">
            <BookOutlined style={{ color: '#0891b2', marginRight: 8 }} />
            报表
          </h2>
          <div className="page-sub">已保存的查询结果，重开为只读快照，不重新查库</div>
        </div>
        <Button icon={<PlusOutlined />} onClick={() => navigate('/')} style={{ borderRadius: 10 }}>
          新建查询
        </Button>
      </div>

      {list.length === 0 && !loading ? (
        <div className="surface" style={{ padding: 48 }}>
          <Empty description="还没有保存的报表">
            <Button type="primary" onClick={() => navigate('/')}>
              去提问
            </Button>
          </Empty>
        </div>
      ) : (
        <div className="surface" style={{ padding: 6, overflow: 'hidden' }}>
          <ReportTable
            data={list}
            total={total}
            loading={loading}
            page={page}
            onPageChange={setPage}
          />
        </div>
      )}
    </div>
  );
}
