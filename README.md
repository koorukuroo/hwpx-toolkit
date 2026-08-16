# hwpx-toolkit

한글(Hancom Office) HWPX 문서를 생성·읽기·편집·검증하는 MIT 라이선스 Claude 스킬.

- 순수 Python stdlib 코어 (pip install 불필요)
- 원본 바이트 보존 편집 (변경 엔트리 외 바이트 동일)
- 전달 전 필수 검증 게이트

## 사용법

    python3 scripts/hwpx.py extract 문서.hwpx            # 텍스트 추출
    python3 scripts/hwpx.py extract 문서.hwpx --format markdown
    python3 scripts/hwpx.py analyze 문서.hwpx            # 구조/슬롯 JSON
    python3 scripts/hwpx.py validate 문서.hwpx           # 구조 검증
    python3 scripts/hwpx.py unpack 문서.hwpx ./out/      # ZIP 해체
    python3 scripts/hwpx.py pack ./out/ 결과.hwpx --source 문서.hwpx
    python3 scripts/hwpx.py new 문서.md -o 문서.hwpx              # 마크다운 → HWPX
    python3 scripts/hwpx.py build --section sec.xml -o 문서.hwpx  # 직접 조립
    python3 scripts/hwpx.py replace 원본.hwpx 결과.hwpx --map map.json   # 문구 교체
    python3 scripts/hwpx.py fill 양식.hwpx 결과.hwpx --values values.json # 양식 채우기
    python3 scripts/hwpx.py set-text-style 원본.hwpx 결과.hwpx --after "제목" --bold --size 16
    python3 scripts/hwpx.py insert-image 원본.hwpx 결과.hwpx --image 그림.png --after "그림 위치" --width-mm 80
    python3 scripts/hwpx.py set-header 원본.hwpx 결과.hwpx --text "대외비" --align center
    python3 scripts/hwpx.py check 결과.hwpx                               # 전달 전 게이트
    python3 scripts/hwpx.py from-hwp 원본.hwp -o 변환.hwpx                # HWP→HWPX 변환 (Node.js 18+)
    python3 scripts/hwpx.py lint 문서.hwpx                                # 공문서 표기 검수
    python3 scripts/hwpx.py new 입력.md -o 결과.hwpx --template report    # 보고서 템플릿

## 개발

    python3 -m pytest tests/ -v

## 라이선스

MIT — [LICENSE](LICENSE) 참조. 외부 컴포넌트는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 참조 (rhwp MIT 동봉). 설계 배경은 docs/superpowers/specs/ 참조.
