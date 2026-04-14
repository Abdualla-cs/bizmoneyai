"use client";

import { useEffect, useState } from "react";

import Navbar from "@/components/Navbar";
import { useAuth } from "@/hooks/useAuth";
import api from "@/lib/api";

type Category = { category_id: number; name: string; type: "income" | "expense" | "both" };
type Budget = {
  budget_id: number;
  category_id: number;
  category_name: string;
  amount: number;
  spent: number;
  remaining: number;
  status: "on_track" | "near_limit" | "over";
  month: string;
  note: string | null;
  created_at: string;
};
type Form = { category_id: string; amount: string; month: string; note: string };

const EMPTY_MONTH = new Date().toISOString().slice(0, 7);
const EMPTY_FORM: Form = { category_id: "", amount: "", month: EMPTY_MONTH, note: "" };
const DUPLICATE_BUDGET_MESSAGE = "Budget already exists for this category and month";
const STATUS = {
  on_track: "bg-green-100 text-green-700",
  near_limit: "bg-amber-100 text-amber-700",
  over: "bg-red-100 text-red-700",
};

export default function BudgetsPage() {
  const { user, loading } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [form, setForm] = useState<Form>(EMPTY_FORM);
  const [selectedMonth, setSelectedMonth] = useState(EMPTY_MONTH);
  const [editId, setEditId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async (month = selectedMonth) => {
    const monthParam = `${month}-01`;
    const [categoriesResponse, budgetsResponse] = await Promise.all([
      api.get<Category[]>("/categories"),
      api.get<Budget[]>(`/budgets?month=${monthParam}`),
    ]);
    setCategories(categoriesResponse.data.filter((category) => category.type !== "income"));
    setBudgets(budgetsResponse.data);
  };

  useEffect(() => {
    if (!user) return;
    refresh();
  }, [user, selectedMonth]); // eslint-disable-line react-hooks/exhaustive-deps

  const reset = () => {
    setEditId(null);
    setForm({ ...EMPTY_FORM, month: selectedMonth });
    setError("");
  };

  useEffect(() => {
    setForm((current) => ({ ...current, month: selectedMonth }));
  }, [selectedMonth]);

  const save = async () => {
    if (!form.category_id || !form.amount) {
      setError("Category and amount are required.");
      return;
    }

    setBusy(true);
    setError("");
    const payload = {
      category_id: Number(form.category_id),
      amount: Number(form.amount),
      month: `${form.month}-01`,
      note: form.note || null,
    };
    try {
      if (editId !== null) {
        await api.put(`/budgets/${editId}`, payload);
      } else {
        await api.post("/budgets", payload);
      }
      if (form.month !== selectedMonth) {
        setSelectedMonth(form.month);
      }
      reset();
      await refresh(form.month);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to save budget.";
      const message = String(detail);
      if (
        message === DUPLICATE_BUDGET_MESSAGE ||
        message.toLowerCase().includes("already exists for this category and month")
      ) {
        setError(DUPLICATE_BUDGET_MESSAGE);
      } else {
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (budget: Budget) => {
    setEditId(budget.budget_id);
    setForm({
      category_id: String(budget.category_id),
      amount: String(budget.amount),
      month: budget.month.slice(0, 7),
      note: budget.note ?? "",
    });
  };

  const remove = async (budgetId: number) => {
    if (!confirm("Delete this budget?")) return;
    try {
      await api.delete(`/budgets/${budgetId}`);
      await refresh();
    } catch {
      setError("Failed to delete budget.");
    }
  };

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-slate-400">Loading...</div>;
  }

  const totalBudget = budgets.reduce((sum, budget) => sum + budget.amount, 0);
  const totalSpent = budgets.reduce((sum, budget) => sum + budget.spent, 0);
  const totalRemaining = budgets.reduce((sum, budget) => sum + budget.remaining, 0);

  return (
    <>
      <Navbar userName={user?.name} />
      <main className="mx-auto max-w-6xl space-y-8 p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-ink">Budgets</h1>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Month</label>
            <input type="month" value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)} className="text-sm" />
          </div>
        </div>

        {error && <div className="rounded bg-red-100 px-4 py-2 text-sm text-red-700">{error}</div>}

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl bg-white p-5 shadow">
            <p className="text-xs uppercase tracking-wide text-slate-400">Budgeted</p>
            <p className="mt-1 text-2xl font-bold text-ink">${totalBudget.toFixed(2)}</p>
          </div>
          <div className="rounded-xl bg-white p-5 shadow">
            <p className="text-xs uppercase tracking-wide text-slate-400">Spent</p>
            <p className="mt-1 text-2xl font-bold text-red-500">${totalSpent.toFixed(2)}</p>
          </div>
          <div className="rounded-xl bg-white p-5 shadow">
            <p className="text-xs uppercase tracking-wide text-slate-400">Remaining</p>
            <p className={`mt-1 text-2xl font-bold ${totalRemaining >= 0 ? "text-green-600" : "text-red-500"}`}>
              ${Math.abs(totalRemaining).toFixed(2)}
              {totalRemaining < 0 ? " overspent" : ""}
            </p>
          </div>
        </div>

        <div className="rounded-xl bg-white p-6 shadow">
          <h2 className="mb-4 font-semibold">{editId !== null ? "Edit Budget" : "Add Monthly Budget"}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs text-slate-500">Category</label>
              <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })} className="w-full">
                <option value="">Select category</option>
                {categories.map((category) => (
                  <option key={category.category_id} value={category.category_id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">Amount</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="w-full"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">Month</label>
              <input type="month" value={form.month} onChange={(e) => setForm({ ...form, month: e.target.value })} className="w-full" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">Note</label>
              <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className="w-full" />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button onClick={save} disabled={busy}>{editId !== null ? "Update Budget" : "Add Budget"}</button>
            {editId !== null && (
              <button onClick={reset} type="button" className="bg-slate-500">
                Cancel
              </button>
            )}
          </div>
        </div>

        <div className="rounded-xl bg-white shadow overflow-x-auto">
          {budgets.length === 0 ? (
            <p className="p-8 text-center text-sm text-slate-400">No budgets set for this month yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Category</th>
                  <th className="px-4 py-3 text-right">Budget</th>
                  <th className="px-4 py-3 text-right">Spent</th>
                  <th className="px-4 py-3 text-right">Remaining</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Note</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {budgets.map((budget, index) => (
                  <tr key={budget.budget_id} className={index % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                    <td className="px-4 py-3 font-medium">{budget.category_name}</td>
                    <td className="px-4 py-3 text-right">${budget.amount.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right text-red-500">${budget.spent.toFixed(2)}</td>
                    <td className={`px-4 py-3 text-right ${budget.remaining >= 0 ? "text-green-600" : "text-red-500"}`}>
                      ${Math.abs(budget.remaining).toFixed(2)}
                      {budget.remaining < 0 ? " over" : ""}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS[budget.status]}`}>
                        {budget.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{budget.note || "-"}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button onClick={() => startEdit(budget)} className="bg-slate-700 px-3 py-1 text-xs">Edit</button>
                      <button onClick={() => remove(budget.budget_id)} className="bg-red-600 px-3 py-1 text-xs">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </>
  );
}
