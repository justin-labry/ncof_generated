// md2docx.js — 시연 스크립트 md(이 파일 전용 마크다운 부분집합) → .docx
// 사용: node md2docx.js <in.md> <out.docx>   (FONT 환경변수로 본문 글꼴 바꿈, 기본 맑은 고딕)
// 필요: npm 패키지 docx 9.x — 빈 폴더에서 `npm install docx@9` 뒤 NODE_PATH=<그 폴더>/node_modules 로 실행
// 원칙: 글자는 md 그대로(겉모양만 더함). md 가 정본.
const fs = require('fs');
const D = require('docx');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, AlignmentType, HeadingLevel, LevelFormat, Header, Footer,
  PageNumber, VerticalAlign, UnderlineType,
} = D;

const [, , IN, OUT] = process.argv;
const KO = process.env.FONT || '맑은 고딕';
const MONO = { ascii: 'Consolas', hAnsi: 'Consolas', cs: 'Consolas', eastAsia: KO };
const NOTE_COLOR = '595959';     // 진행자 메모(읽지 않음)
const HEAD_COLOR = '1F3864';
const LONG_CODE = 60;            // 이보다 긴 인라인 명령은 따로 한 줄(복사하기 쉽게)

// A4 세로, 여백 2cm
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1134;
const TEXT_W = PAGE_W - 2 * MARGIN; // 9638

// 대괄호 종류 — 색 + 흑백 인쇄용 표시(굵게·밑줄·테두리)
const STYLE = {
  dir:     { color: '1F4E79', fill: 'E8F0FA' },                                   // 진행 지시(읽지 않음)
  cue:     { color: '1F4E79', fill: 'C9DAF0', bold: true },                       // 시점 신호·분기 조건
  read:    { color: '1F4E79', bold: true, underline: { type: UnderlineType.SINGLE, color: '1F4E79' } }, // 그 자리에서 값을 읽어 말함
  confirm: { color: '7F4F00', fill: 'FFF2CC', underline: { type: UnderlineType.DOTTED, color: '7F4F00' } }, // 확인 필요
  warn:    { color: '9C0006', fill: 'FCE4E4', bold: true, border: { style: BorderStyle.SINGLE, size: 4, color: '9C0006', space: 0 } }, // 주의
};
const CUE_RE = /^(위상|시작 신호|시작 위상|대기|시간 맞추기|30초 정리|아래 두 문단|화면 시연일 때|숫자 시연일 때|나뉜 구간|노트북1 이 눈에|화면에 '— 선제|방식:)/;
const CODE_FILL = 'EFEFEF';

function bracketKind(rest) {
  if (rest.startsWith('확인 필요')) return 'confirm';
  if (rest.startsWith('주의')) return 'warn';
  if (rest.startsWith('읽기') || rest.startsWith('값')) return 'read';
  if (CUE_RE.test(rest)) return 'cue';
  return 'dir';
}

const warnings = [];

// ---------- 인라인: `코드` · **굵게** · [지시] ----------
function runOpts(text, { size, codeSize, bold, inCode, kind, color, forceBold }) {
  const o = { text, size: inCode ? codeSize : size, bold: forceBold ? true : bold };
  if (inCode) {
    o.font = MONO; o.noProof = true;
    o.shading = { type: ShadingType.CLEAR, fill: CODE_FILL, color: 'auto' };
  } else {
    o.font = KO;
  }
  if (kind) {
    const s = STYLE[kind];
    o.color = s.color;
    if (s.fill && !inCode) o.shading = { type: ShadingType.CLEAR, fill: s.fill, color: 'auto' };
    if (s.bold) o.bold = true;
    if (s.underline) o.underline = s.underline;
    if (s.border) o.border = s.border;
  } else if (color) {
    o.color = color;
  }
  return o;
}

function parseInline(text, base = {}) {
  const size = base.size || 20;
  const codeSize = base.codeSize || Math.max(size - 2, 15);
  const runs = [];
  let buf = '';
  let inCode = false, bold = false, depth = 0, kind = base.kind || null;
  const flush = () => {
    if (!buf) return;
    runs.push(new TextRun(runOpts(buf, { size, codeSize, bold, inCode, kind, color: base.color, forceBold: base.forceBold })));
    buf = '';
  };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '`') { flush(); inCode = !inCode; continue; }
    if (inCode) { buf += c; continue; }
    if (c === '*' && text[i + 1] === '*') { flush(); bold = !bold; i++; continue; }
    if (c === '[' && !base.kind) {
      if (depth === 0) { flush(); kind = bracketKind(text.slice(i + 1)); }
      depth++; buf += c; continue;
    }
    if (c === ']' && depth > 0) {
      buf += c; depth--;
      if (depth === 0) { flush(); kind = null; }
      continue;
    }
    buf += c;
  }
  if (inCode) warnings.push(`닫히지 않은 백틱: ${text.slice(0, 60)}`);
  if (depth) warnings.push(`닫히지 않은 대괄호: ${text.slice(0, 60)}`);
  if (bold) warnings.push(`닫히지 않은 **: ${text.slice(0, 60)}`);
  flush();
  return runs;
}

