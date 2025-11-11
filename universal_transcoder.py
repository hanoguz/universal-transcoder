#!/usr/bin/env python3
"""
universal_transcoder.py
=======================
CLI-only universal video/audio transcoder/remuxer using FFmpeg.

Key features
------------
- Works with any input format supported by ffmpeg.
- Choose target container via --target-format (alias: --output-ext).
- Quality presets: --quality {auto,ultra,high,balanced,fast,custom}
- Auto mode: remux if codecs are container-compatible, else transcode.
- Full manual control for codecs/CRF/preset/bitrate when needed.
- Batch on folders, optional recursion, subtitle copy/drop, deinterlace, scale.

Examples
--------
# Auto quality, MP4 target (remux if possible, else CRF20/preset fast, 192k audio)
python universal_transcoder.py --input "C:\in\movie.mkv" --target-format mp4 --quality auto --overwrite

# Ultra quality H.264 MP4 (CRF 18, slow, 320k)
python universal_transcoder.py --input "C:\in" --target-format mp4 --quality ultra --overwrite

# High/Balanced/Fast qualities
python universal_transcoder.py --input "C:\in" --target-format mkv --quality high --overwrite
python universal_transcoder.py --input "C:\in" --target-format mp4 --quality balanced --overwrite
python universal_transcoder.py --input "C:\in" --target-format webm --quality fast --overwrite

# Custom (full control)
python universal_transcoder.py --input "C:\in\file.avi" --target-format mp4 --quality custom \
  --mode transcode --vcodec libx264 --acodec aac --crf 18 --preset slow --audio-bitrate 320k --overwrite
"""

import argparse
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple, List

# ----------------------- Utilities -----------------------

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def require_tools():
    for tool in ("ffmpeg", "ffprobe"):
        if not which(tool):
            print(f"[ERROR] Required tool not found in PATH: {tool}")
            print("Please install FFmpeg (includes ffprobe) and try again.")
            sys.exit(1)

def run_streaming(cmd: list) -> int:
    print(">>", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
    try:
        for line in proc.stdout:
            if line.strip():
                print(line.rstrip())
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
        raise
    return proc.wait()

def ffprobe_codecs(file: Path) -> Tuple[Optional[str], Optional[str]]:
    """Return (vcodec, acodec) names using ffprobe, or (None, None) if absent."""
    vcodec = None
    acodec = None
    try:
        vcodec = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(file)
        ], text=True).strip() or None
    except subprocess.CalledProcessError:
        pass
    try:
        acodec = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(file)
        ], text=True).strip() or None
    except subprocess.CalledProcessError:
        pass
    return vcodec, acodec

def container_allows_codecs(container: str, vcodec: Optional[str], acodec: Optional[str]) -> bool:
    """
    Conservative checks. If unsure, return False to force transcode.
    """
    container = (container or "").lower()
    v = (vcodec or "").lower()
    a = (acodec or "").lower()

    if container in {"mkv"}:
        return True  # MKV is very permissive

    if container in {"mp4", "m4v", "mov"}:
        v_ok = v in {"h264", "hevc", "mpeg4"}
        a_ok = a in {"aac", "mp3", "ac3", "eac3"} or a == ""
        return v_ok and a_ok

    if container in {"webm"}:
        v_ok = v in {"vp8", "vp9"}
        a_ok = a in {"vorbis", "opus"}
        return v_ok and a_ok

    if container in {"mpg", "mpeg", "ts", "m2ts"}:
        v_ok = v in {"mpeg1video", "mpeg2video"}
        a_ok = a in {"mp2", "mp1", "ac3"}
        return v_ok and a_ok

    if container in {"avi"}:
        v_ok = v in {"mpeg4", "msmpeg4v3", "h263", "h264"}
        a_ok = a in {"mp3", "ac3", "aac"}
        return v_ok and a_ok

    return False

def default_container_flags(container: str) -> list:
    container = (container or "").lower()
    flags = []
    if container in {"mp4", "m4v", "mov"}:
        flags += ["-movflags", "+faststart", "-pix_fmt", "yuv420p"]
    return flags

def discover_inputs(path: Path, include_ext: List[str], recursive: bool) -> List[Path]:
    if path.is_file():
        return [path]
    exts = {e.lower().lstrip(".") for e in include_ext}
    pattern = "**/*" if recursive else "*"
    files = []
    for p in path.glob(pattern):
        if p.is_file() and p.suffix.lower().lstrip(".") in exts:
            files.append(p)
    return sorted(files)

# ----------------------- Main conversion logic -----------------------

