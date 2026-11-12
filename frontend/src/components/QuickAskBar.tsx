interface Props {
  onPick: (q: string) => void;
}

export const QUICK_QUESTIONS = [
  { label: '渠道表现', q: '最近一周各渠道 GMV 是多少' },
  { label: '转化效率', q: '最近一周的 ACOS 是多少' },
  { label: '商品退货', q: '本月退货率最高的 5 个类目' },
  { label: '用户结构', q: '新老客 GMV 占比' },
];

export default function QuickAskBar({ onPick }: Props) {
  return (
    <div className="quick-ask-bar">
      {QUICK_QUESTIONS.map((item) => (
        <div key={item.q} className="quick-card" onClick={() => onPick(item.q)}>
          <div className="quick-card-label">
            <span>{item.label}</span>
            <span className="quick-card-arrow">↗</span>
          </div>
          <div className="quick-card-query">{item.q}</div>
        </div>
      ))}
    </div>
  );
}