// 긴 인라인 명령(대괄호·굵게 밖, LONG_CODE 초과)을 경계로 자른다 → [{t:'text'|'code', s}]
function splitLongCode(text) {
  const segs = [];
  let start = 0, depth = 0, bold = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '`') {
      const j = text.indexOf('`', i + 1);
      if (j < 0) break;
      const code = text.slice(i + 1, j);
      // 앞뒤가 공백(또는 줄 끝)일 때만 — 조사·문장부호가 붙은 경로는 그대로 둔다
      const after = text[j + 1], before = text[i - 1];
      if (code.length > LONG_CODE && code.includes(' ') /* 명령만(경로 제외) */ && depth === 0 && !bold && i > 0 && /\s/.test(before) && (after === undefined || /\s/.test(after))) {
        segs.push({ t: 'text', s: text.slice(start, i) });
        segs.push({ t: 'code', s: code });
        start = j + 1;
      }
      i = j; continue;
    }
    if (c === '*' && text[i + 1] === '*') { bold = !bold; i++; continue; }
    if (c === '[') depth++;
    else if (c === ']' && depth > 0) depth--;
  }
  segs.push({ t: 'text', s: text.slice(start) });
  // 경계 공백 정리(보이지 않는 공백만)
  return segs.map((g, k) => g.t === 'code' ? g : { t: 'text', s: g.s.replace(k > 0 ? /^\s+/ : /$^/, '').replace(k < segs.length - 1 ? /\s+$/ : /$^/, '') })
    .filter(g => g.t === 'code' || g.s.length > 0);
}

// ---------- 블록 ----------
const LIST_INDENT = 400, LIST_HANG = 280, CHECK_HANG = 320;

function para(text, opts = {}) {
  return new Paragraph({
    children: parseInline(text, opts.inline || {}),
    spacing: { before: opts.before ?? 0, after: opts.after ?? 100, line: 288 },
    indent: opts.indent,
    numbering: opts.numbering,
    heading: opts.heading,
    keepNext: opts.keepNext,
    keepLines: opts.keepLines ?? (text.length <= 600), // 짧은 문단(대사·신호)은 쪽에서 안 쪼갬
    pageBreakBefore: opts.pageBreakBefore,
    alignment: opts.alignment,
    wordWrap: true,
  });
}

function codePara(line, indentLeft, { boxed = true, size = 16, after = 140, keepNext = false } = {}) {
  const b = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF', space: 4 };
  return new Paragraph({
    children: [new TextRun({ text: line, font: MONO, size, noProof: true })],
    shading: { type: ShadingType.CLEAR, fill: 'F4F4F4', color: 'auto' },
    border: boxed ? { top: b, bottom: b, left: b, right: b } : undefined,
    indent: boxed ? { left: indentLeft + 80, right: 80 } : undefined,
    spacing: { before: boxed ? 60 : 20, after, line: 260 },
    keepNext,
    wordWrap: true,
  });
}

