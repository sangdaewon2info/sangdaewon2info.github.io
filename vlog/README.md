# 데일리 오피스 브이로그 파이프라인

촬영 클립 + `storyboard.json` 하나 → 보정·자막·음악·효과음이 들어간 완성 영상, 썸네일, 업로드용 캡션.

```
vlog/
├── PROMPT.md               매일 쓰는 요청 프롬프트 · 스타일 바이블 · 자막 규칙
├── presets/
│   ├── reels-natural.json  레퍼런스 릴스 감성: 선명한 자연색, 박스 없는 작은 명조 자막, 빠른 오프닝 훅 (현재 사용)
│   └── default.json        처음 버전: 베이지 웜톤, 필 박스 자막, 로파이 음악
├── days/
│   └── 2026-11-12/
│       ├── storyboard.json 그날의 컷 · 시간 태그 · 자막 · 효과음 · 썸네일 · 캡션
│       ├── raw/            원본 클립 (git 제외)
│       └── out/            vlog.mp4 · thumb_N.jpg · post.txt (git 제외)
└── tools/
    ├── setup.sh            Pretendard 폰트 등 준비
    ├── build.py            렌더링
    └── analyze_ref.py      레퍼런스 릴스 분석 → 프리셋 제안
```

## 매일 하는 일

1. 클립을 올리고 Claude Code에서 `/daily-vlog` + `PROMPT.md`의 A 템플릿을 보냅니다.
2. Claude가 `days/<날짜>/storyboard.json`을 만들고 렌더링한 뒤 결과물을 보내줍니다.
3. 자막이나 컷을 고치고 싶으면 말로 요청하거나 `storyboard.json`을 직접 고치고 다시 빌드합니다.

직접 돌릴 때:

```bash
bash vlog/tools/setup.sh                      # 처음 한 번
python3 vlog/tools/build.py vlog/days/2026-11-12
```

## storyboard.json

```jsonc
{
  "date": "2026-11-12",
  "preset": "reels-natural",
  "preset_overrides": { "grade": { "saturation": 0.9 } },   // 선택: 그날만 바꾸기
  "intro": {                                                 // 선택: 오프닝 훅 (0.4초 컷 몽타주 + 타이틀)
    "title": ["A day in my life", "10am – 9pm", "Yongin → Gangnam"],
    "shots": [{ "clip": 0, "at": 0.85, "dur": 0.4 }]        // 본편 클립 번호 + 그 클립 안에서의 시작 초
  },
  "clips": [
    { "src": "raw/a.mp4", "in": 0.0, "out": 1.8,             // 원본에서 쓸 구간(초)
      "speed": 1.2,                                          // 선택: 기본은 preset.pacing.speed
      "tag": "09:50 AM", "text": "집 나서기 1분 전 착장 점검 🤎",
      "sfx": [{ "type": "shutter", "at": 0.3 }] }            // leaves footsteps cup keyboard ding shutter pour
  ],
  "thumbnails": [                                            // style 4종
    { "style": "chunky", "clip": 2, "at": 0.4, "label": "문과 BD", "lines": ["강남", "IT 회사원", "출근로그"], "accent": [1], "feat": "feat 용인에서 출근 🥲" },
    { "style": "butter", "clip": 0, "at": 0.85, "title": "Work Day\nin my life", "sub": "용인 → 강남 출퇴근 직장인의 하루" },
    { "style": "serif",  "clip": 2, "at": 0.4, "lines": ["A day in my life", "10am – 9pm", "Yongin → Gangnam"] },
    { "style": "classic", "clip": 2, "at": 0.4, "tag": "SEOUL OFFICE VLOG", "copy": "..." }
  ],                                                         // 공통: "y"(0~1)로 글자 높이 조절, 카피 안 "\n"으로 줄바꿈
  "post": { "caption": "...", "hashtags": ["#직장인브이로그"] }
}
```

## 감성 바꾸기 (레퍼런스 맞추기)

마음에 드는 릴스를 mp4로 저장해서 올린 뒤:

```bash
python3 vlog/tools/analyze_ref.py ref1.mp4 ref2.mp4 ref3.mp4 \
        --against vlog/days/2026-11-12/out/vlog.mp4 --save-as reels-mood
```

평균 컷 길이, 밝기, 블랙 리프트, 대비, 채도, 웜톤을 비교해서 `presets/reels-mood.json`을 만듭니다. 각 레퍼런스 옆에 contact sheet(`.sheet.jpg`)도 생기니 눈으로 함께 확인하세요. 이후 storyboard의 `"preset": "reels-mood"`로 바꾸면 그 감성으로 렌더링됩니다.

## 참고

- 이 저장소는 공개 저장소라서 `raw/`와 `out/`(얼굴이 나오는 영상·사진)은 `.gitignore`로 커밋하지 않습니다.
- 썸네일 스타일: `chunky`(둥근 굵은 글씨 + 민트 강조 + 손글씨 feat 박스), `butter`(버터 옐로 영문 제목 + 한글 부제), `serif`(명조 A day in my life), `classic`(필 박스 카피).
- 음악은 매일 날짜를 seed로 코드/아르페지오가 바뀌는 자체 생성 로파이라 저작권 문제가 없습니다. 인스타 인기 음원을 쓰려면 `music.mode`를 `"none"`으로 두고 앱에서 음원을 붙이세요.
