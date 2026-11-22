// Transcribed facts from the 2026-10-12 notice linked in the review panel.
// The replay cutoff bounds our evidence, not the actual duration of construction.
const replayThrough = '2026-10-13';
const events = [
  { station: '金海路', exits: [1, 2], from: '2026-10-12', closed: true },
  { station: '金海路', exits: [3], from: '2026-10-12', closed: false },
  { station: '上海火车站', exits: [2], from: '2026-10-13', closed: true }
];

function validDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + 'T00:00:00Z');
  return Number.isFinite(date.getTime()) && date.toISOString().startsWith(value);
}

export function reviewPoint(name, exit, start, end) {
  const station = name.trim().replace(/站$/, '');
  const event = events.find(e =>
    (e.station === name.trim() || e.station === station) && e.exits.includes(exit));
  if (!validDate(start) || !validDate(end) || end < start || !name.trim() ||
      !Number.isInteger(exit) || exit < 1) throw new Error('请检查站名、正整数口号及档期起止日期。');
  if (!event || end < event.from) return '本公告未命中，请另查目标档期。';
  if (start > replayThrough) return '有历史调整记录，须查最新公告和现场情况后再推荐。';
  const action = event.closed ? '暂停推荐，请媒介复核施工影响。' :
    '可核查替代位置，请确认载体、覆盖范围和红豆档期。';
  return end > replayThrough ? action + ' 跨出历史回放窗口的日期须另核。' : action;
}

if (typeof document !== 'undefined') {
  const form = document.getElementById('metroReview');
  form.addEventListener('submit', event => {
    event.preventDefault();
    const result = document.getElementById('metroResult');
    const data = new FormData(form);
    const lines = data.get('points').trim().split(/\r?\n/);
    result.replaceChildren();
    for (const line of lines) {
      const row = document.createElement('li');
      const fields = line.split(/[,，]/).map(field => field.trim());
      try {
        if (fields.length !== 2 || !/^\d+$/.test(fields[1])) throw new Error('格式应为：站名，口号。');
        row.textContent = line + ' — ' + reviewPoint(fields[0], Number(fields[1]), data.get('start'), data.get('end'));
      } catch (error) {
        row.textContent = line + ' — ' + error.message;
      }
      result.append(row);
    }
  });
}