// 문단(목록 항목 포함)을 긴 명령 기준으로 여러 문단으로 낸다
function richParas(text, opts = {}, indentLeft = 0) {
  const segs = splitLongCode(text);
  const out = [];
  segs.forEach((g, k) => {
    const keepNext = k < segs.length - 1 ? true : opts.keepNext; // 잘린 조각끼리 같은 쪽에
    if (g.t === 'code') { out.push(codePara(g.s, indentLeft, { after: 80, keepNext })); return; }
    if (k === 0) out.push(para(g.s, { ...opts, keepNext }));
    else out.push(para(g.s, { ...opts, keepNext, numbering: undefined, indent: indentLeft ? { left: indentLeft } : opts.indent, before: 0 }));
  });
  if (segs.length && segs[0].t === 'code') warnings.push(`명령으로 시작하는 문단: ${text.slice(0, 50)}`);
  return out;
}

function splitRow(line) {
  const t = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return t.replace(/\\\|/g, '\u0000').split('|').map(s => s.trim().replace(/\u0000/g, '|'));
}

const TABLE_WIDTHS = {
  '순서': [550, 1650, 1000, 2750, 3688],
  '위상(초)': [950, 950, 1100, 2700, 1750, 2188],
  '증상': [2000, 2900, 4738],
};

function cellParas(text, { header, boldFirstCol }) {
  const inline = { size: 17, codeSize: 15, forceBold: header || boldFirstCol };
  const sp = { before: 0, after: 0, line: 252 };
  if (header) return [new Paragraph({ children: parseInline(text, inline), spacing: sp, wordWrap: true })];
  return splitLongCode(text).map(g => g.t === 'code'
    ? codePara(g.s, 0, { boxed: false, size: 15, after: 20 })
    : new Paragraph({ children: parseInline(g.s, inline), spacing: { ...sp, after: 20 }, wordWrap: true }));
}

function makeTable(rows) {
  const header = rows[0];
  const ncol = header.length;
  let widths = TABLE_WIDTHS[header[0]];
  if (!widths || widths.length !== ncol) {
    warnings.push(`표 폭 기본값 사용: ${header.join('|')}`);
    widths = Array(ncol).fill(Math.floor(TEXT_W / ncol));
    widths[ncol - 1] += TEXT_W - widths.reduce((a, b) => a + b, 0);
  }
  if (widths.reduce((a, b) => a + b, 0) !== TEXT_W) warnings.push(`표 폭 합 ≠ ${TEXT_W}: ${header[0]}`);
  const boldFirstCol = header[0] === '위상(초)';
  const border = { style: BorderStyle.SINGLE, size: 4, color: 'A6A6A6' };
  const borders = { top: border, bottom: border, left: border, right: border };
  const trs = rows.map((cells, ri) => {
    if (cells.length !== ncol) warnings.push(`표 칸 수 불일치(${cells.length}≠${ncol}): ${cells[0]}`);
    return new TableRow({
      tableHeader: ri === 0,
      cantSplit: true,
      children: widths.map((w, ci) => new TableCell({
        width: { size: w, type: WidthType.DXA },
        borders,
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: 'D9E2F3', color: 'auto' } : undefined,
        margins: { top: 50, bottom: 50, left: 90, right: 90 },
        verticalAlign: VerticalAlign.TOP,
        children: cellParas(cells[ci] ?? '', { header: ri === 0, boldFirstCol: boldFirstCol && ci === 0 }),
      })),
    });
  });
  return new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: widths, rows: trs });
}

