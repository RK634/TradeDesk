import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, CheckCircle2, Circle, Clock3, MessageSquare, Plus, RefreshCw, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { getMembers } from '@/features/organizations/api'
import { addTaskComment, createTask, getTask, listTasks, updateTaskStatus } from '@/features/workflow/api'
import type { TaskPriority, TaskStatus } from '@/features/workflow/types'
import { useOutletContext } from 'react-router-dom'

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100'
const statusLabels: Record<TaskStatus, string> = { open: 'Open', in_progress: 'In progress', blocked: 'Blocked', completed: 'Completed', cancelled: 'Cancelled' }
const priorityColors: Record<TaskPriority, string> = { low: 'bg-slate-100 text-slate-600', normal: 'bg-sky-50 text-sky-700', high: 'bg-amber-50 text-amber-700', urgent: 'bg-rose-50 text-rose-700' }

function dateLabel(value: string | null) {
  if (!value) return 'No due date'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Invalid date' : date.toLocaleString()
}

export function TasksPage() {
  const queryClient = useQueryClient()
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const role = selectedOrganization?.role ?? ''
  const canCreate = ['organization_owner', 'administrator', 'import_manager', 'export_manager'].includes(role)
  const canAssign = ['organization_owner', 'administrator'].includes(role)
  const canUpdate = ['organization_owner', 'administrator', 'import_manager', 'export_manager', 'operations_staff'].includes(role)
  const canComment = role !== 'read_only'

  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [assignedTo, setAssignedTo] = useState('')
  const [priority, setPriority] = useState<TaskPriority>('normal')
  const [dueAt, setDueAt] = useState('')
  const [comment, setComment] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const tasksQuery = useQuery({
    queryKey: ['workflow', 'tasks', selectedOrganizationId, statusFilter],
    queryFn: () => listTasks(selectedOrganizationId, statusFilter),
    enabled: Boolean(selectedOrganizationId), retry: false,
  })
  const membersQuery = useQuery({
    queryKey: ['workflow', 'members', selectedOrganizationId],
    queryFn: () => getMembers(selectedOrganizationId),
    enabled: Boolean(selectedOrganizationId) && canAssign, retry: false,
  })
  const detailQuery = useQuery({
    queryKey: ['workflow', 'task', selectedOrganizationId, selectedTaskId],
    queryFn: () => getTask(selectedOrganizationId, selectedTaskId),
    enabled: Boolean(selectedOrganizationId && selectedTaskId), retry: false,
  })
  const createMutation = useMutation({
    mutationFn: () => createTask(selectedOrganizationId, {
      title: title.trim(), description: description.trim() || null,
      ...(canAssign && assignedTo ? { assigned_to_user_id: assignedTo } : {}),
      priority,
      due_at: dueAt ? new Date(dueAt).toISOString() : null,
    }),
    onSuccess: (task) => {
      setTitle(''); setDescription(''); setAssignedTo(''); setPriority('normal'); setDueAt('')
      setNotice(`Task “${task.title}” was created.`); setError(''); setSelectedTaskId(task.id)
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'tasks', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'task', selectedOrganizationId] })
    },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Task could not be created.'); setNotice('') },
  })
  const statusMutation = useMutation({
    mutationFn: ({ taskId, nextStatus }: { taskId: string; nextStatus: TaskStatus }) => updateTaskStatus(selectedOrganizationId, taskId, nextStatus),
    onSuccess: (task) => {
      setNotice(`Task status changed to ${statusLabels[task.status]}.`); setError('')
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'tasks', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'task', selectedOrganizationId, task.id] })
    },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Task status could not be updated.'); setNotice('') },
  })
  const commentMutation = useMutation({
    mutationFn: () => addTaskComment(selectedOrganizationId, selectedTaskId, comment.trim()),
    onSuccess: () => {
      setComment(''); setNotice('Comment added.'); setError('')
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'task', selectedOrganizationId, selectedTaskId] })
    },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Comment could not be added.'); setNotice('') },
  })

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setNotice(''); setError('')
    if (!title.trim()) { setError('Enter a task title.'); return }
    createMutation.mutate()
  }

  const tasks = tasksQuery.data?.items ?? []
  const selectedTask = detailQuery.data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-sky-700">Work management</p><h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Tasks</h2><p className="mt-1 text-sm text-slate-500">Assign work, track due dates, and keep a clear activity history.</p></div>
        <Button variant="outline" onClick={() => void tasksQuery.refetch()}><RefreshCw size={15} className="mr-2" />Refresh</Button>
      </div>

      {notice && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
      {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      {canCreate && <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Plus size={17} />Create a task</CardTitle><CardDescription>Assign an owner, priority, and due date. Task assignments create an in-app notification.</CardDescription></CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-5" onSubmit={handleCreate}>
            <label className="space-y-1.5 text-xs font-semibold text-slate-600 md:col-span-2 xl:col-span-2">Task title<input className={inputClass} value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={180} placeholder="e.g. Verify import documents" /></label>
            <label className="space-y-1.5 text-xs font-semibold text-slate-600">Priority<select className={inputClass} value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>
            <label className="space-y-1.5 text-xs font-semibold text-slate-600">Due date<input className={inputClass} type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
            {canAssign && <label className="space-y-1.5 text-xs font-semibold text-slate-600">Assign to<select className={inputClass} value={assignedTo} onChange={(event) => setAssignedTo(event.target.value)}><option value="">Unassigned</option>{(membersQuery.data ?? []).filter((member) => member.is_active).map((member) => <option key={member.user_id} value={member.user_id}>{member.full_name} · {member.role.replaceAll('_', ' ')}</option>)}</select></label>}
            <label className="space-y-1.5 text-xs font-semibold text-slate-600 md:col-span-2 xl:col-span-4">Description<textarea className={inputClass} rows={2} value={description} onChange={(event) => setDescription(event.target.value)} maxLength={10000} placeholder="Add context, checklist details, or completion criteria…" /></label>
            <div className="flex items-end"><Button type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? 'Creating…' : 'Create task'}</Button></div>
          </form>
        </CardContent>
      </Card>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.85fr)]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3"><div><CardTitle className="text-base">Task register</CardTitle><CardDescription>{tasksQuery.data?.total ?? 0} tasks in this view</CardDescription></div><select aria-label="Filter tasks by status" className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></CardHeader>
          <CardContent className="space-y-2">
            {tasksQuery.isPending && <p className="py-8 text-center text-sm text-slate-500">Loading tasks…</p>}
            {tasksQuery.isError && <p role="alert" className="py-8 text-center text-sm text-rose-600">{tasksQuery.error instanceof Error ? tasksQuery.error.message : 'Tasks could not be loaded.'}</p>}
            {!tasksQuery.isPending && !tasksQuery.isError && tasks.length === 0 && <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center"><Circle className="mx-auto text-slate-300" size={25} /><p className="mt-2 text-sm font-semibold text-slate-700">No tasks found</p><p className="mt-1 text-xs text-slate-500">Create a task to coordinate the next action.</p></div>}
            {tasks.map((task) => <button key={task.id} type="button" onClick={() => setSelectedTaskId(task.id)} className={`w-full rounded-xl border p-3 text-left transition hover:border-sky-300 hover:bg-sky-50/40 ${selectedTaskId === task.id ? 'border-sky-400 bg-sky-50/60' : 'border-slate-200 bg-white'}`}>
              <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{task.title}</p><p className="mt-1 text-xs text-slate-500">{task.assigned_to_name ? `Assigned to ${task.assigned_to_name}` : 'Unassigned'} · Due {dateLabel(task.due_at)}</p></div><span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-bold ${priorityColors[task.priority]}`}>{task.priority}</span></div>
              <div className="mt-3 flex items-center justify-between gap-2"><span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-600">{task.status === 'completed' ? <CheckCircle2 size={13} className="text-emerald-600" /> : <Clock3 size={13} />}{statusLabels[task.status]}</span><span className="text-[10px] text-slate-400">Created by {task.created_by_name}</span></div>
            </button>)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Task activity</CardTitle><CardDescription>{selectedTask ? selectedTask.title : 'Select a task to review comments and completion history.'}</CardDescription></CardHeader>
          <CardContent className="space-y-5">
            {!selectedTaskId && <div className="rounded-xl bg-slate-50 p-8 text-center text-sm text-slate-500">Choose a task from the register.</div>}
            {selectedTaskId && detailQuery.isPending && <p className="text-sm text-slate-500">Loading task activity…</p>}
            {selectedTask && <>
              <div className="flex flex-wrap gap-2">
                {canUpdate && selectedTask.status !== 'completed' && selectedTask.status !== 'cancelled' && <>
                  {selectedTask.status !== 'in_progress' && <Button size="sm" variant="outline" onClick={() => statusMutation.mutate({ taskId: selectedTask.id, nextStatus: 'in_progress' })} disabled={statusMutation.isPending}>Start</Button>}
                  {selectedTask.status !== 'blocked' && <Button size="sm" variant="outline" onClick={() => statusMutation.mutate({ taskId: selectedTask.id, nextStatus: 'blocked' })} disabled={statusMutation.isPending}>Block</Button>}
                  <Button size="sm" onClick={() => statusMutation.mutate({ taskId: selectedTask.id, nextStatus: 'completed' })} disabled={statusMutation.isPending}>Complete</Button>
                </>}
                {canUpdate && selectedTask.status === 'blocked' && <Button size="sm" variant="outline" onClick={() => statusMutation.mutate({ taskId: selectedTask.id, nextStatus: 'open' })}>Reopen</Button>}
                {canUpdate && selectedTask.status === 'completed' && <Button size="sm" variant="outline" onClick={() => statusMutation.mutate({ taskId: selectedTask.id, nextStatus: 'in_progress' })}>Reopen task</Button>}
              </div>
              {canComment && <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); if (comment.trim()) commentMutation.mutate() }}><input className={inputClass} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a comment…" maxLength={4000} /><Button type="submit" disabled={commentMutation.isPending || !comment.trim()}><MessageSquare size={15} /></Button></form>}
              <section><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Comments</h3>{selectedTask.comments.length === 0 ? <p className="text-xs text-slate-400">No comments yet.</p> : <div className="space-y-3">{selectedTask.comments.map((row) => <div key={row.id} className="rounded-lg bg-slate-50 p-3"><div className="flex justify-between gap-2"><span className="text-xs font-semibold text-slate-700">{row.author_name}</span><span className="text-[10px] text-slate-400">{new Date(row.created_at).toLocaleString()}</span></div><p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{row.body}</p></div>)}</div>}</section>
              <section><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Completion history</h3>{selectedTask.history.length === 0 ? <p className="text-xs text-slate-400">No history has been recorded.</p> : <ol className="space-y-3 border-l border-slate-200 pl-4">{selectedTask.history.map((row) => <li key={row.id} className="relative"><span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-sky-500 ring-1 ring-sky-200" /><p className="text-xs font-semibold text-slate-700">{row.from_status ? `${statusLabels[row.from_status as TaskStatus] ?? row.from_status} → ` : ''}{statusLabels[row.to_status as TaskStatus] ?? row.to_status}</p><p className="mt-0.5 text-[10px] text-slate-400">{row.actor_name} · {new Date(row.created_at).toLocaleString()}</p>{row.note && <p className="mt-1 text-xs text-slate-600">{row.note}</p>}</li>)}</ol>}</section>
              <div className="flex items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500"><UserRound size={14} /> Created by {selectedTask.created_by_name}<span className="ml-auto inline-flex items-center gap-1"><CalendarClock size={13} />{dateLabel(selectedTask.due_at)}</span></div>
            </>}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
