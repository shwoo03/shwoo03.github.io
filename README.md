# 스우스우 블로그

Jekyll + [Chirpy](https://github.com/cotes2020/jekyll-theme-chirpy)로 만든 개인 블로그입니다.

## 글 작성

1. `_drafts/post-template.md` 내용을 복사합니다.
2. `_posts/YYYY-MM-DD-slug.md` 파일로 저장합니다. 예: `_posts/2026-09-29-first-note.md`
3. 제목, 설명, 카테고리, 태그와 본문을 수정합니다.
4. `main`에 커밋하면 GitHub Actions가 빌드하고 GitHub Pages에 배포합니다.

`_drafts`는 블로그에 게시되지 않지만 이 저장소는 공개되어 있으므로 비공개 메모나 비밀정보를 넣지 않습니다.

이미지는 `assets/img/posts/`에 넣고 `![설명](/assets/img/posts/example.png)`로 연결합니다.

## 설정과 미리보기

- 사이트 설정: `_config.yml`
- 소개: `_tabs/about.md`
- 연락처 링크: `_data/contact.yml`
- 배포 결과: 저장소의 Actions 탭

Ruby 3.4와 Bundler를 설치한 환경에서:

```sh
bundle install
bundle exec jekyll serve
```

기본 미리보기 주소는 `http://127.0.0.1:4000`입니다. 초안까지 미리 보려면 `--drafts`를 추가합니다.

## 배포 검증

```sh
JEKYLL_ENV=production bundle exec jekyll build
bundle exec htmlproofer _site --disable-external
```

## 라이선스

테마와 Starter의 MIT 라이선스는 `LICENSE`를 참고하세요.
