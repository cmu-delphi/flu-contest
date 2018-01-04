"""
===============
=== Purpose ===
===============

Reads and writes forecast metadata, even in forecast formats lacking metadata
fields (e.g. 2016 flu contest). This is done by embedding arbitrary data in the
low bits of IEEE 754 double values in distributional forecast bins. Although
this does technically change the forecast, the change in both probability and
log probability is on the order of 1e-15. Bins with probability less than 0.01
or greater than 0.99 are assumed to have special meaning and are not modified.
All other bins can be used to store 4 bits of data.


=================
=== Changelog ===
=================

2016-12-07
  + first version
"""

# standard library
import argparse
import math
import struct

# first party
from delphi.flu_contest.utils.forecast_io import ForecastIO


def double_to_long(x):
  return struct.unpack('>Q', struct.pack('>d', x))[0]


def long_to_double(x):
  return struct.unpack('>d', struct.pack('>Q', x))[0]


def get_values(fc):
  mask = 0xff
  not_mask = ((1 << 64) - 1) ^ mask
  prob_floor = 0.01
  # TODO: use new forecast class
  raise NotImplementedError()
  for r in fc.regions:
    for t in fc.targets:
      bins = fc.data[r][t]['dist']
      for (i, prob) in enumerate(bins):
        long_prob = double_to_long(prob)
        long_prob &= not_mask
        prob = long_to_double(long_prob)
        if prob_floor <= prob < (1 - prob_floor):
          yield bins, i


def get_value(src):
  try:
    bins, i = next(src)
    return (double_to_long(bins[i]) >> 4) & 0b1111
  except StopIteration:
    return None


def set_value(src, bits):
  mask = 0b11110000
  not_mask = ((1 << 64) - 1) ^ mask
  bins, i = next(src)
  v1 = double_to_long(bins[i]) & not_mask
  v2 = (bits << 4) & mask
  bins[i] = long_to_double(v1 | v2)


def read_tag(fc):
  src = get_values(fc)
  bits = get_value(src)
  tag = []
  next_byte = 0
  chunk = 0
  while bits is not None:
    next_byte = ((next_byte << 4) | bits) & 0xff
    chunk += 1
    if chunk == 2:
      tag.append(next_byte)
      chunk = 0
    bits = get_value(src)
  if chunk == 1:
    next_byte = (next_byte << 4) & 0xff
    tag.append(next_byte)
  return bytes(tag)


def write_tag(fc, tag):
  src = get_values(fc)
  idx = 0
  for next_byte in tag:
    for i in range(2):
      offset = 8 - 4 * (i + 1)
      try:
        set_value(src, next_byte >> offset)
      except StopIteration as ex:
        raise Exception('write failed at index %d' % idx)
    idx += 1


def read_tag_str(fc):
  tag_bytes = read_tag(fc)
  if len(tag_bytes) < 2:
    raise Exception('missing string length field')
  length = struct.unpack('>H', tag_bytes[:2])[0]
  if len(tag_bytes) < 2 + length:
    raise Exception('string is truncated')
  return str(tag_bytes[2:2 + length], 'utf-8')


def write_tag_str(fc, tag):
  tag_bytes = tag.encode('utf-8')
  if len(tag_bytes) > 0xffff:
    raise Exception('string too long')
  write_tag(fc, struct.pack('>H', len(tag_bytes)) + tag_bytes)
  if read_tag_str(fc) != tag:
    raise Exception('read tag != written tag')


if __name__ == '__main__':
  # args and usage
  parser = argparse.ArgumentParser()
  parser.add_argument('file', action='store', type=str, help='input forecast')
  args = parser.parse_args()

  # read the tag
  fc = ForecastIO.load_csv(args.file)
  try:
    print('tag found:', read_tag_str(fc))
  except Exception as e:
    print('tag not found (%s)' % str(e))
