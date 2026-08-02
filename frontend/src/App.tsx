import { FormEvent, useEffect, useState } from 'react'
import { api, apiBase, Dashboard, setApiBase, Task } from './api'

const stages = ['Orchestrator', 'Planner', 'Researcher', 'Reviewer', 'Summarizer']

export default function App() {
  const [endpoint, setEndpoint] = useState(apiBase)
  const [sessionId, setSessionId] = useState('')
  const [title, setTitle] = useState('Product research')
  const [prompt, setPrompt] = useState('Compare durable agent-memory strategies and produce a rollout plan.')
  const [query, setQuery] = useState('durable agent memory')
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async (id = sessionId) => { if (!id) return; setBusy(true); try { setData(await api.dashboard(id)); setError('') } catch (e) { setError(String(e)) } finally { setBusy(false) } }
  useEffect(() => { void load() }, [])
  const connect = async (event: FormEvent) => { event.preventDefault(); setApiBase(endpoint); try { await api.health(); setError(''); } catch(e) { setError(`API unavailable: ${String(e)}`) } }
  const create = async (event: FormEvent) => { event.preventDefault(); setBusy(true); try { const session = await api.createSession(title); const task = await api.createTask(session.id, prompt); setSessionId(session.id); setData({session, tasks:[task], memories:[], events:[], retrieval:[], graph:{nodes:[],edges:[]}, system:{mock_llm:true,database:'connecting'}}); setError('') } catch(e) { setError(String(e)) } finally { setBusy(false) } }
  const act = async (action: (task:Task)=>Promise<unknown>) => { const task=data?.tasks[0]; if (!task) return; setBusy(true); try { await action(task); await load(); } catch(e) { setError(String(e)) } finally { setBusy(false) } }
  const search = async (event: FormEvent) => { event.preventDefault(); if (!sessionId) return; setBusy(true); try { const result = await api.search(sessionId, query); setData(current => current ? {...current, retrieval:result.results} : current) } catch(e) { setError(String(e)) } finally { setBusy(false) } }

  return <main>
    <header><div><p className="eyebrow">COCKROACHDB × AWS</p><h1>MemoryGraph <span>AI</span></h1></div><div className="status"><i /> {busy ? 'working' : data ? 'connected' : 'awaiting API'}</div></header>
    <p className="intro">A live dashboard for durable multi-agent work. Each step is persisted before the next agent begins.</p>
    <section className="panel setup"><form onSubmit={connect}><label>API endpoint<input value={endpoint} onChange={e=>setEndpoint(e.target.value)} placeholder="https://your-api.example.com" /></label><button>Connect</button></form><small>For local Docker, leave blank. GitHub Pages uses the deployed Lambda/API Gateway endpoint.</small></section>
    <section className="grid">
      <form className="panel" onSubmit={create}><h2>Start session</h2><label>Title<input value={title} onChange={e=>setTitle(e.target.value)} /></label><label>Task prompt<textarea value={prompt} onChange={e=>setPrompt(e.target.value)} /></label><button disabled={busy}>Create durable task</button></form>
      <section className="panel"><h2>System status</h2>{data ? <dl>{Object.entries(data.system).map(([k,v])=><div key={k}><dt>{k.replace('_',' ')}</dt><dd>{String(v)}</dd></div>)}</dl> : <p>Connect an API, then create a session.</p>}</section>
    </section>
    {error && <p className="error">{error}</p>}
    {data && <>
      <section className="panel task"><div><p className="eyebrow">SESSION {sessionId.slice(0,8)}</p><h2>{data.session.title}</h2><p>{data.tasks[0]?.prompt}</p></div><div className="actions"><button onClick={()=>act(t=>api.run(t.id))} disabled={busy || data.tasks[0]?.state==='completed'}>Run next agent</button><button className="quiet" onClick={()=>act(t=>api.stop(t.id))}>Stop</button><button className="quiet" onClick={()=>act(t=>api.resume(t.id))}>Resume</button></div></section>
      <section className="panel"><h2>Agent state</h2><div className="stages">{stages.map((stage,index)=><div className={index < (data.tasks[0]?.next_agent_index||0) ? 'done' : ''} key={stage}><b>{index+1}</b>{stage}</div>)}</div></section>
      <section className="grid lower"><section className="panel"><h2>Persistent memories</h2>{data.memories.map(memory=><article className="memory" key={memory.id}><b>{memory.agent_name}</b><span>{memory.content}</span></article>) || <p>No memories yet.</p>}</section><section className="panel"><h2>Semantic retrieval</h2><form className="search" onSubmit={search}><input value={query} onChange={e=>setQuery(e.target.value)} /><button>Search</button></form>{data.retrieval.map(memory=><article className="memory" key={memory.id}><b>{memory.agent_name} <em>{memory.score?.toFixed(3)}</em></b><span>{memory.content}</span></article>)}</section></section>
      <section className="panel"><h2>Memory graph relations</h2><div className="graph">{data.graph.edges.map((edge,index)=><div key={`${edge.source}-${edge.target}`}><code>{edge.source.replace(/.*:/,'')}</code><span> —{edge.type}→ </span><code>{edge.target.replace(/.*:/,'')}</code></div>)}</div></section>
    </>}
  </main>
}
