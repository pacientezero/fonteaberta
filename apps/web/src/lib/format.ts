export function formatPtBrDate(value: string | null | undefined): string {
  if (!value) {
    return 'Não informado';
  }
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'long',
    timeZone: 'UTC',
  }).format(new Date(value));
}

export function formatPtBrDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'Não informado';
  }
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function formatPtBrMoney(value: string | null | undefined): string {
  if (!value) {
    return 'Não informado';
  }
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return value;
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(amount);
}

export function formatPtBrNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return 'Não informado';
  }
  return new Intl.NumberFormat('pt-BR').format(value);
}