def build_ffmpeg_cmd(
    src: Path,
    dst: Path,
    mode: str,
    vcodec: str,
    acodec: str,
    crf: Optional[str],
    preset: Optional[str],
    video_bitrate: Optional[str],
    maxrate: Optional[str],
    bufsize: Optional[str],
    audio_bitrate: Optional[str],
    scale: Optional[str],
    deint: bool,
    extra_filters: Optional[str],
    copy_subs: bool,
    no_subs: bool,
    burn_subs: Optional[Path],
    threads: Optional[int],
    overwrite: bool
) -> list:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info"]
    cmd += ["-y" if overwrite else "-n", "-i", str(src)]

    vf_chain = []
    if deint:
        vf_chain.append("yadif")
    if scale:
        vf_chain.append(f"scale={scale}")
    if extra_filters:
        vf_chain.append(extra_filters)

    if burn_subs:
        subs_path = str(burn_subs).replace("\\", "\\\\").replace(":", r"\:")
        vf_chain.append(f"subtitles='{subs_path}'")

    if no_subs:
        cmd += ["-sn"]
    elif copy_subs:
        cmd += ["-c:s", "copy"]

    if mode == "remux":
        cmd += ["-c", "copy"]
        cmd += default_container_flags(dst.suffix.lstrip(".").lower())
        cmd += [str(dst)]
        return cmd

    if vcodec:
        cmd += ["-c:v", vcodec]
        if vcodec in {"libx264", "libx265", "h264_nvenc", "hevc_nvenc"}:
            if crf and not video_bitrate:
                cmd += ["-crf", str(crf)]
            if preset:
                cmd += ["-preset", preset]
        if video_bitrate:
            cmd += ["-b:v", video_bitrate]
        if maxrate:
            cmd += ["-maxrate", maxrate]
        if bufsize:
            cmd += ["-bufsize", bufsize]

    if acodec:
        cmd += ["-c:a", acodec]
        if audio_bitrate and acodec not in {"copy"}:
            cmd += ["-b:a", audio_bitrate]

    if vf_chain:
        cmd += ["-vf", ",".join(vf_chain)]

    cmd += default_container_flags(dst.suffix.lstrip(".").lower())

    if threads:
        cmd += ["-threads", str(threads)]

    cmd += [str(dst)]
    return cmd

