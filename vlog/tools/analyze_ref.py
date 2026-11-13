#!/usr/bin/env python3
"""레퍼런스 릴스(내려받은 mp4)의 편집 감성을 숫자로 뽑아 프리셋에 반영한다.

    python3 vlog/tools/analyze_ref.py ref1.mp4 ref2.mp4 ...                 # 분석만
    python3 vlog/tools/analyze_ref.py refs/*.mp4 --against out/vlog.mp4 \\
            --preset default --save-as reels-mood                           # 새 프리셋 제안·저장

뽑는 값: 길이, 컷 수, 평균 컷 길이, 밝기/블랙 리프트/화이트 레벨, 대비, 채도, 웜톤(R-B), 음량.
각 영상 옆에 contact sheet(.sheet.jpg)를 만들어 눈으로도 확인할 수 있게 한다.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(cmd):
    return subprocess.run(cmd, capture_output=True)


def stats(path):
    dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout or 0)
    cuts = [float(x) for x in re.findall(rb"pts_time:([0-9.]+)", sh(
        ["ffmpeg", "-i", path, "-vf", "select='gt(scene,0.12)',showinfo", "-f", "null", "-"]).stderr)]
    cuts = [c for i, c in enumerate(cuts) if i == 0 or c - cuts[i - 1] > 0.2]
    shots = np.diff([0.0] + cuts + [dur])
    raw = sh(["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=4,scale=90:160", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
    px = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(float) / 255
    luma = px @ [0.2126, 0.7152, 0.0722]
    mx, mn = px.max(1), px.min(1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    vol = re.search(rb"mean_volume: (-?[0-9.]+)", sh(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"]).stderr)
    sh(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf", f"fps={16 / max(dur, 1):.4f},scale=180:-1,tile=8x2", "-frames:v", "1",
        os.path.splitext(path)[0] + ".sheet.jpg"])
    return {
        "file": os.path.basename(path), "duration": round(dur, 2), "shots": len(shots),
        "avg_shot": round(float(shots.mean()), 2), "min_shot": round(float(shots.min()), 2), "max_shot": round(float(shots.max()), 2),
        "luma_mean": round(float(luma.mean()), 3), "black_p2": round(float(np.percentile(luma, 2)), 3),
        "white_p98": round(float(np.percentile(luma, 98)), 3), "contrast_std": round(float(luma.std()), 3),
        "saturation": round(float(sat.mean()), 3), "warmth_r_minus_b": round(float((px[:, 0] - px[:, 2]).mean()), 3),
        "mean_volume_db": float(vol.group(1)) if vol else None,
    }


def suggest(ref, cur, P):
    """현재 결과물(cur)을 레퍼런스 평균(ref)에 가깝게 옮기는 프리셋 수정안."""
    g = P["grade"]
    g["saturation"] = round(float(np.clip(g["saturation"] * ref["saturation"] / max(cur["saturation"], 1e-3), 0.6, 1.2)), 3)
    g["contrast"] = round(float(np.clip(g["contrast"] * ref["contrast_std"] / max(cur["contrast_std"], 1e-3), 0.7, 1.15)), 3)
    g["brightness"] = round(float(np.clip(g["brightness"] + (ref["luma_mean"] - cur["luma_mean"]) * 0.8, -0.1, 0.1)), 3)
    lift = float(np.clip(ref["black_p2"], 0.0, 0.15))
    warm = float(np.clip((ref["warmth_r_minus_b"] - cur["warmth_r_minus_b"]) * 0.5, -0.05, 0.05))
    top = float(np.clip(ref["white_p98"] + 0.02, 0.85, 1.0))
    g["curves"] = {
        "r": f"0/{lift + 0.01:.3f} 0.5/{0.5 + 0.035 + warm:.3f} 1/{min(1, top + 0.01):.3f}",
        "g": f"0/{lift + 0.005:.3f} 0.5/{0.515:.3f} 1/{top:.3f}",
        "b": f"0/{lift:.3f} 0.5/{0.47 - warm:.3f} 1/{max(0.85, top - 0.05):.3f}",
    }
    P["_avg_shot_target"] = ref["avg_shot"]
    return P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("refs", nargs="+")
    ap.add_argument("--against", help="비교할 내 결과물 mp4")
    ap.add_argument("--preset", default="default")
    ap.add_argument("--save-as", help="제안 프리셋을 presets/<이름>.json 으로 저장")
    a = ap.parse_args()

    rows = [stats(p) for p in a.refs]
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    keys = [k for k in rows[0] if isinstance(rows[0][k], (int, float)) and rows[0][k] is not None]
    avg = {k: float(np.mean([r[k] for r in rows if r[k] is not None])) for k in keys}
    print("레퍼런스 평균:", json.dumps({k: round(v, 3) for k, v in avg.items()}, ensure_ascii=False))

    if a.against:
        cur = stats(a.against)
        print("내 결과물:  ", json.dumps(cur, ensure_ascii=False))
        P = json.load(open(os.path.join(ROOT, "presets", a.preset + ".json"), encoding="utf-8"))
        P = suggest(avg, cur, P)
        print("제안 grade:", json.dumps(P["grade"], ensure_ascii=False))
        print(f"레퍼런스 평균 컷 길이 {avg['avg_shot']:.2f}s → storyboard 클립 길이(in/out 또는 speed)를 여기에 맞추세요.")
        if a.save_as:
            P["name"] = a.save_as
            path = os.path.join(ROOT, "presets", a.save_as + ".json")
            json.dump(P, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("저장:", path)


if __name__ == "__main__":
    main()
