import re, math
entity = re.compile('<code.*?>(.*?)</code>.*?<td> (.*?) </td>')
hex_strings = re.compile('[0-9a-fA-F]+')

def entity_processor_json(input, json):
  json.write('{\n')
  last = None
  for line in input:
    match = entity.search(line)
    name, points =  match.groups(1)
    points = hex_strings.findall(points)
    if len(points) == 1:
      codepoint = int(points[0], 16)
      if codepoint <= 0xFFFF:
        data = '"codepoints": [{0:d}], "characters": "\u{1:0.4X}"'.format(codepoint, codepoint)
      else:
        highSurrogate = int(math.floor((codepoint - 0x10000) / 0x400) + 0xD800)
        lowSurrogate = int((codepoint - 0x10000) % 0x400 + 0xDC00)
        data = '"codepoints": [{0:d}], "characters": "\u{1:0.4X}\u{2:0.4X}"'.format(codepoint, highSurrogate, lowSurrogate)
    else:
      points = map(lambda s: int(s, 16), points)
      data = '"codepoints": [{0:d}, {1:d}], "characters": "\u{2:0.4X}\u{3:0.4X}"'.format(points[0], points[1], points[0], points[1])
    if last: json.write(last + ',\n')
    last = '  "&{0!s}": {{ {1!s} }}'.format(name, data)
  json.write(last + "\n")
  json.write('}\n')

if __name__ == '__main__':
  import sys
  entity_processor_json(sys.stdin, sys.stdout) 
