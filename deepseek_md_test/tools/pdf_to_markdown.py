from pathlib import Path

import pymupdf4llm

from tools.timing import StepRecorder

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
OUT = ROOT / "output" / "markdown"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    pdfs = sorted(SAMPLES.glob("*.pdf"))
    with StepRecorder("pdf_to_markdown",
                      meta={"pdf_count": len(pdfs)}) as rec:
        rec.extra["files"] = []
        for pdf in pdfs:
            md = pymupdf4llm.to_markdown(str(pdf))
            target = OUT / (pdf.stem + ".md")
            target.write_text(md, encoding="utf-8")

            rec.extra["files"].append({
                "pdf": pdf.name,
                "markdown": target.name,
                "chars": len(md),
            })

            print(f"\n===== {pdf.name} =====")
            print(f"字符数: {len(md)}")
            print("--- 前 1000 字符 ---")
            print(md[:1000])
            print("--- 后 500 字符 ---")
            print(md[-500:])


if __name__ == "__main__":
    main()