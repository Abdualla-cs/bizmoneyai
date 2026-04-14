"use client";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
type MonthlyTrend = { month: string; income: number; expense: number };
export default function MonthlyTrendChart({ data }: { data: MonthlyTrend[] }) {
  if (!data?.length) return (
    <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-400">No trend data yet</div>
  );
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="income" stroke="#34d399" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="expense" stroke="#f87171" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
