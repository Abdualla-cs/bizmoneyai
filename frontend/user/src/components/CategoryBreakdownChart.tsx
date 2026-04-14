"use client";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
type CategoryBreakdown = { category_name: string; total: number };
const COLORS = ["#0f172a","#34d399","#f87171","#60a5fa","#fbbf24","#a78bfa","#fb923c"];
export default function CategoryBreakdownChart({ data }: { data: CategoryBreakdown[] }) {
  if (!data?.length) return (
    <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-400">No expense data yet</div>
  );
  const pieData = data.map(d => ({ name: d.category_name, value: d.total }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={90} label>
            {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
