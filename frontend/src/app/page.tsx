"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import SummaryChart from "@/components/SummaryChart";
import api from "@/lib/api";

type User = { user_id: number; name: string; email: string };
type Category = { category_id: number; name: string; type: "income" | "expense" | "both" };
type Transaction = {
  transaction_id: number;
  amount: number;
  type: "income" | "expense";
  description?: string;
  date: string;
};
type Summary = { total_income: number; total_expense: number; balance: number; transaction_count: number };
type Insight = { insight_id: number; title: string; message: string; severity: string };

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [error, setError] = useState<string>("");

  const [registerForm, setRegisterForm] = useState({ name: "", email: "", password: "" });
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [categoryForm, setCategoryForm] = useState({ name: "", type: "expense" as "income" | "expense" | "both" });
  const [txForm, setTxForm] = useState({
    category_id: "",
    amount: "",
    type: "expense" as "income" | "expense",
    description: "",
    date: new Date().toISOString().slice(0, 10),
  });

  const categoryOptions = useMemo(() => categories.map((c) => ({ id: c.category_id, name: c.name })), [categories]);

  const loadPrivateData = async () => {
    const [catRes, txRes, summaryRes, insightRes] = await Promise.all([
      api.get<Category[]>("/categories"),
      api.get<Transaction[]>("/transactions"),
      api.get<Summary>("/dashboard/summary"),
      api.get<Insight[]>("/ai/insights"),
    ]);
    setCategories(catRes.data);
    setTransactions(txRes.data);
    setSummary(summaryRes.data);
    setInsights(insightRes.data);
  };

  useEffect(() => {
    loadPrivateData().catch(() => {
      // No active session yet.
    });
  }, []);

  const register = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await api.post<User>("/auth/register", registerForm);
      setUser(res.data);
    } catch {
      setError("Registration failed");
    }
  };

  const login = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await api.post<User>("/auth/login", loginForm);
      setUser(res.data);
      await loadPrivateData();
    } catch {
      setError("Login failed");
    }
  };

  const createCategory = async (e: FormEvent) => {
    e.preventDefault();
    await api.post("/categories", categoryForm);
    setCategoryForm({ ...categoryForm, name: "" });
    await loadPrivateData();
  };

  const createTransaction = async (e: FormEvent) => {
    e.preventDefault();
    if (!txForm.category_id) return;
    await api.post("/transactions", {
      category_id: Number(txForm.category_id),
      amount: Number(txForm.amount),
      type: txForm.type,
      description: txForm.description || null,
      date: txForm.date,
    });
    setTxForm({ ...txForm, amount: "", description: "" });
    await loadPrivateData();
  };

  const generateInsights = async () => {
    await api.post("/ai/generate");
    await loadPrivateData();
  };

  const exportCsv = async () => {
    const res = await api.get("/transactions/export-csv", { responseType: "blob" });
    const url = URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "transactions.csv");
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const importCsv = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    await api.post("/transactions/import-csv", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    await loadPrivateData();
  };

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <h1 className="text-4xl font-bold">BizMoneyAI</h1>
      {error ? <p className="text-red-600">{error}</p> : null}

      <section className="grid gap-4 md:grid-cols-2">
        <form onSubmit={register} className="space-y-2 rounded-lg bg-white p-4 shadow">
          <h2 className="text-xl font-semibold">Register</h2>
          <input placeholder="Name" value={registerForm.name} onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })} required />
          <input placeholder="Email" type="email" value={registerForm.email} onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })} required />
          <input placeholder="Password" type="password" value={registerForm.password} onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })} required />
          <button type="submit">Create account</button>
        </form>

        <form onSubmit={login} className="space-y-2 rounded-lg bg-white p-4 shadow">
          <h2 className="text-xl font-semibold">Login</h2>
          <input placeholder="Email" type="email" value={loginForm.email} onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })} required />
          <input placeholder="Password" type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} required />
          <button type="submit">Login</button>
        </form>
      </section>

      {user ? <p className="text-sm">Signed in as {user.name}</p> : null}

      <section className="grid gap-4 md:grid-cols-2">
        <form onSubmit={createCategory} className="space-y-2 rounded-lg bg-white p-4 shadow">
          <h2 className="text-xl font-semibold">New Category</h2>
          <input placeholder="Category name" value={categoryForm.name} onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })} required />
          <select value={categoryForm.type} onChange={(e) => setCategoryForm({ ...categoryForm, type: e.target.value as "income" | "expense" | "both" })}>
            <option value="income">income</option>
            <option value="expense">expense</option>
            <option value="both">both</option>
          </select>
          <button type="submit">Save category</button>
        </form>

        <form onSubmit={createTransaction} className="space-y-2 rounded-lg bg-white p-4 shadow">
          <h2 className="text-xl font-semibold">New Transaction</h2>
          <select value={txForm.category_id} onChange={(e) => setTxForm({ ...txForm, category_id: e.target.value })} required>
            <option value="">Select category</option>
            {categoryOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input placeholder="Amount" type="number" step="0.01" value={txForm.amount} onChange={(e) => setTxForm({ ...txForm, amount: e.target.value })} required />
          <select value={txForm.type} onChange={(e) => setTxForm({ ...txForm, type: e.target.value as "income" | "expense" })}>
            <option value="income">income</option>
            <option value="expense">expense</option>
          </select>
          <input placeholder="Description" value={txForm.description} onChange={(e) => setTxForm({ ...txForm, description: e.target.value })} />
          <input type="date" value={txForm.date} onChange={(e) => setTxForm({ ...txForm, date: e.target.value })} required />
          <button type="submit">Save transaction</button>
        </form>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-sm">Income</p>
          <p className="text-2xl font-bold">{summary?.total_income ?? 0}</p>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-sm">Expense</p>
          <p className="text-2xl font-bold">{summary?.total_expense ?? 0}</p>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <p className="text-sm">Balance</p>
          <p className="text-2xl font-bold">{summary?.balance ?? 0}</p>
        </div>
      </section>

      <SummaryChart income={summary?.total_income ?? 0} expense={summary?.total_expense ?? 0} />

      <section className="space-y-2 rounded-lg bg-white p-4 shadow">
        <h2 className="text-xl font-semibold">Transactions ({transactions.length})</h2>
        <div className="flex gap-2">
          <button type="button" onClick={exportCsv}>Export CSV</button>
          <label className="cursor-pointer bg-ink px-3 py-2 text-white">
            Import CSV
            <input
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) importCsv(f);
              }}
            />
          </label>
        </div>
        <ul className="space-y-1 text-sm">
          {transactions.slice(0, 10).map((tx) => (
            <li key={tx.transaction_id}>
              {tx.date} | {tx.type} | {tx.amount} | {tx.description || "-"}
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2 rounded-lg bg-white p-4 shadow">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">AI Insights</h2>
          <button type="button" onClick={generateInsights}>Generate</button>
        </div>
        <ul className="space-y-2">
          {insights.map((ins) => (
            <li key={ins.insight_id} className="rounded border border-slate-200 p-2">
              <p className="font-semibold">{ins.title} ({ins.severity})</p>
              <p>{ins.message}</p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
