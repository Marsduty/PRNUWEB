"use client";

import ReactECharts from "echarts-for-react";

type DistributionChartProps = {
  data: Array<{ name: string; value: number }>;
};

export function DistributionChart({ data }: DistributionChartProps) {
  if (data.length === 0) {
    return <div className="grid h-[260px] place-items-center text-sm text-sky-200">暂无设备分布数据</div>;
  }

  const sortedData = [...data].sort((a, b) => b.value - a.value);
  const total = sortedData.reduce((sum, item) => sum + item.value, 0);
  const colors = ["#1f8bff", "#10d6ff", "#45e58d", "#f5c84b", "#ff6b6b", "#9b8cff", "#2c8cff", "#26d3ea", "#34de7b", "#e6b940", "#ff8a5c", "#7aa7ff"];
  const percentOf = (value: number) => (total > 0 ? (value / total) * 100 : 0);
  const brandLabel = (name: string) => {
    const item = sortedData.find((entry) => entry.name === name);
    const value = item?.value ?? 0;
    const percent = percentOf(value).toFixed(1);
    return `${name}  ${value} 台 (${percent}%)`;
  };
  const chartData = sortedData.map((item, index) => {
    const showInsideLabel = index < 6 && percentOf(item.value) >= 4;
    return {
      ...item,
      label: { show: showInsideLabel }
    };
  });

  const option = {
    color: colors,
    tooltip: {
      trigger: "item",
      formatter: ({ name, value, percent }: { name: string; value: number; percent: number }) =>
        `${name}<br/>${value} 台 / ${percent}%`
    },
    series: [
      {
        name: "设备品牌分布",
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "52%"],
        avoidLabelOverlap: true,
        label: {
          show: true,
          position: "inside",
          formatter: "{d}%",
          color: "#ffffff",
          fontSize: 11,
          fontWeight: 700
        },
        labelLine: {
          show: false
        },
        data: chartData
      }
    ]
  };

  return (
    <div className="distribution-chart">
      <div className="distribution-chart-canvas">
        <ReactECharts option={option} style={{ height: 280, width: "100%" }} />
      </div>
      <div className="distribution-legend" aria-label="设备品牌分布明细">
        {sortedData.map((item, index) => (
          <div className="distribution-legend-item" key={item.name} title={brandLabel(item.name)}>
            <span className="distribution-legend-swatch" style={{ backgroundColor: colors[index % colors.length] }} />
            <span>{brandLabel(item.name)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
