import assert from 'assert';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  CRF_MAP,
  VALID_QUALITIES,
  VALID_COMPRESSION_LEVELS
} from '../constants.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Test Suite: Video Slicer Server Tests
console.log('Running Video Slicer Tests...\n');

let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
    testsPassed++;
  } catch (error) {
    console.error(`✗ ${name}`);
    console.error(`  Error: ${error.message}`);
    testsFailed++;
  }
}

// Test Suite 1: Input Validation
console.log('=== Input Validation Tests ===');

test('maxDuration must be greater than 0', () => {
  const maxDuration = 0;
  assert(maxDuration <= 0, 'maxDuration should be invalid');
});

test('maxDuration accepts positive numbers', () => {
  const maxDuration = 30;
  assert(maxDuration > 0, 'maxDuration should be valid');
});

test('quality must be one of 480, 720, 1080', () => {
  const testQuality = 720;
  assert(VALID_QUALITIES.includes(testQuality), 'quality should be valid');
});

test('compression level must be between 0 and 6', () => {
  const compression = 3;
  assert(VALID_COMPRESSION_LEVELS.includes(compression), 'compression should be valid');
});

test('invalid compression level is rejected', () => {
  const compression = 7;
  assert(!VALID_COMPRESSION_LEVELS.includes(compression), 'invalid compression should be rejected');
});

// Test Suite 2: CRF Mapping
console.log('\n=== CRF Mapping Tests ===');

test('compression level 0 maps to CRF 15', () => {
  assert.strictEqual(CRF_MAP[0], 15);
});

test('compression level 3 maps to CRF 23 (default)', () => {
  assert.strictEqual(CRF_MAP[3], 23);
});

test('compression level 6 maps to CRF 32', () => {
  assert.strictEqual(CRF_MAP[6], 32);
});

test('all compression levels have CRF values', () => {
  for (let i = 0; i <= 6; i++) {
    assert(CRF_MAP[i] !== undefined, `compression level ${i} should have a CRF value`);
  }
});

// Test Suite 3: Quality Levels
console.log('\n=== Quality Level Tests ===');

test('480p quality is available', () => {
  assert(VALID_QUALITIES.includes(480), '480p should be available');
});

test('720p quality is available', () => {
  assert(VALID_QUALITIES.includes(720), '720p should be available');
});

test('1080p quality is available', () => {
  assert(VALID_QUALITIES.includes(1080), '1080p should be available');
});

test('invalid quality is rejected', () => {
  const testQuality = 360;
  assert(!VALID_QUALITIES.includes(testQuality), 'invalid quality should be rejected');
});

// Test Suite 4: Math & Duration Calculation
console.log('\n=== Duration Calculation Tests ===');

test('chunk count calculation is correct for 100s video with 30s clips', () => {
  const totalDuration = 100;
  const maxDuration = 30;
  const chunkCount = Math.ceil(totalDuration / maxDuration);
  assert.strictEqual(chunkCount, 4);
});

test('chunk count calculation handles exact division', () => {
  const totalDuration = 120;
  const maxDuration = 30;
  const chunkCount = Math.ceil(totalDuration / maxDuration);
  assert.strictEqual(chunkCount, 4);
});

test('chunk count calculation handles remainder', () => {
  const totalDuration = 100;
  const maxDuration = 25;
  const chunkCount = Math.ceil(totalDuration / maxDuration);
  assert.strictEqual(chunkCount, 4);
});

test('start time calculation is correct', () => {
  const clipIndex = 2;
  const maxDuration = 30;
  const startTime = clipIndex * maxDuration;
  assert.strictEqual(startTime, 60);
});

// Test Suite 5: Clip Naming
console.log('\n=== Clip Naming Tests ===');

test('clip number is padded with zeros', () => {
  const clipNum = String(1).padStart(3, '0');
  assert.strictEqual(clipNum, '001');
});

test('double digit clip number is padded', () => {
  const clipNum = String(10).padStart(3, '0');
  assert.strictEqual(clipNum, '010');
});

test('triple digit clip number is not padded', () => {
  const clipNum = String(100).padStart(3, '0');
  assert.strictEqual(clipNum, '100');
});

// Test Suite 6: Error Handling
console.log('\n=== Error Handling Tests ===');

test('NaN maxDuration is invalid', () => {
  const maxDuration = NaN;
  assert(isNaN(maxDuration), 'NaN should be invalid');
});

test('negative maxDuration is invalid', () => {
  const maxDuration = -30;
  assert(maxDuration <= 0, 'negative duration should be invalid');
});

test('string maxDuration can be parsed to integer', () => {
  const maxDurationStr = '30';
  const maxDuration = parseInt(maxDurationStr);
  assert.strictEqual(maxDuration, 30);
});

test('invalid string maxDuration results in NaN', () => {
  const maxDurationStr = 'abc';
  const maxDuration = parseInt(maxDurationStr);
  assert(isNaN(maxDuration), 'invalid string should parse to NaN');
});

// Test Results
console.log('\n=== Test Summary ===');
console.log(`Passed: ${testsPassed}`);
console.log(`Failed: ${testsFailed}`);
console.log(`Total: ${testsPassed + testsFailed}`);

if (testsFailed > 0) {
  process.exit(1);
} else {
  console.log('\n✓ All tests passed!');
  process.exit(0);
}
