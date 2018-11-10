#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import copy
import signal
import struct
import re
import argparse
import ebooklib
from ebooklib import epub
import subprocess
import pprint
import magic
from profanity_filter import ProfanityFilter

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

METADATA_FILESPEC = "/tmp/metadata.opf"
def main():
  devnull = open(os.devnull, 'w')

  parser = argparse.ArgumentParser(description='e-book profanity scrubber', add_help=False, usage='cleanbook.py [options]')
  requiredNamed = parser.add_argument_group('required arguments')
  requiredNamed.add_argument('-i', '--input', required=True, dest='input', metavar='<STR>', type=str, default='', help='Input file')
  requiredNamed.add_argument('-o', '--output', required=True, dest='output', metavar='<STR>', type=str, default='', help='Output file')
  parser.add_argument('-l', '--languages', dest='languages', metavar='<STR>', type=str, default='en', help='Test for profanity using specified languages (comma separated, default: en)')
  parser.add_argument('-w', '--whole-words', dest='censor_whole_words', action='store_true', help='Censor whole words (default: false)')
  parser.add_argument('-d', '--deep', dest='deep_analysis', action='store_true', help='Deep analysis (default: false, may cause some issues depending on word list)')
  try:
    parser.error = parser.exit
    args = parser.parse_args()
  except SystemExit:
    parser.print_help()
    exit(2)

  # initialize the profanity filter
  pf = ProfanityFilter(languages=args.languages.split(','), censor_whole_words=args.censor_whole_words, deep_analysis=args.deep_analysis)

  # determine the type of the ebook
  bookMagic = "application/octet-stream"
  with magic.Magic() as m:
    bookMagic = m.id_filename(args.input)

  eprint(f"Processing \"{args.input}\" of type \"{''.join(bookMagic)}\"")

  # save off the metadata to be restored after conversion
  eprint(f"Extracting metadata...")
  metadataExitCode = subprocess.call(["/usr/bin/ebook-meta", "--to-opf="+METADATA_FILESPEC, args.input], stdout=devnull, stderr=devnull)
  if (metadataExitCode != 0):
    raise subprocess.CalledProcessError(metadataExitCode, f"/usr/bin/ebook-meta --to-opf={METADATA_FILESPEC} {args.input}")

  # convert the book from whatever format it is into epub for conversion
  if "epub" in bookMagic.lower():
    epubFileSpec = args.input
    wasEpub = True
  else:
    wasEpub = False
    epubFileSpec = "/tmp/ebook.epub"
    eprint(f"Converting to EPUB...")
    toEpubExitCode = subprocess.call(["/usr/bin/ebook-convert", args.input, epubFileSpec], stdout=devnull, stderr=devnull)
    if (toEpubExitCode != 0):
      raise subprocess.CalledProcessError(toEpubExitCode, f"/usr/bin/ebook-convert {args.input} {epubFileSpec}")

  eprint(f"Processing book contents...")
  book = epub.read_epub(epubFileSpec)
  newBook = epub.EpubBook()
  newBook.spine = ['nav']
  for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
      cleanLines = []
      dirtyLines = item.get_content().decode("latin-1").split("\n")
      for line in dirtyLines:
        try:
          censoredLine = pf.censor(line)
        except BaseException as error:
          eprint(f"Got error \"{format(error)}\" censoring [{line}], it will not be censored!")
          censoredLine = line
        cleanLines.append(censoredLine)
      item.set_content("\n".join(cleanLines).encode("latin-1"))
      newBook.spine.append(item)
      newBook.add_item(item)
    else:
      newBook.add_item(item)

  book.add_item(epub.EpubNcx())
  book.add_item(epub.EpubNav())
  epub.write_epub(args.output, newBook)

if __name__ == '__main__': main()
