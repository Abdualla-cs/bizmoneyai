import { createClient } from "@/utils/supabase/server";
import { isSupabaseConfigured } from "@/utils/supabase/config";

type Todo = {
  id: number;
  name: string;
};

export default async function SupabaseExamplePage() {
  if (!isSupabaseConfigured) {
    return (
      <main className="mx-auto max-w-3xl space-y-6 p-6">
        <div>
          <h1 className="text-3xl font-bold text-ink">Supabase Example</h1>
          <p className="text-sm text-slate-500">
            This optional demo is disabled because Supabase frontend env vars are not configured.
          </p>
        </div>
      </main>
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase.from("todos").select("id, name").returns<Todo[]>();

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">Supabase Example</h1>
        <p className="text-sm text-slate-500">
          This page uses the SSR Supabase client so you can confirm the frontend integration is working.
        </p>
      </div>

      {error ? (
        <div className="rounded-lg bg-red-100 px-4 py-3 text-sm text-red-700">
          Failed to load `todos`: {error.message}
        </div>
      ) : data && data.length > 0 ? (
        <ul className="space-y-3">
          {data.map((todo) => (
            <li key={todo.id} className="rounded-xl bg-white p-4 shadow">
              {todo.name}
            </li>
          ))}
        </ul>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-sm text-slate-500">
          No rows found in `todos`. Create the table in Supabase if you want to test this sample route.
        </div>
      )}
    </main>
  );
}
