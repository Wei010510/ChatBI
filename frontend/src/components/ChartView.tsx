import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { ResultBody } from '../types';

interface Props {
  result: ResultBody;
}

const PALETTE = ['#0891b2', '#4f46e5', '#f59e0b', '#10b981', '#f43f5e'];

// 按 result.chart 渲染 bar/line，x_field=null 用 ['当前值']，null 不渲染，异常降级表格
export default function ChartView({ result }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const { chart, rows } = result;
  const visible = !!chart && rows.length > 0;

  useEffect(() => {
    if (!visible || !ref.current) return;
    try {
      const xData = chart!.x_field
        ? rows.map((r) => String(r[chart!.x_field!] ?? ''))
        : ['当前值'];

      const series = chart!.series.map((s, idx) => {
        const color = PALETTE[idx % PALETTE.length];
        const base = {
          name: s.name,
          type: chart!.type as 'bar' | 'line',
          data: rows.map((r) => r[s.key]),
          itemStyle: { color },
        };
        if (chart!.type === 'bar') {
          return {
            ...base,
            itemStyle: { color, borderRadius: [6, 6, 0, 0] },
            barMaxWidth: 42,
          };
        }
        return {
          ...base,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { width: 2.5, color },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}33` },
              { offset: 1, color: `${color}00` },
            ]),
          },
        };
      });

      const option = {
        color: PALETTE,
        textStyle: {
          fontFamily:
            "'Plus Jakarta Sans', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(15, 23, 42, 0.92)',
          borderWidth: 0,
          padding: [8, 12],
          textStyle: { color: '#e2e8f0', fontSize: 12 },
          axisPointer: { type: chart!.type === 'bar' ? 'shadow' : 'line' },
        },
        legend:
          chart!.series.length > 1
            ? {
                top: 0,
                right: 8,
                icon: 'roundRect',
                itemWidth: 10,
                itemHeight: 10,
                textStyle: { color: '#64748b', fontSize: 11 },
              }
            : undefined,
        grid: { left: 16, right: 24, top: chart!.series.length > 1 ? 36 : 24, bottom: 8, containLabel: true },
        xAxis: {
          type: 'category',
          data: xData,
          axisLine: { lineStyle: { color: '#e2e8f0' } },
          axisTick: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 11, hideOverlap: true },
        },
        yAxis: {
          type: 'value',
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 11 },
          splitLine: { lineStyle: { color: '#f1f5f9' } },
        },
        series,
      };

      if (!chartRef.current) {
        chartRef.current = echarts.init(ref.current);
      }
      chartRef.current.setOption(option, true);
    } catch {
      // 异常降级：不渲染图表
      if (chartRef.current) {
        chartRef.current.dispose();
        chartRef.current = null;
      }
    }

    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, [chart, rows, visible]);

  useEffect(() => {
    const onResize = () => chartRef.current?.resize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  if (!visible) return null;

  return <div ref={ref} style={{ width: '100%', height: 300 }} />;
}
