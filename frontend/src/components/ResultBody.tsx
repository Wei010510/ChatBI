import { Table, Alert } from 'antd';
import { BarChartOutlined, LineChartOutlined, BulbOutlined, TableOutlined } from '@ant-design/icons';
import ChartView from './ChartView';
import type { ResultBody } from '../types';

interface Props {
  result: ResultBody;
}

const RATE_HINTS = ['rate', 'ratio', 'share', 'growth', '增长', '占比', 'yoy', '同比'];

// 数值列格式化：比率类按百分比，其余千分位；空值用 —（SDD-前端 §3.3 表格）
function formatCell(value: unknown, column: ResultBody['columns'][number]) {
  if (value === null || value === undefined || value === '') return '—';
  if (column.type !== 'number') return String(value);
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  const hint = `${column.key} ${column.title}`.toLowerCase();
  if (RATE_HINTS.some((h) => hint.includes(h)) && Math.abs(num) <= 1) {
    return `${(num * 100).toFixed(2)}%`;
  }
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
}

// 结果体：表格 → 图表 → 解读。空数据/截断提示。
export default function ResultBody({ result }: Props) {
  const { columns, rows, narrative, truncated } = result;

  const tableColumns = columns.map((c) => ({
    title: c.title,
    dataIndex: c.key,
    key: c.key,
    width: 140,
    render: (value: unknown) => formatCell(value, c),
  }));

  return (
    <div>
      {truncated && (
        <Alert
          message="结果超过 1000 行，仅展示前 1000 行"
          type="warning"
          showIcon
          style={{ marginBottom: 12, borderRadius: 10 }}
        />
      )}

      <div className="result-section-title">
        <TableOutlined /> 数据表
      </div>
      <div className="surface" style={{ padding: 4, overflow: 'hidden' }}>
        <Table
          size="small"
          columns={tableColumns}
          dataSource={rows.map((r, i) => ({ ...r, key: i }))}
          pagination={rows.length > 10 ? { pageSize: 10, size: 'small' } : false}
          scroll={{ y: 300 }}
        />
      </div>

      {rows.length === 0 && (
        <Alert
          message="该条件下暂无数据"
          description="可尝试调整时间范围或更换分析维度"
          type="info"
          showIcon
          style={{ marginTop: 12, borderRadius: 10 }}
        />
      )}

      {rows.length > 0 && result.chart && (
        <>
          <div className="result-section-title">
            {result.chart.type === 'bar' ? <BarChartOutlined /> : <LineChartOutlined />} 可视化
          </div>
          <div className="chart-frame">
            <ChartView result={result} />
          </div>
        </>
      )}

      {narrative && (
        <div className="narrative-line">
          <BulbOutlined style={{ marginRight: 6, color: '#0891b2' }} />
          {narrative}
        </div>
      )}
    </div>
  );
}
