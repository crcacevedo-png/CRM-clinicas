import { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { LifeBuoy, Send, ArrowLeft, RefreshCw, Building2, User } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS = {
  open: { label: 'Abierto', cls: 'bg-amber-100 text-amber-700' },
  answered: { label: 'Respondido', cls: 'bg-emerald-100 text-emerald-700' },
  closed: { label: 'Cerrado', cls: 'bg-slate-200 text-slate-600' },
};

export default function AdminSupportPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [tickets, setTickets] = useState([]);
  const [summary, setSummary] = useState({});
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = filter !== 'all' ? { status: filter } : {};
      const res = await axios.get(`${API}/admin/support/tickets`, { headers, params });
      setTickets(res.data?.tickets || []);
      setSummary(res.data?.summary || {});
    } catch { toast.error('Error al cargar tickets'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const openTicket = async (t) => {
    setSelected(t);
    try {
      const res = await axios.get(`${API}/admin/support/tickets/${t.id}`, { headers });
      setMessages(res.data?.messages || []);
      setSelected(res.data?.ticket || t);
    } catch { toast.error('Error al abrir el ticket'); }
  };

  const sendReply = async () => {
    if (!reply.trim()) return;
    setSending(true);
    try {
      await axios.post(`${API}/admin/support/tickets/${selected.id}/reply`, { body: reply }, { headers });
      setReply('');
      toast.success('Respuesta enviada (se notificó al usuario por correo)');
      openTicket(selected);
      load();
    } catch { toast.error('No se pudo enviar la respuesta'); }
    finally { setSending(false); }
  };

  const changeStatus = async (status) => {
    try {
      await axios.post(`${API}/admin/support/tickets/${selected.id}/status`, { status }, { headers });
      setSelected({ ...selected, status });
      load();
      toast.success('Estado actualizado');
    } catch { toast.error('No se pudo cambiar el estado'); }
  };

  return (
    <div className="p-6 lg:p-8" data-testid="admin-support-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <LifeBuoy className="w-6 h-6 text-teal-600" /> Soporte
          </h1>
          <p className="text-sm text-slate-500 mt-1">Mensajes de clínicas y usuarios. Responde y gestiona su estado.</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40 h-9 text-sm" data-testid="status-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos ({summary.total || 0})</SelectItem>
              <SelectItem value="open">Abiertos ({summary.open || 0})</SelectItem>
              <SelectItem value="answered">Respondidos ({summary.answered || 0})</SelectItem>
              <SelectItem value="closed">Cerrados ({summary.closed || 0})</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={load} data-testid="admin-support-refresh"><RefreshCw className="w-4 h-4" /></Button>
        </div>
      </div>

      {selected ? (
        <Card className="border border-slate-200" data-testid="admin-ticket-conversation">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={() => setSelected(null)} data-testid="admin-back-btn"><ArrowLeft className="w-4 h-4" /></Button>
                <CardTitle className="text-base">{selected.subject}</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`text-[10px] ${STATUS[selected.status]?.cls || ''}`}>{STATUS[selected.status]?.label || selected.status}</Badge>
                <Select value={selected.status} onValueChange={changeStatus}>
                  <SelectTrigger className="w-36 h-8 text-xs" data-testid="ticket-status-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">Abierto</SelectItem>
                    <SelectItem value="answered">Respondido</SelectItem>
                    <SelectItem value="closed">Cerrado</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-500 mt-2">
              <span className="flex items-center gap-1"><User className="w-3 h-3" /> {selected.user_name} · {selected.user_email}</span>
              {selected.clinic_name && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" /> {selected.clinic_name}</span>}
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-[50vh] overflow-y-auto mb-4">
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.author_type === 'super_admin' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${m.author_type === 'super_admin' ? 'bg-teal-50 text-teal-900' : 'bg-slate-100 text-slate-800'}`} data-testid={`admin-msg-${m.id}`}>
                    <p className="text-[10px] font-semibold opacity-60 mb-0.5">{m.author_type === 'super_admin' ? 'Soporte' : (m.author_name || 'Usuario')}</p>
                    <p className="whitespace-pre-wrap">{m.body}</p>
                    <p className="text-[10px] opacity-50 mt-1">{m.created_at ? new Date(m.created_at).toLocaleString('es-GT') : ''}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Escribe una respuesta…" rows={2} className="text-sm" data-testid="admin-reply-input" />
              <Button className="bg-teal-600 hover:bg-teal-700 self-end" onClick={sendReply} disabled={sending || !reply.trim()} data-testid="admin-send-reply-btn">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : loading ? (
        <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>
      ) : tickets.length === 0 ? (
        <Card className="border border-dashed border-slate-300"><CardContent className="p-10 text-center text-sm text-slate-500">No hay tickets en esta vista.</CardContent></Card>
      ) : (
        <div className="space-y-2" data-testid="admin-ticket-list">
          {tickets.map((t) => (
            <Card key={t.id} className="border border-slate-200 hover:shadow-sm transition-shadow cursor-pointer" onClick={() => openTicket(t)} data-testid={`admin-ticket-row-${t.id}`}>
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800">{t.subject}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {t.user_name} {t.clinic_name ? `· ${t.clinic_name}` : ''} · {t.last_message_at ? new Date(t.last_message_at).toLocaleString('es-GT') : ''}
                  </p>
                </div>
                <Badge className={`text-[10px] ${STATUS[t.status]?.cls || ''}`}>{STATUS[t.status]?.label || t.status}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