def main():
    parser = argparse.ArgumentParser(description="Universal batch transcoder/remuxer using ffmpeg.")
    parser.add_argument("--input", required=True, help="Input file or folder.")
    parser.add_argument("--output", default=None, help="Output folder (default: alongside input or same folder).")
    parser.add_argument("--output-ext", default=None, help="Target container extension, e.g. mp4, mkv, webm, avi, ts, mpg.")
    parser.add_argument("--target-format", default=None, help="Alias for --output-ext.")
    parser.add_argument("--quality", choices=["auto","ultra","high","balanced","fast","custom"], default="auto",
                        help="Quality preset. 'auto' tries remux else CRF20/fast/192k.")
    parser.add_argument("--mode", choices=["auto", "remux", "transcode"], default="auto", help="Only used with --quality custom (or to override).")
    parser.add_argument("--include-ext", default="mp4,mkv,avi,ts,m2ts,mpg,mpeg,dat,mov,webm,flv,vob,wmv,3gp",
                        help="Comma list of input extensions to process when input is a folder.")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subfolders when input is a folder.")
    parser.add_argument("--vcodec", default=None, help="Video codec for transcode: libx264, libx265, libvpx-vp9, h264_nvenc, hevc_nvenc, copy, ...")
    parser.add_argument("--acodec", default=None, help="Audio codec for transcode: aac, libopus, libvorbis, mp3, ac3, copy, ...")
    parser.add_argument("--crf", default=None, help="CRF value (e.g., 18). Applies to x264/x265/NVENC CQ when no -b:v given.")
    parser.add_argument("--preset", default=None, help="Encoder preset (x264/x265/NVENC).")
    parser.add_argument("--b:v", dest="video_bitrate", default=None, help="Target video bitrate (e.g., 5M).")
    parser.add_argument("--maxrate", default=None, help="Max video rate (VBV).")
    parser.add_argument("--bufsize", default=None, help="VBV buffer size (e.g., 10M).")
    parser.add_argument("--audio-bitrate", default=None, help="Audio bitrate for lossy audio (e.g., 128k, 192k, 320k).")
    parser.add_argument("--scale", default=None, help="Scale WxH (e.g., 1280:720).")
    parser.add_argument("--deinterlace", action="store_true", help="Apply yadif deinterlacing.")
    parser.add_argument("--filters", default=None, help="Extra video filters chain, e.g., 'hqdn3d=4.0:3.0:6.0:4.5,unsharp=3:3:0.5'")
    parser.add_argument("--copy-subs", action="store_true", help="Copy subtitles stream(s) when possible.")
    parser.add_argument("--no-subs", action="store_true", help="Drop subtitles.")
    parser.add_argument("--burn-subs", default=None, help="Burn external .srt into video.")
    parser.add_argument("--threads", type=int, default=None, help="ffmpeg -threads value.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite outputs if exist.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without running ffmpeg.")
    args = parser.parse_args()

    require_tools()

    # Resolve target container
    out_ext = args.target_format or args.output_ext
    if not out_ext:
        print("[ERROR] You must specify --target-format (e.g., mp4)")
        sys.exit(2)
    out_ext = out_ext.lstrip(".").lower()

    inp = Path(args.input).expanduser().resolve()
    out_root = Path(args.output).expanduser().resolve() if args.output else None

    include_ext = [e.strip() for e in args.include_ext.split(",") if e.strip()]
    recursive = args.recursive

    files = []
    if inp.is_file():
        files = [inp]
    else:
        files = discover_inputs(inp, include_ext, recursive)

    if not files:
        print(f"[ERROR] No input files found under: {inp}")
        sys.exit(2)

    print(f"Found {len(files)} file(s). Target: .{out_ext} | Quality: {args.quality}")

    # Defaults per container
    VCODEC_DEFAULTS = {"mp4":"libx264","mkv":"libx264","webm":"libvpx-vp9","avi":"libx264","ts":"libx264","mpg":"libx264"}
    ACODEC_DEFAULTS = {"mp4":"aac","mkv":"aac","webm":"libopus","avi":"aac","ts":"aac","mpg":"aac"}

    for src in files:
        out_dir = out_root if out_root else src.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / (src.stem + f".{out_ext}")

        vcodec, acodec = ffprobe_codecs(src)
        print(f"\n--- {src} ---")
        print(f"Detected: video={vcodec} | audio={acodec}")

        # Decide mode/codecs based on quality preset
        effective_mode = "auto"
        vcodec_use = args.vcodec
        acodec_use = args.acodec
        crf_use = args.crf
        preset_use = args.preset
        abr_use = args.audio_bitrate

        if args.quality == "auto":
            if container_allows_codecs(out_ext, vcodec, acodec):
                effective_mode = "remux"
            else:
                effective_mode = "transcode"
                vcodec_use = vcodec_use or VCODEC_DEFAULTS.get(out_ext, "libx264")
                acodec_use = acodec_use or ACODEC_DEFAULTS.get(out_ext, "aac")
                crf_use = crf_use or "20"
                preset_use = preset_use or "fast"
                abr_use = abr_use or "192k"

        elif args.quality == "ultra":
            effective_mode = "transcode"
            vcodec_use = vcodec_use or VCODEC_DEFAULTS.get(out_ext, "libx264")
            acodec_use = acodec_use or ACODEC_DEFAULTS.get(out_ext, "aac")
            crf_use = crf_use or "18"
            preset_use = preset_use or "slow"
            abr_use = abr_use or "320k"

        elif args.quality == "high":
            effective_mode = "transcode"
            vcodec_use = vcodec_use or VCODEC_DEFAULTS.get(out_ext, "libx264")
            acodec_use = acodec_use or ACODEC_DEFAULTS.get(out_ext, "aac")
            crf_use = crf_use or "19"
            preset_use = preset_use or "medium"
            abr_use = abr_use or "256k"

        elif args.quality == "balanced":
            effective_mode = "transcode"
            vcodec_use = vcodec_use or VCODEC_DEFAULTS.get(out_ext, "libx264")
            acodec_use = acodec_use or ACODEC_DEFAULTS.get(out_ext, "aac")
            crf_use = crf_use or "21"
            preset_use = preset_use or "fast"
            abr_use = abr_use or "192k"

        elif args.quality == "fast":
            effective_mode = "transcode"
            vcodec_use = vcodec_use or VCODEC_DEFAULTS.get(out_ext, "libx264")
            acodec_use = acodec_use or ACODEC_DEFAULTS.get(out_ext, "aac")
            crf_use = crf_use or "23"
            preset_use = preset_use or "veryfast"
            abr_use = abr_use or "160k"

        else:  # custom
            effective_mode = args.mode
            # user-specified codecs and rates are already in *_use variables

        print(f"Mode chosen: {effective_mode}")
        extra_filters = args.filters
        burn_subs = Path(args.burn_subs).expanduser().resolve() if args.burn_subs else None

        cmd = build_ffmpeg_cmd(
            src=src, dst=dst, mode=effective_mode,
            vcodec=vcodec_use, acodec=acodec_use,
            crf=crf_use, preset=preset_use,
            video_bitrate=args.video_bitrate,
            maxrate=args.maxrate, bufsize=args.bufsize,
            audio_bitrate=abr_use,
            scale=args.scale, deint=args.deinterlace,
            extra_filters=extra_filters,
            copy_subs=args.copy_subs, no_subs=args.no_subs,
            burn_subs=burn_subs, threads=args.threads,
            overwrite=args.overwrite
        )

        if args.dry_run:
            print("[DRY-RUN]", " ".join(cmd))
            continue

        rc = run_streaming(cmd)
        if rc == 0:
            print(f"[OK] -> {dst}")
        else:
            print(f"[FAIL] {src} (exit {rc})")

if __name__ == "__main__":
    main()
