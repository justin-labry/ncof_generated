// NF 타입별 Tailwind 컬러 클래스 매핑
export function nodeColorClass(name: string): string {
  const upper = name.toUpperCase();
  if (upper.includes('NCOF')) return 'bg-amber-500/20 text-amber-400';
  if (upper.includes('RICF')) return 'bg-rose-500/20 text-rose-400';
  if (upper.includes('PCF')) return 'bg-blue-500/20 text-blue-400';
  if (upper.includes('AF')) return 'bg-purple-500/20 text-purple-400';
  if (upper.includes('SMF')) return 'bg-cyan-500/20 text-cyan-400';
  if (upper.includes('UPF')) return 'bg-emerald-500/20 text-emerald-400';
  return 'text-slate-400';
}

/** NOTIF_PCF_xxx 형식의 문자열에서 NF 타입(중간 부분)을 추출 */
export function extractMiddle(text: string | undefined | null): string {
  if (!text) return '';
  const parts = text.split('_');
  if (parts.length < 3) return '';
  return parts[1] ?? '';
}
