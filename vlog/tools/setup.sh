#!/usr/bin/env bash
# 브이로그 파이프라인 준비: Pretendard 폰트(npm), numpy/Pillow 확인. 여러 번 실행해도 안전합니다.
set -euo pipefail
VLOG="$(cd "$(dirname "$0")/.." && pwd)"
FONTS="$VLOG/.cache/fonts"
mkdir -p "$FONTS"

if [ ! -f "$FONTS/Pretendard-Regular.otf" ]; then
  tmp="$(mktemp -d)"
  (cd "$tmp" && npm pack --silent pretendard@1.3.9 >/dev/null && tar xzf pretendard-1.3.9.tgz)
  cp "$tmp"/package/dist/public/static/Pretendard-{Regular,Medium,SemiBold,Bold,ExtraBold}.otf "$FONTS/"
  rm -rf "$tmp"
fi

# 명조(자막·serif 썸네일), 둥근 굵은체(출근로그 썸네일), 손글씨(feat 박스): Google Fonts TTF
get_gf() {  # $1 패키지  $2 폴더/파일  $3 저장 이름
  [ -f "$FONTS/$3" ] && return
  tmp="$(mktemp -d)"
  (cd "$tmp" && npm pack --silent "@expo-google-fonts/$1" >/dev/null && tar xzf ./*.tgz)
  cp "$tmp/package/$2" "$FONTS/$3"
  rm -rf "$tmp"
}
get_gf gowun-batang 400Regular/GowunBatang_400Regular.ttf GowunBatang-Regular.ttf
get_gf gowun-batang 700Bold/GowunBatang_700Bold.ttf GowunBatang-Bold.ttf
get_gf jua 400Regular/Jua_400Regular.ttf Jua-Regular.ttf
get_gf nanum-myeongjo 400Regular/NanumMyeongjo_400Regular.ttf NanumMyeongjo-Regular.ttf
get_gf nanum-myeongjo 700Bold/NanumMyeongjo_700Bold.ttf NanumMyeongjo-Bold.ttf
get_gf nanum-pen-script 400Regular/NanumPenScript_400Regular.ttf NanumPenScript-Regular.ttf

python3 -c "import numpy, PIL" 2>/dev/null || pip install -q numpy pillow
command -v ffmpeg >/dev/null || { echo "ffmpeg 가 필요합니다 (apt-get install -y ffmpeg)"; exit 1; }
[ -f /usr/share/fonts/truetype/noto/NotoColorEmoji.ttf ] || echo "경고: 컬러 이모지 폰트 없음 (apt-get install -y fonts-noto-color-emoji)"
echo "준비 완료: $FONTS"
