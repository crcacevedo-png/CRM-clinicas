import { FileText, Eye, Activity } from 'lucide-react';

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const STATUS_MAP = {
  scheduled: { label: 'Programada', class: 'bg-blue-50 text-blue-700 border-blue-200' },
  confirmed: { label: 'Confirmada', class: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  in_progress: { label: 'En curso', class: 'bg-amber-50 text-amber-700 border-amber-200' },
  completed: { label: 'Completada', class: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  cancelled: { label: 'Cancelada', class: 'bg-red-50 text-red-600 border-red-200' },
  no_show: { label: 'No asistió', class: 'bg-slate-100 text-slate-600 border-slate-300' },
};

export const FILE_ICONS = {
  'application/pdf': { icon: FileText, color: 'text-red-500 bg-red-50' },
  'image/jpeg': { icon: Eye, color: 'text-blue-500 bg-blue-50' },
  'image/png': { icon: Eye, color: 'text-green-500 bg-green-50' },
  'application/dicom': { icon: Activity, color: 'text-purple-500 bg-purple-50' },
};

export const VITAL_RANGES = {
  blood_pressure_systolic: { min: 70, max: 180 },
  blood_pressure_diastolic: { min: 40, max: 120 },
  heart_rate: { min: 50, max: 120 },
  respiratory_rate: { min: 10, max: 30 },
  temperature: { min: 35.5, max: 38.0 },
  oxygen_saturation: { min: 92, max: 100 },
};

export const ROS_LABELS = {
  general: 'General', cardiovascular: 'Cardiovascular', respiratory: 'Respiratorio',
  gastrointestinal: 'Gastrointestinal', genitourinary: 'Genitourinario',
  musculoskeletal: 'Musculoesquelético', neurological: 'Neurológico',
  skin: 'Piel', endocrine: 'Endocrino',
};

export const EXAM_LABELS = {
  head: 'Cabeza', neck: 'Cuello', chest: 'Tórax',
  abdomen: 'Abdomen', extremities: 'Extremidades', neurological: 'Neurológico',
};
