---
name: daily-vlog
description: 업로드한 촬영 클립으로 그날의 오피스 브이로그(보정·자막·로파이 음악·ASMR 효과음·썸네일·인스타 캡션)를 만든다. 사용자가 "/daily-vlog", "오늘 브이로그 만들어줘", 클립을 올리며 브이로그 편집을 요청할 때 사용.
---

# daily-vlog

파이프라인 설명은 `vlog/README.md`, 요청 템플릿·스타일·자막 규칙은 `vlog/PROMPT.md`에 있다. 둘 다 먼저 읽는다.

## 순서

1. **준비**: `bash vlog/tools/setup.sh`
2. **날짜 폴더**: `vlog/days/<YYYY-MM-DD>/raw/`를 만들고 업로드된 클립을 복사한다 (파일명은 순서가 보이게 `01_mirror.mp4`처럼).
3. **클립 파악**: 각 클립의 길이(ffprobe), 컷 위치(`select='gt(scene,0.12)',showinfo`), contact sheet(`fps=4,scale=180:-1,tile=8x8`)를 만들어 직접 본다. 하나로 이어진 영상이면 컷 위치로 구간을 나눈다.
4. **storyboard.json 작성**: 사용자의 장면 메모를 따르고, 빈 자막은 PROMPT.md C 규칙으로 채운다. 클립은 1.5~2.0초, 장면에 맞는 sfx를 단다. 썸네일은 얼굴과 옷이 또렷한 프레임 2~3개. 영상이 메모와 다르면(예: 낙엽이 없는 보도) 화면에 맞춰 쓰고 사용자에게 알린다.
5. **렌더링**: `python3 vlog/tools/build.py vlog/days/<날짜>`
6. **확인**: 결과 영상에서 장면마다 한 프레임씩 뽑아 자막 줄바꿈·이모지·가림을 확인하고, 문제가 있으면 고쳐서 다시 빌드한다.
7. **전달**: `out/vlog.mp4`, `out/thumb_*.jpg`, `out/post.txt` 내용을 SendUserFile로 보내고, 적용한 것과 메모와 달라진 점을 짧게 알린다.
8. **커밋**: `storyboard.json`만 커밋한다. `raw/`, `out/`은 공개 저장소에 올리지 않는다(.gitignore).

## 레퍼런스 감성 맞추기

사용자가 레퍼런스 영상 파일을 주면 `vlog/tools/analyze_ref.py <refs> --against <내 결과물> --save-as <이름>`으로 프리셋을 만들고, contact sheet를 보며 숫자를 눈으로 다듬는다. 인스타 링크만 주면 이 환경에서는 열 수 없으니 mp4 저장본이나 화면 녹화를 요청한다.
