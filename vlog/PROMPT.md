# 브이로그 프롬프트

매일 쓰는 프롬프트(A)와 스타일 기준 프롬프트(B), 자막 작성 규칙(C)입니다.

---

## A. 매일 쓰는 요청 프롬프트 (Claude Code에 붙여넣기)

촬영한 클립을 업로드한 뒤 아래를 채워서 보내면 됩니다. 비워둔 칸은 Claude가 영상을 보고 채웁니다.

```
/daily-vlog
날짜: 2026-11-13 (금)
스타일: soft-minimal       ← 프리셋 이름 (vlog/presets/*.json)
오프닝: Work Day in my life / 10am – 9pm / Yongin → Gangnam  (썸네일 제목과 같은 문구로)
길이: 16초 내외 / 컷당 1.5~2초
클립 순서: 업로드한 순서대로  ← 다르면 "3번 → 1번 → ..." 처럼 적기

장면 메모 (시간 · 상황 · 자막, 자막 비우면 자동 작성):
1. 08:40 AM · 현관 거울 OOTD ·
2. 08:50 AM · 출근길 발 POV ·
3. 09:30 AM · 사무실 거울샷 · 오늘의 니트 OOTD ✨
4. ...

효과음: 자동 (발걸음/낙엽/컵/타건/엘리베이터 딩/셔터/커피 따르기 중 장면에 맞게)
음악: 없음 (인스타 앱에서 음원 붙이기) / 필요하면 "로파이 넣어줘"
썸네일: butter (버터 레몬 Work Day in my life) / 거울 셀카 사진 따로 올리면 그걸로, 없으면 영상에서
포스트 캡션 + 해시태그: 자동
```

---

## B. 마스터 스타일 프롬프트 (스타일 바이블)

프리셋 숫자의 근거가 되는 원문입니다. CapCut AI나 다른 영상 AI에 그대로 써도 됩니다. `{ }` 부분만 바꾸세요.

```
[Video Overview]
A {16}-second aesthetic Korean daily office vlog of a stylish IT business-development
manager and working mom in Seoul. Quiet luxury, cozy {autumn} mood, minimalist,
effortless yet relatable. Shot on phone, vertical 9:16.

[Color Grading & Lighting]
Warm neutral tone, muted beige and soft cream palette. Slightly lifted blacks, subtle
film grain. Low contrast, -5% saturation. Authentic, unpolished yet chic
Scandinavian/Korean look. Natural daylight in the morning shots, soft office light indoors.

[Pacing & Rhythm]
Snappy jump cuts, 1.5–2.0 s per clip, landing on a calm lo-fi beat.
No wipes or fades: clean cuts only (micro-whip allowed).

[Storyboard]
{장면 1~N: 시간 · 장소 · 동작 · 카메라 (거울샷 / POV / 클로즈업 / 셀프캠)}
Arc: leaving home → commute → office arrival → small rituals (breakfast, hair, lunch)
→ focused work → clock-out mirror wave.

[Typography & Subtitle Styling Guide]
- Main Subtitles (Dialogue/Info): Modern clean Sans-Serif (Pretendard, Bareun Dotum, Paperlogy,
  S-Core Dream). High legibility, neutral aesthetic tone.
  Weight: Regular (no bold). Thin, light letterforms read as more refined.
- Sub/Point Subtitles (Emotion/Whisper): Delicate Serif or handwritten font (Nanum Myeongjo,
  Jeju Myeongjo, Memoment). Used for short side notes in brackets like (소신발언..) or <감성 포인트>.
- Letter Spacing (Tracking): -2 (tight and refined, eliminating loose spacing).
- Stroke: Ultra-thin subtle outline (Width 10). Avoid heavy, bulky borders.
- Shadow: Soft atmospheric drop shadow (Opacity 25%, Blur 15). Keep it subtle for pure legibility.
- Background Box: None. No badge, pill or box behind the text (boxes look dated); text sits
  directly on the footage in cream white. Legibility comes only from the ultra-thin stroke and the
  soft shadow. On very bright footage (white desk, sky), raise the shadow to 40-50% or move the
  line over a darker part of the frame.

[Sound]
Warm lo-fi indie acoustic bed (guitar arpeggio, soft e-piano, dusty drums, vinyl crackle)
with subtle ASMR on top: footsteps / leaf rustle, cup placed on wood, keyboard clicks,
elevator ding.
```

---

## C. 자막 작성 규칙

### 자막 디자인 (B의 Typography 가이드 요약, 프리셋 `clean-minimal`)

| 항목 | 기준 |
|---|---|
| 본문 자막 (정보·대사) | 깔끔한 산세리프: Pretendard, 바른돋움, Paperlogy, 에스코어 드림 |
| 굵기 | **Regular (볼드 금지)**. 얇고 가벼운 글씨가 더 세련돼 보임 |
| 포인트 자막 (감정·속삭임) | 섬세한 명조 또는 손글씨: 나눔명조, 제주명조, Memoment. 괄호 속 짧은 한마디에만 `(소신발언..)` `<감성 포인트>` |
| 자간 | -2 (빈틈 없이 촘촘하게) |
| 외곽선 | 아주 얇게 (두께 10). 두껍고 무거운 테두리 금지 |
| 그림자 | 은은하게 (불투명도 25%, 블러 15) |
| 배경 박스 | **없음**. 배지 · 필 · 박스 모두 쓰지 않음 (촌스러워 보임). 크림 화이트 글씨를 영상 위에 바로 올리고, 얇은 외곽선과 그림자로만 가독성 확보. 흰 책상처럼 아주 밝은 화면에서는 그림자를 40~50%로 올리거나 자막을 어두운 쪽으로 옮김 |

### 문장 쓰는 법

- soft-minimal 형식: 위쪽 가운데 명조 두 줄 (시간은 작게, 라벨은 굵고 크게). `시간`(9:50, 16:50처럼 24시간) + `짧은 라벨`(10자 안팎, 이모지 없이). 예) 7:40 / breakfast, 11:20 / 회의 전 앞머리 사수
- default 형식: `시간 태그` + `한 줄 문장 + 이모지 1개`, 1.5초 컷은 12자 안팎
- 오프닝 타이틀: `A day in my life` / `시작 – 끝 시간` / `Yongin → Gangnam`
- 말투: 친구에게 말하듯 담백하게. "~했어요", "~사수", "~직행", "냠냠"처럼 짧은 구어.
- 흐름: 장면마다 작은 사건 하나 (지각 위기 → 세이프 → 회의 준비 → 야근 → 퇴근).
- 썸네일 카피: `[장소] + [직업, 민트 강조] + [시리즈명]` + `feat 그날의 사건`. 예) 강남 / IT 회사원 / 출근로그 + feat 용인에서 출근 🥲
