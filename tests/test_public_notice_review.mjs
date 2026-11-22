import assert from 'node:assert/strict';
import { test } from 'node:test';
import { reviewPoint } from '../judge_site/metro-review.mjs';

const day = '2026-10-13';
for (const [station, exit, start, end, expected] of [
  ['金海路站', 1, day, day, '暂停推荐'], ['金海路', 2, day, day, '暂停推荐'],
  ['金海路', 3, day, day, '替代位置'], ['上海火车站站', 2, day, day, '暂停推荐'],
  ['上海火车站', 2, '2026-10-12', '2026-10-12', '未命中'],
  ['上海南站', 2, day, day, '未命中'], ['上海火车站', 2, day, '2026-11-22', '跨出'],
  ['上海火车站', 2, '2026-11-22', '2026-11-22', '历史调整']
]) {
  test([station, exit, start, end].join(' '), () =>
    assert.ok(reviewPoint(station, exit, start, end).includes(expected)));
}
test('reject invalid dates', () => assert.throws(() => reviewPoint('金海路', 1, day, '2026-13-01')));
