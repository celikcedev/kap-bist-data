import test from 'node:test';
import assert from 'node:assert/strict';

import { parseTurkishDate, findHeaderIndex } from '../src/utils/helpers.js';

test('parseTurkishDate handles slash separated format', () => {
  const value = parseTurkishDate('01/06/1990');
  assert.ok(value, 'Date should be parsed');
  assert.equal(value?.toISOString().slice(0, 10), '1990-06-01');
});

test('parseTurkishDate handles dot separated format', () => {
  const value = parseTurkishDate('14.11.1975');
  assert.ok(value, 'Date should be parsed');
  assert.equal(value?.toISOString().slice(0, 10), '1975-11-14');
});

test('parseTurkishDate handles iso format', () => {
  const value = parseTurkishDate('2024-09-30');
  assert.ok(value, 'Date should be parsed');
  assert.equal(value?.toISOString().slice(0, 10), '2024-09-30');
});

test('parseTurkishDate handles natural language format', () => {
  const value = parseTurkishDate('1 Ocak 2024');
  assert.ok(value, 'Date should be parsed');
  assert.equal(value?.toISOString().slice(0, 10), '2024-01-01');
});

test('parseTurkishDate handles abbreviated month names', () => {
  const value = parseTurkishDate('30 Eyl 2023');
  assert.ok(value, 'Date should be parsed');
  assert.equal(value?.toISOString().slice(0, 10), '2023-09-30');
});

test('findHeaderIndex matches normalized headers', () => {
  const headers = ['Adı-Soyadı', 'Görevi'];
  const index = findHeaderIndex(headers, ['Adı Soyadı', 'Ad Soyadı']);
  assert.equal(index, 0);
});
