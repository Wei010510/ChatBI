import { useState } from 'react';
import { Table, Button, Input, Popconfirm, message } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useReportStore } from '../store/reportStore';
import type { ReportListItem } from '../types';

interface Props {
  data: ReportListItem[];
  total: number;
  loading: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

// 报表列表：名称/来源问题/created_at 倒序，分页 20；行内改名、Popconfirm 删除
export default function ReportTable({ data, total, loading, page, onPageChange }: Props) {
  const navigate = useNavigate();
  const remove = useReportStore((s) => s.remove);
  const rename = useReportStore((s) => s.rename);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  const startEdit = (record: ReportListItem) => {
    setEditingId(record.id);
    setEditName(record.name);
  };

  const confirmEdit = async (id: string) => {
    if (!editName.trim()) return;
    const ok = await rename(id, editName.trim());
    if (ok) {
      setEditingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await remove(id);
    if (ok) message.success('已删除');
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ReportListItem) =>
        editingId === record.id ? (
          <Input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onPressEnter={() => confirmEdit(record.id)}
            onBlur={() => confirmEdit(record.id)}
            onKeyDown={(e) => e.key === 'Escape' && setEditingId(null)}
            autoFocus
          />
        ) : (
          <a style={{ fontWeight: 500 }} onClick={() => navigate(`/reports/${record.id}`)}>
            {text}
          </a>
        ),
    },
    { title: '来源问题', dataIndex: 'question', key: 'question', ellipsis: true },
    {
      title: '保存时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--muted)' }}>
          {new Date(v).toLocaleString()}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: unknown, record: ReportListItem) => (
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => startEdit(record)}
          />
          <Popconfirm
            title="删除后不可恢复"
            okText="删除"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </div>
      ),
    },
  ];

  return (
    <Table
      rowKey="id"
      columns={columns}
      dataSource={data}
      loading={loading}
      rowClassName="report-row"
      style={{ background: 'transparent' }}
      pagination={{
        current: page,
        pageSize: 20,
        total,
        onChange: onPageChange,
        hideOnSinglePage: true,
      }}
      onRow={(record) => ({
        onClick: () => {
          if (editingId !== record.id) navigate(`/reports/${record.id}`);
        },
      })}
    />
  );
}