// 범례(생성기 글 — md 에 없음)
function legend() {
  const sz = 17;
  const t = (text, o = {}) => new TextRun({ text, font: KO, size: sz, ...o });
  const k = (text, kind) => new TextRun(runOpts(text, { size: sz, codeSize: 15, bold: false, inCode: false, kind }));
  const lines = [
    [t('읽는 법', { bold: true }), t('  (이 표시는 Word 판에만 있음 · 글은 md 와 같음)', { color: NOTE_COLOR })],
    [t('검은 글씨 = 소리 내어 읽는 대사(1~4부 본문 · 부록 B 답)   '), t('회색 글씨 = 진행자 메모(목표·화면·진행 전제·짚을 숫자), 읽지 않음', { color: NOTE_COLOR })],
    [k('[파란 바탕 = 진행 지시·화면 조작, 읽지 않음]', 'dir'), t('   '), k('[굵은 파랑 = 위상(시점) 신호·분기 조건]', 'cue'), t('   '), k('[밑줄 = 그 자리에서 값을 읽어 말함]', 'read')],
    [k('[확인 필요: 점선 밑줄·노란 바탕 = 시연 전에 정할 것]', 'confirm'), t('   '), k('[주의: 테두리·빨간 바탕 = 하지 말 것]', 'warn')],
    [new TextRun({ text: '명령', font: MONO, size: 15, noProof: true, shading: { type: ShadingType.CLEAR, fill: CODE_FILL, color: 'auto' } }),
      t(' = 터미널에 그대로 붙여 넣는 명령(고정폭 · 회색 바탕, 긴 명령은 따로 한 줄)   ☐ = 점검표   부록 A·C = 진행자용 점검·대처표')],
  ];
  const b = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF', space: 4 };
  return lines.map((runs, idx) => new Paragraph({
    children: runs,
    border: { top: idx === 0 ? b : undefined, bottom: idx === lines.length - 1 ? b : undefined },
    spacing: { before: idx === 0 ? 60 : 0, after: idx === lines.length - 1 ? 200 : 40, line: 276 },
    keepNext: idx < lines.length - 1,
    wordWrap: true,
  }));
}

// ---------- 본문 ----------
const lines = fs.readFileSync(IN, 'utf8').replace(/\r\n/g, '\n').split('\n');
const children = [];
let h2count = 0, h2title = '';
let inFence = false, fenceIndent = 0;
let lastWasListItem = false;
let noteList = false;     // 진행 전제·짚을 숫자 아래 목록 → 회색

