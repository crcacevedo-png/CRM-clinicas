import { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { LifeBuoy, Plus, Send, MessageSquare, ArrowLeft } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS = {
  open: { label: 'Abierto', cls: 'bg-amber-100 text-amber-700' },
  answered: { label: 'Respondido', cls: 'bg-emerald-100 text-emerald-700' },
  closed: { label: 'Cerrado', cls: 'bg-slate-200 text-slate-600' },
};

export default function SupportPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ subject: '', body: '' });
  const [creating, setCreating] = useState(false);

  const loadTickets = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/support/tickets`, { headers });
      setTickets(res.data?.tickets || []);
    } catch { toast.error('Error al cargar tus mensajes'); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadTickets(); /* eslint-disable-next-line */ }, []);

  const openTicket = async (t) => {
    setSelected(t);
    try {
      const res = await axios.get(`${API}/support/tickets/${t.id}`, { headers });
      setMessages(res.data?.messages || []);
      setSelected(res.data?.ticket || t);
    } catch { toast.error('Error al abrir el mensaje'); }
  };

  const createTicket = async () => {
    if (!form.subject.trim() || !form.body.trim()) { toast.error('Completa asunto y mensaje'); return; }
    setCreating(true);
    try {
      await axios.post(`${API}/support/tickets`, form, { headers });
      toast.success('Mensaje enviado a soporte');
      setShowNew(false);
      setForm({ subject: '', body: '' });
      loadTickets();
    } catch { toast.error('No se pudo enviar el mensaje'); }
    finally { setCreating(false); }
  };

  const sendReply = async () => {
    if (!reply.trim()) return;
    setSending(true);
    try {
      await axios.post(`${API}/support/tickets/${selected.id}/messages`, { body: reply }, { headers });
      setReply('');
      openTicket(selected);
      loadTickets();
    } catch { toast.error('No se pudo enviar'); }
    finally { setSending(false); }
  };

  return (
    <div className="p-6 lg:p-8" data-testid="support-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <LifeBuoy className="w-6 h-6 text-teal-600" /> Soporte
          </h1>
          <p className="text-sm text-slate-500 mt-1">Envía tus dudas o problemas; el equipo te responderá aquí.</p>
        </div>
        {!selected && (
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setShowNew(true)} data-testid="new-ticket-btn">
            <Plus className="w-4 h-4 mr-1" /> Nuevo mensaje
          </Button>
        )}
      </div>

      {selected ? (
        <Card className="border border-slate-200" data-testid="ticket-conversation">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={() => setSelected(null)} data-testid="back-to-list-btn"><ArrowLeft className="w-4 h-4" /></Button>
              <CardTitle className="text-base">{selected.subject}</CardTitle>
            </div>
            <Badge className={`text-[10px] ${STATUS[selected.status]?.cls || ''}`}>{STATUS[selected.status]?.label || selected.status}</Badge>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-[50vh] overflow-y-auto mb-4">
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.author_type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${m.author_type === 'user' ? 'bg-teal-50 text-teal-900' : 'bg-slate-100 text-slate-800'}`} data-testid={`msg-${m.id}`}>
                    <p className="text-[10px] font-semibold opacity-60 mb-0.5">{m.author_type === 'user' ? 'Tú' : 'Soporte'}</p>
                    <p className="whitespace-pre-wrap">{m.body}</p>
                    <p className="text-[10px] opacity-50 mt-1">{m.created_at ? new Date(m.created_at).toLocaleString('es-GT') : ''}</p>
                  </div>
                </div>
              ))}
            </div>
            {selected.status !== 'closed' ? (
              <div className="flex gap-2">
                <Textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Escribe tu respuesta…" rows={2} className="text-sm" data-testid="reply-input" />
                <Button className="bg-teal-600 hover:bg-teal-700 self-end" onClick={sendReply} disabled={sending || !reply.trim()} data-testid="send-reply-btn">
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <p className="text-xs text-slate-400 text-center py-2">Esta conversación está cerrada.</p>
            )}
          </CardContent>
        </Card>
      ) : loading ? (
        <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>
      ) : tickets.length === 0 ? (
        <Card className="border border-dashed border-slate-300">
          <CardContent className="p-10 text-center">
            <MessageSquare className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">Aún no has enviado mensajes de soporte.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2" data-testid="ticket-list">
          {tickets.map((t) => (
            <Card key={t.id} className="border border-slate-200 hover:shadow-sm transition-shadow cursor-pointer" onClick={() => openTicket(t)} data-testid={`ticket-row-${t.id}`}>
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800">{t.subject}</p>
                  <p className="text-xs text-slate-400 mt-0.5">Actualizado {t.last_message_at ? new Date(t.last_message_at).toLocaleString('es-GT') : ''}</p>
                </div>
                <Badge className={`text-[10px] ${STATUS[t.status]?.cls || ''}`}>{STATUS[t.status]?.label || t.status}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent data-testid="new-ticket-dialog">
          <DialogHeader><DialogTitle>Nuevo mensaje de soporte</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <label className="text-xs text-slate-500">Asunto</label>
              <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Resumen breve" className="mt-1" data-testid="ticket-subject-input" />
            </div>
            <div>
              <label className="text-xs text-slate-500">Descripción</label>
              <Textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} rows={5} placeholder="Cuéntanos qué sucede…" className="mt-1" data-testid="ticket-body-input" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={createTicket} disabled={creating} data-testid="submit-ticket-btn">
              {creating ? 'Enviando…' : 'Enviar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
