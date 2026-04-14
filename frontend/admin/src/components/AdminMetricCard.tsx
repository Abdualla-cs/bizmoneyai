type AdminMetricCardProps = {
  label: string;
  value: string;
  tone?: "default" | "success" | "warning" | "danger";
  helper?: string;
};

const toneClasses = {
  default: "from-slate-900 to-slate-700 text-white",
  success: "from-emerald-600 to-teal-600 text-white",
  warning: "from-amber-500 to-orange-500 text-white",
  danger: "from-rose-600 to-pink-600 text-white",
};

export default function AdminMetricCard({
  label,
  value,
  tone = "default",
}: AdminMetricCardProps) {
  return (
    <div className={`rounded-2xl bg-gradient-to-br p-5 shadow-lg shadow-slate-200 ${toneClasses[tone]}`}>
      <p className="text-xs uppercase tracking-[0.24em] text-white/70">{label}</p>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
    </div>
  );
}
