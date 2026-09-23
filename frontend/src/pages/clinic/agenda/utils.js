import { DOCTOR_COLORS } from './constants';

export function getDoctorColor(doctorId, doctorMap) {
  const ids = Object.keys(doctorMap).sort();
  const idx = ids.indexOf(doctorId);
  return DOCTOR_COLORS[idx >= 0 ? idx % DOCTOR_COLORS.length : 0];
}

export function getWeekDates(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 6 }, (_, i) => {
    const dd = new Date(monday);
    dd.setDate(monday.getDate() + i);
    return dd;
  });
}

export function timeToMinutes(timeStr) {
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + (m || 0);
}

export function formatTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
}

export function getMonthDays(year, month) {
  const first = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0).getDate();
  let startDow = first.getDay();
  startDow = startDow === 0 ? 6 : startDow - 1;
  const days = [];
  for (let i = 0; i < startDow; i++) {
    const d = new Date(year, month, -startDow + i + 1);
    days.push({ date: d, inMonth: false });
  }
  for (let i = 1; i <= lastDay; i++) {
    days.push({ date: new Date(year, month, i), inMonth: true });
  }
  while (days.length % 7 !== 0) {
    const d = new Date(year, month + 1, days.length - startDow - lastDay + 1);
    days.push({ date: d, inMonth: false });
  }
  return days;
}

export function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function blockCoversSlot(block, date, slotMin, slotLen) {
  const bs = new Date(block.starts_at);
  const be = new Date(block.ends_at);
  const slotStart = new Date(date); slotStart.setHours(Math.floor(slotMin / 60), slotMin % 60, 0, 0);
  const slotEnd = new Date(slotStart.getTime() + slotLen * 60000);
  return bs < slotEnd && be > slotStart;
}

export function slotBlockInfo(blocks, date, slotMin, slotLen, firstSlotMin) {
  for (const b of (blocks || [])) {
    if (blockCoversSlot(b, date, slotMin, slotLen)) {
      const bs = new Date(b.starts_at);
      const slotStart = new Date(date); slotStart.setHours(Math.floor(slotMin / 60), slotMin % 60, 0, 0);
      const slotEnd = new Date(slotStart.getTime() + slotLen * 60000);
      const showLabel = (bs >= slotStart && bs < slotEnd) || (slotMin === firstSlotMin && bs < slotStart);
      return { block: b, showLabel };
    }
  }
  return null;
}

export const BLOCK_STRIPE = {
  backgroundImage: 'repeating-linear-gradient(45deg, rgba(100,116,139,0.16), rgba(100,116,139,0.16) 6px, rgba(148,163,184,0.06) 6px, rgba(148,163,184,0.06) 12px)',
};
