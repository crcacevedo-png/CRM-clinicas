export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const STATUS_CONFIG = {
  scheduled:   { label: 'Pendiente',   dot: 'bg-blue-500' },
  confirmed:   { label: 'Confirmada',  dot: 'bg-emerald-500' },
  in_progress: { label: 'En curso',    dot: 'bg-amber-500' },
  completed:   { label: 'Completada',  dot: 'bg-slate-400' },
  cancelled:   { label: 'Cancelada',   dot: 'bg-red-500' },
  no_show:     { label: 'No asistió',  dot: 'bg-orange-400' },
};
export const STATUS_OPTIONS = Object.entries(STATUS_CONFIG).map(([k, v]) => ({ value: k, label: v.label }));

// Doctor color palette (cycled by index)
export const DOCTOR_COLORS = [
  { bg: 'bg-indigo-50',  border: 'border-indigo-300', text: 'text-indigo-800', accent: '#6366f1', label: 'bg-indigo-500' },
  { bg: 'bg-rose-50',    border: 'border-rose-300',   text: 'text-rose-800',   accent: '#f43f5e', label: 'bg-rose-500' },
  { bg: 'bg-amber-50',   border: 'border-amber-300',  text: 'text-amber-800',  accent: '#f59e0b', label: 'bg-amber-500' },
  { bg: 'bg-cyan-50',    border: 'border-cyan-300',   text: 'text-cyan-800',   accent: '#06b6d4', label: 'bg-cyan-500' },
  { bg: 'bg-violet-50',  border: 'border-violet-300', text: 'text-violet-800', accent: '#8b5cf6', label: 'bg-violet-500' },
  { bg: 'bg-lime-50',    border: 'border-lime-300',   text: 'text-lime-800',   accent: '#84cc16', label: 'bg-lime-500' },
  { bg: 'bg-pink-50',    border: 'border-pink-300',   text: 'text-pink-800',   accent: '#ec4899', label: 'bg-pink-500' },
  { bg: 'bg-teal-50',    border: 'border-teal-300',   text: 'text-teal-800',   accent: '#14b8a6', label: 'bg-teal-500' },
];

export const DAY_NAMES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
export const MONTH_NAMES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
export const DAY_NAMES_FULL_WEEK = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
