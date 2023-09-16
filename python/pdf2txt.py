#!/usr/bin/env python3

import pdf2txt
import sys

filename = sys.argv[1]
with open(filename, 'rb') as f:
    pdf = pdf2txt.PDF(f)

# Iterate over all the pages
for page in pdf:
    print(page)

