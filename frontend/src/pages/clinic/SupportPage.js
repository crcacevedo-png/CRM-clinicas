import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { LifeBuoy, Plus, Send, MessageSquare, ArrowLeft, Paperclip, X, ImageIcon } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS = {
  open: { label: 'Abierto', cls: 'bg-amber-100 text-amber-700' },
  answered: { label: 'Respondido', cls: 'bg-emerald-100 text-emerald-700' },
  closed: { label: 'Cerrado', cls: 'bg-slate-200 text-slate-600' },
};

function MessageAttachments({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {items.map((a, i) => (
        <a key={i} href={a.url} target="_blank" rel="noopener noreferrer" className="block" data-testid={`attachment-${i}`}>
          <img src={a.url} alt={a.name || 'adjunto'} className="w-20 h-20 object-cover rounded border border-black/10 hover:opacity-80 transition-opacity" />
        </a>
      ))}
    </div>
  );
}

function AttachButton({ attachments, setAttachments, uploading, setUploading, headers, testid }) {
  const inputRef = useRef(null);
  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (attachments.length >= 5) { toast.error('Máximo 5 imágenes'); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await axios.post(`${API}/support/upload`, fd, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } });
      setAttachments((prev) => [...prev, res.data]);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo subir la imagen');
    } finally { setUploading(false); }
  };
  return (
    <>
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={onPick} data-testid={`${testid}-input`} />
      <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()} disabled={uploading} data-testid={testid}>
        <Paperclip className="w-4 h-4 mr-1" /> {uploading ? 'Subiendo…' : 'Adjuntar captura'}
      </Button>
    </>
  );
}

function AttachPreview({ attachments, setAttachments }) {
  if (!attachments.length) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {attachments.map((a, i) => (
        <div key={i} className="relative" data-testid={`attach-preview-${i}`}>
          <img src={a.url} alt={a.name} className="w-16 h-16 object-cover rounded border border-slate-200" />
          <button type="button" onClick={() => setAttachments((prev) => prev.filter((_, j) => j !== i))} className="absolute -top-1.5 -right-1.5 bg-rose-500 text-white rounded-full p-0.5" data-testid={`remove-attach-${i}`}>
            <X className="w-3 h-3" />
          </button>
        </div>
      ))}
    </div>
  );
}

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
  const [newAttach, setNewAttach] = useState([]);
  const [replyAttach, setReplyAttach] = useState([]);
  const [uploading, setUploading] = useState(false);

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
      await axios.post(`${API}/support/tickets`, { ...form, attachments: newAttach }, { headers });
      toast.success('Mensaje enviado a soporte');
      setShowNew(false);
      setForm({ subject: '', body: '' });
      setNewAttach([]);
      loadTickets();
    } catch { toast.error('No se pudo enviar el mensaje'); }
    finally { setCreating(false); }
  };

  const sendReply = async () => {
    if (!reply.trim() && replyAttach.length === 0) return;
    setSending(true);
    try {
      await axios.post(`${API}/support/tickets/${selected.id}/messages`, { body: reply || '(adjunto)', attachments: replyAttach }, { headers });
      setReply('');
      setReplyAttach([]);
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
                    <MessageAttachments items={m.attachments} />
                    <p className="text-[10px] opacity-50 mt-1">{m.created_at ? new Date(m.created_at).toLocaleString('es-GT') : ''}</p>
                  </div>
                </div>
              ))}
            </div>
            {selected.status !== 'closed' ? (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Escribe tu respuesta…" rows={2} className="text-sm" data-testid="reply-input" />
                  <Button className="bg-teal-600 hover:bg-teal-700 self-end" onClick={sendReply} disabled={sending || (!reply.trim() && replyAttach.length === 0)} data-testid="send-reply-btn">
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
                <AttachButton attachments={replyAttach} setAttachments={setReplyAttach} uploading={uploading} setUploading={setUploading} headers={headers} testid="reply-attach-btn" />
                <AttachPreview attachments={replyAttach} setAttachments={setReplyAttach} />
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
            <div>
              <label className="text-xs text-slate-500 flex items-center gap-1 mb-1"><ImageIcon className="w-3.5 h-3.5" /> Captura de pantalla (opcional)</label>
              <AttachButton attachments={newAttach} setAttachments={setNewAttach} uploading={uploading} setUploading={setUploading} headers={headers} testid="ticket-attach-btn" />
              <AttachPreview attachments={newAttach} setAttachments={setNewAttach} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowNew(false); setNewAttach([]); }}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={createTicket} disabled={creating} data-testid="submit-ticket-btn">
              {creating ? 'Enviando…' : 'Enviar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