for (let i = 0; i < lines.length; i++) {
  const raw = lines[i];
  const fence = raw.match(/^(\s*)```/);
  if (fence) {
    if (!inFence) { inFence = true; fenceIndent = fence[1].length; }
    else { inFence = false; }
    continue;
  }
  if (inFence) {
    const ln = raw.startsWith(' '.repeat(fenceIndent)) ? raw.slice(fenceIndent) : raw.trimStart();
    children.push(codePara(ln, fenceIndent ? LIST_INDENT : 0));
    continue;
  }
  if (raw.trim() === '') continue;

  // 표
  if (/^\s*\|/.test(raw)) {
    const rows = [];
    while (i < lines.length && /^\s*\|/.test(lines[i])) {
      const r = splitRow(lines[i]);
      if (!r.every(c => /^:?-{3,}:?$/.test(c))) rows.push(r);
      i++;
    }
    i--;
    children.push(makeTable(rows));
    children.push(new Paragraph({ children: [], spacing: { before: 0, after: 120 } }));
    lastWasListItem = false; noteList = false;
    continue;
  }

  let m;
  if ((m = raw.match(/^# (.*)$/))) {
    children.push(para(m[1], { heading: HeadingLevel.HEADING_1, after: 160, inline: { size: 36, forceBold: true, color: HEAD_COLOR } }));
    continue;
  }
  if ((m = raw.match(/^## (.*)$/))) {
    h2count++; h2title = m[1];
    children.push(para(m[1], {
      heading: HeadingLevel.HEADING_2, before: 120, after: 160, keepNext: true,
      pageBreakBefore: h2count > 1, inline: { size: 28, forceBold: true, color: HEAD_COLOR },
    }));
    lastWasListItem = false; noteList = false;
    continue;
  }
  const note = noteList ? { color: NOTE_COLOR } : {};
  if ((m = raw.match(/^- \[ \] (.*)$/))) {
    children.push(...richParas(m[1], { numbering: { reference: 'check', level: 0 }, after: 80, inline: note }, LIST_INDENT));
    lastWasListItem = true;
    continue;
  }
  if ((m = raw.match(/^- (.*)$/))) {
    children.push(...richParas(m[1], { numbering: { reference: 'bullet', level: 0 }, after: 80, inline: note }, LIST_INDENT));
    lastWasListItem = true;
    continue;
  }
  if ((m = raw.match(/^ {2,}(\S.*)$/))) {
    if (!lastWasListItem) warnings.push(`목록 밖 들여쓰기 문단: ${m[1].slice(0, 50)}`);
    children.push(...richParas(m[1], { indent: { left: LIST_INDENT }, after: 100, inline: note }, LIST_INDENT));
    continue;
  }
  // 소제목: 굵은 글씨만 있는 줄, 또는 '**X** (설명)' → 제목은 굵은 부분만, 설명은 회색 문단으로
  if (/^\*\*[^*]+\*\*$/.test(raw) || /^\*\*[^*]+\*\* \(/.test(raw)) {
    const mm = raw.match(/^(\*\*[^*]+\*\*)(?: (\(.*))?$/);
    children.push(para(mm[1], { heading: HeadingLevel.HEADING_3, before: 160, after: 80, keepNext: true, inline: { size: 21, color: HEAD_COLOR } }));
    if (mm[2]) children.push(para(mm[2], { after: 80, keepNext: true, inline: { color: NOTE_COLOR, size: 18 } }));
    const ht = mm[1].replace(/\*/g, '');
    noteList = ht.startsWith('진행 전제') || ht.startsWith('짚을 숫자');
    lastWasListItem = false;
    continue;
  }
  if (i === 2) { // 작성 기준 줄 + 범례
    children.push(para(raw, { inline: { size: 17, color: NOTE_COLOR }, after: 120 }));
    children.push(...legend());
    continue;
  }
  // 일반 문단: 목표·화면 문단과 진행 개요 절의 문단은 진행자 메모(회색)
  const isNote = /^\*\*(목표|화면):\*\*/.test(raw) || h2title === '진행 개요';
  children.push(...richParas(raw, { after: 120, inline: isNote ? { color: NOTE_COLOR } : {} }));
  lastWasListItem = false; noteList = false;
}

const headingStyle = (id, name, size, before, after, outlineLevel) => ({
  id, name, basedOn: 'Normal', next: 'Normal', quickFormat: true,
  run: { font: KO, size, bold: true, color: HEAD_COLOR },
  paragraph: { spacing: { before, after }, keepNext: true, outlineLevel },
});

const bulletLevel = (text, hang, run) => ({
  level: 0, format: LevelFormat.BULLET, text, alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: LIST_INDENT, hanging: hang } }, run },
});

const doc = new Document({
  creator: 'ETRI NCOF',
  title: 'NCOF 통합 제어 시연 스크립트 (2026-11-06)',
  description: 'prototype/docs/dodo1-interop/NCOF_통합제어_시연스크립트_1106.md 에서 생성',
  styles: {
    default: { document: { run: { font: KO, size: 20 } } },
    paragraphStyles: [
      headingStyle('Heading1', 'Heading 1', 36, 0, 160, 0),
      headingStyle('Heading2', 'Heading 2', 28, 120, 160, 1),
      headingStyle('Heading3', 'Heading 3', 21, 160, 80, 2),
    ],
  },
  numbering: {
    config: [
      { reference: 'bullet', levels: [bulletLevel('•', LIST_HANG, { font: KO })] },
      { reference: 'check', levels: [bulletLevel('☐', CHECK_HANG, { font: 'Segoe UI Symbol', size: 24 })] },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN, header: 560, footer: 560 } },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: 'NCOF 통합 제어 시연 스크립트 · 2026-11-06 · 내부용', font: KO, size: 15, color: '808080' })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ children: [PageNumber.CURRENT], font: KO, size: 16, color: '808080' }),
          new TextRun({ text: ' / ', font: KO, size: 16, color: '808080' }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: KO, size: 16, color: '808080' }),
        ],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`wrote ${OUT} (${buf.length} bytes), blocks=${children.length}`);
  if (warnings.length) { console.log('WARNINGS:'); warnings.forEach(w => console.log(' - ' + w)); }
  else console.log('warnings: none');
});
