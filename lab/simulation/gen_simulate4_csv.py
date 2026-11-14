#!/usr/bin/env python3
"""合并 test set_20000.csv + 20000_test_attack_label.csv → simulate4.csv
保留原始 IP 和特征，加入 Attack_Type 作为 label 列"""

import csv

FEATURES = 'test set_20000.csv'
LABELS   = '20000_test_attack_label.csv'
OUTPUT   = 'simulate4.csv'

with open(FEATURES, encoding='utf-8-sig', newline='') as ff, \
     open(LABELS,   encoding='utf-8-sig', newline='') as fl, \
     open(OUTPUT,   'w', encoding='utf-8', newline='') as fo:

    reader_f = csv.DictReader(ff)
    reader_l = csv.DictReader(fl)

    fieldnames = reader_f.fieldnames + ['label']
    writer = csv.DictWriter(fo, fieldnames=fieldnames)
    writer.writeheader()

    for row, lrow in zip(reader_f, reader_l):
        row['label'] = lrow['Attack_Type']
        writer.writerow(row)

print(f'生成完毕：{OUTPUT}')
