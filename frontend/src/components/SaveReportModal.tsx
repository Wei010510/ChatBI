import { useState } from 'react';
import { Modal, Input, Radio, message, Button } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { reportApi } from '../api/report';
import { ApiError } from '../api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  messageId: string;
  defaultName: string;
  chartType?: 'bar' | 'line';
}

// 存报表弹窗：报表名 + 图表类型 bar/line；409 同名给改名/覆盖
export default function SaveReportModal({ open, onClose, messageId, defaultName, chartType }: Props) {
  const [name, setName] = useState(defaultName);
  const [type, setType] = useState<'bar' | 'line'>(chartType || 'bar');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [conflict, setConflict] = useState(false);

  const handleSubmit = async (overwrite = false) => {
    if (!name.trim()) {
      setErrorMsg('请输入报表名');
      return;
    }
    setSubmitting(true);
    setErrorMsg('');
    try {
      await reportApi.create({
        message_id: messageId,
        name: name.trim(),
        chart_type: type,
        overwrite,
      });
      message.success('已存为报表');
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.code === 'REPORT_NAME_EXISTS') {
        setConflict(true);
        setErrorMsg('已存在同名报表');
      } else {
        setErrorMsg((e as Error).message || '保存失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <SaveOutlined style={{ color: 'var(--accent)' }} />
          存为报表
        </span>
      }
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <div className="field-label">报表名</div>
        <Input
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setConflict(false);
            setErrorMsg('');
          }}
          placeholder="请输入报表名"
          onPressEnter={() => handleSubmit(false)}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="field-label">图表类型</div>
        <Radio.Group
          value={type}
          onChange={(e) => setType(e.target.value)}
          optionType="button"
          buttonStyle="solid"
        >
          <Radio.Button value="bar">柱状图</Radio.Button>
          <Radio.Button value="line">折线图</Radio.Button>
        </Radio.Group>
      </div>

      {errorMsg && (
        <div
          style={{
            fontSize: 12,
            color: conflict ? '#b45309' : '#e11d48',
            background: conflict ? '#fffbeb' : 'rgba(225, 29, 72, 0.06)',
            border: `1px solid ${conflict ? '#fde68a' : 'rgba(225, 29, 72, 0.2)'}`,
            borderRadius: 8,
            padding: '8px 10px',
            marginBottom: 16,
          }}
        >
          {errorMsg}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        {conflict ? (
          <>
            <Button onClick={() => setConflict(false)}>改名</Button>
            <Button type="primary" danger loading={submitting} onClick={() => handleSubmit(true)}>
              覆盖
            </Button>
          </>
        ) : (
          <>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" loading={submitting} onClick={() => handleSubmit(false)}>
              保存
            </Button>
          </>
        )}
      </div>
    </Modal>
  );
}
