"""归档还原：把增量归档（.csv.gz）还原为 CSV，输出到数据目录的 restored/。只读归档，不改数据库。

不带 --merge：每个归档一个 CSV。
带 --merge：合并为一个 CSV，按第一列 id 去重（归档之间有 OVERLAP 重叠）。
"""

import gzip
from datetime import datetime
from pathlib import Path

from knettf_common import DATA_DIR, check_safety


def run(args):
    check_safety()
    inc_dir = DATA_DIR / "increments"
    if args.files:
        # 相对路径按数据目录的 increments/ 解析，绝对路径原样使用
        files = [Path(f) if Path(f).is_absolute() else inc_dir / f for f in args.files]
    else:
        files = sorted(inc_dir.glob("collect-*.csv.gz"))
    if not files:
        raise SystemExit(f"❌ 没有找到归档（目录：{DATA_DIR / 'increments'}）")

    out_dir = DATA_DIR / "restored"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.merge:
        for f in files:
            out = out_dir / f.name.removesuffix(".gz")
            with gzip.open(f, "rb") as src, open(out, "wb") as dst:
                dst.write(src.read())
            print(f"{out.stat().st_size} 字节 → {out}")
        return

    out = out_dir / f"collect-merged-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    seen: set[str] = set()
    n = 0
    with open(out, "w", encoding="utf-8", newline="") as dst:
        header_written = False
        for f in files:
            with gzip.open(f, "rt", encoding="utf-8", newline="") as src:
                for i, line in enumerate(src):
                    if i == 0:
                        if not header_written:
                            dst.write(line)
                            header_written = True
                        continue
                    key = line.split(",", 1)[0]
                    if key in seen:
                        continue
                    seen.add(key)
                    dst.write(line)
                    n += 1
    print(f"合并 {len(files)} 个归档，去重后 {n} 条 → {out}")
