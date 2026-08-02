export type Task = { id: string; session_id: string; prompt: string; state: string; next_agent_index: number }
export type Memory = { id: string; agent_name: string; content: string; created_at: string; score?: number }
export type Dashboard = { session: {id:string;title:string}; tasks: Task[]; memories: Memory[]; events: {agent_name:string;event_type:string;created_at:string}[]; retrieval: Memory[]; graph: {nodes:{id:string;label:string;type:string}[];edges:{source:string;target:string;type:string}[]}; system: Record<string, string|boolean> }

const initial = (import.meta.env.VITE_API_BASE_URL as string | undefined) || localStorage.getItem('memorygraph-api') || ''
export let apiBase = initial.replace(/\/$/, '')
export const setApiBase = (value: string) => { apiBase = value.replace(/\/$/, ''); localStorage.setItem('memorygraph-api', apiBase) }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { headers: {'Content-Type':'application/json'}, ...options })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{status:string}>('/health'),
  createSession: (title:string) => request<{id:string;title:string}>('/api/sessions', {method:'POST', body:JSON.stringify({title})}),
  createTask: (sessionId:string,prompt:string) => request<Task>(`/api/sessions/${sessionId}/tasks`, {method:'POST', body:JSON.stringify({prompt})}),
  dashboard: (id:string) => request<Dashboard>(`/api/sessions/${id}/dashboard`),
  run: (id:string) => request<Task>(`/api/tasks/${id}/run-step`, {method:'POST'}),
  stop: (id:string) => request<Task>(`/api/tasks/${id}/stop`, {method:'POST'}),
  resume: (id:string) => request<Task>(`/api/tasks/${id}/resume`, {method:'POST'}),
  search: (session:string,q:string) => request<{results:Memory[]}>(`/api/sessions/${session}/memories/search?query=${encodeURIComponent(q)}`),
}
