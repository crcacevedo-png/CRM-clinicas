export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const PAY_LABEL = {
  cash: 'Efectivo',
  credit_card: 'Tarjeta crédito',
  debit_card: 'Tarjeta débito',
  transfer: 'Transferencia',
  credit: 'Crédito',
  check: 'Cheque',
  other: 'Otro',
};

export const STATUS_LABEL = {
  paid: 'Pagada',
  partial: 'Parcial',
  pending: 'Pendiente',
  cancelled: 'Anulada',
};
